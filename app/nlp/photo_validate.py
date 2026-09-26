"""Evidence-photo intake: authenticity signals, metadata stripping, and
encryption at rest.

process_upload() reads signals from the ORIGINAL bytes, then re-encodes a
clean upright JPEG with no metadata at all. The original bytes are never
written to disk.

What the signals can and cannot say (shown to the reviewer as-is):
  - ai_generator_metadata is strong when present: generators write it
    themselves (IPTC trainedAlgorithmicMedia, Stable Diffusion/ComfyUI
    prompt fields, generator names in Software/CreatorTool).
  - Its absence proves nothing: anyone can strip metadata, or inject fake
    camera EXIF. No metadata check can confirm a photo is real.
  - Coordinates burned into the pixels by a geotag-overlay app are NOT
    removed; that needs OCR and is out of scope.
Photos are evidence only and never change severity or priority (hard rule
3), which is what caps the damage a convincing fake can do.

Encryption at rest: Fernet (AES-128-CBC + HMAC-SHA256) with the key in
PHOTO_ENCRYPTION_KEY. Without a key, or without the `cryptography`
package, photos are stored unencrypted and the upload record says so.
"""
import io
import os
from pathlib import Path

from PIL import Image, ImageOps

GPS_IFD = 0x8825
MAX_STORED_EDGE = 2048
STORED_JPEG_QUALITY = 85

# Every Fernet token starts with this (version byte 0x80, base64url).
# Plain JPEG/PNG/WebP files never do, so legacy unencrypted files stay readable.
ENCRYPTED_PREFIX = b"gAAAAA"

AI_BYTE_MARKERS = (
    b"trainedAlgorithmicMedia",               # IPTC DigitalSourceType (DALL-E, Imagen, Firefly)
    b"compositeWithTrainedAlgorithmicMedia",  # AI-edited real photo
)
AI_SOFTWARE_NAMES = (
    b"stable diffusion", b"midjourney", b"dall-e", b"dall\xc2\xb7e", b"adobe firefly",
    b"comfyui", b"automatic1111", b"novelai", b"invokeai",
)
# PNG text chunks generators write their prompt/settings into.
AI_PNG_TEXT_KEYS = {"parameters", "prompt", "workflow", "Dream", "sd-metadata"}
GENERATOR_SQUARE_SIZES = {512, 768, 1024, 1536, 2048}


def _ai_marker(body: bytes, img: Image.Image) -> str | None:
    for marker in AI_BYTE_MARKERS:
        if marker in body:
            return f"IPTC digital source type '{marker.decode()}'"
    lowered = body.lower()
    for name in AI_SOFTWARE_NAMES:
        if name in lowered:
            return f"generator name '{name.decode(errors='replace')}' in file metadata"
    png_keys = AI_PNG_TEXT_KEYS & set(img.info)
    if png_keys:
        return f"generator prompt field(s) {sorted(png_keys)} in PNG metadata"
    return None


def process_upload(body: bytes, content_type: str) -> tuple[bytes, dict]:
    """Returns (clean_jpeg_bytes, checks). Raises ValueError if undecodable."""
    try:
        img = Image.open(io.BytesIO(body))
        img.load()
    except Exception as exc:
        raise ValueError(f"undecodable image: {exc}") from exc

    exif = img.getexif()
    had_exif = bool(exif)
    had_gps = bool(exif.get_ifd(GPS_IFD)) if had_exif else False

    flags: dict[str, str] = {}
    marker = _ai_marker(body, img)
    if marker:
        flags["ai_generator_metadata"] = f"strong: {marker}"
    if content_type == "image/jpeg" and not had_exif:
        flags["no_camera_metadata"] = (
            "weak: JPEG carries no EXIF; common for AI images, but also for "
            "screenshots and photos forwarded through WhatsApp"
        )
    width, height = img.size
    if width == height and width in GENERATOR_SQUARE_SIZES:
        flags["generator_typical_size"] = f"weak: exactly {width}x{height}, a common generator output size"

    # Apply the phone's orientation tag BEFORE dropping EXIF, or the stored
    # evidence ends up sideways.
    upright = ImageOps.exif_transpose(img).convert("RGB")
    upright.thumbnail((MAX_STORED_EDGE, MAX_STORED_EDGE))
    buf = io.BytesIO()
    upright.save(buf, format="JPEG", quality=STORED_JPEG_QUALITY)  # no exif= -> no metadata written

    checks = {
        "had_exif": had_exif,
        "had_gps": had_gps,  # a yes/no only - the coordinates themselves are never stored
        "content_credentials_present": b"c2pa" in body,  # C2PA manifest seen, signature NOT verified
        "flags": flags,
    }
    return buf.getvalue(), checks


def _fernet():
    key = os.environ.get("PHOTO_ENCRYPTION_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None
    return Fernet(key.encode())  # a malformed key raises here, loudly


def write_photo(path: Path, data: bytes) -> bool:
    """Writes data, encrypted if a key is configured. Returns whether it was."""
    fernet = _fernet()
    path.write_bytes(fernet.encrypt(data) if fernet else data)
    return fernet is not None


def read_photo(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(ENCRYPTED_PREFIX):
        return data
    fernet = _fernet()
    if fernet is None:
        raise ValueError("photo is encrypted but PHOTO_ENCRYPTION_KEY is not set (or cryptography is not installed)")
    from cryptography.fernet import InvalidToken

    try:
        return fernet.decrypt(data)
    except InvalidToken as exc:
        raise ValueError("photo could not be decrypted: PHOTO_ENCRYPTION_KEY differs from the key it was stored with") from exc
