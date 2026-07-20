from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://afs:afs@localhost:5432/afs"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "afs-raw-evidence"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "change-me-locally"  # noqa: S105 - explicit non-secret local placeholder
    s3_region: str = "us-east-1"
    zyte_api_key: str = ""
    youtube_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    embedding_provider: str = "mock"
    embedding_model: str = "deterministic-v1"
    embedding_dimensions: int = 1536
    generation_provider: str = "mock"
    generation_model: str = "grounded-template-v1"
    extraction_provider: str = "mock"
    extraction_model: str = "deterministic-v1"
    openai_generation_input_cost_per_million: float = 0.75
    openai_generation_output_cost_per_million: float = 4.5
    openai_extraction_input_cost_per_million: float = 0.2
    openai_extraction_output_cost_per_million: float = 1.25
    openai_embedding_cost_per_million: float = 0.02
    gemini_generation_input_cost_per_million: float = 0
    gemini_generation_output_cost_per_million: float = 0
    gemini_extraction_input_cost_per_million: float = 0
    gemini_extraction_output_cost_per_million: float = 0
    transcription_provider: str = "mock"
    transcription_model: str = "disabled"
    paid_transcription_enabled: bool = False
    reranker_provider: str = "none"
    reranker_model: str = "none"
    interview_turn_auto_publish_iyin: bool = True
    interview_turn_auto_publish_min_confidence: float = 0.6
    admin_email: str = "admin@example.com"
    admin_password: str = "change-this-development-password"  # noqa: S105 - local placeholder
    session_secret: str = Field(default="development-only-session-secret-change-me", min_length=32)
    session_ttl_seconds: int = 28_800
    public_app_url: str = "http://localhost:3000"
    crawler_user_agent: str = "AfricanFounderStudiesResearchBot/0.1"
    max_monthly_zyte_cost: float = 25
    max_monthly_ai_cost: float = 25
    max_crawl_run_cost: float = 5
    max_zyte_caption_batch_cost: float = 0.50
    max_zyte_requests_per_video: int = 5
    zyte_caption_estimated_cost_per_video: float = 0.0037
    live_crawling_enabled: bool = False
    public_accounts_enabled: bool = False
    cors_origins: str = "http://localhost:3000,http://localhost:3010"

    @field_validator("embedding_dimensions")
    @classmethod
    def validate_dimensions(cls, value: int) -> int:
        if value < 8 or value > 4096:
            raise ValueError("embedding dimensions must be between 8 and 4096")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def configuration_warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.live_crawling_enabled:
            warnings.append("Live crawling is disabled; fixture workflows remain available.")
        if self.embedding_provider == "mock" or self.generation_provider == "mock":
            warnings.append("Mock AI providers are active; results are labelled fixture/demo output.")
        if (
            "openai"
            in {
                self.embedding_provider,
                self.generation_provider,
                self.extraction_provider,
            }
            and not self.openai_api_key
        ):
            warnings.append("An OpenAI provider is selected but OPENAI_API_KEY is not configured.")
        if self.generation_provider == "gemini" and not self.gemini_api_key:
            warnings.append("Gemini generation is selected but GEMINI_API_KEY is not configured.")
        if self.extraction_provider == "gemini" and not self.gemini_api_key:
            warnings.append("Gemini extraction is selected but GEMINI_API_KEY is not configured.")
        if self.admin_password.startswith("change-"):
            warnings.append("The development admin password must be changed before deployment.")
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()
