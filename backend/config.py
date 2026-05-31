from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://lumen:lumen@localhost:5432/lumen"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    semantic_scholar_api_key: str = ""
    github_token: str = ""
    notion_api_key: str = ""
    cors_origins: str = "http://localhost:3000"
    auth_required: bool = False
    clerk_issuer: str = "https://clerk.your-domain.com"
    clerk_audience: str = ""
    clerk_jwks_url: str = "https://clerk.your-domain.com/.well-known/jwks.json"
    default_workspace_slug: str = "default"
    default_workspace_name: str = "Default Workspace"

    claude_model: str = "claude-sonnet-4-20250514"
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384

    method_similarity_threshold: float = 0.85
    hypothesis_similarity_threshold: float = 0.80
    rss_relevance_threshold: float = 0.75
    benchmark_contradiction_delta: float = 1.0

    max_pdf_tokens: int = 12000
    extraction_retry_limit: int = 1

    rss_feeds: dict[str, str] = {
        "cs.LG": "https://rss.arxiv.org/rss/cs.LG",
        "cs.CL": "https://rss.arxiv.org/rss/cs.CL",
        "cs.CV": "https://rss.arxiv.org/rss/cs.CV",
        "stat.ML": "https://rss.arxiv.org/rss/stat.ML",
    }


settings = Settings()
