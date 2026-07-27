# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""License enforcement — Ed25519-signed license files.

A license file is JSON: ``{"license": {...}, "signature": "<hex>"}`` where
the signature covers the canonical (sorted, compact) JSON of the payload.
Payload fields: ``licensee`` (required), ``expires`` ("" or "YYYY-MM-DD"),
``hosts`` (fnmatch patterns; empty = any machine), ``issued``.

Search order: ``$POLYTESS_LICENSE`` → ``~/.polytess/license.lic`` →
``license.lic`` next to the installation. Verification is offline; the
public key is embedded here (the private signing key never ships).
Licenses are issued with ``tools/generate_license.py``.
"""

from __future__ import annotations

import fnmatch
import json
import os
import socket
from datetime import date

# The Ed25519 public key of the license issuer (raw, hex). The matching
# private key stays with the issuer — it is NOT part of the repository.
PUBLIC_KEY_HEX = "e4e6e68497ff32041f1b5388d38a4de84bc180762dadb20a59b93639d9a88342"

_cached_payload: dict | None = None


class LicenseError(Exception):
    """Raised when no valid license is available."""


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


# --------------------------------------------------------------------------- #
# issuing (used by tools/generate_license.py and the tests)
# --------------------------------------------------------------------------- #

def generate_keypair() -> tuple[str, str]:
    """(private_hex, public_hex) — a fresh Ed25519 keypair."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey)
    private = Ed25519PrivateKey.generate()
    private_hex = private.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
        serialization.NoEncryption()).hex()
    public_hex = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    return private_hex, public_hex


def sign_license(payload: dict, private_key_hex: str) -> dict:
    """The complete license-file content for *payload*."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey)
    private = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(
        private_key_hex.strip()))
    signature = private.sign(_canonical(payload)).hex()
    return {"license": payload, "signature": signature}


# --------------------------------------------------------------------------- #
# verification
# --------------------------------------------------------------------------- #

def find_license_file() -> str | None:
    from polytess.core.userdir import env as _env
    from polytess.core.userdir import user_dir
    env = _env("LICENSE").strip()
    candidates = [env] if env else []
    candidates.append(os.path.join(user_dir(), "license.lic"))
    from polytess.core.userdir import install_roots
    for root in install_roots():
        candidates.append(os.path.join(root, "license.lic"))
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def verify_license_data(data: dict, public_key_hex: str | None = None) -> dict:
    """Validated payload of a parsed license file — raises LicenseError."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey)

    payload = data.get("license")
    signature = data.get("signature", "")
    if not isinstance(payload, dict) or not signature:
        raise LicenseError("License file is malformed.")
    public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(
        public_key_hex or PUBLIC_KEY_HEX))
    try:
        public.verify(bytes.fromhex(signature), _canonical(payload))
    except (InvalidSignature, ValueError):
        raise LicenseError("License signature is invalid — the file was "
                           "modified or issued with a different key.") from None

    if not str(payload.get("licensee", "")).strip():
        raise LicenseError("License has no licensee.")

    expires = str(payload.get("expires", "") or "").strip()
    if expires:
        try:
            year, month, day = (int(p) for p in expires.split("-"))
        except ValueError:
            raise LicenseError(f"License has an invalid expiry date: "
                               f"{expires!r}") from None
        if date.today() > date(year, month, day):
            raise LicenseError(f"License expired on {expires}.")

    hosts = payload.get("hosts") or []
    if hosts:
        hostname = socket.gethostname().split(".")[0].lower()
        if not any(fnmatch.fnmatch(hostname, str(p).lower()) for p in hosts):
            raise LicenseError(f"License is not valid for this machine "
                               f"({hostname}).")
    return payload


def verify_license(path: str | None = None) -> dict:
    path = path or find_license_file()
    if path is None:
        raise LicenseError(
            "No license file found. Place it at ~/.polytess/license.lic or "
            "set POLYTESS_LICENSE to its path.")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise LicenseError(f"Cannot read license file {path}: {exc}") from None
    return verify_license_data(data)


def ensure_licensed() -> dict:
    """Verify once per process (cached); raises LicenseError otherwise."""
    global _cached_payload
    if _cached_payload is None:
        _cached_payload = verify_license()
    return _cached_payload


def reset_cache() -> None:
    global _cached_payload
    _cached_payload = None


def license_status() -> str:
    """Human-readable one-liner for the status bar/about dialog. polytess
    runs fully under the Business Source License without any file — this
    only reports an optional *commercial* license (extended rights beyond
    the BUSL Additional Use Grant, e.g. resale/hosting)."""
    try:
        payload = ensure_licensed()
    except LicenseError:
        return "Business Source License 1.1 (no commercial license)"
    expires = str(payload.get("expires", "") or "").strip()
    suffix = f" (until {expires})" if expires else ""
    return f"Commercial license: {payload['licensee']}{suffix}"
