import { useEffect, useState } from "react";
import { Camera, CheckCircle2, HardHat, ShieldCheck, Clock, AlertCircle } from "lucide-react";
import { api, ApiError } from "../../api/client";
import type { AlternativeVerification, EvidenceItem, EvidenceStatus, IssueDetailResponse, ReportInIssue } from "../../api/types";
import { useApi } from "../../hooks/useApi";
import { formatAccuracy, formatCoord, formatTime } from "../../evidence/EvidenceUpload";

// Before -> Work -> After -> Review, built only from what the API returns.
// Location evidence is a verification signal for human review: nothing here
// concludes a report is genuine or false.

const EVIDENCE_STATUS_TEXT: Record<EvidenceStatus, string> = {
  submitted: "Photo evidence submitted",
  alternative_confirmed: "Confirmed through another channel",
  alternative_in_progress: "Alternative verification in progress",
  pending: "Photo evidence pending (window open)",
  not_provided: "No photo provided - awaiting human review",
};

const REVIEW_TEXT: Record<EvidenceItem["review_status"], string> = {
  pending_review: "Pending review",
  verified: "Reviewed: verified",
  review_required: "Reviewed: needs follow-up",
};

/** Hours from device capture to server receipt; negative means the device
 * clock was ahead of the server. Either is a signal, not a verdict. */
function receiptLagHours(capturedAt: string, submittedAt: string): number {
  return (new Date(submittedAt).getTime() - new Date(capturedAt).getTime()) / 3_600_000;
}

function Stage({ label, icon, children }: { label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <li className="relative pl-8 pb-6 last:pb-0 border-l border-gray-200 ml-3">
      <span className="absolute -left-3 top-0 w-6 h-6 rounded-full bg-white border border-gray-300 flex items-center justify-center">
        {icon}
      </span>
      <h3 className="text-[11px] font-mono uppercase tracking-wider font-bold text-gray-700 mb-2">{label}</h3>
      <div className="space-y-3">{children}</div>
    </li>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-gray-500 shrink-0">{k}</span>
      <span className="font-semibold text-gray-900 text-right">{v}</span>
    </div>
  );
}

/** Signed Storage URL, or a blob URL when photos are on local disk. */
export function useEvidencePhoto(fileUrl: string) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    api
      .evidencePhotoUrl(fileUrl)
      .then((u) => {
        url = u;
        if (!cancelled) setSrc(u);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (url?.startsWith("blob:")) URL.revokeObjectURL(url);
    };
  }, [fileUrl]);
  return { src, failed };
}

function EvidencePhoto({ fileUrl }: { fileUrl: string }) {
  const { src, failed } = useEvidencePhoto(fileUrl);
  if (failed) {
    return <div className="h-40 flex items-center justify-center text-xs text-red-600 bg-gray-50 rounded">Photo couldn't be loaded.</div>;
  }
  if (!src) return <div className="h-72 bg-gray-100 rounded animate-pulse" />;
  return (
    <a href={src} target="_blank" rel="noreferrer" title="Open full size">
      <img src={src} alt="Location-verified evidence" className="w-full max-h-96 object-contain bg-gray-900 rounded" />
    </a>
  );
}

