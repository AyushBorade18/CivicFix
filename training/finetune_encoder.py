"""Fine-tune the multilingual sentence encoder on the synthetic paraphrase
groups, so romanized Marathi / Hindi / code-mixed complaints land near their
English and Devanagari equivalents.

- Base: paraphrase-multilingual-MiniLM-L12-v2 (384-dim, fits vector(384)).
- Data: training/synthetic/paraphrase_groups.csv (400 groups x 3 variants,
  all synthetic). Split BY GROUP, so test groups are never seen in training.
- Loss: MultipleNegativesRankingLoss on (anchor, positive, hard negative).
  The hard negative is a different problem at the SAME locality, so the model
  learns "same problem", not "same place" - otherwise dedup would merge
  unrelated complaints from one street.
- Metrics before and after go to models/encoder_metrics.json. The model goes
  to models/civicfix-encoder-v1/ (not committed: ~470 MB; rebuild with this
  script, seeded).

Plain torch loop: avoids adding `datasets`/`accelerate` just for training.

Run: python -m training.finetune_encoder
"""
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
GROUPS_CSV = ROOT / "training/synthetic/paraphrase_groups.csv"
ICMYC_CSV = ROOT / "training/icmyc_mapped.csv"
BASE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
OUT_DIR = ROOT / "models/civicfix-encoder-v1"
METRICS_JSON = ROOT / "models/encoder_metrics.json"

SEED = 42
TEST_GROUPS_PER_CATEGORY = 6  # 48 of 400 groups held out
EPOCHS = 3
BATCH_SIZE = 16  # fits a 16 GB Mac with other apps open
MAX_SEQ_LENGTH = 128  # complaints are short; caps memory
LEARNING_RATE = 2e-5

# The cross-language pairs checked before fine-tuning (romanized Marathi scored 0.21).
PROBES = [
    ("The streetlight on Baner road is not working for 4 days",
     "बाणेर रस्त्यावरचे दिवे चार दिवसांपासून बंद आहेत", "same: english-marathi"),
    ("The streetlight on Baner road is not working for 4 days",
     "Baner road pe streetlight 4 din se band hai", "same: english-hinglish"),
    ("Kothrud madhe kachra uchalla nahi teen divas",
     "Garbage not collected in Kothrud for three days", "same: romanized_marathi-english"),
    ("Garbage not collected in Kothrud for three days",
     "There is a big pothole near Kothrud depot", "different: same place"),
    ("बाणेर रस्त्यावरचे दिवे बंद आहेत", "कोथरूड मध्ये पाणी येत नाही", "different: marathi-marathi"),
]


def read_rows(path: Path = GROUPS_CSV) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def split_groups(rows: list[dict], test_per_category: int = TEST_GROUPS_PER_CATEGORY,
                 seed: int = SEED) -> tuple[list[dict], list[dict]]:
    """Hold out whole groups, the same number per category."""
    rng = random.Random(seed)
    groups_by_category = defaultdict(set)
    for r in rows:
        groups_by_category[r["category"]].add(r["group_id"])
    test_ids = set()
    for category in sorted(groups_by_category):
        test_ids.update(rng.sample(sorted(groups_by_category[category]), test_per_category))
    return ([r for r in rows if r["group_id"] not in test_ids],
            [r for r in rows if r["group_id"] in test_ids])


def build_triplets(rows: list[dict], seed: int = SEED) -> list[tuple[str, tuple[str, str, str]]]:
    """(group_id, (anchor, positive, negative)) for every ordered pair of variants
    in a group. Negative: another group's text at the same locality with a
    different category; any different-category text if the locality has none."""
    rng = random.Random(seed)
    groups = defaultdict(list)
    by_place = defaultdict(list)
    for r in rows:
        groups[r["group_id"]].append(r)
        by_place[r["locality"]].append(r)
    triplets = []
    for group_id in sorted(groups):
        members = groups[group_id]
        category, locality = members[0]["category"], members[0]["locality"]
        candidates = [r for r in by_place[locality] if r["category"] != category] or \
                     [r for r in rows if r["category"] != category]
        for a in members:
            for p in members:
                if a is not p:
                    triplets.append((group_id, (a["text"], p["text"], rng.choice(candidates)["text"])))
    return triplets


def batches_without_repeated_groups(triplets, batch_size: int = BATCH_SIZE, seed: int = SEED):
    """In-batch negatives assume every other row is a different problem, so a
    batch may hold at most one triplet per group. Round i takes the i-th
    triplet of every group; batches never cross a round."""
    rng = random.Random(seed)
    per_group = defaultdict(list)
    for t in triplets:
        per_group[t[0]].append(t)
    for items in per_group.values():
        rng.shuffle(items)
    group_ids = list(per_group)
    batches = []
    for i in range(max(len(v) for v in per_group.values())):
        rng.shuffle(group_ids)
        round_items = [per_group[g][i] for g in group_ids if i < len(per_group[g])]
        batches += [round_items[j:j + batch_size] for j in range(0, len(round_items), batch_size)]
    rng.shuffle(batches)
    return batches


def _cos_matrix(model, texts: list[str]) -> np.ndarray:
    emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return emb @ emb.T


