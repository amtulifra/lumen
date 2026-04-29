import numpy as np
from openai import OpenAI

from config import settings

client = OpenAI(api_key=settings.openai_api_key)


def embed_text(text: str) -> list[float]:
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=settings.embedding_dimensions,
    )
    return response.data[0].embedding


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
    )
    return [item.embedding for item in response.data]


def embed_knowledge_object(extracted: dict, title: str) -> dict:
    claims = extracted.get("claims", [])
    methods = extracted.get("methods", [])
    open_problems = extracted.get("open_problems", [])

    claim_texts = [c["text"] for c in claims]
    method_texts = [m["description"] for m in methods]

    title_embedding = embed_text(title)
    claim_embeddings = embed_texts(claim_texts)
    method_embeddings = embed_texts(method_texts)
    problem_embeddings = embed_texts(open_problems)

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
