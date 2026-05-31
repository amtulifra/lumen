import asyncio
import math
from typing import Any

from openai import AsyncOpenAI

from config import settings

try:
    from fastembed import TextEmbedding
except ImportError:  # pragma: no cover - optional dependency in some environments
    TextEmbedding = None

_fastembed_client: Any = None


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


def _get_fastembed_client() -> Any:
    global _fastembed_client
    if TextEmbedding is None:
        raise RuntimeError(
            "fastembed is not installed. Install dependencies or switch EMBEDDING_PROVIDER=openai."
        )
    if _fastembed_client is None:
        _fastembed_client = TextEmbedding(model_name=settings.embedding_model)
    return _fastembed_client


async def _embed_texts_fastembed(texts: list[str]) -> list[list[float]]:
    def _run() -> list[list[float]]:
        client = _get_fastembed_client()
        vectors = client.embed(texts)
        result = [list(vec.astype(float)) for vec in vectors]
        if result and len(result[0]) != settings.embedding_dimensions:
            raise ValueError(
                f"Embedding dimension mismatch: expected {settings.embedding_dimensions}, got {len(result[0])}"
            )
        return result

    return await asyncio.to_thread(_run)


async def _embed_texts_openai(texts: str | list[str]) -> list[list[float]]:
    response = await _client().embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
    )
    return [item.embedding for item in response.data]


async def embed_text(text: str) -> list[float]:
    provider = settings.embedding_provider.lower()
    if provider == "fastembed":
        try:
            return (await _embed_texts_fastembed([text]))[0]
        except Exception:
            if settings.openai_api_key:
                return (await _embed_texts_openai(text))[0]
            raise
    if provider == "openai":
        return (await _embed_texts_openai(text))[0]
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    provider = settings.embedding_provider.lower()
    if provider == "fastembed":
        try:
            return await _embed_texts_fastembed(texts)
        except Exception:
            if settings.openai_api_key:
                return await _embed_texts_openai(texts)
            raise
    if provider == "openai":
        return await _embed_texts_openai(texts)
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


async def embed_knowledge_object(extracted: dict, title: str) -> dict:
    claims = extracted.get("claims", [])
    methods = extracted.get("methods", [])
    open_problems = extracted.get("open_problems", [])

    claim_texts = [c["text"] for c in claims]
    method_texts = [m["description"] for m in methods]

    title_embedding = await embed_text(title)
    claim_embeddings = await embed_texts(claim_texts)
    method_embeddings = await embed_texts(method_texts)
    problem_embeddings = await embed_texts(open_problems)

    return {
        "title": title_embedding,
        "claims": claim_embeddings,
        "methods": method_embeddings,
        "open_problems": problem_embeddings,
    }


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return float(dot / (norm_a * norm_b))
