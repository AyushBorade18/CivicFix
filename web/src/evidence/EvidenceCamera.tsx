import { useCallback, useEffect, useRef, useState } from "react";
import type { EvidencePackage } from "../api/client";
import "./camera.css";

// Shared by the citizen app (before photo) and the future worker app (after
// photo). Deliberately camera-only: there is no gallery or file picker here.
// Device location is read separately from the image and sent alongside it -
// EXIF is never relied on.

const POOR_ACCURACY_M = 100;
const FIX_MAX_AGE_MS = 30_000;
const LOCATION_WAIT_MS = 20_000;
const MAX_EDGE_PX = 1920;

type CameraError = "insecure" | "unsupported" | "denied" | "unavailable" | "busy" | "failed";
type LocationError = "denied" | "unavailable" | "timeout" | "unsupported";

interface Fix {
  lat: number;
  lon: number;
  accuracy: number;
  at: number; // position timestamp (device clock)
}

interface Captured {
  photo: Blob;
  previewUrl: string;
  capturedAt: string;
}

const CAMERA_MESSAGES: Record<CameraError, { title: string; body: string }> = {
  insecure: {
    title: "Secure connection required",
    body: "Browsers only allow the camera on a secure (https) page. Open WardSentry through its https address.",
  },
  unsupported: {
    title: "Camera not supported",
    body: "This browser can't open the camera. Try Chrome or Safari on your phone.",
  },
  denied: {
    title: "Camera permission required",
    body: "WardSentry needs camera access to capture evidence. Allow camera access in your browser's site settings, then try again.",
  },
  unavailable: {
    title: "No camera found",
    body: "We couldn't find a camera on this device.",
  },
  busy: {
    title: "Camera is in use",
    body: "Another app is using the camera. Close it and try again.",
  },
  failed: {
    title: "Camera didn't start",
    body: "Something went wrong opening the camera. Try again.",
  },
};

const LOCATION_MESSAGES: Record<LocationError, string> = {
  denied: "Location permission is off. Photo evidence needs your location - allow it in your browser's site settings and retry.",
  unavailable: "We couldn't obtain a reliable location. Move to open sky and retry, or continue without photo evidence.",
  timeout: "Getting your location is taking too long. Retry, or continue without photo evidence.",
  unsupported: "This browser can't share location, so the photo can't be attached as evidence.",
};

function cameraErrorFrom(err: unknown): CameraError {
  const name = err instanceof DOMException ? err.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return "denied";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "unavailable";
  if (name === "NotReadableError" || name === "AbortError") return "busy";
  return "failed";
}

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

