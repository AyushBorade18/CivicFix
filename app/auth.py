"""Authentication boundary: verify a provider-issued JWT, then resolve it to
a CivicFix user whose role and scope come from our database.

Provider-neutral: any OIDC provider that publishes a JWKS (Clerk, Auth0,
Cognito, Keycloak, ...) works by setting the env vars below. CivicFix never
sees or stores passwords.

  AUTH_JWKS_URL    provider's JWKS endpoint (required)
  AUTH_ISSUER      expected "iss" claim, exact match (required)
  AUTH_AUDIENCE    expected "aud" claim (set it whenever the provider issues one)
  AUTH_ALGORITHMS  comma-separated, default "RS256"; asymmetric algorithms only

With AUTH_JWKS_URL or AUTH_ISSUER unset, every authenticated endpoint
answers 503 - it never falls back to trusting an unverified token.
"""
import os
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_db
from app.users import CurrentUser, get_user

# Symmetric (HS*) and "none" are refused: with a shared secret, anyone
# holding the verification key could also mint tokens.
_ASYMMETRIC_PREFIXES = ("RS", "ES", "PS", "EdDSA")

_bearer = HTTPBearer(auto_error=False)


def _config() -> dict:
    jwks_url = os.environ.get("AUTH_JWKS_URL")
    issuer = os.environ.get("AUTH_ISSUER")
    if not jwks_url or not issuer:
        raise HTTPException(status_code=503, detail="authentication is not configured on this server")
    algorithms = [a.strip() for a in os.environ.get("AUTH_ALGORITHMS", "RS256").split(",") if a.strip()]
    if not algorithms or not all(a.startswith(_ASYMMETRIC_PREFIXES) for a in algorithms):
        raise HTTPException(status_code=503, detail="AUTH_ALGORITHMS must list asymmetric algorithms only")
    return {
        "jwks_url": jwks_url, "issuer": issuer,
        "audience": os.environ.get("AUTH_AUDIENCE") or None, "algorithms": algorithms,
    }


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True)


def verify_token(token: str) -> dict:
    """Return the verified claims, or raise 401. The error detail never
    echoes the token."""
    cfg = _config()
    try:
        key = _jwks_client(cfg["jwks_url"]).get_signing_key_from_jwt(token).key
        return jwt.decode(
            token, key, algorithms=cfg["algorithms"], issuer=cfg["issuer"], audience=cfg["audience"],
            options={"require": ["exp", "iss", "sub"], "verify_aud": cfg["audience"] is not None},
        )
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(status_code=503, detail="identity provider keys unavailable")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})


def get_verified_claims(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    return verify_token(creds.credentials)


def get_current_user(claims: dict = Depends(get_verified_claims), db=Depends(get_db)) -> CurrentUser:
    user = get_user(db, claims["sub"])
    if user is None:
        raise HTTPException(status_code=403, detail="no CivicFix account for this identity; register first")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="account is deactivated")
    return user


def require_staff(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_staff:
        raise HTTPException(status_code=403, detail="municipal staff only")
    return user


def show_test_data() -> bool:
    """Generated test complaints (reports.is_synthetic) stay off the live
    site. Only a developer machine sets SHOW_TEST_DATA=1 to demo with them."""
    return os.environ.get("SHOW_TEST_DATA", "").strip().lower() in ("1", "true", "yes")


def live_issue_sql(alias: str = "") -> str:
    """SQL predicate: the issue holds at least one real citizen report and
    isn't held as likely spam (app/nlp/triage.py). The real-report half is
    dropped when test data is switched on."""
    table = alias or "issues"
    not_held = f"NOT {table}.held_as_spam"
    if show_test_data():
        return not_held
    return (f"{not_held} AND EXISTS (SELECT 1 FROM reports r_live WHERE r_live.issue_id = {table}.id "
            "AND NOT r_live.is_synthetic)")


def issue_scope_sql(user: CurrentUser, alias: str = "") -> tuple[str, dict]:
    """SQL predicate limiting issues to what this staff user may see, for
    list endpoints. Mirrors CurrentUser.can_access_issue exactly, and hides
    test issues on the live site."""
    col = f"{alias}." if alias else ""
    if user.role == "system_admin":
        scope, params = "TRUE", {}
    elif user.role == "ward_officer":
        scope, params = f"{col}ward_id = ANY(%(scope_wards)s)", {"scope_wards": sorted(user.ward_ids)}
    elif user.role == "department_officer":
        scope, params = f"{col}category::text = ANY(%(scope_categories)s)", {"scope_categories": user.department_categories}
    else:
        return "FALSE", {}
    return f"({scope}) AND {live_issue_sql(alias)}", params


def ensure_issue_access(user: CurrentUser, db, issue_id: int) -> None:
    """404 if the issue doesn't exist (or is hidden test data), 403 if it's
    outside the user's scope."""
    with db.cursor() as cur:
        cur.execute(f"SELECT ward_id, category::text FROM issues WHERE id = %s AND {live_issue_sql()}", (issue_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"issue {issue_id} not found")
    if not user.can_access_issue(row[0], row[1]):
        raise HTTPException(status_code=403, detail=f"issue {issue_id} is outside your ward/department scope")
