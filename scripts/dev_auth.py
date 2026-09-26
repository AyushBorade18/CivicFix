"""Local development identity issuer - NOT for production.

Stands in for a managed provider (Clerk/Auth0/...) on a developer's machine.
It generates an RSA keypair locally (never committed: .dev_auth/ is
gitignored) and mints RS256 tokens. The server verifies them through exactly
the same JWKS path it uses for a real provider, so nothing in app/auth.py
knows or cares that this is a dev issuer. Anyone holding
.dev_auth/private_key.pem can mint tokens: never point a shared or deployed
server at this JWKS.

  python -m scripts.dev_auth init           # keypair + prints the .env lines
  python -m http.server 8765 --bind 127.0.0.1 --directory .dev_auth/public   # serve the public JWKS
  python -m scripts.dev_auth token <sub> [--email E] [--name N] [--minutes 60]

The JWKS is served over HTTP because the verifier (PyJWKClient) accepts only
http(s) key URLs - the same path a real provider uses. Only the public key
lives in .dev_auth/public/; the private key is never served.

The token only proves an identity. Role and scope still come from the
database: register the identity (POST /api/me/register) or create it with
`python -m app.users create <sub> --role ...`.
"""
import argparse
import json
import time
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parent.parent
KEY_DIR = ROOT / ".dev_auth"
PRIVATE_KEY = KEY_DIR / "private_key.pem"
JWKS = KEY_DIR / "public" / "jwks.json"
JWKS_PORT = 8765
ISSUER = "https://dev-issuer.civicfix.local"
AUDIENCE = "civicfix-api"
KID = "civicfix-dev-1"


def init() -> None:
    JWKS.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    PRIVATE_KEY.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    PRIVATE_KEY.chmod(0o600)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    JWKS.write_text(json.dumps({"keys": [{**public_jwk, "kid": KID, "use": "sig", "alg": "RS256"}]}))
    print("Add to .env (development only):")
    print(f"AUTH_JWKS_URL=http://127.0.0.1:{JWKS_PORT}/jwks.json")
    print(f"AUTH_ISSUER={ISSUER}")
    print(f"AUTH_AUDIENCE={AUDIENCE}")
    print(f"\nThen serve the public key: python -m http.server {JWKS_PORT} --bind 127.0.0.1 --directory {JWKS.parent}")


def token(sub: str, email: str | None, name: str | None, minutes: int) -> str:
    now = int(time.time())
    claims = {"sub": sub, "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + minutes * 60}
    if email:
        claims["email"] = email
    if name:
        claims["name"] = name
    return jwt.encode(claims, PRIVATE_KEY.read_bytes(), algorithm="RS256", headers={"kid": KID})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="python -m scripts.dev_auth")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    tok = sub.add_parser("token")
    tok.add_argument("sub")
    tok.add_argument("--email")
    tok.add_argument("--name")
    tok.add_argument("--minutes", type=int, default=60)
    args = parser.parse_args()
    if args.command == "init":
        init()
    else:
        print(token(args.sub, args.email, args.name, args.minutes))
