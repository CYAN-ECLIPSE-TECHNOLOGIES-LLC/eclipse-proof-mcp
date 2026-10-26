#!/usr/bin/env python3
# Eclipse Proof MCP
# Copyright © 2026 Cyan Eclipse Technologies LLC · cetech.ai
# ECDSA P-256 sign/verify, pure Python stdlib (Eclipse Proof).

"""ECDSA P-256 sign/verify, pure Python stdlib (Eclipse Proof).

House implementation (same code as eclipse-fathom-mcp/registry_sig.py,
in the style of eclipse-cluster-mcp/sigverify.py). Herald signs approvals
and template pins for Proof: an approval is evidence,
and evidence is signed data, not a row anyone can edit into truth.
Verification needs the public key only; the signing private key is
a local key file (keys/, gitignored, never shipped).
"""
import base64
import hashlib

# NIST P-256 domain parameters.
_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_A = _P - 3
_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
_GX = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
_GY = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5
_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_G = (_GX, _GY)


def _add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % _P == 0:
        return None
    if p1 == p2:
        m = (3 * x1 * x1 + _A) * pow(2 * y1, -1, _P) % _P
    else:
        m = (y2 - y1) * pow(x2 - x1, -1, _P) % _P
    x3 = (m * m - x1 - x2) % _P
    return (x3, (m * (x1 - x3) - y1) % _P)


def _mul(k, point):
    result = None
    addend = point
    while k:
        if k & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        k >>= 1
    return result


def generate_keypair():
    """Return (private_int, (x, y)) — test/seed use only."""
    import secrets
    d = secrets.randbelow(_N - 1) + 1
    return d, _mul(d, _G)


def public_key_pem(point) -> str:
    x, y = point
    spki_prefix = bytes.fromhex(
        "3059301306072a8648ce3d020106082a8648ce3d030107034200")
    der = spki_prefix + b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")
    b64 = base64.b64encode(der).decode()
    lines = "\n".join(b64[i:i + 64] for i in range(0, len(b64), 64))
    return f"-----BEGIN PUBLIC KEY-----\n{lines}\n-----END PUBLIC KEY-----\n"


def parse_public_key_pem(pem: str):
    body = "".join(line.strip() for line in pem.splitlines()
                   if line.strip() and not line.startswith("-----"))
    der = base64.b64decode(body)
    if len(der) < 65 or der[-65] != 0x04:
        raise ValueError("not an uncompressed P-256 SPKI key")
    x = int.from_bytes(der[-64:-32], "big")
    y = int.from_bytes(der[-32:], "big")
    return (x, y)


def key_fingerprint(pem: str) -> str:
    body = "".join(line.strip() for line in pem.splitlines()
                   if line.strip() and not line.startswith("-----"))
    return hashlib.sha256(base64.b64decode(body)).hexdigest()


def _der_int(v: int) -> bytes:
    raw = v.to_bytes((v.bit_length() + 7) // 8 or 1, "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return b"\x02" + bytes([len(raw)]) + raw


def sign(private_int: int, message: bytes) -> bytes:
    """ECDSA/SHA-256, DER-encoded signature."""
    import secrets
    z = int.from_bytes(hashlib.sha256(message).digest(), "big")
    while True:
        k = secrets.randbelow(_N - 1) + 1
        point = _mul(k, _G)
        r = point[0] % _N
        if r == 0:
            continue
        s = (pow(k, -1, _N) * (z + r * private_int)) % _N
        if s:
            break
    body = _der_int(r) + _der_int(s)
    return b"\x30" + bytes([len(body)]) + body


def _parse_der_sig(sig: bytes):
    if sig[0] != 0x30:
        raise ValueError("bad signature DER")
    idx = 2
    vals = []
    for _ in range(2):
        if sig[idx] != 0x02:
            raise ValueError("bad signature DER int")
        ln = sig[idx + 1]
        vals.append(int.from_bytes(sig[idx + 2:idx + 2 + ln], "big"))
        idx += 2 + ln
    return vals


def verify(point, message: bytes, sig: bytes) -> bool:
    try:
        r, s = _parse_der_sig(sig)
    except Exception:
        return False
    if not (1 <= r < _N and 1 <= s < _N):
        return False
    z = int.from_bytes(hashlib.sha256(message).digest(), "big")
    w = pow(s, -1, _N)
    point = _add(_mul((z * w) % _N, _G), _mul((r * w) % _N, point))
    return point is not None and point[0] % _N == r

# Eclipse Proof MCP · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
