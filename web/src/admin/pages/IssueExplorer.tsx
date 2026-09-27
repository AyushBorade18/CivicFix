import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CATEGORY_LABELS } from "../../api/types";
import type { IssueSummary, MapSitePoint } from "../../api/types";
import { IssueDossier } from "../components/IssueDossier";
import { Icon, CATEGORY_ICON, BandChip, band, issueCode, metres, Page, Subheader, LivePill, Segmented, Skeleton, landmark } from "../components/ws";

// Stitch "Issues Triage": WardSentry-UI-References/admin-stitch/wardsentry_issues_evidence_dossier

const PAGE = 10;
const BUFFER_M = 500;
const SENSITIVE_KINDS = new Set(["hospital", "school"]);

type Tab = "all" | "high" | "verification_pending" | "signoff";
type Stage = "all" | "open" | "assigned" | "closed";

async function loadTriage() {
  const [issues, pending, signoff, map] = await Promise.all([
    api.listAllIssues(),
    api.listAllIssues({ queue: "verification_pending" }),
    api.listAllIssues({ queue: "signoff" }),
    api.map(),
  ]);
  return {
    issues,
    pending: new Set(pending.map((i) => i.issue_id)),
    signoff: new Set(signoff.map((i) => i.issue_id)),
    wards: new Map(map.wards.map((w) => [w.ward_id, w.name])),
    sites: map.sensitive_sites,
    loadedAt: Date.now(),
  };
}

