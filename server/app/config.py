from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    anthropic_model:   str = "claude-sonnet-4-6"

    openai_api_key: str = ""
    openai_model:   str = "gpt-4o"

    gemini_api_key: str = ""
    gemini_model:   str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
