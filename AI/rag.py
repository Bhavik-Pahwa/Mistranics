"""Page-aware extraction and a bounded PostgreSQL-backed hybrid vector/keyword store."""

import hashlib
import math
import re
import subprocess
import tempfile
from pathlib import Path
from collections import Counter
from sqlalchemy import select
from backend.app.db import Asset
from backend.app.services import DomainError
from .models import Manual, Chunk
from .provider import ProviderError


def tokens(text):
    return re.findall(r"[\w]+(?:[-./][\w]+)*", text.casefold())


def extract_pdf(content, settings):
    import pymupdf

    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise DomainError("Invalid or unreadable PDF") from exc
    with document:
        if document.is_encrypted or not 1 <= len(document) <= settings.ai_max_pdf_pages:
            raise DomainError("PDF is encrypted, empty or exceeds page limit")
        chunks = []
        heading = "Unspecified section"
        for number, page in enumerate(document, 1):
            text = page.get_text(sort=True)
            if len(text.strip()) < 20:
                if not settings.ai_ocr_enabled:
                    raise DomainError(
                        f"Page {number} requires OCR; enable AI_OCR_ENABLED and install Tesseract"
                    )
                try:
                    with tempfile.TemporaryDirectory(prefix="indux-ocr-") as directory:
                        path = Path(directory) / "page.png"
                        page.get_pixmap(dpi=200).save(path)
                        output = subprocess.run(
                            [
                                "tesseract",
                                str(path),
                                "stdout",
                                "-l",
                                settings.ai_ocr_language,
                            ],
                            capture_output=True,
                            timeout=45,
                            check=True,
                        )
                        text = output.stdout.decode("utf-8")
                except (OSError, subprocess.SubprocessError) as exc:
                    raise DomainError(f"OCR unavailable for page {number}") from exc
                if len(text.strip()) < 20:
                    raise DomainError(f"OCR found insufficient text on page {number}")
            # Preserve page layout and row text. Never interpret tables as approved limits.
            pending = []
            for line in text.splitlines():
                if (
                    line.strip()
                    and (
                        line.strip().isupper()
                        or re.match(r"^\d+(?:\.\d+)*\s+[A-Z]", line.strip())
                    )
                    and len(line) < 140
                ):
                    if pending:
                        chunks.extend(
                            chunk_section(number, heading, "\n".join(pending))
                        )
                        pending = []
                    heading = line.strip()
                pending.append(line)
            chunks.extend(chunk_section(number, heading, "\n".join(pending)))
        if len(chunks) > settings.ai_max_chunks:
            raise DomainError("Document exceeds configured chunk limit")
        return chunks


def chunk_section(page, heading, text):
    # Page and section boundaries are never crossed; overlap retains table row context.
    text = text.strip()
    return [
        {"page": page, "section": heading, "text": text[i : i + 1800]}
        for i in range(0, len(text), 1500)
        if text[i : i + 1800].strip()
    ]


def ingest_manual(
    db,
    provider,
    settings,
    content,
    document_id,
    version,
    asset_id,
    manufacturer,
    machine_model,
):
    if not 1 <= len(content) <= 15 * 1024 * 1024:
        raise DomainError("PDF must contain 1 byte to 15 MiB")
    asset = db.get(Asset, asset_id)
    if not asset:
        raise DomainError("Unknown machine", 404)
    for key, value in [
        ("manufacturer", manufacturer),
        ("machine_model", machine_model),
    ]:
        if asset.metadata_json.get(key) and asset.metadata_json[key] != value:
            raise DomainError("Manual applicability conflicts with machine registry")
    existing = db.scalar(
        select(Manual).where(
            Manual.document_id == document_id, Manual.version == version
        )
    )
    digest = hashlib.sha256(content).hexdigest()
    if existing:
        if (
            existing.sha256 != digest
            or existing.asset_id != asset_id
            or existing.machine_model != machine_model
            or existing.manufacturer != manufacturer
        ):
            raise DomainError(
                "Document version identity conflicts with existing content/applicability",
                409,
            )
        return existing, True
    extracted = extract_pdf(content, settings)
    embeddings = []
    for index in range(0, len(extracted), 16):
        embeddings.extend(
            provider.embed([c["text"] for c in extracted[index : index + 16]])
        )
    if not extracted:
        raise DomainError("No indexable text")
    manual = Manual(
        document_id=document_id,
        version=version,
        asset_id=asset_id,
        manufacturer=manufacturer,
        machine_model=machine_model,
        sha256=digest,
        embedding_model=settings.ai_embedding_model,
    )
    db.add(manual)
    db.flush()
    for chunk, vector in zip(extracted, embeddings):
        db.add(Chunk(manual_id=manual.id, embedding=vector, **chunk))
    db.flush()
    return manual, False


