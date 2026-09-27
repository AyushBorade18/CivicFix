import { useEffect, useState } from "react";
import type { EvidencePackage } from "../api/client";
import "./camera.css";

// Evidence photo picked from a file on this device (no live camera). The
// location sent with it is this device's location at upload time - not where
// the photo was taken - and the package is marked capture_method "upload" so
// reviewers never read it as an on-site capture. The image is re-encoded
// before upload: downscaled, and any metadata inside the file is dropped.

const POOR_ACCURACY_M = 100;
const MAX_EDGE_PX = 1920;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

type LocationError = "denied" | "unavailable" | "timeout" | "unsupported";

interface Fix {
  lat: number;
  lon: number;
  accuracy: number;
  at: number;
}

interface Picked {
  photo: Blob;
  previewUrl: string;
  pickedAt: string;
}

const LOCATION_MESSAGES: Record<LocationError, string> = {
  denied: "Location permission is off. The photo needs this device's location - allow it in your browser's site settings and retry.",
  unavailable: "We couldn't get this device's location. Retry, or continue without a photo.",
  timeout: "Getting this device's location is taking too long. Retry, or continue without a photo.",
  unsupported: "This browser can't share location, so the photo can't be attached as evidence.",
};

export function formatAccuracy(m: number): string {
  return m < 1000 ? `approximately ${Math.round(m)} m` : `approximately ${(m / 1000).toFixed(1)} km`;
}

export function formatCoord(lat: number, lon: number): string {
  return `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

/** Downscale to MAX_EDGE_PX and re-encode as JPEG. */
async function reencode(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_EDGE_PX / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("encode failed"))), "image/jpeg", 0.85));
}

export function EvidenceUpload({
  title,
  onCancel,
  onConfirm,
}: {
  title: string;
  onCancel: () => void;
  onConfirm: (pkg: EvidencePackage) => void;
}) {
  const [picked, setPicked] = useState<Picked | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [fix, setFix] = useState<Fix | null>(null);
  const [locationError, setLocationError] = useState<LocationError | null>(null);
  const [locating, setLocating] = useState(false);

  function locate() {
    setLocationError(null);
    if (!("geolocation" in navigator)) {
      setLocationError("unsupported");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        setFix({ lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: pos.coords.accuracy, at: pos.timestamp });
      },
      (err) => {
        setLocating(false);
        setLocationError(err.code === err.PERMISSION_DENIED ? "denied" : err.code === err.TIMEOUT ? "timeout" : "unavailable");
      },
      { enableHighAccuracy: true, maximumAge: 60_000, timeout: 20_000 },
    );
  }

  useEffect(locate, []);

  useEffect(
    () => () => {
      if (picked) URL.revokeObjectURL(picked.previewUrl);
    },
    [picked],
  );

  async function onFile(file: File | undefined) {
    setFileError(null);
    if (!file) return;
    if (!ACCEPTED.includes(file.type)) {
      setFileError("Choose a JPEG, PNG or WebP image.");
      return;
    }
    try {
      const photo = await reencode(file);
      setPicked({ photo, previewUrl: URL.createObjectURL(photo), pickedAt: new Date().toISOString() });
    } catch {
      setFileError("We couldn't read that image. Try another file.");
    }
  }

  function confirm() {
    if (!picked || !fix) return;
    onConfirm({
      clientSubmissionId: crypto.randomUUID(),
      photo: picked.photo,
      latitude: fix.lat,
      longitude: fix.lon,
      accuracyM: fix.accuracy,
      capturedAt: picked.pickedAt,
      locationCapturedAt: new Date(fix.at).toISOString(),
      captureMethod: "upload",
    });
  }

  const locationFact = fix ? (
    <li className={`ev-cam__fact ${fix.accuracy > POOR_ACCURACY_M ? "ev-cam__fact--warn" : "ev-cam__fact--ok"}`}>
      Location added (this device, now)
      <span className="ev-cam__detail">{formatCoord(fix.lat, fix.lon)}</span>
      <span className="ev-cam__detail">Accuracy: {formatAccuracy(fix.accuracy)}</span>
    </li>
  ) : locating ? (
    <li className="ev-cam__fact ev-cam__fact--pending">Getting this device's location…</li>
  ) : (
    <li className="ev-cam__fact ev-cam__fact--error">
      Location not added
      <span className="ev-cam__detail">{LOCATION_MESSAGES[locationError ?? "unavailable"]}</span>
    </li>
  );

  return (
    <div className="ev-cam" role="dialog" aria-modal="true" aria-label={title}>
      <header className="ev-cam__bar">
        <button type="button" className="ev-cam__textbtn" onClick={onCancel}>
          Cancel
        </button>
        <span className="ev-cam__title">{title}</span>
        <span className="ev-cam__spacer" />
      </header>

      <div className="ev-cam__preview">
        {picked ? (
          <img src={picked.previewUrl} alt="Selected evidence" className="ev-cam__photo" />
        ) : (
          <label className="ev-cam__message" style={{ cursor: "pointer" }}>
            <h2>Upload a photo of the problem</h2>
            <p>JPEG, PNG or WebP from this device.</p>
            <span className="ev-cam__btn ev-cam__btn--primary">Choose file</span>
            <input type="file" accept={ACCEPTED.join(",")} hidden onChange={(e) => onFile(e.target.files?.[0])} />
          </label>
        )}
        {fileError && <p className="ev-cam__detail" role="alert">{fileError}</p>}

        <ul className="ev-cam__facts" aria-live="polite">
          {picked && <li className="ev-cam__fact ev-cam__fact--ok">Photo selected</li>}
          {locationFact}
        </ul>

        <div className="ev-cam__actions">
          {picked && (
            <label className="ev-cam__btn" style={{ cursor: "pointer" }}>
              Choose another
              <input type="file" accept={ACCEPTED.join(",")} hidden onChange={(e) => onFile(e.target.files?.[0])} />
            </label>
          )}
          {!fix && !locating && (
            <button type="button" className="ev-cam__btn" onClick={locate}>
              Retry location
            </button>
          )}
          <button type="button" className="ev-cam__btn ev-cam__btn--primary" onClick={confirm} disabled={!picked || !fix}>
            Use photo
          </button>
        </div>
      </div>
    </div>
  );
}
