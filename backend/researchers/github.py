import json

import anthropic
import httpx

from config import settings

GITHUB_API = "https://api.github.com"


def build_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def search_repos(query: str) -> list[dict]:
    with httpx.Client(timeout=30) as client:
        response = client.get(
            f"{GITHUB_API}/search/repositories",
            params={"q": query, "sort": "stars", "per_page": 5},
            headers=build_headers(),
        )
        if response.status_code != 200:
            return []
        return response.json().get("items", [])


def get_readme(owner: str, repo: str) -> str:
    with httpx.Client(timeout=30) as client:
        response = client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/readme",
            headers={**build_headers(), "Accept": "application/vnd.github.raw"},
        )
        if response.status_code != 200:
            return ""
        return response.text[:3000]


def confirm_match_with_claude(paper_title: str, abstract: str, readme: str) -> bool:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = (
        f"Paper title: {paper_title}\n"
        f"Abstract: {abstract[:500]}\n\n"
        f"GitHub README (first 3000 chars):\n{readme}\n\n"
        "Does this GitHub repository correspond to this paper? "
        "Answer with a single word: yes or no."
    )
    message = client.messages.create(
        model=settings.claude_model,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip().lower().startswith("yes")


def find_github_repo(paper_title: str, author_name: str, abstract: str) -> str | None:
    keywords = " ".join(paper_title.split()[:4])
    query = f"{keywords} {author_name}"

    repos = search_repos(query)
    for repo in repos:
        readme = get_readme(repo["owner"]["login"], repo["name"])
        if confirm_match_with_claude(paper_title, abstract, readme):
            return repo["html_url"]

    return None


def get_user_repos(username: str) -> list[str]:
    with httpx.Client(timeout=30) as client:
        response = client.get(
            f"{GITHUB_API}/users/{username}/repos",
            params={"sort": "updated", "per_page": 5},
            headers=build_headers(),
        )
        if response.status_code != 200:
            return []
        return [r["html_url"] for r in response.json()]
