import numpy as np

from app.ingest.reembed import reembed_all


class _FakeModel:
    """Deterministic 384-dim vector per text, so the test knows the expected values."""

    def encode(self, texts, **_):
        out = []
        for t in texts:
            rng = np.random.default_rng(abs(hash(t)) % (2**32))
            out.append(rng.random(384))
        return np.array(out)


def _vec(raw) -> np.ndarray:
    return np.array([float(x) for x in str(raw).strip("[]").split(",")])


def test_reembeds_works_reports_and_issue_means(db_conn):
    fake = _FakeModel()
    zero = "[" + ",".join(["0"] * 384) + "]"
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO issues (category, status, report_count) VALUES ('garbage_waste','open',2) RETURNING id")
        issue_id = cur.fetchone()[0]
        report_ids = []
        for text in ("Kothrud madhe kachra uchalla nahi", "Garbage not collected in Kothrud"):
            cur.execute(
                "INSERT INTO reports (raw_text, reported_at, category, geom_confidence, is_synthetic, issue_id, embedding) "
                "VALUES (%s, now(), 'garbage_waste', 0.4, true, %s, %s::vector) RETURNING id",
                (text, issue_id, zero),
            )
            report_ids.append(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO works (work_name, description, category, embedding) "
            "VALUES ('Drain work', 'Construction of storm water drain', 'drainage_sewage', %s::vector) RETURNING id",
            (zero,),
        )
        work_id = cur.fetchone()[0]

    counts = reembed_all(db_conn, fake)
    assert counts["works"] >= 1 and counts["reports"] >= 2 and counts["issues"] >= 1

    with db_conn.cursor() as cur:
        cur.execute("SELECT embedding FROM works WHERE id = %s", (work_id,))
        assert np.allclose(_vec(cur.fetchone()[0]), fake.encode(["Construction of storm water drain"])[0], atol=1e-5)
        cur.execute("SELECT raw_text, embedding FROM reports WHERE id = ANY(%s)", (report_ids,))
        report_vecs = []
        for text, emb in cur.fetchall():
            assert np.allclose(_vec(emb), fake.encode([text])[0], atol=1e-5)
            report_vecs.append(_vec(emb))
        cur.execute("SELECT embedding FROM issues WHERE id = %s", (issue_id,))
        assert np.allclose(_vec(cur.fetchone()[0]), np.mean(report_vecs, axis=0), atol=1e-5)
