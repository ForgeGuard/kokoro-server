"""Production entrypoint: launch uvicorn with optional built-in HTTPS.

The container CMD runs ``python -m api.src.serve``. This mirrors
``uvicorn api.src.main:app`` but adds TLS: when ``TLS_ENABLED`` is set it
generates (on first run) and wires a self-signed certificate into uvicorn's
``ssl_certfile`` / ``ssl_keyfile`` so the server speaks HTTPS directly — no
reverse proxy or manual openssl. TLS off is byte-for-byte the previous plain
HTTP launch.
"""

from __future__ import annotations

import os

from loguru import logger

from .core.config import settings


def tls_kwargs() -> dict[str, str]:
    """uvicorn SSL kwargs when TLS is enabled, generating a self-signed cert.

    Returns an empty dict (plain HTTP) unless ``TLS_ENABLED`` is set.
    """
    if not settings.tls_enabled:
        return {}

    cert = settings.resolved_tls_cert
    key = settings.resolved_tls_key
    if not (cert.exists() and key.exists()):
        if not settings.tls_self_signed:
            raise SystemExit(
                f"TLS_ENABLED=true but cert/key not found ({cert}, {key}) and "
                "TLS_SELF_SIGNED=false — provide TLS_CERT_FILE / TLS_KEY_FILE "
                "or enable self-signed generation."
            )
        from .core.tls import ensure_cert

        ensure_cert(cert, key, common_name=settings.tls_cn, extra_sans=settings.tls_san)
    logger.info(f"TLS enabled — serving HTTPS with certificate {cert}")
    return {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}


def main() -> None:
    import uvicorn

    ssl = tls_kwargs()
    log_level = os.getenv("UVICORN_LOG_LEVEL", "info").lower()
    scheme = "https" if ssl else "http"
    logger.info(f"Starting Kokoro server on {scheme}://{settings.host}:{settings.port}")
    uvicorn.run(
        "api.src.main:app",
        host=settings.host,
        port=settings.port,
        log_level=log_level,
        **ssl,
    )


if __name__ == "__main__":
    main()
