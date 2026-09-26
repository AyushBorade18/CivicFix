import { useParams, Link } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { PriorityBreakdownView } from "../../components/PriorityBreakdown";
import { EvidenceTimeline } from "../components/EvidenceTimeline";
import { IssueDossier } from "../components/IssueDossier";
import { CATEGORY_LABELS } from "../../api/types";
import { Icon, Card, SectionLabel, Page, Subheader, BandChip, issueCode, fmtTime, inr, Skeleton } from "../components/ws";

export function IssueDetail() {
  const id = Number(useParams().issueId);
  const { data: issue, loading, error, reload } = useApi(() => api.issueDetail(id), [id]);
  const { data: map } = useApi(() => api.map().catch(() => null), []);
  const wardName = issue?.ward_id != null ? map?.wards.find((w) => w.ward_id === issue.ward_id)?.name : null;

  return (
    <Page>
      <Subheader>
        <div className="flex items-center gap-2 font-ws-label text-xs text-ws-on-surface-variant">
          <Link to="/issues" className="flex items-center gap-1 font-semibold text-ws-primary hover:underline">
            <Icon name="arrow_back" className="text-[16px]" /> Issues Triage
          </Link>
          <Icon name="chevron_right" className="text-[16px]" />
          <span className="font-ws-headline text-ws-on-surface font-semibold">{issueCode(id)}</span>
          {issue && <BandChip score={issue.priority_score} soft />}
        </div>
        {issue && (
          <span className="font-ws-label text-[11px] text-[#535f74]">
            {CATEGORY_LABELS[issue.category] ?? issue.category} • first reported {fmtTime(issue.first_reported)} • last {fmtTime(issue.last_reported)}
          </span>
        )}
      </Subheader>

      <div className="px-6 py-4 grid grid-cols-12 gap-6 items-start">
        <aside className="col-span-12 xl:col-span-5 xl:sticky xl:top-4">
          <IssueDossier issueId={id} wardName={wardName} sites={map?.sensitive_sites} onChanged={reload} />
        </aside>

        <section className="col-span-12 xl:col-span-7 flex flex-col gap-4">
          {error && <Card className="p-4 text-sm text-ws-error">Couldn't load {issueCode(id)}: {error}</Card>}
          {loading && !issue && <Skeleton className="h-96" />}
          {issue && (
            <>
              <EvidenceTimeline issue={issue} onChanged={reload} />

              <Card className="p-4 flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <SectionLabel>Citizen Reports ({issue.reports.length})</SectionLabel>
                </div>
                <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
                  {issue.reports.map((r) => (
                    <div key={r.id} className="p-3 rounded-lg bg-ws-surface-low flex flex-col gap-1">
                      <div className="flex items-center justify-between font-ws-headline text-[11px] text-[#535f74]">
                        <span>Report #{r.id}{r.location_phrase ? ` • ${r.location_phrase}` : ""}</span>
                        <span>{fmtTime(r.reported_at)}</span>
                      </div>
                      <p className="font-ws-body text-sm text-ws-on-surface">{r.translated_text ?? r.raw_text}</p>
                      {r.translated_text && <p className="font-ws-body text-xs text-[#535f74] italic">Original ({r.language}): {r.raw_text}</p>}
                    </div>
                  ))}
                </div>
              </Card>

              <Card className="p-4 flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <SectionLabel>Linked Public Works ({issue.matches.length})</SectionLabel>
                  <span className="font-ws-label text-[11px] text-[#535f74]">MPLADS records matched by category, text and distance</span>
                </div>
                {issue.matches.length === 0 ? (
                  <p className="font-ws-body text-sm text-ws-on-surface-variant">No funded public work matched this issue above the match threshold.</p>
                ) : (
                  issue.matches.map((m) => (
                    <Link key={m.match_id} to={`/works/${m.work_id}`} className="p-3 rounded-lg bg-ws-surface-container hover:bg-ws-surface-high transition-all flex flex-col gap-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-ws-body text-sm font-semibold text-ws-on-surface">MPLADS-{m.work_id}: {m.work?.work_name}</span>
                        <span className="font-ws-headline text-xs font-semibold text-ws-on-surface shrink-0">{inr(m.work?.cost)}</span>
                      </div>
                      <p className="font-ws-body text-xs text-[#535f74]">{m.match_reason}</p>
                      <div className="flex gap-4 font-ws-headline text-[11px] text-ws-on-surface-variant">
                        <span>Score <strong className="text-ws-primary">{m.combined_score.toFixed(2)}</strong></span>
                        <span>Distance <strong>{m.distance_m != null ? `${Math.round(m.distance_m)} m` : "—"}</strong></span>
                        <span>Since completion <strong>{m.days_since_completion != null ? `${m.days_since_completion} d` : "—"}</strong></span>
                        {m.work?.status && <span className="uppercase">{m.work.status}</span>}
                      </div>
                    </Link>
                  ))
                )}
              </Card>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {issue.priority_breakdown && (
                  <Card className="p-4 flex flex-col gap-3">
                    <SectionLabel>Priority Formula</SectionLabel>
                    <PriorityBreakdownView breakdown={issue.priority_breakdown} />
                  </Card>
                )}
                <Card className="p-4 flex flex-col gap-3">
                  <SectionLabel>Anomaly Signals for Human Review ({issue.signals.length})</SectionLabel>
                  {issue.signals.length === 0 ? (
                    <p className="font-ws-body text-sm text-ws-on-surface-variant">No anomaly signals raised for this issue.</p>
                  ) : (
                    issue.signals.map((s) => (
                      <div key={s.signal_id} className="p-3 rounded-lg bg-amber-50 flex flex-col gap-1">
                        <span className="font-ws-body text-sm font-semibold text-amber-900">{s.rule_name.replace(/_/g, " ")}</span>
                        <p className="font-ws-body text-xs text-ws-on-surface-variant">{s.explanation}</p>
                        <details className="font-ws-headline text-[11px] text-[#535f74]">
                          <summary className="cursor-pointer">Source record ids</summary>
                          <pre className="mt-1 p-2 bg-white rounded overflow-auto">{JSON.stringify(s.source_record_ids, null, 2)}</pre>
                        </details>
                      </div>
                    ))
                  )}
                </Card>
              </div>
            </>
          )}
        </section>
      </div>
    </Page>
  );
}
export default IssueDetail;
