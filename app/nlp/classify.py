import csv
import pickle
import sys

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from app.categories import CIVIC_CATEGORIES
from app.nlp.embeddings import get_embedding_model as _get_embedding_model

MODEL_PATH = "models/classifier.pkl"
CONFIDENCE_THRESHOLD = 0.5

# Real trained-and-evaluated model, held OUT of MODEL_PATH deliberately.
# Trained on NYC 311 descriptor text, it scores 0.929 macro-F1 on NYC 311's
# own held-out split (vs 0.385 for the keyword baseline) - but tested
# against our actual synthetic Pune complaint phrasing ("Sewage overflowing
# near Ward 11 again..."), it confidently (0.85-0.97) calls 6 of 7 sample
# complaints 'other'. That's a real domain-shift failure: NYC 311's terse
# bureaucratic descriptors don't resemble how our complaints are phrased,
# and the model learned NYC 311's vocabulary, not general civic-complaint
# semantics. Deploying it live would make classify() worse than the
# baseline it's meant to beat. evaluate_classifier() saves here by
# default, not to MODEL_PATH, so re-running it doesn't silently redeploy
# a known-regressive model - promote it manually only after it's been
# validated on Pune-style text.
ARCHIVED_MODEL_PATH = "models/classifier_nyc311_trained.pkl"

# NYC 311's real "complaint_type" taxonomy (NYC Open Data export column
# names: complaint_type, descriptor - lowercase snake_case) mapped onto our
# 8 categories, verified against the actual values present in a real
# ~14.5k-row export (training/nyc311_sample.csv), not guessed. Anything not
# listed here (the large majority of NYC 311 complaint types) maps to
# 'other' - that's real signal, not a gap: most 311 complaints are outside
# our civic scope (noise, illegal parking, abandoned vehicles, permits...).
NYC311_CATEGORY_MAP = {
    "Street Condition": "pothole_road",
    "Highway Condition": "pothole_road",
    "Sewer Maintenance": "drainage_sewage",
    "Water Maintenance": "water_supply",
    "WATER LEAK": "water_supply",
    "Street Light Condition": "streetlight",
    "UNSANITARY CONDITION": "garbage_waste",
    "Dirty Condition": "garbage_waste",
    "Missed Collection": "garbage_waste",
    "Illegal Dumping": "garbage_waste",
    "Sidewalk Condition": "footpath",
    "Traffic Signal Condition": "traffic_signage",
}

# Citizen complaint phrasing, deliberately different vocabulary from the
# institutional MPLADS work descriptions in app/ingest/category.py.
CITIZEN_KEYWORDS = {
    "pothole_road": [
        "pothole", "craters", "road caved", "road damage", "bumpy road",
        "road cracked", "broken road",
    ],
    "drainage_sewage": [
        "sewage", "drain overflow", "open drain", "manhole", "gutter blocked",
        "stagnant water", "drainage blocked", "sewer",
    ],
    "water_supply": [
        "no water supply", "water shortage", "water not coming",
        "low water pressure", "contaminated water", "water tanker",
    ],
    "streetlight": [
        "streetlight", "street light", "lamp post", "dark street", "no lighting",
    ],
    "garbage_waste": [
        "garbage", "trash", "waste not collected", "overflowing dustbin",
        "dustbin", "foul smell garbage",
    ],
    "footpath": [
        "footpath", "pavement", "no proper footpath", "walkway blocked",
    ],
    "traffic_signage": [
        "traffic signal", "traffic light", "missing signage", "zebra crossing",
        "speed breaker",
    ],
}

_cached_model = None
_cached_model_path = None


def classify_keywords(text: str) -> tuple[str, float]:
    """Lexical baseline classifier for citizen complaint text. Confidence
    reflects how many distinct keyword phrases from the winning category hit,
    not a calibrated probability - it exists so the ML model's improvement
    over it is honestly measurable per ARCHITECTURE.md section 6.
    """
    if not text:
        return "other", 0.0

    lowered = text.lower()
    best_category = None
    best_hits = 0
    for category, keywords in CITIZEN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lowered)
        if hits > best_hits:
            best_hits = hits
            best_category = category

    if best_category is None:
        return "other", 0.0
    confidence = min(0.6 + 0.15 * (best_hits - 1), 0.9)
    return best_category, confidence


