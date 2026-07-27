# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Issue polytess COMMERCIAL license files (grants rights beyond the BUSL
Additional Use Grant, e.g. resale/hosting). Requires the PRIVATE signing key.

Examples:
    # new keypair (once; embed the printed public key in licensing.py)
    python tools/generate_license.py --new-keypair

    # issue a license
    python tools/generate_license.py \\
        --private-key ~/.polytess/license_signing.key \\
        --licensee "Example Corp" --expires 2027-12-31 \\
        --hosts "cluster*,workstation-*" --out license.lic
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polytess.core.licensing import generate_keypair, sign_license  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-keypair", action="store_true",
                        help="generate a fresh signing keypair and exit")
    parser.add_argument("--private-key", help="file containing the private "
                        "key (hex)")
    parser.add_argument("--licensee", help="name of the license holder")
    parser.add_argument("--expires", default="",
                        help="YYYY-MM-DD (empty = perpetual)")
    parser.add_argument("--hosts", default="",
                        help="comma-separated hostname patterns "
                        "(fnmatch, empty = any machine)")
    parser.add_argument("--out", default="license.lic")
    args = parser.parse_args()

    if args.new_keypair:
        private_hex, public_hex = generate_keypair()
        print("PRIVATE key (keep secret, NOT in the repo):", private_hex)
        print("PUBLIC key (embed in polytess/core/licensing.py):", public_hex)
        return 0

    if not args.private_key or not args.licensee:
        parser.error("--private-key and --licensee are required")
    with open(os.path.expanduser(args.private_key), encoding="utf-8") as fh:
        private_hex = fh.read().strip()

    payload = {
        "licensee": args.licensee,
        "expires": args.expires,
        "hosts": [h.strip() for h in args.hosts.split(",") if h.strip()],
        "issued": date.today().isoformat(),
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(sign_license(payload, private_hex), fh, indent=2)
    print(f"License written: {args.out}")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
