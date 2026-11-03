"""Real Ollama HTTP adapter. No synthetic answers or embeddings in application code."""

import math
import copy
import httpx


class ProviderError(Exception):
    pass


def generation_schema(schema):
    """Ollama's grammar compiler rejects large bounded string repetitions.

    Omit generation-only string length bounds. The original Pydantic schema and
    citation/quote checks still validate every returned answer server-side.
    """
    result = copy.deepcopy(schema)
    def visit(node):
        if isinstance(node, dict):
            node.pop("maxLength", None)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(result)
    return result


class OllamaProvider:
    def __init__(self, settings):
        self.settings = settings

    def request(self, path, payload):
        headers = (
            {"Authorization": "Bearer " + self.settings.ai_provider_token}
            if self.settings.ai_provider_token
            else {}
        )
        try:
            response = httpx.post(
                self.settings.ai_provider_url.rstrip("/") + path,
                json=payload,
                headers=headers,
                timeout=self.settings.ai_provider_timeout,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(
                "AI provider unavailable or timed out; retry is available"
            ) from exc

    def embed(self, texts):
        if not self.settings.ai_embedding_model:
            raise ProviderError("Embedding model is not configured")
        data = self.request(
            "/api/embed",
            {
                "model": self.settings.ai_embedding_model,
                "input": texts,
                "truncate": False,
            },
        )
        vectors = data.get("embeddings", [])
        if len(vectors) != len(texts) or any(
            not v
            or not all(type(n) in (int, float) and math.isfinite(n) for n in v)
            or sum(n * n for n in v) == 0
            for v in vectors
        ):
            raise ProviderError("Embedding provider returned invalid vectors")
        if len({len(v) for v in vectors}) != 1:
            raise ProviderError("Embedding dimensions are inconsistent")
        return vectors

    def chat(self, messages, schema):
        if not self.settings.ai_llm_model:
            raise ProviderError("LLM model is not configured")
        data = self.request(
            "/api/chat",
            {
                "model": self.settings.ai_llm_model,
                "messages": messages,
                "format": generation_schema(schema),
                "stream": False,
                "options": {"temperature": 0, "num_ctx": self.settings.ai_context_tokens,
                            "num_predict": self.settings.ai_max_output_tokens},
            },
        )
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderError("LLM provider returned no structured message") from exc
