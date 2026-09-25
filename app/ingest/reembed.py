"""Recompute every stored vector with the current embedding model.

Needed whenever app/nlp/embeddings.py:EMBEDDING_MODEL changes: vectors from
two different models can't be compared, so works, reports and issues must
all be re-embedded together, in one transaction.

- works:   description (same text app/ingest/mplads.py embeds)
- reports: raw_text, the original complaint as typed (not a translation;
           the multilingual model reads Hindi/Marathi directly)
- issues:  mean of their member reports' vectors (same as clustering.py)

Run: python -m app.ingest.reembed   (commits only if everything succeeds)
"""
import numpy as np

from app.db import get_connection
from app.nlp.embeddings import EMBEDDING_MODEL, get_embedding_model

BATCH = 64


def _literal(vector) -> str:
    return "[" + ",".join(str(float(v)) for v in vector) + "]"


def _reembed_table(cur, model, table: str, text_column: str) -> int:
    cur.execute(f"SELECT id, COALESCE({text_column}, '') FROM {table} ORDER BY id")
    rows = cur.fetchall()
    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        vectors = model.encode([text for _, text in chunk], batch_size=BATCH, show_progress_bar=False)
        cur.executemany(
            f"UPDATE {table} SET embedding = %s::vector WHERE id = %s",
            [(_literal(v), row_id) for (row_id, _), v in zip(chunk, vectors)],
        )
    return len(rows)


def reembed_all(conn, model) -> dict:
    """Does not commit; the caller decides (tests roll back)."""
    with conn.cursor() as cur:
        counts = {
            "works": _reembed_table(cur, model, "works", "description"),
            "reports": _reembed_table(cur, model, "reports", "raw_text"),
        }
        cur.execute("SELECT issue_id, embedding FROM reports WHERE issue_id IS NOT NULL")
        members: dict[int, list[np.ndarray]] = {}
        for issue_id, emb in cur.fetchall():
            members.setdefault(issue_id, []).append(np.array([float(x) for x in str(emb).strip("[]").split(",")]))
        cur.executemany(
            "UPDATE issues SET embedding = %s::vector WHERE id = %s",
            [(_literal(np.mean(vs, axis=0)), issue_id) for issue_id, vs in members.items()],
        )
        counts["issues"] = len(members)
    return counts


if __name__ == "__main__":
    with get_connection() as conn:
        print(f"re-embedding with {EMBEDDING_MODEL}")
        print(reembed_all(conn, get_embedding_model()))
        conn.commit()