function EvidenceCard({ item, issue, onChanged }: { item: EvidenceItem; issue: IssueDetailResponse; onChanged: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function review(status: "verified" | "review_required") {
    setBusy(true);
    setError(null);
    try {
      await api.reviewEvidence(item.evidence_id, status, note.trim());
      setNote("");
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save the review.");
    } finally {
      setBusy(false);
    }
  }

  const lag = item.captured_at ? receiptLagHours(item.captured_at, item.submitted_at) : 0;
  const d = item.distance_from_issue_m;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-3 rounded border border-gray-200 bg-white">
      <EvidencePhoto fileUrl={item.file_url} />
      <div className="space-y-1.5 text-xs font-mono text-gray-700">
        <Row k="Submitted by" v={`${item.actor_type === "worker" ? "Field worker" : "Citizen"} #${item.submitted_by}`} />
        <Row k="Capture method" v={item.capture_method === "upload" ? "Uploaded file" : "In-app camera"} />
        <Row k={item.capture_method === "upload" ? "Uploaded (device clock)" : "Captured (device clock)"}
          v={item.captured_at ? formatTime(item.captured_at) : "—"} />
        <Row
          k="Received (server)"
          v={
            <>
              {formatTime(item.submitted_at)}
              {lag >= 1 && <span className="block text-[10px] font-normal text-gray-500">{lag.toFixed(1)} h after capture</span>}
              {lag <= -0.1 && (
                <span className="block text-[10px] font-normal text-amber-700">
                  Device clock {(-lag).toFixed(1)} h ahead of the server
                </span>
              )}
            </>
          }
        />
        <Row k="Device location" v={
          <>
            {formatCoord(item.location.lat, item.location.lon)}
            {item.capture_method === "upload" && (
              <span className="block text-[10px] font-normal text-amber-700">
                Uploader's device at upload time, not where the photo was taken. Treat distance as unverified.
              </span>
            )}
          </>
        } />
        <Row k="Accuracy" v={formatAccuracy(item.accuracy_m)} />
        <Row
          k="Reported issue location"
          v={issue.location ? `${formatCoord(issue.location.lat, issue.location.lon)} (${issue.location_precision})` : "Not located"}
        />
        <Row
          k="Distance"
          v={
            d === null ? (
              "Not calculable"
            ) : (
              <>
                {d < 1000 ? `${Math.round(d)} m` : `${(d / 1000).toFixed(2)} km`} from reported location
                {item.issue_location_precision !== "precise" && (
                  <span className="block text-[10px] font-normal text-amber-700">
                    Measured to an approximate (ward-level) issue location
                  </span>
                )}
                {item.issue_location_precision === "precise" && d <= item.accuracy_m && (
                  <span className="block text-[10px] font-normal text-gray-500">Within the device's accuracy radius</span>
                )}
              </>
            )
          }
        />
        <Row
          k="Review"
          v={
            <span
              className={
                item.review_status === "verified" ? "text-emerald-700" : item.review_status === "review_required" ? "text-amber-700" : ""
              }
            >
              {REVIEW_TEXT[item.review_status]}
              {item.reviewed_at && (
                <span className="block text-[10px] font-normal text-gray-500">
                  {formatTime(item.reviewed_at)} · staff #{item.reviewed_by}
                </span>
              )}
            </span>
          }
        />
        {item.review_note && <p className="text-[11px] italic text-gray-600 font-sans">&ldquo;{item.review_note}&rdquo;</p>}

        <div className="pt-2 space-y-2">
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Review note (optional, staff only)"
            className="w-full px-2 py-1.5 border border-gray-200 rounded text-xs font-sans"
          />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => review("verified")}
              className="flex-1 px-2 py-1.5 rounded bg-emerald-600 text-white text-xs font-bold disabled:opacity-50"
            >
              Mark verified
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => review("review_required")}
              className="flex-1 px-2 py-1.5 rounded border border-amber-400 text-amber-800 text-xs font-bold disabled:opacity-50"
            >
              Needs follow-up
            </button>
          </div>
          {error && <p className="text-red-600">{error}</p>}
        </div>
      </div>
    </div>
  );
}

