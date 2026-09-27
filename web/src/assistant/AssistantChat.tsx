import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { ChatAction } from "../api/types";
import { Icon } from "../admin/components/ws";
import { SignIn } from "../components/SignIn";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { useSignedIn } from "../lib/auth";
import { CardView } from "./cards";
import { PinPicker } from "./PinPicker";
import { RETRY, useAssistant, type Surface } from "./useAssistant";

const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_PHOTO_BYTES = 20 * 1024 * 1024; // same limit as POST /api/uploads/photo
const SPEECH_LANG: Record<string, string> = { hi: "hi-IN", mr: "mr-IN" };

export function AssistantChat({ surface, variant, onClose }: {
  surface: Surface;
  variant: "floating" | "page";
  onClose?: () => void;
}) {
  const { messages, busy, send, retry, reset, lang } = useAssistant(surface);
  const [draft, setDraft] = useState("");
  const [pinOpen, setPinOpen] = useState(false);
  const [signInFor, setSignInFor] = useState<string | null>(null); // action to resume after sign-in
  const [notice, setNotice] = useState<string | null>(null);
  const signedIn = useSignedIn();
  const navigate = useNavigate();
  const fileInput = useRef<HTMLInputElement>(null);
  const logEnd = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const speech = useSpeechRecognition(SPEECH_LANG[lang] ?? "en-IN", (said) =>
    setDraft((prev) => (prev.trim() ? `${prev.trim()} ${said.trim()}` : said.trim())));

  useEffect(() => {
    if (!started.current && messages.length === 0) {
      started.current = true; // StrictMode runs effects twice in dev
      void send({ action: "start" });
    }
  }, [messages.length, send]);

  useEffect(() => {
    logEnd.current?.scrollIntoView({ block: "end" });
  }, [messages.length, busy]);

  // Signed in from the inline form: carry on where the citizen was.
  useEffect(() => {
    if (signedIn && signInFor) {
      const action = signInFor;
      setSignInFor(null);
      void send({ action });
    }
  }, [signedIn, signInFor, send]);

  async function submitText() {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    const ok = await send({ message: text }, text);
    if (!ok) setDraft(text); // nothing typed is lost
  }

  function shareLocation() {
    if (!("geolocation" in navigator)) {
      setNotice("This browser can't share a location. Drop a pin or type a landmark instead.");
      return;
    }
    setNotice("Getting your location…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setNotice(null);
        void send({ action: "location", value: "gps", latitude: pos.coords.latitude, longitude: pos.coords.longitude },
          "My current location");
      },
      () => setNotice("Couldn't get your location. Drop a pin or type a nearby landmark instead."),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  }

  async function attachPhoto(file: File | undefined) {
    if (!file) return;
    if (!PHOTO_TYPES.includes(file.type)) {
      setNotice("Please choose a JPEG, PNG or WebP photo.");
      return;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      setNotice("That photo is larger than 20 MB. Please choose a smaller one.");
      return;
    }
    setNotice("Uploading photo…");
    try {
      const { photo_url } = await api.uploadPhoto(file);
      setNotice(null);
      await send({ action: "photo", photo_url }, "Photo", URL.createObjectURL(file));
    } catch (err) {
      setNotice(err instanceof ApiError && (err.status === 401 || err.status === 403)
        ? "Please sign in to attach a photo."
        : "The photo couldn't be uploaded. Your report is still here; try again or skip the photo.");
    }
  }

  function runAction(a: ChatAction) {
    if (busy) return;
    setNotice(null);
    if (a.action === RETRY) return retry();
    switch (a.kind) {
      case "link":
        if (a.href) navigate(a.href);
        if (variant === "floating" && window.innerWidth < 640) onClose?.();
        return;
      case "location":
        return shareLocation();
      case "pin":
        return setPinOpen(true);
      case "photo":
        return fileInput.current?.click();
      case "sign_in":
        if (signedIn) return void send({ action: a.action ?? "start" });
        return setSignInFor(a.action ?? "start");
      default:
        void send({ action: a.action ?? "menu", value: a.value }, a.label);
    }
  }

  const last = messages[messages.length - 1];

  return (
    <div className={`cfa-chat cfa-chat--${variant}`}>
      <header className="cfa-head">
        <div className="cfa-head__mark" aria-hidden="true"><Icon name="forum" /></div>
        <div className="cfa-head__titles">
          <h2>CivicFix Assistant</h2>
          <p>{surface === "admin" ? "Your ward's issues, explained from the records." : "Your civic issue, understood."}</p>
        </div>
        <div className="cfa-head__tools">
          <button type="button" className="cfa-icon-btn" onClick={reset} disabled={busy} title="New conversation" aria-label="New conversation">
            <Icon name="restart_alt" />
          </button>
          {variant === "floating" && surface === "citizen" && (
            <Link to="/citizen/assistant" className="cfa-icon-btn" title="Open full page" aria-label="Open full page" onClick={onClose}>
              <Icon name="open_in_full" />
            </Link>
          )}
          {onClose && (
            <button type="button" className="cfa-icon-btn" onClick={onClose} title="Close" aria-label="Close assistant">
              <Icon name="close" />
            </button>
          )}
        </div>
      </header>

      <div className="cfa-log" role="log" aria-live="polite" aria-busy={busy}>
        {messages.map((m) => (
          <div key={m.id} className={`cfa-msg cfa-msg--${m.role}${m.failed ? " cfa-msg--failed" : ""}`}>
            {m.photo && <img src={m.photo} alt="Your photo, attached as evidence" className="cfa-msg__photo" />}
            {m.text && m.text.split("\n\n").map((p, i) => <p key={i}>{p}</p>)}
            {m.cards?.map((c, i) => (
              <CardView key={i} card={c} disabled={busy || m !== last}
                onItem={(action, value, label) => void send({ action, value }, label)} />
            ))}
            {m === last && m.actions && m.actions.length > 0 && (
              <div className="cfa-actions">
                {m.actions.map((a, i) => (
                  <button key={i} type="button" disabled={busy} onClick={() => runAction(a)}
                    className={`cfa-chip${a.kind !== "reply" ? " cfa-chip--tool" : ""}`}>
                    {a.kind === "location" && <Icon name="my_location" className="cfa-inline-icon" />}
                    {a.kind === "pin" && <Icon name="pin_drop" className="cfa-inline-icon" />}
                    {a.kind === "photo" && <Icon name="photo_camera" className="cfa-inline-icon" />}
                    {a.kind === "link" && <Icon name="open_in_new" className="cfa-inline-icon" />}
                    {a.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="cfa-msg cfa-msg--assistant cfa-working">Checking CivicFix records…</div>}
        {signInFor && !signedIn && (
          <div className="cfa-signin">
            <SignIn title="Sign in to continue" blurb="Your report is linked to your account so you can follow it. Your name is never shown publicly." />
            <button type="button" className="cfa-chip" onClick={() => setSignInFor(null)}>Not now</button>
          </div>
        )}
        <div ref={logEnd} />
      </div>

      {notice && <p className="cfa-notice" role="status">{notice}</p>}

      <form className="cfa-composer" onSubmit={(e) => { e.preventDefault(); void submitText(); }}>
        {surface === "citizen" && (
          <>
            <button type="button" className="cfa-icon-btn" onClick={() => fileInput.current?.click()} disabled={busy}
              title="Attach a photo" aria-label="Attach a photo"><Icon name="photo_camera" /></button>
            <button type="button" className="cfa-icon-btn" onClick={shareLocation} disabled={busy}
              title="Share my location" aria-label="Share my location"><Icon name="my_location" /></button>
          </>
        )}
        <label htmlFor={`cfa-input-${variant}`} className="cfa-sr">Message</label>
        <textarea id={`cfa-input-${variant}`} rows={1} value={speech.listening ? speech.interimTranscript || draft : draft}
          onChange={(e) => setDraft(e.target.value)} maxLength={1000}
          placeholder={surface === "admin" ? "Ask about an issue, e.g. why #PMC-12" : "Describe the problem, in any language…"}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void submitText(); } }} />
        {surface === "citizen" && speech.supported && (
          <button type="button" className={`cfa-icon-btn${speech.listening ? " cfa-icon-btn--on" : ""}`}
            onClick={speech.listening ? speech.stop : speech.start} disabled={busy}
            title={speech.listening ? "Stop listening" : "Speak instead"} aria-label={speech.listening ? "Stop listening" : "Speak instead"}>
            <Icon name={speech.listening ? "stop_circle" : "mic"} />
          </button>
        )}
        <button type="submit" className="cfa-send" disabled={busy || !draft.trim()} aria-label="Send"><Icon name="send" /></button>
        <input ref={fileInput} type="file" accept={PHOTO_TYPES.join(",")} capture="environment" hidden
          onChange={(e) => { void attachPhoto(e.target.files?.[0]); e.target.value = ""; }} />
      </form>
      <p className="cfa-principle">AI understands · Evidence supports · Rules explain · Humans decide</p>

      {pinOpen && (
        <PinPicker onCancel={() => setPinOpen(false)} onConfirm={([latitude, longitude]) => {
          setPinOpen(false);
          void send({ action: "location", value: "pin", latitude, longitude }, "Pin dropped on the map");
        }} />
      )}
    </div>
  );
}
