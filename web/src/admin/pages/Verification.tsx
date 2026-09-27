import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CATEGORY_LABELS } from "../../api/types";
import type { EvidenceItem, IssueDetailResponse, MapSitePoint } from "../../api/types";
import { useEvidencePhoto } from "../components/EvidenceTimeline";
import { Icon, Card, BandChip, issueCode, fmtTime, metres, bearing, SITE_ICON, Page, Skeleton, landmark } from "../components/ws";

// Stitch "Location-Verified Evidence Workspace":
// WardSentry-UI-References/admin-stitch/wardsentry_location_verified_evidence_workspace
// Every number is computed from GET /api/evidence and GET /api/issues/:id.

/** Same bar the capture screen uses to warn the photographer (EvidenceUpload POOR_ACCURACY_M). */
const GPS_DRIFT_M = 100;
/** Review threshold for "photo taken far from the reported location". A prompt for human review, not a verdict. */
const DISTANCE_REVIEW_M = 50;
const DAY = 86_400_000;

type Filter = "all" | "pending" | "verified" | "drift" | "distance";

function matches(e: EvidenceItem, f: Filter) {
  return f === "all" ? true
    : f === "pending" ? e.review_status === "pending_review"
    : f === "verified" ? e.review_status === "verified"
    : f === "drift" ? e.accuracy_m > GPS_DRIFT_M
    : (e.distance_from_issue_m ?? 0) > DISTANCE_REVIEW_M;
}

async function loadWorkspace() {
  const [evidence, top, map] = await Promise.all([
    api.evidenceQueue(),
    api.listIssues({ limit: 20 }),
    api.map(),
  ]);
  return { evidence, top: top.items, wards: new Map(map.wards.map((w) => [w.ward_id, w.name])), sites: map.sensitive_sites };
}

