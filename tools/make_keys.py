#!/usr/bin/env python3
# Eclipse Proof MCP
# Copyright © 2026 Cyan Eclipse Technologies LLC · cetech.ai
"""Generate local Herald seed keypair: private -> keys/herald-key.local.json
(600, never shipped), public -> herald_pubkey.pem (pinned in package)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import signing
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d, pt = signing.generate_keypair()
kf = os.path.join(base, "keys", "herald-key.local.json")
json.dump({"private_int": d}, open(kf, "w")); os.chmod(kf, 0o600)
open(os.path.join(base, "herald_pubkey.pem"), "w").write(signing.public_key_pem(pt))
print("herald keypair written (private local-only)")
# Eclipse Proof MCP · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
