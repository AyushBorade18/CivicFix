import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { GeoJSON, MapContainer, TileLayer, CircleMarker, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api, ApiError, mediaUrl, type EvidencePackage } from "../../api/client";
import { useSignedIn } from "../../lib/auth";
import { SignIn } from "../../components/SignIn";
import { EvidenceCamera, formatTime } from "../../evidence/EvidenceCamera";
import { captureAndUpload, type UploadResult } from "../../evidence/pendingUploads";
import { useApi } from "../../hooks/useApi";
import { useSpeechRecognition } from "../../hooks/useSpeechRecognition";
import { CATEGORY_LABELS } from "../../api/types";
import type { MapWard, ReportCreateResponse } from "../../api/types";
import { Icon } from "../../admin/components/ws";
import { Kicker, SplitCTA } from "../Shell";

// Report page, ported from the Stitch export
// stitch_wardsentry_citizen_portal/report_an_issue_wardsentry.

const VOICE_LANGUAGES = [
  { code: "en-IN", label: "English" },
  { code: "hi-IN", label: "हिंदी (Hindi)" },
  { code: "mr-IN", label: "मराठी (Marathi)" },
];
const CHIPS = ["pothole_road", "streetlight", "water_supply", "drainage_sewage", "garbage_waste", "footpath", "traffic_signage"];
const DRAFT_KEY = "ws-report-draft";
const PUNE: [number, number] = [18.5204, 73.8567];

type Draft = { text: string; wardId: string; landmark: string; chip: string };

function loadDraft(): Draft | null {
  try { return JSON.parse(localStorage.getItem(DRAFT_KEY) ?? "null"); } catch { return null; }
}

function severityMessage(severity: string): string {
  if (severity === "critical") return "This looks serious - it has been marked urgent for your ward team.";
  if (severity === "moderate") return "Your ward team will attend to this soon.";
  return "Your ward team has been told.";
}

const input = "w-full h-12 px-3 border border-se-outline-variant bg-se-lowest font-se-sans text-se-body text-se-on focus:outline-none focus:border-se-primary";
const label = "block font-se-code text-se-caps uppercase tracking-widest text-se-variant mb-2";

