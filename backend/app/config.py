from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "mysql+pymysql://root:devpass@localhost:3306/listings"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"

    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        if url.startswith("mysql://"):
            url = url.replace("mysql://", "mysql+pymysql://", 1)
        return url.split("?ssl-mode=")[0].split("&ssl-mode=")[0]

    @property
    def requires_ssl(self) -> bool:
        url = self.database_url.lower().replace("ssl_mode", "ssl-mode")
        return "ssl-mode=required" in url


settings = Settings()