function AlternativeVerificationControls({
  report,
  records,
  onChanged,
}: {
  report: ReportInIssue;
  records: AlternativeVerification[];
  onChanged: () => void;
}) {
  const [channel, setChannel] = useState<AlternativeVerification["channel"]>("phone");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const open = records.find((r) => r.status === "initiated");

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setNotes("");
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2 text-xs font-mono">
      {records.map((r) => (
        <div key={r.id} className="text-gray-600">
          {r.channel} verification · {r.status.replace("_", " ")} · started {formatTime(r.initiated_at)} by staff #{r.initiated_by}
          {r.completed_at && <> · completed {formatTime(r.completed_at)}</>}
          {r.notes && <span className="block italic font-sans">&ldquo;{r.notes}&rdquo;</span>}
        </div>
      ))}
      {open ? (
        <div className="flex flex-wrap gap-2 items-center">
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Outcome notes" className="px-2 py-1 border border-gray-200 rounded font-sans" />
          {(["confirmed", "not_confirmed", "unreachable"] as const).map((s) => (
            <button
              key={s}
              type="button"
              disabled={busy}
              onClick={() => run(() => api.completeAlternativeVerification(open.id, s, notes.trim()))}
              className="px-2 py-1 rounded border border-gray-300 bg-white font-bold disabled:opacity-50"
            >
              {s.replace("_", " ")}
            </button>
          ))}
        </div>
      ) : (
        report.evidence_status !== "submitted" &&
        report.evidence_status !== "alternative_confirmed" && (
          <div className="flex flex-wrap gap-2 items-center">
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value as AlternativeVerification["channel"])}
              className="px-2 py-1 border border-gray-200 rounded bg-white"
            >
              <option value="phone">Phone call</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="in_person">Site visit</option>
              <option value="other">Other</option>
            </select>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes" className="px-2 py-1 border border-gray-200 rounded font-sans" />
            <button
              type="button"
              disabled={busy}
              onClick={() => run(() => api.startAlternativeVerification(report.id, channel, notes.trim()))}
              className="px-2 py-1 rounded bg-gray-900 text-white font-bold disabled:opacity-50"
            >
              Start alternative verification
            </button>
          </div>
        )
      )}
      {error && <p className="text-red-600">{error}</p>}
    </div>
  );
}

