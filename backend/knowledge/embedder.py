import numpy as np
from openai import AsyncOpenAI

from config import settings


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def embed_text(text: str) -> list[float]:
    response = await _client().embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=settings.embedding_dimensions,
    )
    return response.data[0].embedding


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    response = await _client().embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
    )
    return [item.embedding for item in response.data]


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
    va = np.array(a)
    vb = np.array(b)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))
