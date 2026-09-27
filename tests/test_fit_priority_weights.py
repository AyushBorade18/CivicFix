import numpy as np

from scripts.fit_priority_weights import agreement, fit


def test_fit_recovers_which_term_humans_care_about():
    # Humans who only ever pick the more severe issue: severity must dominate.
    rng = np.random.default_rng(0)
    X = rng.uniform(-1, 1, size=(300, 4))
    X[:, 1] = np.abs(X[:, 1]) + 0.05  # winner always more severe
    w = fit(X)
    assert w.argmax() == 1
    assert np.isclose(w.sum(), 1.0) and (w >= 0).all()
    assert agreement(X, w) > 0.95
