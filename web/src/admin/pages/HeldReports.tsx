import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { HeldReport } from "../../api/types";
import { Icon, Card, Page, Skeleton, fmtTime, issueCode } from "../components/ws";

// Reports the LLM triage fallback (app/nlp/triage.py) held as likely spam.
// Held, never deleted: they stay off every board until a human releases them.
// Everything shown comes from GET /api/held-reports.

export function HeldReports() {
  const { data, loading, error, reload } = useApi(() => api.heldReports(), []);
  const [released, setReleased] = useState<Record<number, number>>({}); // report_id -> issue_id

  return (
    <Page>
      <div className="px-6 py-3 bg-ws-surface-low flex flex-wrap items-center justify-between gap-3 font-ws-label">
        <div className="flex items-center gap-2 text-xs text-[#535f74]">
          <span className="px-1.5 py-0.5 rounded bg-ws-blue text-white text-[11px] font-bold">PMC-AUDIT</span>
          <span>/</span>
          <span className="font-ws-body text-sm text-ws-on-surface font-semibold">Held for Review</span>
        </div>
        <span className="px-2.5 py-1 rounded-full bg-ws-primary/10 text-ws-primary text-[11px] font-semibold">
          {data ? `${data.length} waiting` : "…"}
        </span>
      </div>

      <div className="px-6 py-4 flex flex-col gap-4 font-ws-label">
        <Card className="p-3 flex items-start gap-2 text-xs text-ws-on-surface-variant">
          <Icon name="info" className="text-[18px] text-ws-primary shrink-0" />
          <span>
            Our classifier couldn't place these complaints, and the language model judged that they describe no civic
            problem. They are held, not deleted, and the citizen sees "under review". Release anything that is a real
            complaint; it goes on the board and is prioritised like any other. The model's reason is a suggestion
            for human review, not a decision.
          </span>
        </Card>

        {error && <Card className="p-4 text-sm text-ws-error">Couldn't load held reports: {error}</Card>}
        {loading && !data && <Skeleton className="h-64" />}
        {data && data.length === 0 && !Object.keys(released).length && (
          <Card className="p-6 text-sm text-ws-on-surface-variant">Nothing is held right now.</Card>
        )}

        {Object.entries(released).map(([reportId, issueId]) => (
          <Card key={reportId} className="p-3 flex items-center gap-2 text-xs text-ws-primary">
            <Icon name="check_circle" className="text-[18px]" />
            Report #{reportId} released to the board as
            <Link to={`/issues/${issueId}`} className="font-semibold underline">{issueCode(issueId)}</Link>
          </Card>
        ))}

        {data?.map((r) => (
          <HeldCard key={r.report_id} report={r} onReleased={(issueId) => {
            setReleased((prev) => ({ ...prev, [r.report_id]: issueId }));
            reload();
          }} />
        ))}
      </div>
    </Page>
  );
}

function HeldCard({ report, onReleased }: { report: HeldReport; onReleased: (issueId: number) => void }) {
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function release() {
    setBusy(true);
    setActionError(null);
    try {
      const res = await api.releaseHeldReport(report.report_id);
      onReleased(res.issue_id);
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Release failed.");
      setBusy(false);
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-[#535f74]">
        <span className="px-1.5 py-0.5 rounded bg-ws-navy text-white font-bold">Report #{report.report_id}</span>
        <span>{fmtTime(report.reported_at)}</span>
        <span>•</span>
        <span>{report.ward_id != null ? `Ward ${report.ward_id}` : "Ward unknown"}</span>
      </div>

      <p className="font-ws-body text-sm text-ws-on-surface whitespace-pre-wrap break-words">{report.raw_text}</p>
      {report.translated_text && (
        <p className="font-ws-body text-xs text-[#535f74] whitespace-pre-wrap break-words">
          <span className="font-semibold uppercase text-[10px]">English translation: </span>{report.translated_text}
        </p>
      )}

      <div className="rounded-lg bg-ws-surface-low p-3 flex items-start gap-2">
        <Icon name="smart_toy" className="text-[18px] text-amber-700 shrink-0" />
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-semibold uppercase text-amber-800">Model suggestion: likely not a civic complaint</span>
          <span className="font-ws-body text-xs text-ws-on-surface">{report.triage.reason}</span>
          <span className="font-ws-headline text-[10px] text-[#535f74]">
            {report.triage.model ?? "unknown model"} • prompt v{report.triage.prompt_version}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button disabled={busy} onClick={release}
          className="px-4 py-2 rounded bg-ws-blue hover:bg-ws-primary text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50">
          <Icon name="publish" className="text-[18px]" /> {busy ? "Releasing…" : "Real complaint: release to board"}
        </button>
        <span className="text-[11px] text-[#535f74]">Leave it here if it isn't one. Nothing is deleted.</span>
      </div>
      {actionError && <p className="text-xs text-ws-error">{actionError}</p>}
    </div>
  );
}

export default HeldReports;
