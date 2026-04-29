from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


FAKE_EMBEDDING = [0.1] * 1536
FAKE_PAPER_ID = "2305.12345"

FAKE_EXTRACTED = {
    "claims": [
        {"text": "Transformers outperform RNNs on NLP tasks.", "confidence": 0.95, "evidence": "We show..."},
    ],
    "methods": [
        {"name": "Self-Attention", "description": "Scaled dot-product attention.", "is_novel": True},
    ],
    "benchmarks": [
        {"dataset": "BLEU", "metric": "score", "value": 28.4, "model": "Transformer", "split": "test"},
    ],
    "limitations": ["Quadratic complexity with sequence length."],
    "open_problems": ["Efficient attention for long sequences."],
    "related_work": ["Attention Is All You Need"],
    "keywords": ["transformer", "attention", "NLP"],
}

FAKE_PAPER_META = {
    "id": FAKE_PAPER_ID,
    "title": "Attention Is All You Need",
    "authors": ["Vaswani et al."],
    "year": 2017,
    "abstract": "We propose the Transformer...",
    "pdf_url": "https://arxiv.org/pdf/1706.03762",
    "arxiv_url": "https://arxiv.org/abs/1706.03762",
}


def make_mock_db() -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def make_mock_result(rows: list) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    result.scalar.return_value = rows[0] if rows else None
    result.scalar_one_or_none.return_value = rows[0] if rows else None
    mappings_mock = MagicMock()
    mappings_mock.all.return_value = rows
    mappings_mock.one_or_none.return_value = rows[0] if rows else None
    result.mappings.return_value = mappings_mock
    return result