export function IssueExplorer() {
  const { data, loading, error, reload } = useApi(loadTriage, []);
  const { data: workers } = useApi(() => api.fieldWorkers().catch(() => []), []);
  const [params, setParams] = useSearchParams();

  const [tab, setTab] = useState<Tab>("all");
  const [stage, setStage] = useState<Stage>("all");
  const [search, setSearch] = useState("");
  const [wardId, setWardId] = useState("");
  const [category, setCategory] = useState("");
  const [nearSensitive, setNearSensitive] = useState(false);
  const [newestFirst, setNewestFirst] = useState(false);
  const [page, setPage] = useState(0);
  const now = useNow();

  useEffect(() => {
    const onSync = () => reload();
    window.addEventListener("ws:sync-layers", onSync);
    return () => window.removeEventListener("ws:sync-layers", onSync);
  }, [reload]);

  // Nearest hospital/school within the buffer, per issue.
  const nearest = useMemo(() => {
    const out = new Map<number, { site: MapSitePoint; d: number }>();
    if (!data) return out;
    const sites = data.sites.filter((s) => SENSITIVE_KINDS.has(s.kind));
    for (const i of data.issues) {
      if (!i.location) continue;
      let best: { site: MapSitePoint; d: number } | null = null;
      for (const s of sites) {
        const d = metres(i.location, s.location);
        if (d <= BUFFER_M && (!best || d < best.d)) best = { site: s, d };
      }
      if (best) out.set(i.issue_id, best);
    }
    return out;
  }, [data]);

  const inTab = (i: IssueSummary, t: Tab) =>
    t === "all" ? true
    : t === "high" ? band(i.priority_score) === "high"
    : t === "verification_pending" ? !!data?.pending.has(i.issue_id)
    : !!data?.signoff.has(i.issue_id);

  const inStage = (i: IssueSummary, s: Stage) =>
    s === "all" ? true
    : s === "closed" ? i.status === "closed"
    : s === "assigned" ? i.status !== "closed" && i.assigned_worker_id != null
    : i.status !== "closed" && i.assigned_worker_id == null;

  const base = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase().replace(/^#?(pmc-)?/, "");
    return data.issues.filter((i) => {
      if (wardId && String(i.ward_id) !== wardId) return false;
      if (category && i.category !== category) return false;
      if (nearSensitive && !nearest.has(i.issue_id)) return false;
      if (q) {
        const hay = [String(i.issue_id), CATEGORY_LABELS[i.category] ?? i.category, i.location_phrase ?? "",
          i.ward_id != null ? data.wards.get(i.ward_id) ?? "" : ""].join(" ").toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [data, search, wardId, category, nearSensitive, nearest]);

  // The API returns priority order; newest-first re-sorts by latest report
  // so a fresh complaint isn't buried under older high-priority issues.
  const reportedAt = (i: IssueSummary) => (i.last_reported ? Date.parse(i.last_reported) : 0);
  const rows = base.filter((i) => inTab(i, tab) && inStage(i, stage));
  if (newestFirst) rows.sort((a, b) => reportedAt(b) - reportedAt(a) || b.issue_id - a.issue_id);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const current = Math.min(page, pages - 1);
  const visible = rows.slice(current * PAGE, current * PAGE + PAGE);

  const selectedId = Number(params.get("id")) || visible[0]?.issue_id || null;
  const select = (id: number) => setParams((p) => { p.set("id", String(id)); return p; }, { replace: true });

  const count = (t: Tab) => base.filter((i) => inTab(i, t)).length;
  const stageCount = (s: Stage) => base.filter((i) => inTab(i, tab) && inStage(i, s)).length;
  const workerName = (id: number | null | undefined) =>
    id == null ? null : workers?.find((w) => w.id === id)?.display_name ?? `Field worker #${id}`;
  const resetPage = <T,>(fn: (v: T) => void) => (v: T) => { fn(v); setPage(0); };

  return (
    <Page>
      <Subheader>
        <div className="flex items-center gap-2 font-ws-label text-[11px] text-ws-on-surface-variant">
          <LivePill label={error ? "DATA UNAVAILABLE" : "LIVE ISSUE REGISTER"} />
          <span className="text-ws-outline">•</span>
          <span className="font-ws-headline text-xs">{data ? `${data.wards.size} wards • Pune Municipal Corporation` : "Loading…"}</span>
          <span className="text-ws-outline">•</span>
          <span>Last sync: <strong className="text-ws-on-surface">{data ? ago(now - data.loadedAt) : "—"}</strong></span>
        </div>
        <Segmented<Tab>
          value={tab}
          onChange={resetPage(setTab)}
          options={[
            { value: "all", label: `All Issues (${count("all").toLocaleString("en-IN")})` },
            { value: "high", label: `High Priority (${count("high")})` },
            {
              value: "verification_pending",
              label: (
                <>
                  Verification Pending
                  <span className="px-1.5 rounded-full bg-[#ffdad6] text-[#93000a] font-ws-headline text-[10px]">{count("verification_pending")}</span>
                </>
              ),
            },
            { value: "signoff", label: `Citizen Sign-off (${count("signoff")})` },
          ]}
        />
      </Subheader>

      <div className="px-6 py-4 grid grid-cols-12 gap-6 items-start">
        <section className="col-span-12 xl:col-span-7 flex flex-col gap-4">
          {/* Filters */}
          <div className="bg-white p-4 rounded-xl shadow-sm flex flex-col gap-2">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-2">
              <div className="md:col-span-5 relative">
                <Icon name="search" className="absolute left-3 top-2.5 text-[#535f74] text-[18px]" />
                <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }}
                  className="w-full pl-9 pr-3 py-2 bg-ws-surface-low rounded-lg text-sm text-ws-on-surface placeholder:text-[#535f74] outline-none focus:bg-white focus:ring-1 focus:ring-ws-primary transition-all"
                  placeholder="Filter by ID, landmark, ward, category…" />
              </div>
              <select value={wardId} onChange={(e) => { setWardId(e.target.value); setPage(0); }}
                className="md:col-span-3 w-full px-3 py-2 bg-ws-surface-low rounded-lg text-sm text-ws-on-surface outline-none cursor-pointer">
                <option value="">All Wards (Pune 1-{data?.wards.size ?? 58})</option>
                {data && [...data.wards].map(([id, name]) => <option key={id} value={id}>Ward {id} - {name}</option>)}
              </select>
              <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(0); }}
                className="md:col-span-4 w-full px-3 py-2 bg-ws-surface-low rounded-lg text-sm text-ws-on-surface outline-none cursor-pointer">
                <option value="">All Categories ({Object.keys(CATEGORY_LABELS).length})</option>
                {Object.entries(CATEGORY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 font-ws-label">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input type="checkbox" className="sr-only peer" checked={nearSensitive} onChange={(e) => { setNearSensitive(e.target.checked); setPage(0); }} />
                <span className="relative w-8 h-4 rounded-full bg-ws-surface-variant peer-checked:bg-ws-blue transition-all after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:w-3 after:h-3 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-4" />
                <span className="text-xs font-semibold text-ws-on-surface-variant flex items-center gap-1">
                  <Icon name="near_me" className="text-[16px] text-ws-tertiary" />
                  Within {BUFFER_M}m of Sensitive Sites (Hospitals, Schools)
                </span>
              </label>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-semibold text-[#535f74] uppercase">Sort:</span>
                {([[false, "Priority"], [true, "Newest first"]] as const).map(([v, l]) => (
                  <button key={l} aria-pressed={newestFirst === v} onClick={() => { setNewestFirst(v); setPage(0); }}
                    className={`px-2 py-0.5 rounded font-ws-headline text-[11px] transition-all ${
                      newestFirst === v ? "bg-ws-primary text-white" : "bg-ws-surface-high text-ws-on-surface-variant hover:bg-ws-primary hover:text-white"
                    }`}>
                    {l}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-semibold text-[#535f74] uppercase">Status Filter:</span>
                {([["open", "Open"], ["assigned", "WIP"], ["closed", "Resolved"]] as const).map(([s, l]) => (
                  <button key={s} onClick={() => { setStage(stage === s ? "all" : s); setPage(0); }}
                    className={`px-2 py-0.5 rounded font-ws-headline text-[11px] transition-all ${
                      stage === s ? "bg-ws-primary text-white" : "bg-ws-surface-high text-ws-on-surface-variant hover:bg-ws-primary hover:text-white"
                    }`}>
                    {l} ({stageCount(s)})
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Filter chain ribbon */}
          <div className="bg-ws-surface-low p-2 rounded-xl flex items-center gap-2 overflow-x-auto shadow-sm font-ws-headline text-[11px]">
            <RibbonNode dot="bg-ws-error" label="SOURCE" value={`${data?.issues.length ?? 0} issues`} />
            <Icon name="arrow_forward" className="text-[#c1c6d7] text-[16px]" />
            <RibbonNode dot="bg-ws-blue" label={nearSensitive ? `${BUFFER_M}M SITE BUFFER` : "FILTERS"}
              value={[wardId && `Ward ${wardId}`, category && CATEGORY_LABELS[category], search && `"${search}"`].filter(Boolean).join(" • ") || "none"} />
            <Icon name="arrow_forward" className="text-[#c1c6d7] text-[16px]" />
            <RibbonNode dot="bg-ws-tertiary" label="QUEUE" value={`${rows.length} matching`} />
            <button onClick={reload} className="ml-auto flex items-center gap-1 font-ws-label text-[11px] font-semibold text-ws-primary hover:underline whitespace-nowrap">
              Refresh <Icon name="sync" className={`text-[14px] ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>

          {/* Table */}
          <div className="bg-white rounded-xl shadow-sm overflow-hidden flex flex-col">
            <div className="grid grid-cols-12 px-4 py-2.5 bg-ws-surface-container text-ws-on-surface-variant font-ws-label text-[11px] font-semibold uppercase tracking-wider">
              <div className="col-span-2">ID & Priority</div>
              <div className="col-span-5">Issue & Location</div>
              <div className="col-span-2">GPS Acc.</div>
              <div className="col-span-3 text-right">Assigned & State</div>
            </div>
            {error && <p className="p-4 text-sm text-ws-error">Couldn't load issues: {error}</p>}
            {loading && !data && <div className="p-4 space-y-3">{[0, 1, 2, 3].map((k) => <Skeleton key={k} className="h-14" />)}</div>}
            {data && visible.length === 0 && <p className="p-6 text-sm text-ws-on-surface-variant">No issues match these filters.</p>}
            {visible.map((i) => {
              const active = i.issue_id === selectedId;
              const near = nearest.get(i.issue_id);
              return (
                <button key={i.issue_id} onClick={() => select(i.issue_id)}
                  className={`grid grid-cols-12 px-4 py-3.5 text-left items-center transition-all ${active ? "bg-ws-surface-high/60" : "hover:bg-ws-surface-low"}`}>
                  <div className="col-span-2 flex flex-col gap-1 items-start">
                    <span className={`font-ws-headline text-sm font-bold ${active ? "text-ws-primary" : "text-ws-on-surface"}`}>{issueCode(i.issue_id)}</span>
                    <BandChip score={i.priority_score} soft />
                  </div>
                  <div className="col-span-5 flex items-start gap-2 pr-2 min-w-0">
                    <div className={`w-12 h-12 rounded shrink-0 relative overflow-hidden flex items-center justify-center ${active ? "bg-ws-inverse" : "bg-ws-surface-container"}`}>
                      <Icon name={CATEGORY_ICON[i.category] ?? "priority_high"} className={`text-[22px] ${active ? "text-ws-tertiary-fixed" : "text-[#535f74]"}`} />
                      <span className={`absolute bottom-0.5 right-0.5 text-[8px] font-ws-headline px-0.5 rounded ${active ? "text-[#93ccff] bg-ws-navy/80" : "text-[#535f74] bg-ws-surface-high"}`}>
                        W{i.ward_id ?? "?"}
                      </span>
                    </div>
                    <div className="flex flex-col min-w-0">
                      <span className={`font-ws-body text-sm text-ws-on-surface truncate ${active ? "font-semibold" : ""}`}>
                        {CATEGORY_LABELS[i.category] ?? i.category}{landmark(i.location_phrase) ? ` near ${i.location_phrase}` : ""}
                      </span>
                      <span className="font-ws-body text-xs text-[#535f74] truncate">
                        {i.ward_id != null ? `Ward ${i.ward_id} ${data?.wards.get(i.ward_id) ?? ""}` : "Ward unknown"} • {i.report_count} report{i.report_count === 1 ? "" : "s"}
                      </span>
                      <div className="flex items-center gap-2 mt-0.5 font-ws-headline text-[10px]">
                        {near && <span className="text-ws-tertiary bg-ws-tertiary-fixed/60 px-1 rounded uppercase">Near {near.site.kind} ({Math.round(near.d)}m)</span>}
                        {i.recurrence_count > 0 && <span className="text-[#535f74]">Recurred ×{i.recurrence_count}</span>}
                      </div>
                    </div>
                  </div>
                  <div className="col-span-2 flex flex-col">
                    {i.evidence_accuracy_m != null ? (
                      <>
                        <span className="font-ws-headline text-xs text-ws-on-surface font-semibold">±{i.evidence_accuracy_m.toFixed(1)}m</span>
                        <span className="text-[10px] text-ws-tertiary flex items-center gap-0.5"><Icon name="verified" className="text-[12px]" /> Camera GPS</span>
                      </>
                    ) : i.location_precision === "precise" ? (
                      <>
                        <span className="font-ws-headline text-xs text-ws-on-surface">Point</span>
                        <span className="text-[10px] text-[#535f74]">Geocoded landmark</span>
                      </>
                    ) : (
                      <>
                        <span className="font-ws-headline text-xs text-ws-on-surface">Ward-level</span>
                        <span className="text-[10px] text-ws-error">No GPS fix</span>
                      </>
                    )}
                  </div>
                  <div className="col-span-3 flex flex-col items-end gap-1">
                    <StatePill issue={i} pending={data?.pending.has(i.issue_id) ?? false} />
                    <span className="font-ws-body text-[11px] text-[#535f74] truncate max-w-full">
                      {workerName(i.assigned_worker_id) ?? i.routed_agency ?? "Unassigned"}
                    </span>
                    {(i.pending_evidence ?? 0) > 0 && (
                      <span className="font-ws-headline text-[10px] text-ws-on-surface-variant">{i.pending_evidence} photo(s) to review</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          <div className="bg-white p-2 rounded-xl shadow-sm flex items-center justify-between text-[#535f74] font-ws-label">
            <span className="text-xs font-semibold px-2">
              Showing {rows.length ? current * PAGE + 1 : 0}-{Math.min(rows.length, current * PAGE + PAGE)} of {rows.length.toLocaleString("en-IN")} Geo-referenced Issues
            </span>
            <div className="flex items-center gap-2">
              <button disabled={current === 0} onClick={() => setPage(current - 1)}
                className="px-3 py-1 rounded bg-ws-surface-container text-ws-on-surface text-[11px] font-semibold hover:bg-ws-surface-high disabled:opacity-50">Prev</button>
              <span className="font-ws-headline text-xs text-ws-primary font-bold">Page {current + 1} of {pages}</span>
              <button disabled={current >= pages - 1} onClick={() => setPage(current + 1)}
                className="px-3 py-1 rounded bg-ws-surface-container text-ws-on-surface text-[11px] font-semibold hover:bg-ws-surface-high disabled:opacity-50">Next</button>
            </div>
          </div>
        </section>

        <aside className="col-span-12 xl:col-span-5 flex flex-col gap-4 xl:sticky xl:top-4">
          {selectedId != null ? (
            <IssueDossier
              key={selectedId}
              issueId={selectedId}
              wardName={(() => { const w = data?.issues.find((i) => i.issue_id === selectedId)?.ward_id; return w != null ? data?.wards.get(w) : null; })()}
              sites={data?.sites}
              onChanged={reload}
            />
          ) : (
            <div className="bg-white rounded-xl p-6 text-sm text-ws-on-surface-variant">Select an issue to open its dossier.</div>
          )}
        </aside>
      </div>
    </Page>
  );
}

function StatePill({ issue, pending }: { issue: IssueSummary; pending: boolean }) {
  const [label, cls] =
    issue.status === "closed" ? ["Resolved", "bg-emerald-100 text-emerald-800"]
    : issue.has_resolution_evidence ? ["Worker Resolved", "bg-ws-primary/10 text-ws-primary"]
    : issue.assigned_worker_id != null ? ["In Progress", "bg-ws-secondary-container text-ws-on-secondary-container"]
    : issue.routed_agency ? ["Work Assigned", "bg-ws-surface-high text-[#535f74]"]
    : pending ? ["Evidence Review", "bg-amber-100 text-amber-800"]
    : ["Open (Triaged)", "bg-ws-surface-highest text-ws-on-surface"];
  return <span className={`px-2 py-0.5 rounded-full font-ws-label text-[11px] font-semibold uppercase whitespace-nowrap ${cls}`}>{label}</span>;
}

function RibbonNode({ dot, label, value }: { dot: string; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2 px-2.5 py-1 bg-white rounded-lg shadow-sm whitespace-nowrap">
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      <span className="text-ws-on-surface uppercase">{label}</span>
      <span className="text-[#535f74] max-w-[220px] truncate">{value}</span>
    </div>
  );
}

function useNow() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

function ago(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s}s ago` : `${Math.round(s / 60)}m ago`;
}

export default IssueExplorer;