def cosine(left, right):
    if len(left) != len(right):
        raise ProviderError(
            "Embedding model dimensions changed; reindex as a new document version"
        )
    return sum(a * b for a, b in zip(left, right)) / math.sqrt(
        sum(a * a for a in left) * sum(b * b for b in right)
    )


def retrieve(db, provider, settings, session, question, limit=6):
    if not session.document_id or not session.document_version:
        return (
            [],
            "Select an applicable document ID and exact version for manual evidence",
        )
    manual = db.scalar(
        select(Manual).where(
            Manual.asset_id == session.asset_id,
            Manual.document_id == session.document_id,
            Manual.version == session.document_version,
        )
    )
    if not manual:
        return [], "Selected manual version is not indexed for this machine"
    asset = db.get(Asset, session.asset_id)
    if any(
        asset.metadata_json.get(k) and asset.metadata_json[k] != getattr(manual, k)
        for k in ["manufacturer", "machine_model"]
    ):
        return [], "Manual no longer matches the machine manufacturer/model"
    if manual.embedding_model != settings.ai_embedding_model:
        raise ProviderError(
            "Embedding model differs from indexed manual; use its original model or reindex"
        )
    rows = db.scalars(
        select(Chunk)
        .where(Chunk.manual_id == manual.id)
        .order_by(Chunk.page, Chunk.id)
        .limit(settings.ai_max_chunks + 1)
    ).all()
    if len(rows) > settings.ai_max_chunks:
        raise ProviderError("Manual exceeds bounded retrieval limit")
    if not rows:
        return [], "No indexed manual passages"
    vector = provider.embed([question])[0]
    query_tokens = tokens(question)
    docs = [Counter(tokens(row.text)) for row in rows]
    average = sum(sum(doc.values()) for doc in docs) / len(docs) or 1
    ranked = []
    for row, document in zip(rows, docs):
        bm25 = 0.0
        for term in set(query_tokens):
            freq = document[term]
            df = sum(term in other for other in docs)
            idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
            bm25 += (
                idf
                * freq
                * 2.5
                / (freq + 1.5 * (0.25 + 0.75 * sum(document.values()) / average))
                if freq
                else 0
            )
        semantic = cosine(vector, row.embedding)
        if bm25 > 0 or semantic >= 0.35:
            ranked.append((bm25, semantic, row))
    # Reciprocal rank fusion preserves exact identifiers alongside semantic matches.
    scores = {}
    for order in [
        sorted(ranked, key=lambda v: v[0], reverse=True),
        sorted(ranked, key=lambda v: v[1], reverse=True),
    ]:
        for rank, (_, _, row) in enumerate(order):
            scores[row.id] = scores.get(row.id, 0) + 1 / (60 + rank)
    selected = sorted(
        ranked, key=lambda item: (scores[item[2].id], item[2].id), reverse=True
    )[:limit]
    return [
        {
            "chunk_id": row.id,
            "document_id": manual.document_id,
            "version": manual.version,
            "page": row.page,
            "section": row.section,
            "text": row.text,
            "manufacturer": manual.manufacturer,
            "machine_model": manual.machine_model,
        }
        for _, _, row in selected
    ], None if selected else "No relevant manufacturer passages were found"
