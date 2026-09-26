import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, mediaUrl } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { useSpeechRecognition } from "../../hooks/useSpeechRecognition";
import { CATEGORY_LABELS } from "../../api/types";
import type { ReportCreateResponse } from "../../api/types";
import { LanguageTag } from "../../components/Badges";
import { GlowingCard } from "../../components/ui/GlowingCard";
import { 
  Mic, 
  MicOff, 
  UploadCloud, 
  Send, 
  CheckCircle2, 
  AlertCircle, 
  MapPin, 
  Layers,
  ArrowRight,
  Camera,
  Image as ImageIcon
} from "lucide-react";

const VOICE_LANGUAGES = [
  { code: "en-IN", label: "English" },
  { code: "hi-IN", label: "हिंदी (Hindi)" },
  { code: "mr-IN", label: "मराठी (Marathi)" },
];

function severityMessage(severity: string): string {
  if (severity === "critical") return "This looks serious and has been flagged for prompt attention.";
  if (severity === "moderate") return "This has been logged as a moderate-priority issue.";
  return "This has been logged as a minor issue.";
}

export function ReportIssue() {
  const { data: mapData } = useApi(() => api.map(), []);
  const [text, setText] = useState("");
  const [wardId, setWardId] = useState<string>("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReportCreateResponse | null>(null);
  const [voiceLang, setVoiceLang] = useState(VOICE_LANGUAGES[0].code);
  const speech = useSpeechRecognition(voiceLang, (finalText) => {
    setText((prev) => (prev.trim() ? `${prev.trim()} ${finalText.trim()}` : finalText.trim()));
  });

  function handlePhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhoto(file);
    setPhotoPreview(file ? URL.createObjectURL(file) : null);
    e.target.value = ""; // lets the same photo be re-picked after switching inputs
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      let photo_url: string | null = null;
      if (photo) {
        photo_url = (await api.uploadPhoto(photo)).photo_url;
      }
      const response = await api.createReport({
        raw_text: text.trim(),
        ward_id: wardId ? Number(wardId) : null,
        photo_url,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong submitting your report. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return <ReportResult result={result} onReportAnother={() => { setResult(null); setText(""); setPhoto(null); setPhotoPreview(null); }} />;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground mb-2">
          Report a Civic Issue
        </h1>
        <p className="text-secondary text-base sm:text-lg leading-relaxed">
          Describe the problem in your own words. Mentioning a landmark or selecting your ward helps place it accurately on the Pune spatial map.
        </p>
      </div>

      <GlowingCard className="border-border">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Textarea description */}
          <div className="space-y-2">
            <label htmlFor="raw_text" className="text-sm font-semibold text-foreground flex items-center justify-between">
              <span>What is the issue? *</span>
              <span className="text-xs text-secondary font-normal">Min 10 characters</span>
            </label>
            <textarea
              id="raw_text"
              rows={4}
              required
              minLength={10}
              placeholder="e.g. Deep pothole right outside Pune Railway Station gate 2, traffic slowing down severely..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full font-sans text-sm sm:text-base p-3.5 border border-border rounded-xl bg-muted/40 text-foreground placeholder:text-secondary/60 focus:bg-background focus:outline-none focus:ring-2 focus:ring-primary transition-all"
            />

            {/* Speech Input */}
            {speech.supported && (
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <select
                  value={voiceLang}
                  onChange={(e) => setVoiceLang(e.target.value)}
                  disabled={speech.listening}
                  aria-label="Spoken language"
                  className="px-3 py-1.5 border border-border rounded-lg bg-background text-foreground text-xs font-medium"
                >
                  {VOICE_LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={speech.listening ? speech.stop : speech.start}
                  className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    speech.listening 
                      ? "bg-red-600 text-white animate-pulse" 
                      : "bg-muted border border-border text-foreground hover:bg-border/60"
                  }`}
                >
                  {speech.listening ? (
                    <>
                      <MicOff className="w-3.5 h-3.5" />
                      Stop recording
                    </>
                  ) : (
                    <>
                      <Mic className="w-3.5 h-3.5 text-primary" />
                      Speak instead
                    </>
                  )}
                </button>
                {speech.listening && (
                  <span className="text-xs text-secondary font-mono">
                    {speech.interimTranscript || "Listening…"}
                  </span>
                )}
                {speech.error && (
                  <span className="text-xs text-red-600 flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5" />
                    {speech.error}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Optional Ward */}
          <div className="space-y-2">
            <label htmlFor="ward" className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <MapPin className="w-4 h-4 text-primary" />
              <span>Ward location (optional)</span>
            </label>
            <select
              id="ward"
              value={wardId}
              onChange={(e) => setWardId(e.target.value)}
              className="w-full px-3.5 py-2.5 border border-border rounded-xl bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">I didn't mention a ward above / not sure</option>
              {mapData?.wards.map((w) => (
                <option key={w.ward_id} value={w.ward_id}>
                  Ward {w.ward_id} — {w.name}
                </option>
              ))}
            </select>
            <p className="text-xs text-secondary">
              Our spatial engine detects locations from text, but you can explicitly specify a ward if known.
            </p>
          </div>

          {/* Photo attachment */}
          <div className="space-y-2">
            <span className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <UploadCloud className="w-4 h-4 text-primary" />
              <span>Attach a photo (optional)</span>
            </span>
            <div className="flex flex-wrap gap-3">
              {/* capture="environment" opens the rear camera directly on phones; desktops fall back to a file picker. */}
              <label className="btn cursor-pointer px-4 py-2 rounded-lg border border-border bg-primary/10 text-primary text-xs font-semibold flex items-center gap-1.5">
                <Camera className="w-4 h-4" />
                Take photo
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  capture="environment"
                  onChange={handlePhotoChange}
                  className="sr-only"
                />
              </label>
              <label className="btn cursor-pointer px-4 py-2 rounded-lg border border-border bg-muted/40 text-foreground text-xs font-semibold flex items-center gap-1.5">
                <ImageIcon className="w-4 h-4" />
                Choose from gallery
                <input
                  id="photo"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handlePhotoChange}
                  className="sr-only"
                />
              </label>
              {photo && <span className="self-center text-xs text-secondary truncate max-w-[12rem]">{photo.name}</span>}
            </div>
            <p className="text-xs text-secondary">
              Stored as evidence for ward officer verification — never used to score severity. Location
              data and other metadata are removed from the photo before it is stored.
            </p>
            {photoPreview && (
              <div className="mt-3 relative rounded-xl overflow-hidden border border-border max-w-sm">
                <img src={photoPreview} alt="Report preview" className="w-full h-48 object-cover" />
              </div>
            )}
          </div>

          {error && (
            <div className="p-3.5 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm flex items-start gap-2" role="alert">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-600" />
              <span>{error}</span>
            </div>
          )}

          <div className="pt-2">
            <button
              type="submit"
              disabled={submitting || !text.trim()}
              className="btn btn-black w-full py-3.5 rounded-xl font-semibold text-base shadow-sm flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {submitting ? (
                <>Submitting report…</>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  Submit Civic Report
                </>
              )}
            </button>
          </div>
        </form>
      </GlowingCard>
    </div>
  );
}

function ReportResult({
  result,
  onReportAnother,
}: {
  result: ReportCreateResponse;
  onReportAnother: () => void;
}) {
  const categoryLabel = CATEGORY_LABELS[result.category] ?? result.category;
  const locationMessage =
    result.location_precision === "precise"
      ? "Placed at a verified precise coordinate."
      : result.location_precision === "ward_level"
      ? `Placed within Ward ${result.report.ward_id ?? "—"}.`
      : "Couldn't determine a specific geographic coordinate from description.";

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div className="text-center space-y-2">
        <div className="w-12 h-12 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-600 mx-auto flex items-center justify-center">
          <CheckCircle2 className="w-6 h-6" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Thank you — your report is registered.
        </h1>
        <p className="text-secondary text-base">
          Here is how our deterministic intake engine analyzed and placed your complaint:
        </p>
      </div>

      <GlowingCard className="border-border">
        {result.report.language && result.report.language !== "en" && (
          <div className="mb-6 p-4 bg-muted/60 rounded-xl border border-border/70">
            <LanguageTag language={result.report.language} />
            {result.report.translated_text && (
              <p className="mt-2 text-sm text-secondary">
                Translated for automated clustering: <em>&ldquo;{result.report.translated_text}&rdquo;</em>
              </p>
            )}
          </div>
        )}

        {result.report.photo_url && (
          <div className="mb-6 p-4 bg-muted/40 rounded-xl border border-border">
            <img
              src={mediaUrl(result.report.photo_url)}
              alt="Reported evidence"
              className="max-h-56 rounded-lg border border-border object-cover mx-auto"
            />
            {result.report.photo_severity_band && (
              <p className="mt-2 text-xs text-secondary text-center">
                Photo severity metric: <strong>{result.report.photo_severity_band}</strong>
                {result.report.photo_severity_score != null && ` (score ${result.report.photo_severity_score.toFixed(2)})`}
              </p>
            )}
          </div>
        )}

        <ol className="space-y-4 mb-8">
          <li className="flex items-start gap-3 p-3 bg-muted/30 rounded-lg border border-border/60">
            <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
              1
            </span>
            <div>
              <strong className="text-foreground text-sm block">Category Classification</strong>
              <span className="text-secondary text-sm">{categoryLabel}</span>
            </div>
          </li>

          <li className="flex items-start gap-3 p-3 bg-muted/30 rounded-lg border border-border/60">
            <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
              2
            </span>
            <div>
              <strong className="text-foreground text-sm block">Spatial Resolution</strong>
              <span className="text-secondary text-sm">{locationMessage}</span>
            </div>
          </li>

          <li className="flex items-start gap-3 p-3 bg-muted/30 rounded-lg border border-border/60">
            <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
              3
            </span>
            <div>
              <strong className="text-foreground text-sm block">Clustering Status</strong>
              <span className="text-secondary text-sm">
                {result.joined_existing_issue
                  ? "Matched an existing tracked issue nearby. Added as corroborating evidence to increase resolution priority."
                  : "Registered as a newly discovered distinct civic issue."}
              </span>
            </div>
          </li>

          <li className="flex items-start gap-3 p-3 bg-muted/30 rounded-lg border border-border/60">
            <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
              4
            </span>
            <div>
              <strong className="text-foreground text-sm block">Public Works Cross-Check</strong>
              <span className="text-secondary text-sm">
                {result.matched_work
                  ? "Surfaced related MPLADS government works record in this vicinity."
                  : "No related MPLADS public works record found for this coordinate."}
              </span>
            </div>
          </li>

          <li className="flex items-start gap-3 p-3 bg-muted/30 rounded-lg border border-border/60">
            <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
              5
            </span>
            <div>
              <strong className="text-foreground text-sm block">Severity Band</strong>
              <span className="text-secondary text-sm">{severityMessage(result.severity)}</span>
            </div>
          </li>
        </ol>

        <div className="flex flex-col sm:flex-row gap-3.5 pt-2">
          <Link
            to={`/citizen/issues/${result.issue_id}`}
            className="btn btn-black flex-1 py-3 rounded-xl justify-center text-sm font-semibold flex items-center gap-2"
          >
            <Layers className="w-4 h-4" />
            View Tracked Issue #{result.issue_id}
            <ArrowRight className="w-4 h-4" />
          </Link>
          <button
            onClick={onReportAnother}
            className="btn py-3 px-6 rounded-xl border border-border hover:bg-muted text-foreground text-sm font-medium transition-colors"
          >
            Report Another Issue
          </button>
        </div>
      </GlowingCard>
    </div>
  );
}
export default ReportIssue;