function AssignWorker({ issue, onChanged }: { issue: IssueDetailResponse; onChanged: () => void }) {
  const { data: workers, error: loadError } = useApi(() => api.fieldWorkers(), []);
  const [workerId, setWorkerId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function assign() {
    setBusy(true);
    setError(null);
    try {
      await api.assignIssue(issue.issue_id, Number(workerId));
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't assign.");
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return <p className="text-xs text-red-600 font-mono">Couldn't load field workers: {loadError}</p>;
  if (workers && workers.length === 0) {
    return (
      <p className="text-xs text-gray-500 font-mono">
        No field-worker accounts yet. Crew members sign in once, then a system administrator sets their role to
        Field Worker on the Staff &amp; Roles page.
      </p>
    );
  }
  return (
    <div className="flex flex-wrap gap-2 items-center text-xs font-mono">
      <select value={workerId} onChange={(e) => setWorkerId(e.target.value)} className="px-2 py-1 border border-gray-200 rounded bg-white">
        <option value="">{issue.assigned_worker_id ? "Reassign to…" : "Assign field worker…"}</option>
        {workers?.map((w) => (
          <option key={w.id} value={w.id}>
            #{w.id} {w.display_name ?? ""}
          </option>
        ))}
      </select>
      <button type="button" disabled={!workerId || busy} onClick={assign} className="px-2 py-1 rounded bg-gray-900 text-white font-bold disabled:opacity-50">
        Assign
      </button>
      {error && <span className="text-red-600">{error}</span>}
    </div>
  );
}

export function EvidenceTimeline({ issue, onChanged }: { issue: IssueDetailResponse; onChanged: () => void }) {
  const evidence = issue.evidence ?? [];
  const before = evidence.filter((e) => e.evidence_type === "initial_report");
  const after = evidence.filter((e) => e.evidence_type === "resolution");
  const windowOpen = issue.reverification_due_at ? new Date(issue.reverification_due_at).getTime() > Date.now() : null;

  return (
    <div className="ws-panel p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between border-b border-gray-100 pb-2.5 gap-2">
        <div className="flex items-center gap-2">
          <Camera className="w-4 h-4 text-blue-600" />
          <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-gray-800">Location-Verified Evidence Timeline</h2>
        </div>
        <span className="text-[10px] font-mono text-gray-500">A verification signal for human review - not proof</span>
      </div>

      <ol>
        <Stage label="Before · citizen evidence" icon={<Camera className="w-3 h-3 text-blue-600" />}>
          {issue.reports.map((r) => {
            const photo = before.find((e) => e.report_id === r.id);
            return (
              <div key={r.id} className="space-y-2">
                <div className="text-xs font-mono text-gray-600">
                  Report #{r.id} · {formatTime(r.reported_at)}
                  ·{" "}
                  <span className="font-bold">{EVIDENCE_STATUS_TEXT[r.evidence_status ?? "not_provided"]}</span>
                  {r.evidence_status === "pending" && r.evidence_due_at && <> until {formatTime(r.evidence_due_at)}</>}
                </div>
                {photo ? (
                  <EvidenceCard item={photo} issue={issue} onChanged={onChanged} />
                ) : (
                  <AlternativeVerificationControls
                    report={r}
                    records={issue.alternative_verifications.filter((a) => a.report_id === r.id)}
                    onChanged={onChanged}
                  />
                )}
              </div>
            );
          })}
        </Stage>

        <Stage label="Work" icon={<HardHat className="w-3 h-3 text-amber-600" />}>
          <div className="text-xs font-mono text-gray-700 space-y-1">
            <Row k="Routed to" v={issue.routed_agency && issue.routed_at ? `${issue.routed_agency} · ${formatTime(issue.routed_at)}` : "Not routed"} />
            <Row
              k="Assigned field worker"
              v={issue.assigned_worker_id && issue.assigned_at ? `#${issue.assigned_worker_id} · ${formatTime(issue.assigned_at)}` : "Not assigned"}
            />
            <Row
              k="Stage"
              v={
                issue.status === "closed"
                  ? "Completed"
                  : after.length
                    ? "Resolution evidence submitted - awaiting review"
                    : issue.assigned_worker_id
                      ? "In progress"
                      : "Awaiting assignment"
              }
            />
          </div>
          {issue.status !== "closed" && <AssignWorker issue={issue} onChanged={onChanged} />}
        </Stage>

        <Stage label="After · worker resolution evidence" icon={<CheckCircle2 className="w-3 h-3 text-emerald-600" />}>
          {after.length ? (
            after.map((e) => <EvidenceCard key={e.evidence_id} item={e} issue={issue} onChanged={onChanged} />)
          ) : (
            <p className="text-xs font-mono text-gray-500">
              No resolution evidence yet. The assigned field worker captures it on site with the in-app camera.
            </p>
          )}
        </Stage>

        <Stage label="Review & reverification" icon={<ShieldCheck className="w-3 h-3 text-emerald-600" />}>
          <div className="text-xs font-mono text-gray-700 space-y-1">
            <Row k="Status" v={issue.status} />
            {issue.closed_at && <Row k="Marked resolved" v={formatTime(issue.closed_at)} />}
            {issue.status === "closed" && (
              <Row
                k="Citizen reverification window"
                v={
                  issue.reverification_due_at
                    ? `${windowOpen ? "Open until" : "Closed on"} ${formatTime(issue.reverification_due_at)}`
                    : "No window (closed before windows existed)"
                }
              />
            )}
          </div>
          {issue.feedback.map((fb) => (
            <div
              key={fb.feedback_id}
              className={`p-3 rounded border text-xs font-mono flex items-start gap-2 ${
                fb.resolved_confirmed ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"
              }`}
            >
              {fb.resolved_confirmed ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
              )}
              <div>
                <div className="font-bold">
                  {fb.resolved_confirmed ? "Citizen confirmed the fix" : "Citizen says the problem remains - reopened for review"}
                </div>
                {fb.comment && <p className="italic font-sans">&ldquo;{fb.comment}&rdquo;</p>}
                <div className="text-[10px] text-gray-500 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> {formatTime(fb.submitted_at)}
                </div>
              </div>
            </div>
          ))}
        </Stage>
      </ol>
    </div>
  );
}
