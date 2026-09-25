"""The one sentence-embedding model every module shares. Classifier,
clustering, matcher and the stored vectors (reports, issues, works) must all
come from the same model, or cosine similarities between them are
meaningless. Changing EMBEDDING_MODEL means re-embedding every stored
vector and retraining the classifier; the output size must stay 384 to fit
the vector(384) columns in schema.sql.
"""
from functools import lru_cache
from pathlib import Path

from sentence_transformers import SentenceTransformer

# Fine-tuned from paraphrase-multilingual-MiniLM-L12-v2 (training/finetune_encoder.py,
# metrics in models/encoder_metrics.json). Not committed; unzip it into models/.
EMBEDDING_MODEL = str(Path(__file__).resolve().parents[2] / "models/civicfix-encoder-v1")


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)