export function Verification() {
  const { data, loading, error, reload } = useApi(loadWorkspace, []);
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("all");

  const ev = useMemo(() => data?.evidence ?? [], [data]);
  const count = (f: Filter) => ev.filter((e) => matches(e, f)).length;

  // Target issues: those with evidence in the current filter, else the top-priority issues.
  const targets = useMemo(() => {
    const ids = [...new Set(ev.filter((e) => matches(e, filter)).map((e) => e.issue_id))];
    if (ids.length || filter !== "all") return ids.map((id) => ({ id, hasEvidence: true }));
    return (data?.top ?? []).map((i) => ({ id: i.issue_id, hasEvidence: false }));
  }, [ev, filter, data]);
  const targetId = Number(params.get("id")) || targets[0]?.id || null;

  const pending = count("pending");
  const last24 = ev.filter((e) => Date.now() - Date.parse(e.submitted_at) < DAY).length;
  const meanAcc = ev.length ? ev.reduce((a, e) => a + e.accuracy_m, 0) / ev.length : null;
  const underDrift = ev.length ? (100 * ev.filter((e) => e.accuracy_m <= GPS_DRIFT_M).length) / ev.length : null;
  const flagged = ev.filter((e) => e.review_status === "review_required").length;
  const reviewed = ev.filter((e) => e.review_status !== "pending_review");
  const confidence = reviewed.length ? (100 * reviewed.filter((e) => e.review_status === "verified").length) / reviewed.length : null;

  return (
    <Page>
      {/* Breadcrumb bar */}
      <div className="px-6 py-3 bg-ws-surface-low flex flex-wrap items-center justify-between gap-3 font-ws-label">
        <div className="flex items-center gap-2 text-xs text-[#535f74]">
          <span className="px-1.5 py-0.5 rounded bg-ws-blue text-white text-[11px] font-bold">PMC-AUDIT</span>
          <span>/</span>
          <span>Field Verification</span>
          <span>/</span>
          <span className="font-ws-body text-sm text-ws-on-surface font-semibold">Location-Verified Evidence Workspace</span>
          {targetId && <span className="px-1.5 py-0.5 rounded bg-ws-surface-high font-ws-headline text-[11px] text-ws-on-surface-variant">{issueCode(targetId)}</span>}
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-ws-primary/10 text-ws-primary text-[11px] font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-ws-primary animate-pulse" /> REVIEW QUEUE LIVE
          </span>
          <ExportButton issueId={targetId} evidence={ev.filter((e) => e.issue_id === targetId)} />
        </div>
      </div>

      <div className="px-6 py-4 flex flex-col gap-4">
        {/* KPIs */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Kpi title="Queue Volume" icon="assignment_turned_in" value={String(pending)} unit="Pending Verification"
            note={`${last24} submission${last24 === 1 ? "" : "s"} added in last 24h`} dot="bg-ws-blue" />
          <Kpi title="GPS Accuracy" icon="social_distance" value={meanAcc != null ? meanAcc.toFixed(1) : "—"} suffix={meanAcc != null ? "m" : ""}
            unit="Mean device accuracy" note={underDrift != null ? `${underDrift.toFixed(0)}% within ${GPS_DRIFT_M} m` : "No captures yet"} dot="bg-ws-blue" />
          <Kpi title="Flagged for Review" icon="flag" value={String(flagged)} unit="Needs human review" valueCls="text-ws-error"
            note="Marked by a reviewer, not automatic" dot="bg-ws-error" />
          <Kpi title="Review Confidence" icon="verified_user" value={confidence != null ? `${confidence.toFixed(1)}%` : "—"}
            unit={`${reviewed.length} reviewed`} note="Share of reviewed captures verified" dot="bg-ws-blue" />
        </div>

        {/* Filter bar */}
        <div className="bg-ws-surface-low rounded-xl p-2 flex flex-wrap items-center justify-between gap-2 font-ws-label">
          <div className="flex flex-wrap items-center gap-1">
            {([
              ["all", `All Submissions (${count("all")})`],
              ["pending", `Pending Audit (${count("pending")})`],
              ["verified", `Verified (${count("verified")})`],
              ["drift", `GPS Drift > ${GPS_DRIFT_M}m (${count("drift")})`, "bg-ws-error"],
              ["distance", `Distance > ${DISTANCE_REVIEW_M}m (${count("distance")})`, "bg-ws-error"],
            ] as [Filter, string, string?][]).map(([f, label, dot]) => (
              <button key={f} onClick={() => { setFilter(f); setParams({}, { replace: true }); }}
                className={`px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  filter === f ? "bg-ws-blue text-white" : "text-[#535f74] hover:text-ws-on-surface"
                }`}>
                {dot && <span className={`w-1.5 h-1.5 rounded-full ${filter === f ? "bg-white" : dot}`} />}
                {label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-[11px] text-[#535f74]">
            Target Audit ID:
            <select value={targetId ?? ""} onChange={(e) => setParams({ id: e.target.value }, { replace: true })}
              className="px-2 py-1 rounded bg-ws-surface-high font-ws-headline text-xs text-ws-on-surface outline-none cursor-pointer">
              {targets.map((t) => <option key={t.id} value={t.id}>{issueCode(t.id)}{t.hasEvidence ? "" : " (no evidence yet)"}</option>)}
            </select>
          </label>
        </div>

        {error && <Card className="p-4 text-sm text-ws-error">Couldn't load the verification queue: {error}</Card>}
        {loading && !data && <Skeleton className="h-[600px]" />}
        {data && !ev.length && (
          <Card className="p-3 flex items-center gap-2 text-xs text-ws-on-surface-variant">
            <Icon name="info" className="text-[18px] text-ws-primary" />
            No location-verified photos have been submitted yet. Showing the highest-priority issues so their evidence status can be reviewed.
          </Card>
        )}
        {data && targets.length === 0 && <Card className="p-6 text-sm text-ws-on-surface-variant">No submissions match this filter.</Card>}
        {data && targetId && (
          <Workspace key={targetId} issueId={targetId} wards={data.wards} sites={data.sites} onChanged={reload} />
        )}

        {data && <PipelineGraph evidence={ev} />}
      </div>
    </Page>
  );
}

function Workspace({ issueId, wards, sites, onChanged }: {
  issueId: number;
  wards: Map<number, string>;
  sites: MapSitePoint[];
  onChanged: () => void;
}) {
  const { data: issue, error, reload } = useApi(() => api.issueDetail(issueId), [issueId]);
  const { data: workers } = useApi(() => api.fieldWorkers().catch(() => []), []);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (error) return <Card className="p-4 text-sm text-ws-error">Couldn't load {issueCode(issueId)}: {error}</Card>;
  if (!issue) return <Skeleton className="h-[600px]" />;

  const before = issue.evidence.find((e) => e.evidence_type === "initial_report") ?? null;
  const after = [...issue.evidence].reverse().find((e) => e.evidence_type === "resolution") ?? null;
  const workerName = issue.assigned_worker_id != null
    ? workers?.find((w) => w.id === issue.assigned_worker_id)?.display_name ?? `Field worker #${issue.assigned_worker_id}`
    : null;
  const pairDelta = before && after ? metres(before.location, after.location) : null;
  const delta = after?.distance_from_issue_m ?? before?.distance_from_issue_m ?? null;
  const report = issue.reports[0] ?? null;
  const wardName = issue.ward_id != null ? wards.get(issue.ward_id) : null;
  const nearestSite = issue.location
    ? sites.filter((s) => s.kind === "hospital" || s.kind === "school")
        .map((s) => ({ s, d: metres(issue.location!, s.location) }))
        .sort((a, b) => a.d - b.d)[0] ?? null
    : null;

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      setNote("");
      reload();
      onChanged();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  const verdict =
    delta == null ? { ok: null as boolean | null, text: "No geo-tagged photo yet" }
    : delta <= DISTANCE_REVIEW_M && (after ?? before)!.accuracy_m <= GPS_DRIFT_M
      ? { ok: true, text: `Consistent with reported location (Δ ${delta.toFixed(1)}m)` }
      : { ok: false, text: `Needs human review (Δ ${delta.toFixed(1)}m)` };

  return (
    <div className="bg-white rounded-xl shadow-sm p-5 flex flex-col gap-5 font-ws-label">
      {/* Incident header */}
      <div className="p-4 rounded-lg bg-ws-surface-low flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="px-1.5 py-0.5 rounded bg-ws-blue text-white text-[11px] font-bold uppercase">Incident {issueCode(issue.issue_id)}</span>
            <span className="font-ws-headline text-lg text-ws-on-surface font-semibold">
              {CATEGORY_LABELS[issue.category] ?? issue.category}{landmark(report?.location_phrase) ? ` near ${report!.location_phrase}` : ""}
            </span>
            <BandChip score={issue.priority_score} soft />
          </div>
          <p className="font-ws-body text-xs text-[#535f74]">
            {issue.ward_id != null ? `Ward ${issue.ward_id}${wardName ? ` (${wardName})` : ""}` : "Ward unknown"} • {issue.report_count} report(s)
            {issue.matches[0]?.work ? ` • Public work MPLADS-${issue.matches[0].work_id}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-[11px] text-[#535f74] uppercase font-semibold">Evidence Match Verdict</div>
            <div className={`text-xs font-semibold flex items-center gap-1 justify-end ${verdict.ok ? "text-ws-primary" : verdict.ok === false ? "text-amber-700" : "text-[#535f74]"}`}>
              <Icon name={verdict.ok ? "check_circle" : verdict.ok === false ? "error" : "radio_button_unchecked"} className="text-[16px]" />
              {verdict.text}
            </div>
          </div>
          <Link to={`/issues/${issue.issue_id}`} title="Open issue dossier" className="w-9 h-9 rounded-lg bg-ws-primary/10 text-ws-primary flex items-center justify-center hover:bg-ws-primary/20">
            <Icon name="open_in_new" className="text-[20px]" />
          </Link>
        </div>
      </div>

      {/* Comparator */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <EvidencePanel stage="Before Record" title="Citizen Location-Verified Evidence" tagCls="bg-ws-navy" item={before}
          empty={issue.reports.length ? "Citizen report has no in-app photo" : "No citizen report"}
          rows={before ? [
            ["Reporting actor", `Citizen user #${before.submitted_by}`],
            ["Capture method", "In-app camera, live location"],
            ["Upload delay", lag(before.captured_at, before.submitted_at)],
            ["Location fix age", lag(before.location_captured_at, before.captured_at)],
          ] : [["Report", report ? fmtTime(report.reported_at) : "—"], ["Location basis", issue.location_precision === "precise" ? "Precise point" : "Ward centroid"]]} />
        <EvidencePanel stage="After Resolution" title="Field Worker Completion Evidence" tagCls="bg-ws-blue" item={after}
          empty={workerName ? "Awaiting completion photo" : "No crew assigned"}
          rows={after ? [
            ["Executing officer", workerName ?? `User #${after.submitted_by}`],
            ["Capture method", "In-app camera, live location"],
            ["Distance to citizen point", pairDelta != null ? `${pairDelta.toFixed(1)} m${pairDelta <= DISTANCE_REVIEW_M ? " [WITHIN RANGE]" : " [REVIEW]"}` : "No citizen photo"],
            ["File integrity", `SHA-256 ${after.sha256.slice(0, 10)}… (${Math.round(after.byte_size / 1024)} KB)`],
          ] : [["Assigned to", workerName ?? "Unassigned"], ["Assigned at", fmtTime(issue.assigned_at)]]} />
      </div>

      {/* Radar + chain of custody */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-lg bg-ws-navy text-white overflow-hidden flex flex-col">
          <div className="p-3 flex items-center justify-between gap-2 border-b border-white/10">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-ws-blue" />
              <span className="font-ws-headline text-sm font-semibold">Location Comparison</span>
              <span className="px-1.5 py-0.5 rounded bg-white/10 font-ws-headline text-[10px]">Radius: {DISTANCE_REVIEW_M}.0m Window</span>
            </div>
            <span className="font-ws-headline text-[11px] text-ws-tertiary-fixed">
              {delta != null ? `Distance: ${delta.toFixed(2)}m` : "No photo location"}
            </span>
          </div>
          <Radar issue={issue} before={before} after={after} />
          <div className="px-3 py-2 flex flex-wrap items-center justify-between gap-2 bg-black/20 font-ws-headline text-[11px] text-ws-surface-variant">
            <span>WGS 84</span>
            <span>
              Review threshold: &lt; {DISTANCE_REVIEW_M}.0m{" "}
              {delta != null && <strong className={delta <= DISTANCE_REVIEW_M ? "text-emerald-400" : "text-amber-400"}>[{delta <= DISTANCE_REVIEW_M ? "WITHIN" : "OUTSIDE"}]</strong>}
            </span>
            <span>Issue location: {issue.location_precision === "precise" ? "precise point" : "ward centroid"}</span>
          </div>
          <div className="p-3 flex items-center justify-between gap-2 border-t border-white/10 text-xs">
            <div className="flex items-center gap-2 min-w-0">
              <Icon name={nearestSite ? SITE_ICON[nearestSite.s.kind] ?? "shield" : "shield"} className="text-[18px] text-ws-tertiary-fixed" />
              <span className="text-ws-surface-variant">Sensitive site check:</span>
              <span className="truncate capitalize">
                {nearestSite ? `Nearest ${nearestSite.s.kind} ${Math.round(nearestSite.d)}m ${bearing(issue.location!, nearestSite.s.location)}` : "No location to check"}
              </span>
            </div>
            {nearestSite && (
              <span className={`px-2 py-0.5 rounded text-[11px] font-bold shrink-0 ${nearestSite.d <= 500 ? "bg-amber-500" : "bg-ws-blue"}`}>
                {nearestSite.d <= 500 ? "PRIORITY ZONE" : "CLEAR TO AUDIT"}
              </span>
            )}
          </div>
        </div>

        <div className="rounded-lg bg-ws-surface-low p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="font-ws-headline text-sm text-ws-on-surface font-semibold">Evidence Chain of Custody</span>
            <Icon name="history_edu" className="text-[18px] text-ws-primary" />
          </div>
          <ol className="flex flex-col gap-3">
            {custody(issue, workerName).map((s, i) => (
              <li key={i} className="flex gap-2">
                <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${s.state === "done" ? "bg-ws-blue" : s.state === "current" ? "bg-ws-tertiary-container ring-4 ring-ws-tertiary-container/20" : "bg-ws-surface-highest"}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-xs font-semibold ${s.state === "current" ? "text-ws-primary" : s.state === "todo" ? "text-[#535f74]" : "text-ws-on-surface"}`}>{s.title}</span>
                    <span className="font-ws-headline text-[10px] text-[#535f74] shrink-0">{s.when}</span>
                  </div>
                  <p className="font-ws-body text-[11px] text-[#535f74]">{s.detail}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-auto pt-2 border-t border-ws-surface-highest text-[11px] text-[#535f74] flex justify-between">
            <span>File fingerprints:</span>
            <span className="font-ws-headline text-ws-primary font-semibold">SHA-256 recorded ({issue.evidence.length})</span>
          </div>
        </div>
      </div>

      {/* Decision bar */}
      <div className="rounded-lg bg-ws-surface-low p-4 flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Icon name="gavel" className="text-[20px] text-ws-primary" />
          <div>
            <div className="text-sm font-semibold text-ws-on-surface">Administrator Decision</div>
            <div className="text-[11px] text-[#535f74]">Recorded against the evidence with your name and time. Evidence supports a decision; it is not proof on its own.</div>
          </div>
        </div>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="Note for the record (optional)"
          className="w-full px-3 py-2 rounded-lg bg-white text-sm font-ws-body outline-none focus:ring-1 focus:ring-ws-primary" />
        <div className="flex flex-wrap gap-2">
          <button disabled={busy || !after} onClick={() => run(() => api.reviewEvidence(after!.evidence_id, "review_required", note || "Worker clarification requested"))}
            className="px-3 py-2 rounded bg-white hover:bg-ws-surface-high text-xs font-semibold text-ws-on-surface flex items-center gap-1.5 disabled:opacity-50">
            <Icon name="contact_support" className="text-[18px]" /> Request Worker Clarification
          </button>
          <button disabled={busy || !before} onClick={() => run(() => api.reviewEvidence(before!.evidence_id, "verified", note))}
            className="px-3 py-2 rounded bg-white hover:bg-ws-surface-high text-xs font-semibold text-ws-on-surface flex items-center gap-1.5 disabled:opacity-50">
            <Icon name="person_pin_circle" className="text-[18px]" /> Verify Citizen Evidence
          </button>
          <button disabled={busy || !report || !!before} onClick={() => run(() => api.startAlternativeVerification(report!.id, "phone", note))}
            className="px-3 py-2 rounded bg-white hover:bg-ws-surface-high text-xs font-semibold text-ws-on-surface flex items-center gap-1.5 disabled:opacity-50"
            title="For reports without a photo: confirm with the citizen by phone">
            <Icon name="send_to_mobile" className="text-[18px]" /> Confirm with Citizen by Phone
          </button>
          <button disabled={busy || !after || issue.status === "closed"} onClick={() => run(async () => {
              if (after!.review_status !== "verified") await api.reviewEvidence(after!.evidence_id, "verified", note);
              await api.closeIssue(issue.issue_id);
            })}
            className="ml-auto px-4 py-2 rounded bg-ws-blue hover:bg-ws-primary text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50">
            <Icon name="check_box" className="text-[18px]" /> {issue.status === "closed" ? "Resolved" : "Verify & Mark Resolved"}
          </button>
        </div>
        {actionError && <p className="text-xs text-ws-error">{actionError}</p>}
        {issue.alternative_verifications.length > 0 && (
          <p className="text-[11px] text-[#535f74]">
            Phone/other confirmations: {issue.alternative_verifications.map((a) => `${a.channel} — ${a.status}`).join(", ")}
          </p>
        )}
      </div>
    </div>
  );
}

function EvidencePanel({ stage, title, tagCls, item, empty, rows }: {
  stage: string; title: string; tagCls: string; item: EvidenceItem | null; empty: string; rows: [string, string][];
}) {
  return (
    <div className="rounded-lg bg-ws-surface-low p-3 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className={`px-1.5 py-0.5 rounded text-white text-[10px] font-bold uppercase ${tagCls}`}>{stage}</span>
        <span className="font-ws-headline text-sm font-semibold text-ws-on-surface">{title}</span>
        {item && (
          <span className={`ml-auto px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
            item.review_status === "verified" ? "bg-emerald-100 text-emerald-800" : item.review_status === "review_required" ? "bg-amber-100 text-amber-800" : "bg-ws-surface-high text-[#535f74]"
          }`}>
            {item.review_status.replace("_", " ")}
          </span>
        )}
      </div>
      {item ? <HudPhoto item={item} /> : (
        <div className="aspect-[4/3] rounded-lg bg-ws-surface-container flex flex-col items-center justify-center gap-1 text-xs text-[#535f74]">
          <Icon name="no_photography" className="text-[28px]" />{empty}
        </div>
      )}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex flex-col">
            <span className="text-[10px] text-[#535f74] uppercase font-semibold">{k}</span>
            <span className="font-ws-headline text-[11px] text-ws-on-surface">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HudPhoto({ item }: { item: EvidenceItem }) {
  const { src, failed } = useEvidencePhoto(item.file_url);
  return (
    <div className="relative aspect-[4/3] rounded-lg overflow-hidden bg-ws-navy">
      {src && !failed ? <img src={src} alt={`${item.actor_type} evidence`} className="w-full h-full object-cover" />
        : failed ? <div className="w-full h-full flex items-center justify-center text-xs text-ws-surface-variant">Photo couldn't be loaded</div>
        : <div className="w-full h-full animate-pulse" />}
      <div className="absolute inset-0 p-2 flex flex-col justify-between font-ws-headline text-[10px] text-white pointer-events-none">
        <div className="flex justify-between gap-2">
          <span className="px-1.5 py-0.5 rounded bg-ws-navy/80">LAT: {item.location.lat.toFixed(4)}° N • LON: {item.location.lon.toFixed(4)}° E</span>
          <span className="px-1.5 py-0.5 rounded bg-ws-blue">{item.evidence_type === "resolution" ? "WORK RESOLUTION" : "INCIDENT PRIMARY"}</span>
        </div>
        <div className="flex justify-between items-end gap-2">
          <div className="px-1.5 py-1 rounded bg-ws-navy/80">
            <div>{fmtTime(item.captured_at ?? item.submitted_at)}</div>
            <div className="text-ws-surface-variant">Device accuracy: ±{item.accuracy_m.toFixed(1)}m</div>
          </div>
          <span className="px-1.5 py-0.5 rounded bg-ws-navy/80">HASH: {item.sha256.slice(0, 6)}…{item.sha256.slice(-4)}</span>
        </div>
      </div>
    </div>
  );
}

/** Issue point at the centre; photo locations plotted at their true offsets, scaled to the review window. */
function Radar({ issue, before, after }: { issue: IssueDetailResponse; before: EvidenceItem | null; after: EvidenceItem | null }) {
  const R = 110;
  const origin = issue.location;
  const pts = [
    before && { e: before, label: "A (Citizen)", color: "#f59e0b" },
    after && { e: after, label: "B (Worker)", color: "#10b981" },
  ].filter(Boolean) as { e: EvidenceItem; label: string; color: string }[];
  const place = (e: EvidenceItem) => {
    if (!origin) return { x: 0, y: 0 };
    const dx = (e.location.lon - origin.lon) * 111_320 * Math.cos((origin.lat * Math.PI) / 180);
    const dy = (e.location.lat - origin.lat) * 110_540;
    const d = Math.hypot(dx, dy);
    const k = d > DISTANCE_REVIEW_M * 1.4 ? (DISTANCE_REVIEW_M * 1.4) / d : 1; // clamp far points to the edge
    return { x: (dx * k * R) / DISTANCE_REVIEW_M, y: (-dy * k * R) / DISTANCE_REVIEW_M };
  };
  return (
    <svg viewBox="-200 -150 400 300" className="w-full h-64 bg-[#070e19]">
      <defs>
        <pattern id="ws-radar-grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1e293b" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect x="-200" y="-150" width="400" height="300" fill="url(#ws-radar-grid)" />
      <circle r={R} fill="rgba(0,112,243,0.06)" stroke="#0070f3" strokeDasharray="4 4" />
      <text y={-R - 6} textAnchor="middle" fontSize="9" fill="#93ccff" fontFamily="Space Grotesk">{DISTANCE_REVIEW_M}m review perimeter</text>
      <circle r="4" fill="#0070f3" stroke="#fff" strokeWidth="1.5" />
      <text x="7" y="-6" fontSize="9" fill="#fff" fontFamily="Space Grotesk">Reported location</text>
      {pts.map(({ e, label, color }) => {
        const p = place(e);
        const acc = Math.min(R * 1.4, (e.accuracy_m * R) / DISTANCE_REVIEW_M);
        return (
          <g key={e.evidence_id}>
            <line x1="0" y1="0" x2={p.x} y2={p.y} stroke={color} strokeWidth="1" strokeDasharray="2 2" />
            <circle cx={p.x} cy={p.y} r={acc} fill={color} fillOpacity="0.08" stroke={color} strokeOpacity="0.4" />
            <circle cx={p.x} cy={p.y} r="4" fill={color} stroke="#fff" strokeWidth="1.5" />
            <text x={p.x + 7} y={p.y + 3} fontSize="9" fill="#fff" fontFamily="Space Grotesk">
              {label} {e.distance_from_issue_m != null ? `${e.distance_from_issue_m.toFixed(1)}m` : ""}
            </text>
          </g>
        );
      })}
      {!pts.length && <text y="40" textAnchor="middle" fontSize="10" fill="#8ea0bd" fontFamily="Inter">No photo locations to compare yet</text>}
    </svg>
  );
}

function custody(issue: IssueDetailResponse, workerName: string | null) {
  const before = issue.evidence.find((e) => e.evidence_type === "initial_report");
  const after = [...issue.evidence].reverse().find((e) => e.evidence_type === "resolution");
  const reviewed = after && after.review_status !== "pending_review";
  const steps: { title: string; when: string; detail: string; state: "done" | "current" | "todo" }[] = [
    { title: "Report Created", when: fmtTime(issue.first_reported), detail: `${issue.report_count} citizen report(s) clustered into this issue.`, state: "done" },
    before
      ? { title: "Citizen Photo Captured", when: fmtTime(before.submitted_at), detail: `±${before.accuracy_m.toFixed(1)}m, ${before.distance_from_issue_m != null ? `${before.distance_from_issue_m.toFixed(1)}m from report` : "no issue location"}.`, state: "done" }
      : { title: "Citizen Photo", when: "Not provided", detail: "Report has no in-app photo; confirm by phone if needed.", state: "todo" },
    issue.assigned_at
      ? { title: "Work Order Dispatched", when: fmtTime(issue.assigned_at), detail: `Assigned to ${workerName ?? "field worker"}.`, state: "done" }
      : { title: "Work Order Dispatch", when: "Pending", detail: issue.routed_agency ? `Routed to ${issue.routed_agency}.` : "No crew assigned yet.", state: after ? "done" : "current" },
    after
      ? { title: "Worker Resolution Evidence", when: fmtTime(after.submitted_at), detail: `Completion photo, ±${after.accuracy_m.toFixed(1)}m.`, state: "done" }
      : { title: "Worker Resolution Evidence", when: "Pending", detail: "Awaiting completion photo.", state: issue.assigned_at ? "current" : "todo" },
    { title: "Admin Verification", when: reviewed ? fmtTime(after!.reviewed_at) : after ? "In session" : "Pending",
      detail: reviewed ? `Marked ${after!.review_status.replace("_", " ")}.` : "Compare before/after and record a decision.", state: reviewed ? "done" : after ? "current" : "todo" },
    { title: "Citizen Re-verification", when: issue.reverification_due_at ? `Until ${fmtTime(issue.reverification_due_at)}` : "Pending",
      detail: issue.feedback.length ? `${issue.feedback.length} citizen response(s).` : "Citizen can confirm or dispute after closure.",
      state: issue.feedback.length ? "done" : issue.status === "closed" ? "current" : "todo" },
  ];
  return steps;
}

function lag(from: string | null, to: string | null) {
  if (!from || !to) return "—";
  const s = Math.round((Date.parse(to) - Date.parse(from)) / 1000);
  return Math.abs(s) < 120 ? `${s}s` : `${Math.round(s / 60)} min`;
}

function Kpi({ title, icon, value, suffix = "", unit, note, dot, valueCls = "text-ws-on-surface" }: {
  title: string; icon: string; value: string; suffix?: string; unit: string; note: string; dot: string; valueCls?: string;
}) {
  return (
    <Card className="p-4 flex flex-col gap-2 font-ws-label">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-[#535f74] uppercase font-semibold tracking-[0.06em]">{title}</span>
        <Icon name={icon} className="text-[18px] text-ws-primary" />
      </div>
      <div className="flex items-baseline gap-2">
        <span className={`font-ws-headline text-3xl font-bold ${valueCls}`}>{value}<span className="text-base">{suffix}</span></span>
        <span className="text-[11px] text-ws-primary font-semibold">{unit}</span>
      </div>
      <div className="flex items-center gap-1.5 text-[11px] text-[#535f74]">
        <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />{note}
      </div>
    </Card>
  );
}

function PipelineGraph({ evidence }: { evidence: EvidenceItem[] }) {
  const citizen = evidence.filter((e) => e.actor_type === "citizen");
  const worker = evidence.filter((e) => e.actor_type === "worker");
  const within = evidence.filter((e) => e.distance_from_issue_m != null && e.distance_from_issue_m <= DISTANCE_REVIEW_M).length;
  const withDist = evidence.filter((e) => e.distance_from_issue_m != null).length;
  const verified = evidence.filter((e) => e.review_status === "verified").length;
  const nodes = [
    { tag: "Data Source", tagCls: "bg-[#ffe4e6] text-[#be123c]", title: "Citizen Captures", sub: "In-app camera + live location", a: `Photos: ${citizen.length}`, b: "Citizen app" },
    { tag: "Location Check", tagCls: "bg-[#dbeafe] text-[#1d4ed8]", title: `Within ${DISTANCE_REVIEW_M}m of report`, sub: "Distance photo → issue", a: `${within}/${withDist}`, b: withDist ? `${((100 * within) / withDist).toFixed(0)}% within` : "No data" },
    { tag: "Worker Join", tagCls: "bg-[#fef3c7] text-[#b45309]", title: "Field Resolution", sub: "Completion photo per issue", a: `Photos: ${worker.length}`, b: "Before/after linked" },
    { tag: "Human Review", tagCls: "bg-ws-surface-high text-ws-primary", title: "Administrator Decision", sub: "Verified or needs review", a: `Verified: ${verified}`, b: `${evidence.length - verified} open/flagged` },
  ];
  return (
    <Card className="p-5 flex flex-col gap-4 font-ws-label">
      <div>
        <span className="px-1.5 py-0.5 rounded bg-ws-surface-high text-[10px] font-bold uppercase text-ws-primary">Verification Flow</span>
        <h3 className="font-ws-headline text-xl text-ws-on-surface mt-1">Evidence Verification Pipeline</h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {nodes.map((n) => (
          <div key={n.tag} className="rounded-lg border border-ws-surface-highest p-3 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${n.tagCls}`}>{n.tag}</span>
              <span className="w-1.5 h-1.5 rounded-full bg-ws-blue" />
            </div>
            <div className="font-ws-body text-sm text-ws-on-surface mt-1">{n.title}</div>
            <p className="text-[11px] text-[#535f74]">{n.sub}</p>
            <div className="flex justify-between font-ws-headline text-[11px] mt-1">
              <span className="text-[#535f74]">{n.a}</span>
              <span className="text-ws-primary">{n.b}</span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ExportButton({ issueId, evidence }: { issueId: number | null; evidence: EvidenceItem[] }) {
  return (
    <button
      disabled={!issueId}
      onClick={async () => {
        const detail = await api.issueDetail(issueId!);
        const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), issue: detail, evidence }, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = Object.assign(document.createElement("a"), { href: url, download: `chain-of-custody-PMC-${issueId}.json` });
        a.click();
        URL.revokeObjectURL(url);
      }}
      className="px-3 py-1 rounded bg-white text-xs font-semibold text-ws-primary flex items-center gap-1 shadow-sm hover:bg-ws-surface-high disabled:opacity-50"
    >
      <Icon name="file_download" className="text-[16px]" /> Export Chain of Custody
    </button>
  );
}

export default Verification;