export function EvidenceCamera({
  title,
  onCancel,
  onConfirm,
}: {
  title: string;
  onCancel: () => void;
  onConfirm: (pkg: EvidencePackage) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const watchRef = useRef<number | null>(null);
  const [cameraError, setCameraError] = useState<CameraError | null>(null);
  const [live, setLive] = useState(false);
  const [fix, setFix] = useState<Fix | null>(null);
  const [locationError, setLocationError] = useState<LocationError | null>(null);
  const [captured, setCaptured] = useState<Captured | null>(null);
  const [waitingForFix, setWaitingForFix] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  // Camera: rear camera preferred, no audio.
  useEffect(() => {
    let cancelled = false;
    setCameraError(null);
    setLive(false);
    if (!window.isSecureContext) {
      setCameraError("insecure");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("unsupported");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      })
      .then(async (stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const video = videoRef.current;
        if (video) {
          video.srcObject = stream;
          await video.play().catch(() => undefined);
        }
        setLive(true);
      })
      .catch((err) => {
        if (!cancelled) setCameraError(cameraErrorFrom(err));
      });
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
  }, [attempt]);

  // The viewfinder only exists while no photo is held, so re-attach the
  // stream when returning from the preview (retake).
  useEffect(() => {
    const video = videoRef.current;
    if (!captured && live && video && streamRef.current && video.srcObject !== streamRef.current) {
      video.srcObject = streamRef.current;
      video.play().catch(() => undefined);
    }
  }, [captured, live]);

  // Location: asked for only once the camera is live, so the user meets one
  // permission prompt at a time. Keeps the freshest usable reading.
  const startLocation = useCallback(() => {
    if (watchRef.current !== null) navigator.geolocation.clearWatch(watchRef.current);
    setLocationError(null);
    if (!("geolocation" in navigator)) {
      setLocationError("unsupported");
      return;
    }
    watchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setLocationError(null);
        setFix((prev) => {
          const next = { lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: pos.coords.accuracy, at: pos.timestamp };
          // Keep a better reading unless it has gone stale.
          if (prev && prev.accuracy < next.accuracy && next.at - prev.at < 10_000) return prev;
          return next;
        });
      },
      (err) => {
        setLocationError(
          err.code === err.PERMISSION_DENIED ? "denied" : err.code === err.TIMEOUT ? "timeout" : "unavailable",
        );
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout: LOCATION_WAIT_MS },
    );
  }, []);

  useEffect(() => {
    if (live) startLocation();
  }, [live, startLocation]);

  useEffect(
    () => () => {
      if (watchRef.current !== null) navigator.geolocation.clearWatch(watchRef.current);
    },
    [],
  );

  // Re-evaluates fix freshness while the dialog is open.
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 2000);
    return () => window.clearInterval(timer);
  }, []);

  const usableFix = fix && now - fix.at < FIX_MAX_AGE_MS ? fix : null;

  // A capture taken before a usable fix waits here, with a hard stop so it
  // can never spin forever.
  useEffect(() => {
    if (!waitingForFix) return;
    if (usableFix || locationError) {
      setWaitingForFix(false);
      return;
    }
    const timer = window.setTimeout(() => {
      setWaitingForFix(false);
      setLocationError("timeout");
    }, LOCATION_WAIT_MS);
    return () => window.clearTimeout(timer);
  }, [waitingForFix, usableFix, locationError]);

  useEffect(
    () => () => {
      if (captured) URL.revokeObjectURL(captured.previewUrl);
    },
    [captured],
  );

  function capture() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const scale = Math.min(1, MAX_EDGE_PX / Math.max(video.videoWidth, video.videoHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d")!.drawImage(video, 0, 0, canvas.width, canvas.height);
    const capturedAt = new Date().toISOString();
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setCameraError("failed");
          return;
        }
        setCaptured({ photo: blob, previewUrl: URL.createObjectURL(blob), capturedAt });
        if (!usableFix) setWaitingForFix(true);
      },
      "image/jpeg",
      0.85,
    );
  }

  function retryLocation() {
    setFix(null);
    startLocation();
    if (captured) setWaitingForFix(true);
  }

  function confirm() {
    if (!captured || !usableFix) return;
    onConfirm({
      clientSubmissionId: crypto.randomUUID(),
      photo: captured.photo,
      latitude: usableFix.lat,
      longitude: usableFix.lon,
      accuracyM: usableFix.accuracy,
      capturedAt: captured.capturedAt,
      locationCapturedAt: new Date(usableFix.at).toISOString(),
    });
  }

  const cameraMessage = cameraError ? CAMERA_MESSAGES[cameraError] : null;

  return (
    <div className="ev-cam" role="dialog" aria-modal="true" aria-label={title}>
      <header className="ev-cam__bar">
        <button type="button" className="ev-cam__textbtn" onClick={onCancel}>
          Cancel
        </button>
        <span className="ev-cam__title">{title}</span>
        <span className="ev-cam__spacer" />
      </header>

      {cameraMessage ? (
        <div className="ev-cam__message" role="alert">
          <h2>{cameraMessage.title}</h2>
          <p>{cameraMessage.body}</p>
          <div className="ev-cam__actions">
            {cameraError !== "insecure" && cameraError !== "unsupported" && (
              <button type="button" className="ev-cam__btn ev-cam__btn--primary" onClick={() => setAttempt((a) => a + 1)}>
                Try again
              </button>
            )}
            <button type="button" className="ev-cam__btn" onClick={onCancel}>
              Continue without photo
            </button>
          </div>
        </div>
      ) : captured ? (
        <div className="ev-cam__preview">
          <img src={captured.previewUrl} alt="Captured evidence" className="ev-cam__photo" />
          <ul className="ev-cam__facts" aria-live="polite">
            <li className="ev-cam__fact ev-cam__fact--ok">Photo captured</li>
            {usableFix ? (
              <li className={`ev-cam__fact ${usableFix.accuracy > POOR_ACCURACY_M ? "ev-cam__fact--warn" : "ev-cam__fact--ok"}`}>
                Location captured
                <span className="ev-cam__detail">{formatCoord(usableFix.lat, usableFix.lon)}</span>
                <span className="ev-cam__detail">Accuracy: {formatAccuracy(usableFix.accuracy)}</span>
                {usableFix.accuracy > POOR_ACCURACY_M && (
                  <span className="ev-cam__detail">Low accuracy. If you can, step into open sky and retake.</span>
                )}
              </li>
            ) : waitingForFix ? (
              <li className="ev-cam__fact ev-cam__fact--pending">Getting your location…</li>
            ) : (
              <li className="ev-cam__fact ev-cam__fact--error">
                Location not captured
                <span className="ev-cam__detail">{LOCATION_MESSAGES[locationError ?? "unavailable"]}</span>
              </li>
            )}
            <li className="ev-cam__fact ev-cam__fact--ok">
              Capture time recorded
              <span className="ev-cam__detail">{formatTime(captured.capturedAt)}</span>
            </li>
          </ul>
          <div className="ev-cam__actions">
            <button type="button" className="ev-cam__btn" onClick={() => setCaptured(null)}>
              Retake
            </button>
            {usableFix ? (
              <button type="button" className="ev-cam__btn ev-cam__btn--primary" onClick={confirm}>
                Use photo
              </button>
            ) : (
              !waitingForFix && (
                <button type="button" className="ev-cam__btn ev-cam__btn--primary" onClick={retryLocation}>
                  Retry location
                </button>
              )
            )}
          </div>
        </div>
      ) : (
        <div className="ev-cam__viewfinder">
          <video ref={videoRef} className="ev-cam__video" playsInline muted autoPlay />
          {!live && (
            <div className="ev-cam__overlay">
              <p>Opening camera…</p>
              <p className="ev-cam__privacy">
                Your camera is used to capture evidence of the reported issue. Your location is used to associate the
                evidence with the reported site.
              </p>
            </div>
          )}
          <div className="ev-cam__status" aria-live="polite">
            {locationError
              ? LOCATION_MESSAGES[locationError]
              : usableFix
                ? `Location ready · ${formatAccuracy(usableFix.accuracy)}`
                : live
                  ? "Finding your location…"
                  : ""}
          </div>
          <div className="ev-cam__shutterbar">
            <button type="button" className="ev-cam__shutter" onClick={capture} disabled={!live} aria-label="Capture photo" />
          </div>
        </div>
      )}
    </div>
  );
}
