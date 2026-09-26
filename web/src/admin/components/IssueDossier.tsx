import { useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, TileLayer, CircleMarker } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { api, mediaUrl, ApiError } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CATEGORY_LABELS } from "../../api/types";
import type { EvidenceItem, IssueDetailResponse, MapSitePoint } from "../../api/types";
import { useEvidencePhoto } from "./EvidenceTimeline";
import { Icon, SITE_ICON, issueCode, fmtTime, metres, bearing, SectionLabel, landmark } from "./ws";

// Right-hand dossier from the Stitch "Issues Triage" screen
// (WardSentry-UI-References/admin-stitch/wardsentry_issues_evidence_dossier).
// Everything shown comes from GET /api/issues/:id; nothing is filled in.

const BUFFER_M = 500;

export function IssueDossier({ issueId, wardName, sites, onChanged }: {
  issueId: number;
  wardName?: string | null;
  sites?: MapSitePoint[];
  onChanged?: () => void;
}) {
  const { data: issue, loading, error, reload } = useApi(() => api.issueDetail(issueId), [issueId]);
  if (error) return <div className="bg-white rounded-xl p-6 text-sm text-ws-error">Couldn't load {issueCode(issueId)}: {error}</div>;
  if (loading && !issue) return <div className="bg-white rounded-xl h-[640px] animate-pulse" />;
  if (!issue) return null;
  return (
    <DossierBody
      issue={issue}
      wardName={wardName ?? null}
      sites={sites}
      onChanged={() => {
        reload();
        onChanged?.();
      }}
    />
  );
}

