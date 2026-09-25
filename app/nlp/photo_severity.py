"""Photo-derived severity: a deterministic formula over real pixel
statistics, computed fresh from each uploaded photo - not a trained model,
no learned weights, nothing fit to labeled data. In the same spirit as
app/core/priority.py's fixed formula and app/nlp/severity.py's keyword
bands: every number here comes from the actual image bytes at request time.

Evidence only (hard rule 3, re-confirmed 2026-09-25): the score is stored
and shown to the human reviewer, but never changes a report's severity or
priority. Pixel statistics can't tell a pothole from a photo taken at
night, so letting them rank issues would be gameable.

Three real, cheap image statistics combine into one score:
  - edge_density: mean intensity after edge detection - cracked/broken/
    cluttered surfaces produce far more edges than a plain road or wall.
  - dark_ratio: fraction of pixels below a brightness threshold - proxies
    pooled water, deep cavities, and shadow-heavy damage.
  - saturation_variance: spread of HSV saturation - a chaotic pile (garbage,
    debris) has wildly inconsistent color saturation; a clean surface doesn't.
"""
import io

from PIL import Image, ImageFilter

_BAND_ORDER = ("cosmetic", "moderate", "critical")

EDGE_WEIGHT = 0.45
DARK_WEIGHT = 0.35
SATURATION_WEIGHT = 0.20

DARK_PIXEL_THRESHOLD = 60  # 0-255; below this counts as "dark"
CRITICAL_CUTOFF = 0.60
MODERATE_CUTOFF = 0.32


def _band_for_score(score: float) -> str:
    if score >= CRITICAL_CUTOFF:
        return "critical"
    if score >= MODERATE_CUTOFF:
        return "moderate"
    return "cosmetic"


def estimate_photo_severity(image_bytes: bytes) -> dict:
    """Returns {score, band, edge_density, dark_ratio, saturation_variance}.
    Raises ValueError if the bytes aren't a decodable image - callers must
    catch this and degrade gracefully (no photo severity, not a crash)."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as exc:
        raise ValueError(f"undecodable image: {exc}") from exc

    img = img.convert("RGB")
    # Cap the analysis resolution - severity statistics don't need full
    # resolution and this keeps the request fast regardless of upload size.
    img.thumbnail((512, 512))

    gray = img.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_pixels = list(edges.getdata())
    edge_density = min(1.0, (sum(edge_pixels) / len(edge_pixels)) / 255.0 * 3.0)

    gray_pixels = list(gray.getdata())
    dark_ratio = sum(1 for p in gray_pixels if p < DARK_PIXEL_THRESHOLD) / len(gray_pixels)

    hsv = img.convert("HSV")
    saturation_pixels = [p[1] for p in hsv.getdata()]
    mean_sat = sum(saturation_pixels) / len(saturation_pixels)
    variance = sum((p - mean_sat) ** 2 for p in saturation_pixels) / len(saturation_pixels)
    saturation_variance = min(1.0, (variance ** 0.5) / 90.0)

    score = round(
        EDGE_WEIGHT * edge_density + DARK_WEIGHT * dark_ratio + SATURATION_WEIGHT * saturation_variance,
        4,
    )
    return {
        "score": score,
        "band": _band_for_score(score),
        "edge_density": round(edge_density, 4),
        "dark_ratio": round(dark_ratio, 4),
        "saturation_variance": round(saturation_variance, 4),
    }
