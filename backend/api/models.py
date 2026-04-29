from pydantic import BaseModel, Field


class IngestURLRequest(BaseModel):
    url: str


class IngestAbstractRequest(BaseModel):
    title: str
    abstract: str


class SuggestRequest(BaseModel):
    notes: str


class HypothesisCreateRequest(BaseModel):
    text: str


class ClaimOut(BaseModel):
    text: str
    confidence: float
    evidence: str


class MethodOut(BaseModel):
    name: str
    description: str
    is_novel: bool


class BenchmarkOut(BaseModel):
    dataset: str
    metric: str
    value: float
    model: str
    split: str


class KnowledgeObjectOut(BaseModel):
    claims: list[ClaimOut] = Field(default_factory=list)
    methods: list[MethodOut] = Field(default_factory=list)
    benchmarks: list[BenchmarkOut] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    open_problems: list[str] = Field(default_factory=list)
    related_work: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class PaperOut(BaseModel):
    id: str
    title: str
    authors: list[str]
    year: int
    arxiv_url: str | None
    pdf_url: str | None
    knowledge_obj: dict | None


class IngestResponse(BaseModel):
    paper_id: str
    knowledge_object: dict


class LinkOut(BaseModel):
    source_id: str
    target_id: str
    link_type: str
    strength: float
    metadata: dict


class GraphSubgraphOut(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class ResearcherOut(BaseModel):
    id: str
    name: str
    institution: str | None
    github_username: str | None
    h_index: int | None
    citation_count: int | None
    research_themes: list[str] | None
    recent_repos: list[str] | None


class HypothesisOut(BaseModel):
    id: str
    text: str
    status: str
    evidence_for: list[dict]
    evidence_against: list[dict]


class BenchmarkDriftPoint(BaseModel):
    year: int
    sota_value: float
    model: str
    paper_id: str
    paper_title: str


class RSSStatusOut(BaseModel):
    feeds: list[str]
    schedule: str
