"""Regression checks for GHSA-6q48-6c7w-9gw2 using the installed CA bundle."""

import ssl
from pathlib import Path

import certifi
import requests
from cryptography import x509
from cryptography.x509.oid import NameOID
from packaging.version import Version


def test_certifi_version_is_patched():
    assert Version(certifi.__version__) >= Version("2026.10.19")


def test_compromised_emsign_root_is_not_trusted():
    context = ssl.create_default_context(cafile=certifi.where())
    certificates = x509.load_pem_x509_certificates(Path(certifi.where()).read_bytes())
    assert certificates
    common_names = {
        attribute.value
        for certificate in certificates
        for attribute in certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    }
    assert "emSign ECC Root CA - G3" not in common_names
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname


def test_requests_uses_updated_bundle():
    assert requests.certs.where() == certifi.where()
    with requests.Session() as session:
        assert session.verify is True
