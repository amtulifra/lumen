import httpx

from config import settings

BASE_URL = "https://api.semanticscholar.org/graph/v1"


def build_headers() -> dict:
    headers = {"Accept": "application/json"}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
    return headers


def search_author(name: str) -> dict | None:
    with httpx.Client(timeout=30) as client:
        response = client.get(
            f"{BASE_URL}/author/search",
            params={"query": name, "fields": "authorId,name,affiliations,hIndex,citationCount,papers"},
            headers=build_headers(),
        )
        response.raise_for_status()
        data = response.json()

    candidates = data.get("data", [])
    if not candidates:
        return None

    return candidates[0]


def get_author_papers(author_id: str) -> list[dict]:
    with httpx.Client(timeout=30) as client:
        response = client.get(
            f"{BASE_URL}/author/{author_id}/papers",
            params={"fields": "title,year,externalIds", "limit": 20},
            headers=build_headers(),
        )
        response.raise_for_status()
        return response.json().get("data", [])