def evaluate(model, test_rows: list[dict]) -> dict:
    texts = [r["text"] for r in test_rows]
    sim = _cos_matrix(model, texts)
    np.fill_diagonal(sim, -1.0)
    groups = [r["group_id"] for r in test_rows]
    hits = defaultdict(list)
    for i, row in enumerate(test_rows):
        correct = groups[int(sim[i].argmax())] == groups[i]
        hits["all"].append(correct)
        hits[row["language"]].append(correct)
    same, diff, same_place_diff_problem = [], [], []
    for i in range(len(test_rows)):
        for j in range(i + 1, len(test_rows)):
            if groups[i] == groups[j]:
                same.append(sim[i, j])
            else:
                diff.append(sim[i, j])
                if (test_rows[i]["locality"] == test_rows[j]["locality"]
                        and test_rows[i]["category"] != test_rows[j]["category"]):
                    same_place_diff_problem.append(sim[i, j])
    probe_scores = {}
    for a, b, name in PROBES:
        e = model.encode([a, b], normalize_embeddings=True, show_progress_bar=False)
        probe_scores[name] = round(float(e[0] @ e[1]), 3)
    return {
        "top1_same_problem": {k: round(float(np.mean(v)), 3) for k, v in sorted(hits.items())},
        "mean_cos_same_problem": round(float(np.mean(same)), 3),
        "mean_cos_different_problem": round(float(np.mean(diff)), 3),
        "mean_cos_same_place_different_problem": round(float(np.mean(same_place_diff_problem)), 3)
        if same_place_diff_problem else None,
        "probes": probe_scores,
        "english_classification_macro_f1": english_retention(model),
    }


def english_retention(model, n_train: int = 2000, n_test: int = 1000) -> float | None:
    """Macro-F1 of a logistic regression on real English (Bengaluru iCMyC)
    complaints. Guards against fine-tuning on synthetic text hurting English."""
    if not ICMYC_CSV.exists():
        return None
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    from sklearn.model_selection import train_test_split
    rows = read_rows(ICMYC_CSV)
    random.Random(SEED).shuffle(rows)
    rows = rows[: n_train + n_test]
    texts, labels = [r["text"] for r in rows], [r["category"] for r in rows]
    x_tr, x_te, y_tr, y_te = train_test_split(texts, labels, test_size=n_test, random_state=SEED, stratify=labels)
    enc = lambda t: model.encode(t, normalize_embeddings=True, show_progress_bar=False)  # noqa: E731
    clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(enc(x_tr), y_tr)
    return round(float(f1_score(y_te, clf.predict(enc(x_te)), average="macro")), 3)


def train(model, triplets, epochs: int = EPOCHS) -> list[float]:
    import torch
    from sentence_transformers.losses import MultipleNegativesRankingLoss

    device = model.device
    loss_fn = MultipleNegativesRankingLoss(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    epoch_losses = []
    model.train()
    for epoch in range(epochs):
        batches = batches_without_repeated_groups(triplets, seed=SEED + epoch)
        total = 0.0
        for step, batch in enumerate(batches, 1):
            columns = list(zip(*[t for _, t in batch]))  # anchors, positives, negatives
            features = [{k: v.to(device) if hasattr(v, "to") else v for k, v in model.tokenize(list(col)).items()} for col in columns]
            loss = loss_fn(features, torch.zeros(len(batch), device=device))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += loss.item()
            if step % 10 == 0:
                print(f"  epoch {epoch + 1} step {step}/{len(batches)} loss {loss.item():.3f}", flush=True)
        epoch_losses.append(round(total / len(batches), 4))
        print(f"epoch {epoch + 1}: mean loss {epoch_losses[-1]}", flush=True)
    model.eval()
    return epoch_losses


def main() -> int:
    import torch
    from sentence_transformers import SentenceTransformer

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    rows = read_rows()
    train_rows, test_rows = split_groups(rows)
    triplets = build_triplets(train_rows)
    print(f"{len(train_rows) // 3} train groups, {len(test_rows) // 3} test groups, {len(triplets)} triplets")

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = SentenceTransformer(BASE_MODEL, device=device)
    model.max_seq_length = MAX_SEQ_LENGTH
    before = evaluate(model, test_rows)
    print("before:", json.dumps(before, ensure_ascii=False))
    losses = train(model, triplets)
    after = evaluate(model, test_rows)
    print("after:", json.dumps(after, ensure_ascii=False))

    model.save(str(OUT_DIR))
    METRICS_JSON.write_text(json.dumps({
        "base_model": BASE_MODEL, "output_dir": str(OUT_DIR.relative_to(ROOT)),
        "data": "training/synthetic/paraphrase_groups.csv (synthetic)",
        "seed": SEED, "epochs": EPOCHS, "batch_size": BATCH_SIZE, "max_seq_length": MAX_SEQ_LENGTH, "learning_rate": LEARNING_RATE,
        "train_groups": len(train_rows) // 3, "test_groups": len(test_rows) // 3,
        "epoch_losses": losses, "before": before, "after": after,
        "note": "Test groups are synthetic too; real-world accuracy must be measured on the human test set.",
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
