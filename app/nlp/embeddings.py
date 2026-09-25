"""The one sentence-embedding model every module shares. Classifier,
clustering, matcher and the stored vectors (reports, issues, works) must all
come from the same model, or cosine similarities between them are
meaningless. Changing EMBEDDING_MODEL means re-embedding every stored
vector and retraining the classifier; the output size must stay 384 to fit
the vector(384) columns in schema.sql.
"""
from functools import lru_cache

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)
