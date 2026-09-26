"""Move the fine-tuned encoder (models/civicfix-encoder-v1, ~465 MB, gitignored)
between this machine and a PRIVATE Hugging Face model repo, so a hosted
build can get it without committing weights to git.

  python -m scripts.encoder_hub upload   # once, from the machine that has it
  python -m scripts.encoder_hub fetch    # in the Render build; no-op if present

Env: ENCODER_REPO (e.g. "your-hf-user/civicfix-encoder-v1"), HF_TOKEN
(write scope to upload, read scope to fetch).

The stored report/issue embeddings were produced by exactly this encoder, so
the hosted API must load the same weights - never a stand-in model.
"""
import os
import sys

from dotenv import load_dotenv
from huggingface_hub import HfApi, snapshot_download

from app.nlp.embeddings import EMBEDDING_MODEL


load_dotenv()  # HF_TOKEN / ENCODER_REPO from .env locally; Render sets real env vars


def _repo_and_token() -> tuple[str, str]:
    repo, token = os.environ.get("ENCODER_REPO"), os.environ.get("HF_TOKEN")
    if not repo or not token:
        sys.exit("set ENCODER_REPO and HF_TOKEN")
    return repo, token


def upload() -> None:
    repo, token = _repo_and_token()
    api = HfApi(token=token)
    api.create_repo(repo, private=True, exist_ok=True)
    api.upload_folder(folder_path=EMBEDDING_MODEL, repo_id=repo, commit_message="civicfix encoder v1")
    print(f"uploaded {EMBEDDING_MODEL} -> {repo} (private)")


def fetch() -> None:
    if os.path.exists(os.path.join(EMBEDDING_MODEL, "model.safetensors")):
        print(f"encoder already present at {EMBEDDING_MODEL}")
        return
    repo, token = _repo_and_token()
    snapshot_download(repo_id=repo, token=token, local_dir=EMBEDDING_MODEL)
    print(f"fetched {repo} -> {EMBEDDING_MODEL}")


if __name__ == "__main__":
    {"upload": upload, "fetch": fetch}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