def _load_training_data(nyc311_csv: str) -> tuple[list[str], list[str]]:
    """Rows whose complaint_type isn't in NYC311_CATEGORY_MAP are kept as
    'other' training examples rather than dropped, since most real 311
    traffic genuinely is outside our 8 categories and the classifier needs
    to learn that too.

    Training text is the descriptor ONLY - complaint_type is excluded even
    though it's more informative, because complaint_type is also exactly
    what NYC311_CATEGORY_MAP derives the label from. Including it as input
    is label leakage (the model would just learn to pattern-match the
    literal category string, not classify free text) and doesn't match
    what classify() actually receives at runtime: plain citizen text with
    no category label attached. Found by noticing a suspicious 0.998
    macro-F1 on the first run - real citizen complaints don't come
    prefixed with their own answer.
    """
    csv.field_size_limit(sys.maxsize)  # this export has some very long free-text fields
    texts, labels = [], []
    with open(nyc311_csv, newline="") as f:
        for row in csv.DictReader(f):
            complaint_type = row.get("complaint_type", "")
            text = row.get("descriptor", "").strip()
            if not text:
                continue
            texts.append(text)
            labels.append(NYC311_CATEGORY_MAP.get(complaint_type, "other"))
    return texts, labels


def train_classifier(nyc311_csv: str, model_path: str = MODEL_PATH) -> None:
    """Trains the MiniLM-embedding + LogisticRegression classifier on NYC 311
    data, per ARCHITECTURE.md 5.2, and saves it to model_path. Trains on the
    full dataset - for a held-out accuracy number, use evaluate_classifier
    instead (it fits its own train-only model for scoring, then calls this
    to save the production model on everything).
    """
    texts, labels = _load_training_data(nyc311_csv)
    embeddings = _get_embedding_model().encode(texts, show_progress_bar=False)

    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(labels)

    model = LogisticRegression(max_iter=1000)
    model.fit(embeddings, y)

    with open(model_path, "wb") as f:
        pickle.dump({"model": model, "label_encoder": label_encoder}, f)


def evaluate_classifier(
    nyc311_csv: str, model_path: str = ARCHIVED_MODEL_PATH, test_size: float = 0.2, seed: int = 42
) -> dict:
    """Real held-out evaluation, per ARCHITECTURE.md section 6: macro-F1 for
    the trained model AND the keyword baseline, on the same held-out split,
    so the model's improvement over the baseline is honestly measurable -
    not asserted. Trains the final model on the FULL dataset afterward
    (standard practice: evaluate on a held-out split, ship a model trained
    on everything), so the saved model differs slightly from the one scored
    here. Saves to ARCHIVED_MODEL_PATH, not MODEL_PATH, by default - see
    ARCHIVED_MODEL_PATH's comment for why this model isn't live.
    """
    texts, labels = _load_training_data(nyc311_csv)
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts, labels, test_size=test_size, random_state=seed, stratify=labels
    )

    embed = _get_embedding_model()
    train_embeddings = embed.encode(train_texts, show_progress_bar=False)
    test_embeddings = embed.encode(test_texts, show_progress_bar=False)

    label_encoder = LabelEncoder()
    label_encoder.fit(labels)
    y_train = label_encoder.transform(train_labels)
    y_test = label_encoder.transform(test_labels)

    model = LogisticRegression(max_iter=1000)
    model.fit(train_embeddings, y_train)
    model_preds = model.predict(test_embeddings)
    model_f1 = f1_score(y_test, model_preds, average="macro", zero_division=0)

    baseline_preds = label_encoder.transform([classify_keywords(t)[0] for t in test_texts])
    baseline_f1 = f1_score(y_test, baseline_preds, average="macro", zero_division=0)

    train_classifier(nyc311_csv, model_path=model_path)  # ship the production model, trained on everything

    return {
        "model_macro_f1": float(model_f1),
        "baseline_macro_f1": float(baseline_f1),
        "n_train": len(train_texts),
        "n_test": len(test_texts),
        "n_total": len(texts),
        "categories": sorted(label_encoder.classes_.tolist()),
    }


def classify(text: str) -> tuple[str, float]:
    """Classifies citizen complaint text into a civic_category with a
    confidence. Uses the trained MiniLM+LogisticRegression model if
    models/classifier.pkl exists, else falls back to the keyword baseline.
    Below CONFIDENCE_THRESHOLD, forces category to 'other' (manual review)
    per ARCHITECTURE.md 5.2 - the returned confidence is left as-is so
    callers can still see how low it was.
    """
    global _cached_model, _cached_model_path

    if not text:
        return "other", 0.0

    import os

    if os.path.exists(MODEL_PATH):
        if _cached_model is None or _cached_model_path != MODEL_PATH:
            with open(MODEL_PATH, "rb") as f:
                _cached_model = pickle.load(f)
            _cached_model_path = MODEL_PATH
        embedding = _get_embedding_model().encode([text], show_progress_bar=False)
        model = _cached_model["model"]
        label_encoder = _cached_model["label_encoder"]
        probs = model.predict_proba(embedding)[0]
        best_idx = probs.argmax()
        category = label_encoder.inverse_transform([best_idx])[0]
        confidence = float(probs[best_idx])
    else:
        category, confidence = classify_keywords(text)

    if confidence < CONFIDENCE_THRESHOLD:
        return "other", confidence
    return category, confidence
