"""Tests for self-signed TLS certificate generation (api.src.core.tls)."""

import datetime as dt
import ipaddress
import stat

from cryptography import x509

from api.src.core.tls import ensure_cert


def _read_cert(cert_path):
    return x509.load_pem_x509_certificate(cert_path.read_bytes())


def test_ensure_cert_creates_files(tmp_path):
    cert = tmp_path / "tls" / "cert.pem"
    key = tmp_path / "tls" / "key.pem"

    out_cert, out_key = ensure_cert(cert, key, common_name="localhost")

    assert out_cert == cert and out_key == key
    assert cert.exists() and key.exists()
    assert cert.read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")
    assert b"PRIVATE KEY" in key.read_bytes()


def test_key_permissions_are_0600(tmp_path):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    ensure_cert(cert, key)

    mode = stat.S_IMODE(key.stat().st_mode)
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"


def test_ensure_cert_is_idempotent(tmp_path):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"

    ensure_cert(cert, key)
    cert_bytes = cert.read_bytes()
    key_bytes = key.read_bytes()

    # Second call must be a no-op: same bytes, not a freshly minted pair.
    ensure_cert(cert, key)
    assert cert.read_bytes() == cert_bytes
    assert key.read_bytes() == key_bytes


def test_sans_include_cn_localhost_and_loopback(tmp_path):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    ensure_cert(cert, key, common_name="kokoro.local", extra_sans=["10.0.0.5"])

    san = _read_cert(cert).extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value
    dns = san.get_values_for_type(x509.DNSName)
    ips = san.get_values_for_type(x509.IPAddress)

    assert "kokoro.local" in dns
    assert "localhost" in dns
    assert ipaddress.ip_address("127.0.0.1") in ips
    assert ipaddress.ip_address("::1") in ips
    assert ipaddress.ip_address("10.0.0.5") in ips


def test_cert_validity_is_about_ten_years(tmp_path):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    ensure_cert(cert, key)

    parsed = _read_cert(cert)
    lifetime = parsed.not_valid_after_utc - parsed.not_valid_before_utc
    # ~10 years (3650 days) plus the 5-minute backdate.
    assert lifetime > dt.timedelta(days=3600)
