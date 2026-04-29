from dataclasses import dataclass, field

import numpy as np


@dataclass
class Claim:
    text: str
    confidence: float
    evidence: str


@dataclass
class Method:
    name: str
    description: str
    is_novel: bool


@dataclass
class Benchmark:
    dataset: str
    metric: str
    value: float
    model: str
    split: str


@dataclass
class MethodLink:
    paper_id: str
    method_name: str
    similarity: float


@dataclass
class BenchLink:
    paper_id: str
    dataset: str
    metric: str


@dataclass
class ContradictLink:
    paper_id: str
    dataset: str
    metric: str
    model: str
    value_self: float
    value_other: float
    delta: float


@dataclass
class KnowledgeObject:
    paper_id: str
    title: str
    authors: list[str]
    year: int
    arxiv_url: str
    pdf_url: str

    claims: list[Claim] = field(default_factory=list)
    methods: list[Method] = field(default_factory=list)
    benchmarks: list[Benchmark] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    open_problems: list[str] = field(default_factory=list)
    related_work: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    claim_embeddings: np.ndarray = field(default_factory=lambda: np.array([]))
    method_embeddings: np.ndarray = field(default_factory=lambda: np.array([]))

    cites: list[str] = field(default_factory=list)
    cited_by: list[str] = field(default_factory=list)
    shares_method: list[MethodLink] = field(default_factory=list)
    benchmarks_on: list[BenchLink] = field(default_factory=list)
    contradicts: list[ContradictLink] = field(default_factory=list)
