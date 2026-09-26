import io

import pytest
from PIL import Image, PngImagePlugin

from app.nlp.photo_validate import (
    ENCRYPTED_PREFIX,
    process_upload,
    read_photo,
    write_photo,
)

GPS_IFD = 0x8825
ORIENTATION = 0x0112


def _jpeg_with_gps_and_rotation() -> bytes:
    img = Image.new("RGB", (200, 100), color=(120, 90, 60))
    exif = Image.Exif()
    exif[0x010F] = "TestMake"
    exif[0x0110] = "TestPhone"
    exif[ORIENTATION] = 6  # "rotate 90 CW to display" - what phones write
    gps = exif.get_ifd(GPS_IFD)
    gps[1] = "N"
    gps[2] = (18.0, 31.0, 12.0)
    gps[3] = "E"
    gps[4] = (73.0, 51.0, 24.0)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def test_gps_is_detected_then_stripped():
    raw = _jpeg_with_gps_and_rotation()
    assert Image.open(io.BytesIO(raw)).getexif().get_ifd(GPS_IFD)  # precondition

    clean, checks = process_upload(raw, "image/jpeg")

    assert checks["had_gps"] is True
    stored = Image.open(io.BytesIO(clean))
    assert not stored.getexif()  # no EXIF at all: no GPS, no make/model, no timestamps
    assert b"TestPhone" not in clean


def test_phone_rotation_is_applied_before_stripping():
    clean, _ = process_upload(_jpeg_with_gps_and_rotation(), "image/jpeg")
    # 200x100 with orientation 6 displays as 100x200; stored upright.
    assert Image.open(io.BytesIO(clean)).size == (100, 200)


def test_stable_diffusion_png_parameters_are_flagged():
    img = Image.new("RGB", (512, 512), color=(10, 200, 10))
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", "a pothole, photorealistic, Steps: 30, Sampler: Euler")
    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=info)

    clean, checks = process_upload(buf.getvalue(), "image/png")

    assert "ai_generator_metadata" in checks["flags"]
    assert b"photorealistic" not in clean  # the prompt text is stripped too


def test_iptc_trained_algorithmic_media_marker_is_flagged():
    img = Image.new("RGB", (300, 200), color=(50, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    # Generators (DALL-E, Imagen, Firefly) write this IPTC value into XMP.
    # Appended after the JPEG end marker so the image still decodes.
    raw = buf.getvalue() + b"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
    _, checks = process_upload(raw, "image/jpeg")
    assert "ai_generator_metadata" in checks["flags"]


def test_plain_camera_like_jpeg_has_no_strong_flags():
    _, checks = process_upload(_jpeg_with_gps_and_rotation(), "image/jpeg")
    assert "ai_generator_metadata" not in checks["flags"]


def test_all_uploads_are_stored_as_jpeg():
    img = Image.new("RGBA", (64, 64), color=(0, 0, 255, 128))
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    clean, _ = process_upload(buf.getvalue(), "image/webp")
    assert Image.open(io.BytesIO(clean)).format == "JPEG"


def test_undecodable_bytes_raise_value_error():
    with pytest.raises(ValueError):
        process_upload(b"not an image", "image/jpeg")


def test_encrypted_at_rest_when_key_set(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    from cryptography.fernet import Fernet

    monkeypatch.setenv("PHOTO_ENCRYPTION_KEY", Fernet.generate_key().decode())
    path = tmp_path / "x.jpg"
    encrypted = write_photo(path, b"\xff\xd8secret-pixels")

    assert encrypted is True
    on_disk = path.read_bytes()
    assert on_disk.startswith(ENCRYPTED_PREFIX)
    assert b"secret-pixels" not in on_disk
    assert read_photo(path) == b"\xff\xd8secret-pixels"


def test_plaintext_fallback_without_key_is_reported(tmp_path, monkeypatch):
    monkeypatch.delenv("PHOTO_ENCRYPTION_KEY", raising=False)
    path = tmp_path / "x.jpg"
    assert write_photo(path, b"\xff\xd8pixels") is False
    assert read_photo(path) == b"\xff\xd8pixels"


def test_legacy_plaintext_files_still_readable_with_key_set(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    from cryptography.fernet import Fernet

    monkeypatch.setenv("PHOTO_ENCRYPTION_KEY", Fernet.generate_key().decode())
    path = tmp_path / "old.jpg"
    path.write_bytes(b"\xff\xd8legacy")
    assert read_photo(path) == b"\xff\xd8legacy"


def test_encrypted_file_without_key_fails_loudly(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    from cryptography.fernet import Fernet

    monkeypatch.setenv("PHOTO_ENCRYPTION_KEY", Fernet.generate_key().decode())
    path = tmp_path / "x.jpg"
    write_photo(path, b"\xff\xd8pixels")
    monkeypatch.delenv("PHOTO_ENCRYPTION_KEY")
    with pytest.raises(ValueError):
        read_photo(path)
