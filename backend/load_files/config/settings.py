from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_env_path = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "Load Files Service"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    LOG_LEVEL: str = "INFO"
    LOG_LEVEL_OVERRIDE: str | None = None

    SFTP_HOST: str = ""
    SFTP_PORT: int = 22
    SFTP_USER: str = ""
    SFTP_PASS: str = ""
    SFTP_UPLOAD_DIR: str = "/upload"

    ALLOWED_FILE_TYPES: str = "REPOSITORIO"
    ALLOWED_EXTENSIONS: str = ".xlsx,.xls,.csv,.pdf"
    MAX_UPLOAD_SIZE_MB: int = 500

    KEYCLOAK_URL: str = ""
    KEYCLOAK_REALM: str = ""
    KEYCLOAK_CLIENT_ID: str = ""
    KEYCLOAK_VERIFY_AUDIENCE: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"
    TEMP_UPLOAD_DIR: str = "/tmp/load_files_uploads"
    SFTP_CHUNK_SIZE: int = 4194304

    model_config = SettingsConfigDict(
        env_file=str(_env_path) if _env_path.exists() else None,
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        if self.ENVIRONMENT.lower() == "production":
            effective = self.LOG_LEVEL_OVERRIDE or "WARNING"
            object.__setattr__(self, "LOG_LEVEL", effective)

    @property
    def KEYCLOAK_ISSUER(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"

    @property
    def KEYCLOAK_JWKS_URL(self) -> str:
        return f"{self.KEYCLOAK_ISSUER}/protocol/openid-connect/certs"

    @property
    def ALLOWED_FILE_TYPES_LIST(self) -> list[str]:
        return [t.strip().upper() for t in self.ALLOWED_FILE_TYPES.split(",") if t.strip()]

    @property
    def ALLOWED_EXTENSIONS_LIST(self) -> list[str]:
        return [e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",") if e.strip()]


settings = Settings()
