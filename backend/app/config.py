from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "mysql+pymysql://root:devpass@localhost:3306/listings"
    gemini_api_key: str | None = None

settings = Settings()