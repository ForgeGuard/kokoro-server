from importlib.metadata import (
    PackageNotFoundError,
    version as _pkg_version,
)
from pathlib import Path
from typing import Annotated, Optional

import torch
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode


def _read_version() -> str:
    version_file = Path(__file__).resolve().parents[3] / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    try:
        return _pkg_version("kokoro-server")
    except PackageNotFoundError:
        return "0.0.0"


class Settings(BaseSettings):
    # API Settings
    api_title: str = "Kokoro Server"
    api_description: str = "OpenAI-compatible text-to-speech API built on Kokoro-82M"
    api_version: str = _read_version()
    host: str = "0.0.0.0"
    port: int = 8880

    # Application Settings
    output_dir: str = "output"
    output_dir_size_limit_mb: float = 500.0  # Maximum size of output directory in MB
    default_voice: str = "af_heart"
    default_voice_code: str | None = (
        None  # If set, overrides the first letter of voice name, though api call param still takes precedence
    )
    use_gpu: bool = True  # Whether to use GPU acceleration if available
    # Eagerly load + warm the model in a background task at startup so the
    # server is ready for requests as soon as possible while /health responds
    # immediately. Set WARMUP_ON_START=false to defer to first request.
    warmup_on_start: bool = True
    device_type: str | None = (
        None  # Will be auto-detected if None, can be "cuda", "mps", or "cpu"
    )
    allow_local_voice_saving: bool = (
        False  # Whether to allow saving combined voices locally
    )

    # Container absolute paths
    model_dir: str = "/app/api/src/models"  # Absolute path in container
    voices_dir: str = "/app/api/src/voices/v1_0"  # Absolute path in container

    # Audio Settings
    sample_rate: int = 24000
    default_volume_multiplier: float = 1.0
    # Text Processing Settings
    target_min_tokens: int = 175  # Target minimum tokens per chunk
    target_max_tokens: int = 250  # Target maximum tokens per chunk
    absolute_max_tokens: int = 450  # Absolute maximum tokens per chunk
    advanced_text_normalization: bool = True  # Preproesses the text before misiki
    voice_weight_normalization: bool = (
        True  # Normalize the voice weights so they add up to 1
    )

    gap_trim_ms: int = (
        1  # Base amount to trim from streaming chunk ends in milliseconds
    )
    dynamic_gap_trim_padding_ms: int = 410  # Padding to add to dynamic gap trim
    dynamic_gap_trim_padding_char_multiplier: dict[str, float] = {
        ".": 1,
        "!": 0.9,
        "?": 1,
        ",": 0.8,
    }

    # Authentication
    # Optional bearer token. When unset the API is open (auth disabled), matching
    # prior behavior; when set, protected endpoints require
    # `Authorization: Bearer <api_key>`. Health and web-player routes stay open.
    api_key: Optional[str] = None

    # Web Player Settings
    enable_web_player: bool = True  # Whether to serve the web player UI
    web_player_path: str = "web"  # Path to web player static files
    cors_origins: list[str] = ["*"]  # CORS origins for web player
    cors_enabled: bool = True  # Whether to enable CORS
    # Kept False by default: the browser UI authenticates with a bearer header,
    # not cookies, and the wildcard `["*"]` origin is invalid together with
    # credentialed CORS. Enable only alongside an explicit `cors_origins` list.
    cors_allow_credentials: bool = False

    # Temp File Settings for WEB Ui
    temp_file_dir: str = "api/temp_files"  # Directory for temporary audio files (relative to project root)
    max_temp_dir_size_mb: int = 2048  # Maximum size of temp directory (2GB)
    max_temp_dir_age_hours: int = 1  # Remove temp files older than 1 hour
    max_temp_dir_count: int = 3  # Maximum number of temp files to keep

    # TLS / HTTPS
    # When TLS_ENABLED is set the server speaks HTTPS directly (uvicorn SSL). If
    # no cert is provided a self-signed one is generated on first run and
    # persisted under {output_dir}/tls so restarts reuse it — no reverse proxy,
    # no manual openssl, no extra container. Point TLS_CERT_FILE / TLS_KEY_FILE
    # at a real cert for anything public.
    tls_enabled: bool = False
    tls_cert_file: Path | None = None  # defaults to {output_dir}/tls/cert.pem
    tls_key_file: Path | None = None  # defaults to {output_dir}/tls/key.pem
    tls_self_signed: bool = True  # auto-generate a self-signed cert if missing
    tls_cn: str = "localhost"  # CN + SAN for the generated certificate
    tls_san: Annotated[list[str], NoDecode] = Field(
        default_factory=list
    )  # extra SANs (comma-separated env, e.g. TLS_SAN="host.local,10.0.0.5")

    @field_validator("tls_san", mode="before")
    @classmethod
    def _split_san(cls, v: object) -> object:
        # Accept a comma-separated string from the environment; NoDecode above
        # disables pydantic's JSON list parsing so this validator sees the raw
        # value (mirrors how cors_origins-style lists are typically split).
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @property
    def resolved_tls_cert(self) -> Path:
        if self.tls_cert_file is not None:
            return self.tls_cert_file
        return Path(self.output_dir) / "tls" / "cert.pem"

    @property
    def resolved_tls_key(self) -> Path:
        if self.tls_key_file is not None:
            return self.tls_key_file
        return Path(self.output_dir) / "tls" / "key.pem"

    class Config:
        env_file = ".env"

    def get_device(self) -> str:
        """Get the appropriate device based on settings and availability"""
        if not self.use_gpu:
            return "cpu"

        if self.device_type:
            return self.device_type

        # Auto-detect device
        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        return "cpu"


settings = Settings()
