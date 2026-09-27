"""End-to-end against the REAL private Supabase bucket. Opt-in only:

    RUN_LIVE_STORAGE=1 python -m pytest tests/test_storage_live.py -p no:cacheprovider

Citizen uploads -> object lands in the bucket under issues/<issue_id>/ ->
admin asks for the photo -> short-lived signed URL -> URL serves the exact
bytes; another citizen is refused; the bucket itself is not publicly
readable. Uses civicfix_test for rows and deletes its object afterwards.
Credentials come from .env and are never printed.
"""
import os

import httpx
import pytest
from dotenv import dotenv_values

from app.api import evidence
from tests.test_auth import auth, auth_env, client, make_token, signing_key, world  # noqa: F401
from tests.test_evidence import JPEG, ev, submit  # noqa: F401

pytestmark = pytest.mark.skipif(os.environ.get("RUN_LIVE_STORAGE") != "1", reason="set RUN_LIVE_STORAGE=1")


@pytest.fixture
def live_bucket(ev, monkeypatch):  # noqa: F811 - ev first: it clears the storage env
    env = dotenv_values(".env")
    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "EVIDENCE_BUCKET"):
        if not env.get(var):
            pytest.skip(f"{var} not set in .env")
        monkeypatch.setenv(var, env[var])
    keys = []
    yield keys
    for key in keys:
        evidence._discard(key)


def test_citizen_photo_round_trips_through_the_private_bucket(client, ev, live_bucket, db_conn):  # noqa: F811
    resp = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"], capture_method="upload")
    assert resp.status_code == 201, resp.text
    item = resp.json()
    with db_conn.cursor() as cur:
        cur.execute("SELECT file_key FROM evidence WHERE id = %s", (item["evidence_id"],))
        key = cur.fetchone()[0]
    live_bucket.append(key)
    assert key.startswith(f"issues/{ev['issues']['road_w1']}/")

    signed = client.get(f"/api/evidence/{item['evidence_id']}/url", headers=ev["as"]("admin")).json()
    assert signed["expires_in"] == evidence.SIGNED_URL_SECONDS
    assert "/storage/v1/object/sign/complaint-images/" in signed["url"]
    photo = httpx.get(signed["url"], timeout=30)
    assert photo.status_code == 200 and photo.content == JPEG

    assert client.get(f"/api/evidence/{item['evidence_id']}/url", headers=ev["as"]("bob")).status_code == 404
    # Private: the plain public-object URL must not serve it.
    public = f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1/object/public/complaint-images/{key}"
    assert httpx.get(public, timeout=30).status_code >= 400
