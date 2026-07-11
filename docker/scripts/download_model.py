#!/usr/bin/env python3
"""Download and prepare Kokoro v1.0 model."""

import hashlib
import json
import os
import sys
import time
import urllib.error
from pathlib import Path
from urllib.request import urlopen

# Base URL for the model assets. Defaults to the canonical Kokoro-82M weights
# on Hugging Face; overridable so a mirror (or a newer weights build) can be
# used instead.
DEFAULT_BASE_URL = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main"
BASE_URL = os.getenv("MODEL_DOWNLOAD_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

# SHA-256 checksum for the model weights: the download is verified against it
# and rejected on mismatch (defends against truncated or tampered artifacts,
# which a non-zero-size check cannot catch). The default pin matches
# kokoro-v1_0.pth on the default URL and is only applied there — a custom
# MODEL_DOWNLOAD_BASE_URL must supply its own MODEL_SHA256 to get verification.
_DEFAULT_MODEL_SHA256 = (
    "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4"
)
MODEL_SHA256 = os.getenv("MODEL_SHA256") or (
    _DEFAULT_MODEL_SHA256 if BASE_URL == DEFAULT_BASE_URL else None
)

_DOWNLOAD_TIMEOUT = int(os.getenv("MODEL_DOWNLOAD_TIMEOUT", "120"))
_DOWNLOAD_RETRIES = int(os.getenv("MODEL_DOWNLOAD_RETRIES", "4"))


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class _Logger:
    def info(self, msg: str) -> None:
        _log(msg)

    def error(self, msg: str) -> None:
        _log(f"ERROR: {msg}")


logger = _Logger()


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _download(url: str, dest: str) -> None:
    """Download ``url`` to ``dest`` with a timeout and exponential-backoff retry."""
    last_error: Exception | None = None
    for attempt in range(1, _DOWNLOAD_RETRIES + 1):
        try:
            with urlopen(url, timeout=_DOWNLOAD_TIMEOUT) as resp, open(dest, "wb") as out:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            return
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_error = e
            backoff = 2 ** attempt
            logger.error(
                f"Download attempt {attempt}/{_DOWNLOAD_RETRIES} for {url} failed: "
                f"{e}. Retrying in {backoff}s"
            )
            if os.path.exists(dest):
                try:
                    os.remove(dest)
                except OSError:
                    pass
            if attempt < _DOWNLOAD_RETRIES:
                time.sleep(backoff)
    raise RuntimeError(f"Failed to download {url}: {last_error}")


def verify_files(model_path: str, config_path: str) -> bool:
    """Verify that model files exist and are valid.

    Args:
        model_path: Path to model file
        config_path: Path to config file

    Returns:
        True if files exist and are valid
    """
    try:
        # Check files exist
        if not os.path.exists(model_path):
            return False
        if not os.path.exists(config_path):
            return False

        # Verify config file is valid JSON
        with open(config_path) as f:
            json.load(f)

        # Check model file size (should be non-zero)
        if os.path.getsize(model_path) == 0:
            return False

        # Verify checksum when one is configured.
        if MODEL_SHA256:
            actual = _sha256(model_path)
            if actual.lower() != MODEL_SHA256.lower():
                logger.error(
                    f"Model checksum mismatch: expected {MODEL_SHA256}, got {actual}"
                )
                return False

        return True
    except Exception:
        return False


def download_model(output_dir: str) -> None:
    """Download model files from the configured base URL.

    Args:
        output_dir: Directory to save model files
    """
    try:
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Define file paths
        model_file = "kokoro-v1_0.pth"
        config_file = "config.json"
        model_path = os.path.join(output_dir, model_file)
        config_path = os.path.join(output_dir, config_file)

        # Check if files already exist and are valid
        if verify_files(model_path, config_path):
            logger.info("Model files already exist and are valid")
            return

        logger.info("Downloading Kokoro v1.0 model files")

        model_url = f"{BASE_URL}/{model_file}"
        config_url = f"{BASE_URL}/{config_file}"

        # Download files (with timeout + retry)
        logger.info("Downloading model file...")
        _download(model_url, model_path)

        logger.info("Downloading config file...")
        _download(config_url, config_path)

        # Verify downloaded files
        if not verify_files(model_path, config_path):
            raise RuntimeError("Failed to verify downloaded files")

        logger.info(f"✓ Model files prepared in {output_dir}")

    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        raise


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Kokoro v1.0 model")
    parser.add_argument(
        "--output", required=True, help="Output directory for model files"
    )

    args = parser.parse_args()
    download_model(args.output)


if __name__ == "__main__":
    main()