function DossierBody({ issue, wardName, sites, onChanged }: {
  issue: IssueDetailResponse;
  wardName: string | null;
  sites?: MapSitePoint[];
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const { data: workers } = useApi(() => api.fieldWorkers().catch(() => []), []);

  const citizenEv = issue.evidence.find((e) => e.actor_type === "citizen") ?? null;
  const workerEv = [...issue.evidence].reverse().find((e) => e.evidence_type === "resolution") ?? null;
  const reportPhoto = issue.reports.find((r) => r.photo_url) ?? null;
  const report = issue.reports[0] ?? null;
  const place = landmark(report?.location_phrase);
  const match = issue.matches[0] ?? null;
  const worker = issue.assigned_worker_id != null ? workers?.find((w) => w.id === issue.assigned_worker_id) : null;
  const workerName = worker?.display_name ?? (issue.assigned_worker_id != null ? `Field worker #${issue.assigned_worker_id}` : null);

  const delta = workerEv?.distance_from_issue_m ?? citizenEv?.distance_from_issue_m ?? null;
  const verified = issue.evidence.some((e) => e.review_status === "verified");
  const due = issue.reverification_due_at ? Date.parse(issue.reverification_due_at) - Date.now() : null;

  const nearby = issue.location && sites
    ? sites
        .map((s) => ({ s, d: metres(issue.location!, s.location) }))
        .filter((x) => x.d <= BUFFER_M)
        .sort((a, b) => a.d - b.d)
        .filter((x, i, all) => all.findIndex((y) => y.s.kind === x.s.kind) === i) // nearest of each kind
    : [];

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      onChanged();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  const trail = auditTrail(issue, workerName);

  return (
    <div className="bg-white rounded-xl shadow-sm overflow-hidden font-ws-label">
      {/* Header */}
      <div className="p-4 bg-gradient-to-r from-ws-surface-container to-ws-surface-high flex items-start justify-between gap-3">
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-ws-headline text-lg text-ws-on-surface font-bold">Dossier {issueCode(issue.issue_id)}</span>
            {verified ? (
              <span className="px-2 py-0.5 rounded-full bg-ws-primary text-white text-[11px] font-bold">VERIFIED MATCH</span>
            ) : match ? (
              <span className="px-2 py-0.5 rounded-full bg-ws-tertiary-container text-white text-[11px] font-bold">LINKED WORK</span>
            ) : null}
          </div>
          <span className="font-ws-body text-sm text-[#535f74]">
            {CATEGORY_LABELS[issue.category] ?? issue.category}
            {place ? ` • ${place}` : ""}
            {issue.ward_id != null ? ` • Ward ${issue.ward_id}${wardName ? ` ${wardName}` : ""}` : ""}
          </span>
        </div>
        <Link to={`/issues/${issue.issue_id}`} title="Open full dossier"
          className="p-1.5 rounded-lg bg-white text-[#535f74] hover:text-ws-on-surface shadow-sm shrink-0">
          <Icon name="share_location" className="text-[20px]" />
        </Link>
      </div>

      {/* Scorecard */}
      <div className="grid grid-cols-3 p-2 bg-ws-surface-low text-center gap-2">
        <Score label="Geo Delta" value={delta != null ? `${delta.toFixed(1)} m` : "—"}
          sub={delta != null ? "From reported location" : "No geo-tagged photo"} tone={delta != null ? "text-ws-primary" : "text-ws-on-surface-variant"} />
        <Score label="Priority" value={issue.priority_score?.toFixed(2) ?? "—"}
          sub={issue.priority_breakdown?.severity_band ? `Severity: ${issue.priority_breakdown.severity_band}` : "Formula score"} />
        {due != null ? (
          <Score label="Sign-off Window" value={due > 0 ? clock(due) : "Closed"} sub={due > 0 ? "Citizen re-verification" : "Window ended"}
            tone={due > 0 ? "text-ws-error" : "text-ws-on-surface-variant"} />
        ) : (
          <Score label="Open For" value={`${Math.round(issue.priority_breakdown?.time_open_days ?? 0)} d`}
            sub={`${issue.report_count} report${issue.report_count === 1 ? "" : "s"}`} tone="text-ws-error" />
        )}
      </div>

      {/* Evidence comparison */}
      <div className="p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-ws-on-surface uppercase tracking-wide flex items-center gap-1.5">
            <Icon name="compare" className="text-[18px] text-ws-primary" />
            Photo & Location Evidence
          </span>
          <span className="font-ws-headline text-[11px] text-ws-primary font-semibold">
            {issue.evidence.length} geo-tagged
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-2">
            {citizenEv ? (
              <EvidenceFrame item={citizenEv} tag="Citizen Report" tagCls="bg-ws-navy/80" />
            ) : reportPhoto?.photo_url ? (
              <Frame src={mediaUrl(reportPhoto.photo_url)} tag="Citizen Report" tagCls="bg-ws-navy/80"
                line1="Photo without device location" line2={fmtTime(reportPhoto.reported_at)} />
            ) : (
              <Empty tag="Citizen Report" text="No citizen photo" />
            )}
            <Meta title="Citizen Capture">
              <span>{citizenEv ? `Camera capture • ±${citizenEv.accuracy_m.toFixed(1)} m GPS` : report ? "Text report only" : "—"}</span>
              <span className="text-ws-tertiary">{citizenEv ? reviewLabel(citizenEv) : `${issue.report_count} report(s) clustered`}</span>
            </Meta>
          </div>
          <div className="flex flex-col gap-2">
            {workerEv ? (
              <EvidenceFrame item={workerEv} tag="Worker Fix" tagCls="bg-ws-primary" />
            ) : (
              <Empty tag="Worker Fix" text={issue.assigned_worker_id != null ? "Awaiting completion photo" : "No crew assigned yet"} />
            )}
            <Meta title="Worker Capture">
              <span>{workerName ?? "Unassigned"}</span>
              <span className="text-ws-primary font-semibold">
                {workerEv?.distance_from_issue_m != null
                  ? `Delta from report: ${workerEv.distance_from_issue_m.toFixed(1)} m (${reviewLabel(workerEv)})`
                  : "No resolution evidence yet"}
              </span>
            </Meta>
          </div>
        </div>

        {issue.location && (
          <div className="w-full h-28 rounded-lg relative overflow-hidden shadow-sm mt-1">
            <MapContainer center={[issue.location.lat, issue.location.lon]} zoom={16} zoomControl={false} dragging={false}
              scrollWheelZoom={false} doubleClickZoom={false} attributionControl={false} style={{ height: "100%", width: "100%" }}>
              <TileLayer className="ward-map__tiles" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <CircleMarker center={[issue.location.lat, issue.location.lon]} radius={7} pathOptions={{ color: "#fff", weight: 2, fillColor: "#0070f3", fillOpacity: 1 }} />
              {issue.evidence.map((e) => (
                <CircleMarker key={e.evidence_id} center={[e.location.lat, e.location.lon]} radius={5}
                  pathOptions={{ color: "#fff", weight: 1.5, fillColor: e.actor_type === "worker" ? "#10b981" : "#f59e0b", fillOpacity: 1 }} />
              ))}
            </MapContainer>
            <div className="absolute bottom-2 left-2 right-2 z-[500] bg-white/90 backdrop-blur-md px-2.5 py-1.5 rounded flex items-center justify-between gap-2 shadow-sm">
              <div className="flex items-center gap-2 min-w-0">
                <Icon name="pin_drop" className="text-[18px] text-ws-primary" />
                <span className="font-ws-body text-xs text-ws-on-surface font-semibold truncate">
                  {issue.location_precision === "precise" ? "Reported point" : "Ward centroid (approximate)"}
                  {place ? `: ${place}` : issue.ward_id != null ? `: Ward ${issue.ward_id}` : ""}
                </span>
              </div>
              <span className="font-ws-headline text-[11px] text-[#535f74] shrink-0">
                {issue.location.lat.toFixed(4)}, {issue.location.lon.toFixed(4)}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Audit trail */}
      <div className="px-4 py-3 bg-ws-surface-low flex flex-col gap-2">
        <SectionLabel>Verification Audit Trail</SectionLabel>
        <div className="flex flex-col gap-3 pl-4">
          {trail.map((t, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${t.current ? "bg-ws-tertiary-container animate-pulse" : "bg-ws-primary"}`} />
              <div className="flex flex-col">
                <span className={`font-ws-body text-[13px] font-semibold ${t.current ? "text-ws-tertiary font-bold" : "text-ws-on-surface"}`}>{t.title}</span>
                <span className="font-ws-headline text-[11px] text-[#535f74]">{t.detail}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="p-4 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          {issue.status === "closed" ? (
            <div className="flex-1 px-4 py-2.5 rounded bg-emerald-50 text-emerald-800 text-xs font-semibold flex items-center justify-center gap-2">
              <Icon name="task_alt" className="text-[18px]" /> Closed {fmtTime(issue.closed_at)}
            </div>
          ) : workerEv ? (
            <>
              <button disabled={busy} onClick={() => run(async () => {
                  if (workerEv.review_status !== "verified") await api.reviewEvidence(workerEv.evidence_id, "verified");
                  await api.closeIssue(issue.issue_id);
                })}
                className="flex-1 px-4 py-2.5 rounded bg-ws-blue hover:bg-ws-primary text-white text-xs font-semibold shadow-sm transition-all flex items-center justify-center gap-2 disabled:opacity-60">
                <Icon name="verified" className="text-[18px]" /> Approve Resolution & Close
              </button>
              <button disabled={busy} onClick={() => run(() => api.reviewEvidence(workerEv.evidence_id, "review_required", "Fix rejected from triage"))}
                className="px-4 py-2.5 rounded bg-ws-surface-container hover:bg-ws-surface-high text-ws-on-surface text-xs font-semibold transition-all flex items-center gap-2 disabled:opacity-60">
                <Icon name="assignment_return" className="text-[18px]" /> Reject Fix
              </button>
            </>
          ) : (
            <>
              <button disabled={busy || !!issue.routed_agency} onClick={() => run(() => api.routeIssue(issue.issue_id))}
                className="flex-1 px-4 py-2.5 rounded bg-ws-blue hover:bg-ws-primary text-white text-xs font-semibold shadow-sm transition-all flex items-center justify-center gap-2 disabled:opacity-60">
                <Icon name="send" className="text-[18px]" /> {issue.routed_agency ? `Routed to ${issue.routed_agency}` : "Route to Department"}
              </button>
              <select disabled={busy} value="" onChange={(e) => e.target.value && run(() => api.assignIssue(issue.issue_id, Number(e.target.value)))}
                className="px-3 py-2.5 rounded bg-ws-surface-container hover:bg-ws-surface-high text-ws-on-surface text-xs font-semibold cursor-pointer outline-none">
                <option value="">{issue.assigned_worker_id != null ? "Reassign crew…" : "Assign crew…"}</option>
                {workers?.map((w) => <option key={w.id} value={w.id}>{w.display_name ?? `Worker #${w.id}`}</option>)}
              </select>
            </>
          )}
        </div>
        {actionError && <p className="text-xs text-ws-error">{actionError}</p>}
        <div className="flex items-center justify-between pt-1">
          {citizenEv && citizenEv.review_status !== "review_required" ? (
            <button disabled={busy} onClick={() => run(() => api.reviewEvidence(citizenEv.evidence_id, "review_required", "Location flagged for human review"))}
              className="text-[11px] font-semibold text-ws-error hover:underline flex items-center gap-1">
              <Icon name="warning" className="text-[16px]" /> Flag Location Anomaly
            </button>
          ) : <span />}
          {match?.work && (
            <Link to={`/works/${match.work.work_id}`} className="text-[11px] text-ws-primary font-semibold hover:underline flex items-center gap-0.5">
              Inspect Public Work MPLADS-{match.work.work_id} <Icon name="arrow_forward" className="text-[14px]" />
            </Link>
          )}
        </div>
      </div>

      {sites && (
        <div className="p-4 border-t border-ws-surface-container flex flex-col gap-2">
          <SectionLabel>Civic Assets in Buffer ({BUFFER_M}m)</SectionLabel>
          {nearby.length ? (
            <div className="space-y-2">
              {nearby.map(({ s, d }) => (
                <div key={s.site_id} className="flex items-center justify-between p-2 rounded bg-ws-surface-container text-xs">
                  <div className="flex items-center gap-2 capitalize">
                    <Icon name={SITE_ICON[s.kind] ?? "location_on"} className="text-[18px] text-ws-tertiary" />
                    <span className="font-ws-body text-ws-on-surface">{s.kind.replace(/_/g, " ")}</span>
                  </div>
                  <span className="font-ws-headline text-ws-on-surface-variant">{Math.round(d)}m {bearing(issue.location!, s.location)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="font-ws-body text-xs text-ws-on-surface-variant">No sensitive sites within {BUFFER_M} m of the issue location.</p>
          )}
        </div>
      )}
    </div>
  );
}

function clock(ms: number) {
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return `${h}:${String(m).padStart(2, "0")}h`;
}

function reviewLabel(e: EvidenceItem) {
  return e.review_status === "verified" ? "VERIFIED" : e.review_status === "review_required" ? "NEEDS REVIEW" : "PENDING REVIEW";
}

function auditTrail(issue: IssueDetailResponse, workerName: string | null) {
  const t: { title: string; detail: string; at: number; current?: boolean }[] = [];
  if (issue.first_reported) {
    const ce = issue.evidence.find((e) => e.actor_type === "citizen");
    t.push({
      title: ce ? "Incident Reported & Geo-tagged" : "Incident Reported",
      detail: `${fmtTime(issue.first_reported)} • ${ce ? `Citizen GPS ±${ce.accuracy_m.toFixed(1)} m` : `${issue.report_count} report(s), ${issue.location_precision === "precise" ? "precise point" : "ward-level location"}`}`,
      at: Date.parse(issue.first_reported),
    });
  }
  if (issue.routed_at) t.push({ title: `Routed to ${issue.routed_agency ?? "department"}`, detail: fmtTime(issue.routed_at), at: Date.parse(issue.routed_at) });
  if (issue.assigned_at) t.push({ title: "Work Order Dispatched", detail: `${fmtTime(issue.assigned_at)} • Assigned to ${workerName ?? "field worker"}`, at: Date.parse(issue.assigned_at) });
  for (const e of issue.evidence.filter((x) => x.evidence_type === "resolution")) {
    t.push({
      title: "Completion Photo Logged",
      detail: `${fmtTime(e.submitted_at)} • ${e.distance_from_issue_m != null ? `${e.distance_from_issue_m.toFixed(1)} m from report` : "no issue location"}, ±${e.accuracy_m.toFixed(1)} m`,
      at: Date.parse(e.submitted_at),
    });
  }
  if (issue.closed_at) t.push({ title: "Resolution Approved & Closed", detail: fmtTime(issue.closed_at), at: Date.parse(issue.closed_at) });
  for (const f of issue.feedback) {
    t.push({
      title: "Citizen Response",
      detail: `${fmtTime(f.submitted_at)} • ${f.resolved_confirmed ? "Confirmed fixed" : "Says not fixed"}${f.comment ? ` — ${f.comment}` : ""}`,
      at: Date.parse(f.submitted_at),
    });
  }
  t.sort((a, b) => a.at - b.at);

  const next =
    issue.status === "closed"
      ? issue.reverification_due_at && Date.parse(issue.reverification_due_at) > Date.now()
        ? { title: "Citizen Sign-off Window", detail: `Open until ${fmtTime(issue.reverification_due_at)}` }
        : null
      : issue.evidence.some((e) => e.evidence_type === "resolution")
        ? { title: "Admin Resolution Approval", detail: "Awaiting ward administrator review of the completion photo" }
        : issue.assigned_worker_id != null
          ? { title: "Field Work In Progress", detail: "Awaiting completion photo from the assigned crew" }
          : { title: "Awaiting Dispatch", detail: "Route to a department or assign a field crew" };
  if (next) t.push({ ...next, at: Infinity, current: true });
  return t;
}

function Score({ label, value, sub, tone = "text-ws-on-surface" }: { label: string; value: string; sub: string; tone?: string }) {
  return (
    <div className="p-2 bg-white rounded-lg shadow-sm">
      <span className="block text-[11px] font-semibold text-[#535f74] uppercase">{label}</span>
      <span className={`font-ws-headline text-base font-bold ${tone}`}>{value}</span>
      <span className="block font-ws-headline text-[10px] text-ws-tertiary truncate">{sub}</span>
    </div>
  );
}

function EvidenceFrame({ item, tag, tagCls }: { item: EvidenceItem; tag: string; tagCls: string }) {
  const { src, failed } = useEvidencePhoto(item.file_url);
  return (
    <Frame src={failed ? null : src} tag={tag} tagCls={tagCls}
      line1={`Lat ${item.location.lat.toFixed(4)}° N, Lng ${item.location.lon.toFixed(4)}° E`}
      line2={`${fmtTime(item.captured_at ?? item.submitted_at)} • Acc ±${item.accuracy_m.toFixed(1)}m`} />
  );
}

function Frame({ src, tag, tagCls, line1, line2 }: { src: string | null; tag: string; tagCls: string; line1: string; line2: string }) {
  return (
    <div className="relative rounded-lg overflow-hidden bg-ws-navy shadow-sm aspect-video">
      {src ? <img src={src} alt={tag} className="w-full h-full object-cover" /> : <div className="w-full h-full animate-pulse" />}
      <div className={`absolute top-2 left-2 px-1.5 py-0.5 rounded text-white text-[10px] uppercase font-bold tracking-wider ${tagCls}`}>{tag}</div>
      <div className="absolute bottom-2 left-2 right-2 p-1.5 rounded bg-ws-navy/90 text-white backdrop-blur-sm font-ws-headline">
        <div className="text-[10px] text-[#aec6ff] truncate">{line1}</div>
        <div className="text-[9px] text-ws-surface-variant truncate">{line2}</div>
      </div>
    </div>
  );
}

function Empty({ tag, text }: { tag: string; text: string }) {
  return (
    <div className="relative rounded-lg overflow-hidden bg-ws-surface-container aspect-video flex items-center justify-center">
      <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-ws-navy/80 text-white text-[10px] uppercase font-bold tracking-wider">{tag}</div>
      <span className="flex flex-col items-center gap-1 text-[11px] text-ws-on-surface-variant">
        <Icon name="no_photography" className="text-[22px]" />
        {text}
      </span>
    </div>
  );
}

function Meta({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="p-2.5 rounded-lg bg-ws-surface-container text-ws-on-surface flex flex-col gap-1 font-ws-headline text-[11px]">
      <span className="font-ws-label text-[11px] text-[#535f74] uppercase font-semibold">{title}</span>
      {children}
    </div>
  );
}
