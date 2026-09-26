import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Camera, CheckCircle2, Clock, AlertCircle, WifiOff } from "lucide-react";
import { api, ApiError, type EvidencePackage } from "../../api/client";
import type { EvidenceStatus, MyReport } from "../../api/types";
import { CATEGORY_LABELS } from "../../api/types";
import { useApi } from "../../hooks/useApi";
import { signOut, useSignedIn } from "../../lib/auth";
import { SignIn } from "../../components/SignIn";
import { LoadingState, ErrorState } from "../../components/States";
import { EvidenceCamera, formatTime } from "../../evidence/EvidenceCamera";
import { captureAndUpload, listPending, uploadPending, type PendingUpload } from "../../evidence/pendingUploads";

const EVIDENCE_LABELS: Record<EvidenceStatus, string> = {
  submitted: "Photo evidence received",
  alternative_confirmed: "Confirmed by the ward office",
  alternative_in_progress: "Ward office is verifying",
  pending: "Photo evidence pending",
  not_provided: "No photo provided",
};

function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

export function MyReports() {
  const signedIn = useSignedIn();
  const { data: reports, loading, error, reload } = useApi(
    () => (signedIn ? api.myReports() : Promise.resolve([] as MyReport[])),
    [signedIn],
  );
  const online = useOnline();
  const [pending, setPending] = useState<PendingUpload[]>([]);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [cameraFor, setCameraFor] = useState<MyReport | null>(null);

  const refreshPending = useCallback(() => listPending().then(setPending), []);

  const sendPending = useCallback(async () => {
    const queue = await listPending();
    if (!queue.length) return;
    setSending(true);
    let sent = 0;
    let lastError: string | null = null;
    for (const entry of queue) {
      const result = await uploadPending(entry);
      if (result.ok) sent += 1;
      else lastError = result.message;
    }
    setSending(false);
    await refreshPending();
    if (sent) reload();
    setNotice(lastError ? { kind: "error", text: lastError } : { kind: "ok", text: "Saved photo evidence sent." });
  }, [refreshPending, reload]);

  useEffect(() => {
    refreshPending();
  }, [refreshPending]);

  // Back online: send anything captured while offline. Via a ref so this runs
  // on connectivity changes only (useApi's reload is a new function each render).
  const sendRef = useRef(sendPending);
  sendRef.current = sendPending;
  useEffect(() => {
    if (online) sendRef.current();
  }, [online]);

  async function onCapture(pkg: EvidencePackage) {
    const report = cameraFor!;
    setCameraFor(null);
    setSending(true);
    const result = await captureAndUpload(report.issue_id!, pkg, report.report_id);
    setSending(false);
    await refreshPending();
    if (result.ok) {
      setNotice({ kind: "ok", text: "Photo evidence received with its location - pending officer review." });
      reload();
    } else {
      setNotice({ kind: "error", text: result.message });
    }
  }

  if (!signedIn) {
    return (
      <SignIn
        title="Sign in to see your reports"
        blurb="Your reports, photo evidence and resolution checks appear here once you're signed in."
      />
    );
  }
  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={reload} />;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-3xl font-bold tracking-tight text-foreground mb-1">My reports</h1>
          <button type="button" onClick={() => signOut()} className="text-sm text-secondary underline">
            Sign out
          </button>
        </div>
        <p className="text-secondary">Add photo evidence, follow progress, and confirm when a problem is fixed.</p>
      </div>

      {!online && (
        <div className="p-3 rounded-xl border border-amber-300 bg-amber-50 text-amber-800 text-sm flex items-center gap-2" role="status">
          <WifiOff className="w-4 h-4 shrink-0" /> You're offline. Photos you capture are kept on this device until you reconnect.
        </div>
      )}

      {pending.length > 0 && (
        <div className="p-4 rounded-xl border border-amber-300 bg-amber-50 space-y-2" role="status">
          <p className="text-sm text-amber-900 font-semibold">
            {pending.length} photo{pending.length > 1 ? "s" : ""} saved on this device, not sent yet
          </p>
          <button
            type="button"
            onClick={sendPending}
            disabled={sending || !online}
            className="btn btn-black w-full py-3 rounded-xl text-sm font-semibold disabled:opacity-50"
          >
            {sending ? "Sending…" : "Send now"}
          </button>
        </div>
      )}

      {notice && (
        <div
          role={notice.kind === "error" ? "alert" : "status"}
          className={`p-3 rounded-xl text-sm flex items-start gap-2 ${
            notice.kind === "error"
              ? "bg-red-50 border border-red-200 text-red-700"
              : "bg-emerald-50 border border-emerald-200 text-emerald-800"
          }`}
        >
          {notice.kind === "error" ? (
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
          )}
          {notice.text}
        </div>
      )}

      {reports && reports.length === 0 && (
        <p className="text-secondary">
          You haven't reported anything yet.{" "}
          <Link to="/citizen/report" className="underline">
            Report an issue
          </Link>
        </p>
      )}

      <ul className="space-y-4">
        {reports?.map((r) => (
          <ReportCard
            key={r.report_id}
            report={r}
            photoQueued={pending.some((p) => p.reportId === r.report_id)}
            busy={sending}
            onAddPhoto={() => setCameraFor(r)}
            onChanged={reload}
          />
        ))}
      </ul>

      {cameraFor && (
        <EvidenceCamera
          title={`Photo for report #${cameraFor.report_id}`}
          onCancel={() => setCameraFor(null)}
          onConfirm={onCapture}
        />
      )}
    </div>
  );
}

