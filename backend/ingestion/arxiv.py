import arxiv


def parse_arxiv_id(url: str) -> str:
    return url.split("/abs/")[-1].strip().split("v")[0]


def fetch_paper(url: str) -> dict:
    arxiv_id = parse_arxiv_id(url)
    client = arxiv.Client()
    results = client.results(arxiv.Search(id_list=[arxiv_id]))
    paper = next(results)

    return {
        "id": arxiv_id,
        "title": paper.title,
        "authors": [a.name for a in paper.authors],
        "year": paper.published.year,
        "abstract": paper.summary,
        "pdf_url": paper.pdf_url,
        "arxiv_url": url,
    }
