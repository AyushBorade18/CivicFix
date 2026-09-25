import csv
from pathlib import Path

from app.categories import CIVIC_CATEGORIES
from app.nlp.classify import (
    CONFIDENCE_THRESHOLD,
    classify,
    classify_keywords,
    evaluate_classifier,
    train_classifier,
)

NYC311_FIXTURE = "tests/fixtures/nyc311_sample.csv"


def test_classify_keywords_pothole():
    category, conf = classify_keywords("Big pothole near my house, almost hit it on my bike")
    assert category == "pothole_road"
    assert conf > 0


def test_classify_keywords_drainage():
    category, conf = classify_keywords("Sewage overflowing onto the street, terrible smell")
    assert category == "drainage_sewage"
    assert conf > 0


def test_classify_keywords_streetlight():
    category, conf = classify_keywords("Streetlight has not worked for two weeks, street is pitch dark")
    assert category == "streetlight"
    assert conf > 0


def test_classify_keywords_unrelated_falls_back_to_other():
    category, conf = classify_keywords("Loud music from a wedding hall until 2am")
    assert category == "other"
    assert conf == 0.0


def test_classify_keywords_empty_text():
    assert classify_keywords("") == ("other", 0.0)
    assert classify_keywords(None) == ("other", 0.0)


def test_classify_uses_keyword_baseline_when_no_trained_model(tmp_path, monkeypatch):
    monkeypatch.setattr("app.nlp.classify.MODEL_PATH", str(tmp_path / "nonexistent.pkl"))
    category, conf = classify("Garbage has not been collected here in over a week")
    assert category == "garbage_waste"
    assert conf > 0


def test_classify_forces_other_below_confidence_threshold(monkeypatch):
    monkeypatch.setattr("app.nlp.classify.MODEL_PATH", "/nonexistent/path.pkl")
    monkeypatch.setattr("app.nlp.classify.classify_keywords", lambda text: ("pothole_road", 0.1))
    category, conf = classify("ambiguous text")
    assert category == "other"
    assert conf == 0.1
    assert conf < CONFIDENCE_THRESHOLD


def test_train_classifier_smoke_test_with_fixture(tmp_path):
    """Real NYC 311 data isn't present locally - this only proves the training
    code path runs end-to-end on a small fixture shaped like NYC 311's real
    columns (Complaint Type, Descriptor). It is NOT a real accuracy claim.
    """
    model_path = tmp_path / "classifier.pkl"
    train_classifier(NYC311_FIXTURE, model_path=str(model_path))
    assert model_path.exists()

    import pickle
    with open(model_path, "rb") as f:
        bundle = pickle.load(f)
    assert "model" in bundle and "label_encoder" in bundle
    assert set(bundle["label_encoder"].classes_) <= set(CIVIC_CATEGORIES)


def test_classify_uses_trained_model_when_present(tmp_path, monkeypatch):
    model_path = tmp_path / "classifier.pkl"
    train_classifier(NYC311_FIXTURE, model_path=str(model_path))
    monkeypatch.setattr("app.nlp.classify.MODEL_PATH", str(model_path))
    monkeypatch.setattr("app.nlp.classify._cached_model", None)
    category, conf = classify("There is a large pothole on my street")
    assert category in CIVIC_CATEGORIES
    assert 0.0 <= conf <= 1.0


def test_evaluate_classifier_smoke_test_with_fixture(tmp_path):
    """Only proves the held-out-split + macro-F1 code path runs on the tiny
    fixture and saves a production model - the fixture is too small for the
    resulting numbers to mean anything about real accuracy.
    """
    model_path = tmp_path / "classifier.pkl"
    result = evaluate_classifier(NYC311_FIXTURE, model_path=str(model_path), test_size=0.5, seed=1)
    assert 0.0 <= result["model_macro_f1"] <= 1.0
    assert 0.0 <= result["baseline_macro_f1"] <= 1.0
    assert result["n_train"] + result["n_test"] == result["n_total"]
    assert model_path.exists()


def test_classify_refuses_a_model_trained_with_a_different_encoder(tmp_path, monkeypatch):
    # Vectors from two encoders aren't comparable; a silent mismatch would give
    # confident nonsense instead of an error.
    import pickle

    import pytest

    model_path = tmp_path / "classifier.pkl"
    train_classifier(NYC311_FIXTURE, model_path=str(model_path))
    with open(model_path, "rb") as f:
        bundle = pickle.load(f)
    bundle["encoder"] = "some-other-encoder"
    with open(model_path, "wb") as f:
        pickle.dump(bundle, f)
    monkeypatch.setattr("app.nlp.classify.MODEL_PATH", str(model_path))
    monkeypatch.setattr("app.nlp.classify._cached_model", None)
    with pytest.raises(RuntimeError, match="encoder"):
        classify("There is a large pothole on my street")


def test_nyc_trainer_never_overwrites_the_live_model_by_default():
    import inspect

    from app.nlp.classify import ARCHIVED_MODEL_PATH
    assert inspect.signature(train_classifier).parameters["model_path"].default == ARCHIVED_MODEL_PATH
