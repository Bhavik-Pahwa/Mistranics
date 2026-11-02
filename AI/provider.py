"""Real Ollama HTTP adapter. No synthetic answers or embeddings in application code."""

import math
import httpx


class ProviderError(Exception):
    pass


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
                "format": schema,
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderError("LLM provider returned no structured message") from exc