function ReportCard({
  report,
  photoQueued,
  busy,
  onAddPhoto,
  onChanged,
}: {
  report: MyReport;
  photoQueued: boolean;
  busy: boolean;
  onAddPhoto: () => void;
  onChanged: () => void;
}) {
  const now = Date.now();
  const canAddPhoto =
    report.issue_id !== null &&
    report.evidence_status === "pending" &&
    !photoQueued &&
    (!report.evidence_due_at || new Date(report.evidence_due_at).getTime() > now);
  const reverificationOpen =
    report.issue_status === "closed" &&
    report.issue_id !== null &&
    (!report.issue_reverification_due_at || new Date(report.issue_reverification_due_at).getTime() > now);

  return (
    <li className="p-4 rounded-2xl border border-border bg-background space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-secondary">
            Report #{report.report_id} · {formatTime(report.reported_at)}
            {report.category && <> · {CATEGORY_LABELS[report.category] ?? report.category}</>}
          </p>
          <p className="text-foreground mt-1 line-clamp-3">{report.raw_text}</p>
        </div>
        {report.issue_status && (
          <span className="text-xs font-semibold px-2 py-1 rounded-lg bg-muted text-foreground shrink-0">
            {report.issue_status}
          </span>
        )}
      </div>

      <div className="text-sm flex items-center gap-1.5 text-secondary">
        {report.evidence_status === "submitted" || report.evidence_status === "alternative_confirmed" ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
        ) : (
          <Clock className="w-4 h-4" />
        )}
        <span>
          {photoQueued ? "Photo saved on this device, waiting to send" : EVIDENCE_LABELS[report.evidence_status ?? "not_provided"]}
          {report.evidence_status === "pending" && report.evidence_due_at && !photoQueued && (
            <> · add until {formatTime(report.evidence_due_at)}</>
          )}
        </span>
      </div>

      {canAddPhoto && (
        <button
          type="button"
          onClick={onAddPhoto}
          disabled={busy}
          className="btn btn-black w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
        >
          <Camera className="w-4 h-4" /> Add location-verified photo
        </button>
      )}

      {reverificationOpen && (
        <Reverification issueId={report.issue_id!} dueAt={report.issue_reverification_due_at} onDone={onChanged} />
      )}

      {report.issue_id !== null && (
        <Link to={`/citizen/issues/${report.issue_id}`} className="text-sm underline text-secondary">
          View issue #{report.issue_id}
        </Link>
      )}
    </li>
  );
}

function Reverification({ issueId, dueAt, onDone }: { issueId: number; dueAt: string | null; onDone: () => void }) {
  const [disputing, setDisputing] = useState(false);
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "confirmed" | "reopened">("idle");
  const [error, setError] = useState<string | null>(null);

  async function send(resolved: boolean) {
    setState("sending");
    setError(null);
    try {
      const res = await api.submitFeedback(issueId, {
        resolved_confirmed: resolved,
        comment: resolved ? null : comment.trim() || null,
      });
      setState(res.issue_status === "reopened" ? "reopened" : "confirmed");
      onDone();
    } catch (err) {
      setState("idle");
      setError(err instanceof ApiError ? err.message : "Couldn't send your answer. Try again.");
    }
  }

  if (state === "confirmed") return <p className="text-sm text-emerald-700">Thanks - you confirmed the fix.</p>;
  if (state === "reopened") {
    return <p className="text-sm text-amber-700">Thanks - the issue has been reopened for the ward office to review.</p>;
  }

  return (
    <div className="p-3 rounded-xl bg-muted/50 border border-border space-y-2">
      <p className="text-sm font-semibold text-foreground">This issue was marked resolved.</p>
      {dueAt && <p className="text-xs text-secondary">You can respond until {formatTime(dueAt)}.</p>}
      {!disputing ? (
        <div className="flex flex-col sm:flex-row gap-2">
          <button
            type="button"
            disabled={state === "sending"}
            onClick={() => send(true)}
            className="btn btn-black flex-1 py-3 rounded-xl text-sm font-semibold"
          >
            Yes, it's resolved
          </button>
          <button
            type="button"
            disabled={state === "sending"}
            onClick={() => setDisputing(true)}
            className="btn flex-1 py-3 rounded-xl border border-border text-sm font-semibold"
          >
            No, the problem remains
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <label htmlFor={`remains-${issueId}`} className="text-sm text-foreground">
            What's still wrong? (no new photo needed)
          </label>
          <textarea
            id={`remains-${issueId}`}
            rows={3}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="w-full p-3 border border-border rounded-xl bg-background text-foreground text-sm"
            placeholder="e.g. The pothole was filled but has sunk again after the rain."
          />
          <div className="flex gap-2">
            <button type="button" onClick={() => setDisputing(false)} className="btn flex-1 py-3 rounded-xl border border-border text-sm">
              Back
            </button>
            <button
              type="button"
              disabled={state === "sending"}
              onClick={() => send(false)}
              className="btn btn-black flex-1 py-3 rounded-xl text-sm font-semibold"
            >
              Reopen issue
            </button>
          </div>
        </div>
      )}
      {error && (
        <p className="text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export default MyReports;
