# Copyright (c) 2026 Winthir Studios. All rights reserved.
"""Ed25519 license files: signing, verification, expiry, host binding."""

import json
from datetime import date, timedelta

import pytest

from polytess.core import licensing
from polytess.core.licensing import (LicenseError, generate_keypair,
                                   sign_license, verify_license,
                                   verify_license_data)


@pytest.fixture()
def keypair():
    return generate_keypair()


def _payload(**overrides):
    payload = {"licensee": "Test GmbH", "expires": "", "hosts": [],
               "issued": "2026-01-01"}
    payload.update(overrides)
    return payload


def test_sign_and_verify_roundtrip(keypair):
    private_hex, public_hex = keypair
    data = sign_license(_payload(), private_hex)
    result = verify_license_data(data, public_key_hex=public_hex)
    assert result["licensee"] == "Test GmbH"


def test_tampered_payload_rejected(keypair):
    private_hex, public_hex = keypair
    data = sign_license(_payload(), private_hex)
    data["license"]["licensee"] = "Someone Else"      # tamper
    with pytest.raises(LicenseError, match="signature"):
        verify_license_data(data, public_key_hex=public_hex)


def test_wrong_key_rejected(keypair):
    private_hex, _ = keypair
    _, other_public = generate_keypair()
    data = sign_license(_payload(), private_hex)
    with pytest.raises(LicenseError, match="signature"):
        verify_license_data(data, public_key_hex=other_public)


def test_expiry(keypair):
    private_hex, public_hex = keypair
    future = (date.today() + timedelta(days=30)).isoformat()
    ok = sign_license(_payload(expires=future), private_hex)
    assert verify_license_data(ok, public_key_hex=public_hex)

    past = (date.today() - timedelta(days=1)).isoformat()
    expired = sign_license(_payload(expires=past), private_hex)
    with pytest.raises(LicenseError, match="expired"):
        verify_license_data(expired, public_key_hex=public_hex)


def test_host_binding(keypair, monkeypatch):
    private_hex, public_hex = keypair
    monkeypatch.setattr("socket.gethostname", lambda: "clusterhost.example")
    ok = sign_license(_payload(hosts=["cluster*"]), private_hex)
    assert verify_license_data(ok, public_key_hex=public_hex)

    wrong = sign_license(_payload(hosts=["other-pc-*"]), private_hex)
    with pytest.raises(LicenseError, match="not valid for this machine"):
        verify_license_data(wrong, public_key_hex=public_hex)


def test_verify_license_file_and_cache(keypair, tmp_path, monkeypatch):
    private_hex, public_hex = keypair
    monkeypatch.setattr(licensing, "PUBLIC_KEY_HEX", public_hex)
    path = tmp_path / "license.lic"
    path.write_text(json.dumps(sign_license(_payload(), private_hex)))

    monkeypatch.setenv("POLYTESS_LICENSE", str(path))
    licensing.reset_cache()
    try:
        payload = licensing.ensure_licensed()
        assert payload["licensee"] == "Test GmbH"
        assert licensing.license_status().startswith("Commercial license: Test GmbH")

        # missing file -> clear error
        monkeypatch.setenv("POLYTESS_LICENSE", str(tmp_path / "nope.lic"))
        licensing.reset_cache()
        monkeypatch.setattr(licensing, "find_license_file", lambda: None)
        with pytest.raises(LicenseError, match="No license file"):
            verify_license()
    finally:
        licensing.reset_cache()      # conftest license takes over again


def test_malformed_file_rejected(keypair):
    _, public_hex = keypair
    with pytest.raises(LicenseError, match="malformed"):
        verify_license_data({"nope": 1}, public_key_hex=public_hex)
    with pytest.raises(LicenseError, match="licensee"):
        _priv, _pub = generate_keypair()
        verify_license_data(sign_license({"licensee": "", "expires": ""},
                                         _priv), public_key_hex=_pub)