export function ReportIssue() {
  const signedIn = useSignedIn();
  const { data: mapData } = useApi(() => api.publicMap(), []);
  const { data: stats } = useApi(() => api.stats(), []);
  const draft = useMemo(loadDraft, []);
  const [chip, setChip] = useState(draft?.chip ?? "");
  const [text, setText] = useState(draft?.text ?? "");
  const [wardId, setWardId] = useState<string>(draft?.wardId ?? "");
  const [landmark, setLandmark] = useState(draft?.landmark ?? "");
  const [tipOpen, setTipOpen] = useState(true);
  const [draftSaved, setDraftSaved] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [evidence, setEvidence] = useState<EvidencePackage | null>(null);
  const [evidencePreview, setEvidencePreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReportCreateResponse | null>(null);
  const [evidenceResult, setEvidenceResult] = useState<UploadResult | null>(null);
  const [voiceLang, setVoiceLang] = useState(VOICE_LANGUAGES[0].code);
  const speech = useSpeechRecognition(voiceLang, (finalText) => {
    setText((prev) => (prev.trim() ? `${prev.trim()} ${finalText.trim()}` : finalText.trim()));
  });

  const issues = mapData?.issues ?? [];
  const open = issues.filter((i) => i.status !== "closed").length;
  const ward = mapData?.wards.find((w) => String(w.ward_id) === wardId) ?? null;

  function keepCapture(pkg: EvidencePackage) {
    if (evidencePreview) URL.revokeObjectURL(evidencePreview);
    setEvidence(pkg);
    setEvidencePreview(URL.createObjectURL(pkg.photo));
    setCameraOpen(false);
  }

  function removeCapture() {
    if (evidencePreview) URL.revokeObjectURL(evidencePreview);
    setEvidence(null);
    setEvidencePreview(null);
  }

  function saveDraft() {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ text, wardId, landmark, chip } satisfies Draft));
      setDraftSaved(true);
    } catch { /* storage blocked: nothing to save to */ }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSubmitting(true);
    setError(null);
    // The citizen's own words, prefixed with the kind of problem they picked
    // (unless they already said it) and followed by their landmark.
    const kind = chip ? CATEGORY_LABELS[chip] : "";
    const saidKind = kind && text.toLowerCase().includes(kind.split(" ")[0].toLowerCase());
    const parts = [kind && !saidKind ? `${kind}:` : "", text.trim(), landmark.trim() ? `Near ${landmark.trim()}.` : ""];
    try {
      const response = await api.createReport({
        raw_text: parts.filter(Boolean).join(" "),
        ward_id: wardId ? Number(wardId) : null,
      });
      // The report is saved at this point; the photo follows as its own
      // request and survives a network drop (kept on the device for retry).
      setEvidenceResult(evidence ? await captureAndUpload(response.issue_id, evidence, response.report.id) : null);
      try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
      setResult(response);
      window.scrollTo(0, 0);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setError("Please sign in to send a report.");
      } else if (!navigator.onLine) {
        setError("You're offline. Your report hasn't been sent yet - reconnect and send again. Nothing you entered is lost.");
      } else {
        setError(err instanceof ApiError ? err.message : "Something went wrong sending your report. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const hero = (
    <section className="w-full bg-se-surface px-5 md:px-12 pt-10 pb-12">
      <h1 className="font-se-sans text-[40px] leading-[46px] md:text-se-xl text-se-on tracking-tight">Report a Problem in Your Ward</h1>
      <p className="mt-4 max-w-2xl font-se-sans text-se-body-xl text-se-variant">
        Goes straight to your ward’s team. Add a photo from the spot and follow it until it’s fixed.
      </p>
    </section>
  );

  if (result) {
    return (
      <ReportResult result={result} evidenceResult={evidenceResult}
        onReportAnother={() => { setResult(null); setEvidenceResult(null); setText(""); setLandmark(""); setChip(""); removeCapture(); }} />
    );
  }

  if (!signedIn) {
    return (
      <>
        {hero}
        <section className="bg-se-lowest border-t border-se-outline-variant/40 px-5 md:px-12 py-12">
          <SignIn title="Sign in to report a problem" blurb="Your reports are linked to your account so you can add a photo later, follow progress and confirm the fix. Your name is never shown publicly." />
        </section>
      </>
    );
  }

  return (
    <>
      {hero}

      {/* Category rail */}
      <section className="w-full bg-se-lowest border-y border-se-outline-variant/40 px-5 md:px-12 py-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-1 overflow-x-auto [scrollbar-width:none] font-se-code text-se-code whitespace-nowrap">
          {CHIPS.map((c) => (
            <button key={c} type="button" onClick={() => setChip(chip === c ? "" : c)}
              className={`px-4 py-2 transition-colors ${chip === c ? "bg-se-primary text-white" : "bg-se-container text-se-on hover:bg-se-high"}`}>
              {CATEGORY_LABELS[c]}
            </button>
          ))}
        </div>
        {speech.supported && (
          <button type="button" onClick={speech.listening ? speech.stop : speech.start}
            className={`shrink-0 hidden sm:flex items-center gap-1 px-3 py-2 border font-se-code text-se-caps uppercase tracking-wider transition-colors ${speech.listening ? "bg-se-primary text-white border-se-primary" : "border-se-outline-variant hover:border-se-primary"}`}>
            <Icon name={speech.listening ? "stop_circle" : "mic"} className="text-[16px]" /> {speech.listening ? "Listening… tap to stop" : "Speak instead"}
          </button>
        )}
      </section>
      {tipOpen && (
        <div className="w-full bg-se-container px-5 md:px-12 py-2 flex items-center justify-between gap-4 font-se-code text-se-code text-se-variant">
          <span className="flex items-center gap-2"><Icon name="graphic_eq" className="text-[16px]" />Tip: pick the kind of problem, tell us where it is, and add a photo if you can.</span>
          <button type="button" onClick={() => setTipOpen(false)} className="hover:text-se-on shrink-0">Dismiss</button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="w-full bg-se-surface px-5 md:px-12 py-12 grid grid-cols-1 lg:grid-cols-12 gap-12">
        {/* Left column */}
        <div className="lg:col-span-7 space-y-12">
          <div>
            <PhaseHead n="01" title="The problem" right="Required" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <div>
                <span className={label}>Kind of problem</span>
                <div className="h-12 px-3 flex items-center bg-se-high border border-se-outline-variant font-se-sans text-se-body">
                  {chip ? CATEGORY_LABELS[chip] : <span className="text-se-variant">Pick one above, or just describe it</span>}
                </div>
              </div>
              <div>
                <label htmlFor="voice-lang" className={label}>Language you’ll speak</label>
                <select id="voice-lang" value={voiceLang} onChange={(e) => setVoiceLang(e.target.value)} disabled={speech.listening} className={input}>
                  {VOICE_LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
                </select>
              </div>
            </div>
            <label htmlFor="raw_text" className={label}>Describe the problem</label>
            <textarea id="raw_text" rows={4} required minLength={10} value={text} onChange={(e) => setText(e.target.value)}
              placeholder="e.g. Big pothole outside the school gate, bikes are slipping, water collects when it rains…"
              className="w-full p-3 border border-se-outline-variant bg-se-lowest font-se-sans text-se-body text-se-on focus:outline-none focus:border-se-primary" />
            <div className="flex flex-wrap items-center gap-3 mt-2 font-se-code text-se-code text-se-variant">
              {speech.supported && (
                <button type="button" onClick={speech.listening ? speech.stop : speech.start}
                  className="sm:hidden flex items-center gap-1 px-3 py-1.5 border border-se-outline-variant uppercase">
                  <Icon name={speech.listening ? "stop_circle" : "mic"} className="text-[16px]" /> {speech.listening ? "Stop" : "Speak instead"}
                </button>
              )}
              {speech.listening && <span>{speech.interimTranscript || "Listening…"}</span>}
              {speech.error && <span className="text-red-700">{speech.error}</span>}
              {!speech.listening && !speech.error && <span>At least 10 characters</span>}
            </div>
          </div>

          <div>
            <PhaseHead n="02" title="Photo from the spot" right="Recommended" />
            <div className="relative w-full aspect-video bg-se-primary-container overflow-hidden">
              {evidence && evidencePreview ? (
                <img src={evidencePreview} alt="Your photo of the problem" className="absolute inset-0 w-full h-full object-cover" />
              ) : (
                <div className="absolute inset-0 bg-cover bg-center opacity-25 grayscale" style={{ backgroundImage: "url(/media/how-it-works.jpg)" }} />
              )}
              <span className="absolute top-3 left-3 px-2 py-1 bg-black/70 text-white font-se-code text-se-caps uppercase flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${evidence ? "bg-emerald-400" : "bg-red-500 animate-pulse"}`} />
                {evidence ? "Photo added" : "Camera"}
              </span>
              {evidence && (
                <span className="absolute top-3 right-3 px-2 py-1 bg-black/70 text-white font-se-code text-se-caps uppercase">
                  {formatTime(evidence.capturedAt)} · Location added
                </span>
              )}
              {!evidence && (
                <div className="absolute left-1/2 top-[42%] -translate-x-1/2 -translate-y-1/2 w-28 h-24">
                  <span className="absolute top-0 left-0 w-5 h-5 border-t-2 border-l-2 border-white/70" />
                  <span className="absolute top-0 right-0 w-5 h-5 border-t-2 border-r-2 border-white/70" />
                  <span className="absolute bottom-0 left-0 w-5 h-5 border-b-2 border-l-2 border-white/70" />
                  <span className="absolute bottom-0 right-0 w-5 h-5 border-b-2 border-r-2 border-white/70" />
                  <Icon name="location_on" className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-white/80 text-[22px]" />
                </div>
              )}
              <div className="absolute bottom-0 inset-x-0 p-3 flex items-end justify-between gap-3 bg-gradient-to-t from-black/80 to-transparent">
                <p className="text-white font-se-sans text-se-sm max-w-xs">
                  {evidence ? "This photo will be sent with your report." : "Take a photo right where the problem is. Optional — you can add one later."}
                </p>
                <div className="flex gap-1 shrink-0">
                  <button type="button" onClick={() => setCameraOpen(true)} className="px-3 py-2 bg-white text-se-on font-se-code text-se-caps uppercase flex items-center gap-1">
                    <Icon name="photo_camera" className="text-[16px]" /> {evidence ? "Retake" : "Open camera"}
                  </button>
                  {evidence && (
                    <button type="button" onClick={removeCapture} className="px-3 py-2 border border-white/60 text-white font-se-code text-se-caps uppercase">Remove</button>
                  )}
                </div>
              </div>
            </div>
            <div className="mt-2 p-3 bg-se-container flex items-start gap-2 font-se-sans text-se-sm text-se-variant">
              <Icon name="verified_user" className="text-[18px] shrink-0" />
              Only live photos are accepted — the time and place are recorded so your ward officer can trust it.
            </div>
          </div>
        </div>

        {/* Right column */}
        <div className="lg:col-span-5 space-y-12">
          <div>
            <PhaseHead n="03" title="Where is it" right="Pune wards" />
            <label htmlFor="ward" className={label}>Your ward</label>
            <select id="ward" value={wardId} onChange={(e) => setWardId(e.target.value)} className={`${input} mb-4`}>
              <option value="">Not sure — find it for me</option>
              {mapData?.wards.map((w) => <option key={w.ward_id} value={w.ward_id}>{w.name} (Ward {w.ward_id})</option>)}
            </select>
            <label htmlFor="landmark" className={label}>Street or nearby landmark</label>
            <input id="landmark" value={landmark} onChange={(e) => setLandmark(e.target.value)} className={`${input} mb-4`}
              placeholder="e.g. Opposite Balgandharva Rangmandir, JM Road" />
            <div className="relative h-56 border border-se-outline-variant bg-se-high">
              <MapContainer center={PUNE} zoom={11} zoomControl={false} scrollWheelZoom={false} attributionControl={false} style={{ height: "100%", background: "#e8e8e9" }}>
                <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
                {ward && <WardFocus ward={ward} />}
                {evidence && <CircleMarker center={[evidence.latitude, evidence.longitude]} radius={7} pathOptions={{ color: "#fff", weight: 2, fillColor: "#000", fillOpacity: 1 }} />}
              </MapContainer>
              <span className="absolute bottom-2 left-2 z-[500] px-2 py-1 bg-se-primary text-white font-se-code text-[10px] uppercase tracking-wider">
                {ward ? `Ward ${ward.ward_id} // ${ward.name.split(" - ")[0]}` : "Pune // ward found from your description"}
              </span>
              {evidence && <span className="absolute top-2 right-2 z-[500] px-2 py-1 bg-se-lowest border border-se-outline-variant font-se-code text-[10px] uppercase flex items-center gap-1"><Icon name="my_location" className="text-[14px]" />Photo location</span>}
            </div>
          </div>

          <div>
            <PhaseHead n="04" title="Updates on your report" right="My reports" />
            <div className="p-4 bg-se-lowest border border-se-outline-variant font-se-sans text-se-sm text-se-variant space-y-1">
              <p className="text-se-on font-medium flex items-center gap-2"><Icon name="check_circle" className="text-[18px]" />You’re signed in</p>
              <p>Follow this report any time from <Link to="/citizen/my-reports" className="underline text-se-on">Track My Report</Link>. Your name is never shown publicly.</p>
            </div>
          </div>

          <div className="space-y-2">
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 font-se-sans text-se-sm flex items-start gap-2" role="alert">
                <Icon name="error" className="text-[18px] shrink-0" />{error}
              </div>
            )}
            <button type="submit" disabled={submitting || text.trim().length < 10}
              className="w-full h-14 px-5 bg-se-primary text-white flex items-center justify-between font-se-code text-se-code uppercase tracking-wider font-semibold hover:bg-se-primary-container disabled:opacity-40 transition-colors">
              <span>{submitting ? "Sending…" : "Send to my ward team"}</span><Icon name="arrow_forward" className="text-[20px]" />
            </button>
            <button type="button" onClick={saveDraft}
              className="w-full h-11 border border-se-outline-variant bg-se-lowest font-se-code text-se-caps uppercase tracking-wider hover:border-se-primary transition-colors">
              {draftSaved ? "Draft saved on this device" : "Save draft on this device"}
            </button>
            <div className="flex justify-between pt-2 font-se-code text-[10px] uppercase tracking-wider text-se-variant">
              <span>Your name is never shown publicly</span><span className="text-se-on font-semibold">Takes under a minute</span>
            </div>
          </div>
        </div>
      </form>

      <SplitCTA
        left={{ to: "/citizen/my-reports", kicker: "Your reports // Check progress", title: "Track Previous Reports", text: "See where each of your complaints stands, add a photo later, and confirm when it’s fixed." }}
        right={{ to: "/citizen/issues", kicker: "Pune Pulse // Your city", title: "See What’s Reported Nearby", text: "Problems reported across Pune’s wards on one map — and how many have been fixed." }}
      />

      <section className="w-full bg-se-lowest border-t border-se-outline-variant/40 px-5 md:px-12 py-10 grid grid-cols-2 md:grid-cols-4 gap-7">
        <Stat label="Wards covered" value={stats?.wards} note="Across Pune city" />
        <Stat label="Reports from residents" value={stats?.reports} note="And counting" />
        <Stat label="Waiting to be fixed" value={mapData ? open : undefined} note="Open right now" />
        <Stat label="Fixed" value={mapData ? issues.length - open : undefined} note="With a photo from the spot" />
      </section>

      {cameraOpen && <EvidenceCamera title="Photo of the problem" onCancel={() => setCameraOpen(false)} onConfirm={keepCapture} />}
    </>
  );
}

function PhaseHead({ n, title, right }: { n: string; title: string; right: string }) {
  return (
    <div className="flex items-center justify-between pb-2 mb-5 border-b border-se-outline-variant/60">
      <Kicker>Step {n} // {title}</Kicker>
      <Kicker className="text-se-on">{right}</Kicker>
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: number | undefined; note: string }) {
  return (
    <div>
      <Kicker>{label}</Kicker>
      <div className="font-se-sans text-se-lg text-se-on mt-1">{value == null ? "—" : value.toLocaleString("en-IN")}</div>
      <div className="font-se-code text-[11px] text-se-variant">{note}</div>
    </div>
  );
}

/** Outline the chosen ward and fit the map to it. */
function WardFocus({ ward }: { ward: MapWard }) {
  const map = useMap();
  useEffect(() => {
    if (!ward.geometry) return;
    const b = L.geoJSON(ward.geometry as GeoJSON.GeoJsonObject).getBounds();
    if (b.isValid()) map.fitBounds(b, { padding: [16, 16] });
  }, [map, ward]);
  if (!ward.geometry) return null;
  return <GeoJSON key={ward.ward_id} data={ward.geometry as GeoJSON.GeoJsonObject} style={{ color: "#000", weight: 1.5, fillColor: "#555f6d", fillOpacity: 0.25 }} />;
}

function EvidenceOutcome({ outcome, dueAt }: { outcome: UploadResult | null; dueAt: string | null }) {
  if (outcome === null) {
    return <p>No photo added yet.{dueAt && <> You can add one from Track My Report until {formatTime(dueAt)}.</>}</p>;
  }
  if (outcome.ok) return <p className="text-emerald-700">Photo received — your ward officer will look at it.</p>;
  return (
    <p className="text-amber-700" role="alert">
      Your report is saved. {outcome.message}
      {outcome.retryable && <> Open <Link to="/citizen/my-reports" className="underline">Track My Report</Link> to send it.</>}
    </p>
  );
}

function ReportResult({ result, evidenceResult, onReportAnother }: {
  result: ReportCreateResponse; evidenceResult: UploadResult | null; onReportAnother: () => void;
}) {
  const where =
    result.location_precision === "precise" ? "We found the exact spot."
    : result.location_precision === "ward_level" ? `Sent to Ward ${result.report.ward_id ?? "—"}.`
    : "We couldn't find the exact spot yet - a ward officer will place it.";
  const rows: [string, React.ReactNode][] = [
    ["Kind of problem", CATEGORY_LABELS[result.category] ?? result.category],
    ["Where", where],
    ["Others nearby", result.joined_existing_issue ? "Others have reported this too. Your report has been added to theirs - more reports means it gets attention sooner." : "You're the first to report this. Thank you!"],
    ["How urgent", result.severity ? severityMessage(result.severity) : "Your ward team will assess it."],
    ["Your photo", <EvidenceOutcome outcome={evidenceResult} dueAt={result.report.evidence_due_at} />],
  ];
  return (
    <>
      <section className="w-full bg-se-surface px-5 md:px-12 pt-10 pb-12">
        <Kicker>Report #{result.report.id} // Sent</Kicker>
        <h1 className="mt-3 font-se-sans text-[40px] leading-[46px] md:text-se-xl text-se-on tracking-tight">Thank you — your report has been sent.</h1>
        <p className="mt-4 max-w-2xl font-se-sans text-se-body-xl text-se-variant">
          {result.report.language && result.report.language !== "en" ? "Thanks for writing in your language — a ward officer will read it. " : ""}Here’s what happens with it.
        </p>
      </section>
      <section className="w-full bg-se-lowest border-t border-se-outline-variant/40 px-5 md:px-12 py-12">
        <div className="max-w-4xl">
          {result.report.photo_url && (
            <img src={mediaUrl(result.report.photo_url)} alt="Your photo of the problem" className="max-h-72 mb-7 border border-se-outline-variant object-cover" />
          )}
          {rows.map(([k, v], i) => (
            <div key={k} className="grid grid-cols-1 md:grid-cols-12 gap-2 py-5 border-b border-se-high">
              <div className="md:col-span-4 flex items-baseline gap-3"><span className="font-se-code text-se-code text-se-secondary">/0.{i + 1}</span><span className="font-se-sans text-se-title text-se-on">{k}</span></div>
              <div className="md:col-span-8 font-se-sans text-se-body text-se-variant">{v}</div>
            </div>
          ))}
          <div className="flex flex-col sm:flex-row gap-2 mt-10">
            <Link to={`/citizen/issues/${result.issue_id}`} className="h-14 px-6 bg-se-primary text-white flex items-center justify-between gap-6 font-se-code text-se-code uppercase tracking-wider font-semibold hover:bg-se-primary-container">
              Follow this problem <Icon name="arrow_forward" className="text-[20px]" />
            </Link>
            <button type="button" onClick={onReportAnother} className="h-14 px-6 border border-se-outline-variant font-se-code text-se-code uppercase tracking-wider hover:border-se-primary">
              Report another problem
            </button>
          </div>
        </div>
      </section>
    </>
  );
}

export default ReportIssue;
