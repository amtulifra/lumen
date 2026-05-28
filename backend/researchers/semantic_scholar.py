import httpx

from config import settings

BASE_URL = "https://api.semanticscholar.org/graph/v1"


def _headers() -> dict:
    headers = {"Accept": "application/json"}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
    return headers


async def search_author(name: str) -> dict | None:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{BASE_URL}/author/search",
            params={"query": name, "fields": "authorId,name,affiliations,hIndex,citationCount,papers"},
            headers=_headers(),
        )
        response.raise_for_status()
        data = response.json()

    candidates = data.get("data", [])
    return candidates[0] if candidates else None


async def get_author_papers(author_id: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{BASE_URL}/author/{author_id}/papers",
            params={"fields": "title,year,externalIds", "limit": 20},
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json().get("data", [])
