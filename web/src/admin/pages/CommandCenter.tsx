import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { GeoJSON, MapContainer, Marker, CircleMarker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { api, mediaUrl, ApiError } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CATEGORY_LABELS } from "../../api/types";
import type { EvidenceItem, IssueDetailResponse, MapIssuePoint, MapWard } from "../../api/types";
import { Icon, CATEGORY_ICON, band, BAND_CHIP, dms, inr, fmtTime, landmark } from "../components/ws";
import type { Band } from "../components/ws";
import { useEvidencePhoto } from "../components/EvidenceTimeline";
import "./commandcenter.css";

// Layout and styling follow the Stitch export in
// WardSentry-UI-References/admin-stitch/wardsentry_admin_command_center.
// Every number on this page is computed from /api/map or /api/issues/:id.

const PUNE: [number, number] = [18.5204, 73.8567];
const DAY = 86_400_000;
const WORK_CORRIDOR_M = 500;

function fmtDate(ms: number) {
  return new Date(ms).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }).toUpperCase();
}

function issueIcon(issue: MapIssuePoint, selected: boolean) {
  const b = band(issue.priority_score);
  const glyph = CATEGORY_ICON[issue.category] ?? "priority_high";
  const html = selected
    ? `<span class="cc-halo"></span><span class="cc-orbit"></span><span class="cc-dot cc-dot--selected"><span class="material-symbols-outlined">${glyph}</span></span>`
    : `${b === "high" ? '<span class="cc-ping"></span>' : ""}<span class="cc-dot cc-dot--${b}"><span class="material-symbols-outlined">${glyph}</span></span>`;
  const size = selected ? 28 : b === "high" ? 24 : b === "med" ? 20 : 16;
  return L.divIcon({ className: "cc-marker", html, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
}

const WORK_ICON = L.divIcon({
  className: "cc-marker",
  html: '<span class="cc-work"><span class="material-symbols-outlined">engineering</span></span>',
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

export function CommandCenter() {
  const navigate = useNavigate();
  const { data: mapData, loading, error, reload } = useApi(() => api.map(), []);

  const [search, setSearch] = useState("");
  const [wardId, setWardId] = useState<number | null>(null);
  const [category, setCategory] = useState("");
  const [minPriority, setMinPriority] = useState(0);
  const [showFilters, setShowFilters] = useState(false);
  const [layers, setLayers] = useState({ issues: true, works: true, sites: false, wards: true });
  const [corridorFocus, setCorridorFocus] = useState(false);
  const [pickedId, setSelectedId] = useState<number | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [cutoff, setCutoff] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const onSync = () => reload();
    window.addEventListener("ws:sync-layers", onSync);
    return () => window.removeEventListener("ws:sync-layers", onSync);
  }, [reload]);

  const wardsById = useMemo(() => new Map((mapData?.wards ?? []).map((w) => [w.ward_id, w])), [mapData]);

  // Timeline range = real first-report span of the data.
  const range = useMemo(() => {
    const times = (mapData?.issues ?? []).map((i) => (i.first_reported ? Date.parse(i.first_reported) : NaN)).filter((t) => !isNaN(t));
    const now = Date.now();
    return { start: times.length ? Math.min(...times) : now - 30 * DAY, end: now };
  }, [mapData]);
  const effectiveCutoff = cutoff ?? range.end;
  const isLive = cutoff === null || cutoff >= range.end;

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      setCutoff((c) => {
        const next = (c ?? range.start) + DAY;
        if (next >= range.end) {
          setPlaying(false);
          return null;
        }
        return next;
      });
    }, 120);
    return () => clearInterval(t);
  }, [playing, range]);

  const inTimeline = useMemo(
    () => (mapData?.issues ?? []).filter((i) => !i.first_reported || Date.parse(i.first_reported) <= effectiveCutoff),
    [mapData, effectiveCutoff],
  );

  const nearWork = useMemo(() => {
    const works = (mapData?.matched_works ?? []).map((w) => L.latLng(w.location.lat, w.location.lon));
    const set = new Set<number>();
    for (const i of mapData?.issues ?? []) {
      const p = L.latLng(i.location.lat, i.location.lon);
      if (works.some((w) => w.distanceTo(p) <= WORK_CORRIDOR_M)) set.add(i.issue_id);
    }
    return set;
  }, [mapData]);

  const visibleIssues = useMemo(() => {
    const q = search.trim().toLowerCase();
    return inTimeline.filter((i) => {
      if (wardId !== null && i.ward_id !== wardId) return false;
      if (category && i.category !== category) return false;
      if ((i.priority_score ?? 0) < minPriority) return false;
      if (corridorFocus && !nearWork.has(i.issue_id)) return false;
      if (q) {
        const ward = i.ward_id != null ? wardsById.get(i.ward_id)?.name.toLowerCase() ?? "" : "";
        const cat = (CATEGORY_LABELS[i.category] ?? i.category).toLowerCase();
        if (!String(i.issue_id).includes(q.replace(/^#/, "")) && !cat.includes(q) && !ward.includes(q)) return false;
      }
      return true;
    });
  }, [inTimeline, wardId, category, minPriority, corridorFocus, nearWork, search, wardsById]);

  // Until one is picked, inspect the highest-priority issue, as the Stitch screen does.
  const topId = useMemo(() => {
    const issues = mapData?.issues ?? [];
    return issues.length ? issues.reduce((a, b) => ((b.priority_score ?? 0) > (a.priority_score ?? 0) ? b : a)).issue_id : null;
  }, [mapData]);
  const selectedId = pickedId ?? topId;

  const highCount = inTimeline.filter((i) => band(i.priority_score) === "high").length;
  const preciseCount = inTimeline.filter((i) => i.location_precision === "precise").length;
  const precisePct = inTimeline.length ? (100 * preciseCount) / inTimeline.length : 0;
  const closedCount = inTimeline.filter((i) => i.status === "closed").length;

  const wardRows = useMemo(() => {
    const rows = new Map<number, { total: number; high: number; med: number; low: number; precise: number }>();
    for (const i of inTimeline) {
      if (i.ward_id == null) continue;
      const r = rows.get(i.ward_id) ?? { total: 0, high: 0, med: 0, low: 0, precise: 0 };
      r.total++;
      r[band(i.priority_score)]++;
      if (i.location_precision === "precise") r.precise++;
      rows.set(i.ward_id, r);
    }
    return [...rows.entries()].sort((a, b) => b[1].high - a[1].high || b[1].total - a[1].total);
  }, [inTimeline]);

  // New issues per day over the last 30 days of the timeline.
  const velocity = useMemo(() => {
    const days = new Array(30).fill(0);
    for (const i of inTimeline) {
      if (!i.first_reported) continue;
      const ago = Math.floor((effectiveCutoff - Date.parse(i.first_reported)) / DAY);
      if (ago >= 0 && ago < 30) days[29 - ago]++;
    }
    return days;
  }, [inTimeline, effectiveCutoff]);
  const perDay = velocity.reduce((a, b) => a + b, 0) / 30;

  const selectedPoint = mapData?.issues.find((i) => i.issue_id === selectedId) ?? null;
  const totalDays = Math.max(1, Math.round((range.end - range.start) / DAY));
  const progress = ((effectiveCutoff - range.start) / (range.end - range.start || 1)) * 100;

  return (
    <div className="relative w-full h-full overflow-hidden bg-ws-navy select-none font-ws-body">
      {/* 1. Full-viewport map */}
      <div className="absolute inset-0 z-0 cc-map">
        <MapContainer center={PUNE} zoom={12} zoomControl={false} preferCanvas style={{ height: "100%", width: "100%", background: "#070e19" }}>
          <TileLayer
            className="cc-tiles"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {mapData && layers.wards && (
            <WardBoundaries wards={mapData.wards} activeWard={wardId} onPick={(id) => setWardId((w) => (w === id ? null : id))} />
          )}
          {mapData && layers.sites &&
            mapData.sensitive_sites.map((s) => (
              <CircleMarker key={s.site_id} center={[s.location.lat, s.location.lon]} radius={2}
                pathOptions={{ color: "#8b5cf6", weight: 0, fillOpacity: 0.55 }} />
            ))}
          {mapData && layers.works &&
            mapData.matched_works.map((w) => (
              <Marker key={w.work_id} position={[w.location.lat, w.location.lon]} icon={WORK_ICON}
                title={w.work_name} eventHandlers={{ click: () => navigate(`/works/${w.work_id}`) }} />
            ))}
          {layers.issues &&
            visibleIssues.map((i) => (
              <Marker key={i.issue_id} position={[i.location.lat, i.location.lon]}
                icon={issueIcon(i, i.issue_id === selectedId)} zIndexOffset={i.issue_id === selectedId ? 1000 : 0}
                title={`#${i.issue_id} ${CATEGORY_LABELS[i.category] ?? i.category}`}
                eventHandlers={{ click: () => { setSelectedId(i.issue_id); setInspectorOpen(true); } }} />
            ))}
          <MapFocus ward={wardId !== null ? wardsById.get(wardId) ?? null : null} issue={selectedPoint} />
          <CursorHud />
        </MapContainer>
        {selectedPoint && inspectorOpen && (
          <div className="absolute top-[88px] left-1/2 -translate-x-1/2 z-[15] px-2.5 py-1 rounded bg-ws-navy/90 backdrop-blur text-white flex items-center gap-2 whitespace-nowrap shadow-xl pointer-events-none">
            <span className="w-2 h-2 rounded-full bg-ws-blue" />
            <span className="font-ws-headline text-[11px] font-semibold tracking-wide">
              {BAND_CHIP[band(selectedPoint.priority_score)].label.split(" ")[0]}: {CATEGORY_LABELS[selectedPoint.category] ?? selectedPoint.category} #{selectedPoint.issue_id}
            </span>
          </div>
        )}
      </div>

      {loading && !mapData && (
        <div className="absolute inset-0 z-30 flex items-center justify-center">
          <div className="px-4 py-3 rounded-lg bg-ws-inverse/90 text-white text-xs font-ws-label flex items-center gap-3">
            <span className="w-4 h-4 border-2 border-ws-blue border-t-transparent rounded-full animate-spin" />
            Loading spatial layers…
          </div>
        </div>
      )}
      {error && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-30 px-4 py-3 rounded-lg bg-ws-error text-white text-xs font-ws-label flex items-center gap-3">
          <Icon name="error" className="text-[18px]" />
          Couldn't load map layers: {error}
          <button onClick={reload} className="underline font-semibold">Retry</button>
        </div>
      )}

      {/* 2. Floating top control bar */}
      <header className="absolute top-4 left-4 right-4 z-20 flex items-center justify-between gap-3 p-2 rounded-lg bg-ws-inverse/90 backdrop-blur-md shadow-2xl font-ws-label">
        <div className="flex items-center gap-2 flex-1 min-w-[220px] max-w-xl">
          <div className="relative w-full">
            <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-ws-surface-variant text-[18px]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                const id = Number(search.replace(/^#/, ""));
                if (e.key === "Enter" && mapData?.issues.some((i) => i.issue_id === id)) {
                  setSelectedId(id);
                  setInspectorOpen(true);
                }
              }}
              className="w-full h-9 pl-9 pr-4 rounded bg-ws-navy text-white placeholder-ws-surface-variant text-xs outline-none focus:bg-ws-navy/80 transition-all"
              placeholder="Search by Ward, Category or Issue # (e.g. 1042)…"
            />
          </div>
          <div className="relative">
            <Icon name="location_on" className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[18px] text-ws-blue pointer-events-none" />
            <select
              value={wardId ?? ""}
              onChange={(e) => setWardId(e.target.value ? Number(e.target.value) : null)}
              className="h-9 pl-9 pr-3 rounded bg-ws-navy text-white text-xs font-semibold outline-none cursor-pointer max-w-[210px]"
            >
              <option value="">Pune ({mapData?.wards.length ?? "…"} Wards)</option>
              {mapData?.wards.map((w) => (
                <option key={w.ward_id} value={w.ward_id}>Ward {w.ward_id} — {w.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-1 bg-ws-navy/80 p-1 rounded-full shrink-0">
          <LayerPill on={layers.issues} dot="bg-white" onClick={() => setLayers((l) => ({ ...l, issues: !l.issues }))}>
            Civic Incidents ({visibleIssues.length})
          </LayerPill>
          <LayerPill on={layers.works} dot="bg-ws-tertiary-fixed" onClick={() => setLayers((l) => ({ ...l, works: !l.works }))}>
            Public Works ({mapData?.matched_works.length ?? 0})
          </LayerPill>
          <LayerPill on={layers.sites} onClick={() => setLayers((l) => ({ ...l, sites: !l.sites }))}>
            Sensitive Sites
          </LayerPill>
          <LayerPill on={layers.wards} onClick={() => setLayers((l) => ({ ...l, wards: !l.wards }))}>
            Ward Boundaries
          </LayerPill>
        </div>

        <div className="relative flex items-center gap-2 shrink-0">
          <div className="hidden 2xl:flex items-center gap-1.5 px-2.5 py-1 rounded bg-ws-navy text-white font-ws-headline text-[11px]">
            <span className={`inline-block w-2 h-2 rounded-full ${error ? "bg-amber-400" : "bg-emerald-400 animate-pulse"}`} />
            <span>Live Layers</span>
            <span className="text-ws-tertiary-fixed">
              {((mapData?.issues.length ?? 0) + (mapData?.matched_works.length ?? 0)).toLocaleString("en-IN")} Nodes
            </span>
          </div>
          <button
            onClick={() => setShowFilters((s) => !s)}
            className="h-9 px-3 rounded bg-ws-blue text-white text-xs font-semibold flex items-center gap-1.5 hover:bg-ws-primary transition-all shadow-md"
          >
            <Icon name="tune" className="text-[18px]" />
            Filter View
          </button>
          {showFilters && (
            <div className="absolute right-0 top-11 w-72 p-4 rounded-lg bg-white shadow-2xl space-y-3 text-ws-on-surface">
              <label className="block text-[11px] font-semibold uppercase tracking-[0.06em] text-ws-on-surface-variant">
                Category
                <select value={category} onChange={(e) => setCategory(e.target.value)}
                  className="mt-1 w-full h-8 px-2 rounded border border-ws-surface-highest text-xs normal-case tracking-normal">
                  <option value="">All categories</option>
                  {Object.entries(CATEGORY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.06em] text-ws-on-surface-variant">
                Minimum priority: <span className="font-ws-headline text-ws-on-surface">{minPriority.toFixed(2)}</span>
                <input type="range" min={0} max={1} step={0.05} value={minPriority}
                  onChange={(e) => setMinPriority(Number(e.target.value))} className="mt-1 w-full accent-ws-blue" />
              </label>
              <button
                onClick={() => { setCategory(""); setMinPriority(0); setSearch(""); setWardId(null); setCorridorFocus(false); }}
                className="text-xs font-semibold text-ws-primary"
              >
                Reset filters
              </button>
            </div>
          )}
        </div>
      </header>

      {/* 3. Left drawer: operational summary and ward ranking */}
      <aside className="absolute left-4 top-20 bottom-16 w-80 z-20 flex flex-col rounded-lg bg-ws-inverse/92 backdrop-blur-md shadow-2xl overflow-hidden font-ws-label">
        <div className="p-3.5 bg-ws-navy/70 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="insights" className="text-[20px] text-ws-blue" />
            <div className="flex flex-col">
              <span className="font-ws-headline text-base font-semibold text-white leading-tight">Spatial Telemetry</span>
              <span className="text-[11px] font-semibold text-ws-surface-variant">PMC Municipal Real-Time Stream</span>
            </div>
          </div>
          <button onClick={reload} title="Refresh layers" className="p-1 rounded hover:bg-white/10 text-ws-surface-variant hover:text-white transition-all">
            <Icon name="sync" className={`text-[18px] ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        <div className="p-3 grid grid-cols-2 gap-2 bg-ws-navy/40">
          <div className="p-2.5 rounded bg-ws-navy/80 flex flex-col">
            <span className="text-[11px] font-semibold text-ws-surface-variant uppercase">Critical P1</span>
            <div className="flex items-baseline gap-1.5 mt-0.5">
              <span className="font-ws-headline text-[22px] text-red-400 font-bold">{highCount}</span>
              <span className="font-ws-headline text-[11px] text-red-400/80">of {inTimeline.length}</span>
            </div>
            <span className="text-[10px] text-ws-surface-variant mt-1">Priority ≥ 0.70, needs dispatch</span>
          </div>
          <div className="p-2.5 rounded bg-ws-navy/80 flex flex-col">
            <span className="text-[11px] font-semibold text-ws-surface-variant uppercase">Spatial Verified</span>
            <div className="flex items-baseline gap-1.5 mt-0.5">
              <span className={`font-ws-headline text-[22px] font-bold ${precisePct >= 90 ? "text-emerald-400" : "text-amber-400"}`}>
                {precisePct.toFixed(1)}%
              </span>
              <span className="font-ws-headline text-[11px] text-emerald-400">Target &gt;90</span>
            </div>
            <span className="text-[10px] text-ws-surface-variant mt-1">Precise location, not ward centroid</span>
          </div>
        </div>

        <div className="px-3 pt-2">
          <button
            onClick={() => setCorridorFocus((f) => !f)}
            className={`w-full py-1.5 px-2 rounded text-[11px] font-semibold flex items-center justify-between transition-all ${
              corridorFocus ? "bg-ws-tertiary-container text-white" : "bg-ws-tertiary-container/30 hover:bg-ws-tertiary-container/50 text-ws-tertiary-fixed"
            }`}
          >
            <span className="flex items-center gap-1.5 whitespace-nowrap">
              <Icon name="alt_route" className="text-[16px]" />
              Focus Linked Works Corridors
            </span>
            <span className="font-ws-headline bg-ws-tertiary-container px-1.5 rounded text-white whitespace-nowrap">{nearWork.size}</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 cc-scroll">
          <div className="flex items-center justify-between text-ws-surface-variant text-[11px] font-semibold px-1">
            <span>WARD JURISDICTION</span>
            <span>INCIDENTS / PRECISE</span>
          </div>
          {wardRows.map(([id, r]) => {
            const active = id === wardId;
            const b: Band = r.high ? "high" : r.med ? "med" : "low";
            const pct = (100 * r.precise) / r.total;
            return (
              <button
                key={id}
                onClick={() => setWardId(active ? null : id)}
                className={`w-full text-left p-2.5 rounded cursor-pointer transition-all ${
                  active ? "bg-ws-blue/20 hover:bg-ws-blue/30" : "bg-ws-navy/60 hover:bg-ws-navy/90"
                }`}
              >
                <div className="flex items-center justify-between mb-1 gap-2">
                  <span className="flex items-center gap-1.5 min-w-0">
                    {active && <span className="w-2 h-2 rounded-full bg-ws-blue animate-ping shrink-0" />}
                    <span className={`font-ws-body text-sm text-white truncate ${active ? "font-semibold" : ""}`}>
                      Ward {String(id).padStart(2, "0")} — {wardsById.get(id)?.name ?? "Unknown"}
                    </span>
                  </span>
                  {active ? (
                    <span className="font-ws-headline text-[11px] px-1.5 py-0.5 rounded bg-ws-blue text-white shrink-0">Active Pin</span>
                  ) : (
                    <span className={`font-ws-headline text-[11px] shrink-0 ${b === "high" ? "text-red-400" : b === "med" ? "text-amber-400" : "text-ws-surface-variant"}`}>
                      {b === "high" ? `Critical ${r.high}` : b === "med" ? `Moderate ${r.med}` : `Low ${r.low}`}
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between text-[11px] text-ws-surface-variant">
                  <span>{r.total} Reported • {r.high} P1</span>
                  <span className={`font-ws-headline font-semibold ${pct >= 90 ? "text-emerald-400" : "text-amber-400"}`}>{pct.toFixed(1)}% Precise</span>
                </div>
                <div className={`w-full bg-ws-navy/70 ${active ? "h-1.5" : "h-1"} rounded-full mt-2 overflow-hidden flex`}>
                  <div className="bg-ws-error h-full" style={{ width: `${(100 * r.high) / r.total}%` }} />
                  <div className="bg-amber-400 h-full" style={{ width: `${(100 * r.med) / r.total}%` }} />
                  <div className="bg-emerald-400 h-full" style={{ width: `${(100 * r.low) / r.total}%` }} />
                </div>
              </button>
            );
          })}
          {mapData && wardRows.length === 0 && (
            <p className="text-[11px] text-ws-surface-variant px-1 py-4">No issues reported in this time window.</p>
          )}
        </div>

        <div className="p-3 bg-ws-navy/80">
          <div className="flex items-center justify-between mb-1 text-[11px] font-semibold">
            <span className="text-white">30-Day Reporting Velocity</span>
            <span className="text-emerald-400 font-ws-headline">{perDay.toFixed(1)} Issues/day</span>
          </div>
          <Sparkline values={velocity} />
        </div>
      </aside>

      {/* 4. Right inspector */}
      {selectedId !== null && inspectorOpen && (
        <Inspector
          issueId={selectedId}
          wardName={(id) => (id != null ? wardsById.get(id)?.name ?? null : null)}
          onClose={() => setInspectorOpen(false)}
          onOpen={() => navigate(`/issues/${selectedId}`)}
        />
      )}

      {/* 5. Bottom timeline scrubber */}
      <div className="absolute bottom-3 left-4 right-4 z-20 h-11 px-4 rounded-lg bg-ws-inverse/92 backdrop-blur-md shadow-xl flex items-center justify-between gap-4 font-ws-label">
        <div className="flex items-center gap-3 min-w-[240px]">
          <button
            onClick={() => {
              if (!playing && isLive) setCutoff(range.start);
              setPlaying((p) => !p);
            }}
            className="w-7 h-7 rounded-full bg-ws-blue hover:bg-ws-primary text-white flex items-center justify-center shadow"
            title={playing ? "Pause" : "Replay the reporting timeline"}
          >
            <Icon name={playing ? "pause" : "play_arrow"} className="text-[18px]" />
          </button>
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-white">{totalDays}-Day Spatial Trajectory</span>
            <span className="font-ws-headline text-[10px] text-ws-surface-variant">{fmtDate(range.start)} — {fmtDate(effectiveCutoff)}</span>
          </div>
        </div>
        <div className="flex-1 flex items-center gap-3">
          <span className="font-ws-headline text-[11px] text-ws-surface-variant">D-{totalDays}</span>
          <div className="relative w-full h-2 rounded-full bg-ws-navy/80 flex items-center">
            <div className="h-full rounded-full bg-gradient-to-r from-ws-primary to-ws-blue" style={{ width: `${progress}%` }} />
            <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full bg-white shadow-md pointer-events-none" style={{ left: `${progress}%` }} />
            <input
              type="range" min={range.start} max={range.end} step={DAY / 4} value={effectiveCutoff}
              onChange={(e) => { setPlaying(false); const v = Number(e.target.value); setCutoff(v >= range.end ? null : v); }}
              className="absolute inset-0 w-full opacity-0 cursor-pointer" aria-label="Timeline"
            />
          </div>
          <button onClick={() => { setPlaying(false); setCutoff(null); }}
            className={`font-ws-headline text-[11px] font-bold whitespace-nowrap ${isLive ? "text-emerald-400" : "text-ws-surface-variant hover:text-white"}`}>
            NOW (LIVE)
          </button>
        </div>
        <div className="hidden md:flex items-center gap-4 text-white font-ws-headline text-[11px] border-l border-ws-surface-variant/20 pl-4">
          <div><span className="text-ws-surface-variant">CLOSED: </span><span className="text-emerald-400 font-bold">{closedCount.toLocaleString("en-IN")}</span></div>
          <div><span className="text-ws-surface-variant">ACTIVE: </span><span className="text-ws-blue font-bold">{(inTimeline.length - closedCount).toLocaleString("en-IN")}</span></div>
          <button onClick={() => document.getElementById("admin-main")?.requestFullscreen?.()} className="p-1 rounded text-ws-surface-variant hover:text-white" title="Fullscreen">
            <Icon name="fullscreen" className="text-[16px]" />
          </button>
        </div>
      </div>
    </div>
  );
}

function LayerPill({ on, dot, onClick, children }: { on: boolean; dot?: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded-full text-[11px] font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 ${
        on ? "bg-ws-blue text-white" : "text-ws-surface-variant hover:text-white"
      }`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />}
      {children}
    </button>
  );
}

function Sparkline({ values }: { values: number[] }) {
  const max = Math.max(1, ...values);
  const w = 290, h = 32;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, h - 3 - (v / max) * (h - 8)]);
  const last = pts[pts.length - 1];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-8" preserveAspectRatio="none">
      <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke="#0070f3" strokeWidth="2" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r="3" fill="#0070f3" stroke="white" strokeWidth="1" />
    </svg>
  );
}

function WardBoundaries({ wards, activeWard, onPick }: { wards: MapWard[]; activeWard: number | null; onPick: (id: number) => void }) {
  const fc = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: wards
        .filter((w) => w.geometry)
        .map((w) => ({ type: "Feature" as const, properties: { ward_id: w.ward_id, name: w.name }, geometry: w.geometry! })),
    }),
    [wards],
  );
  return (
    <GeoJSON
      key={activeWard ?? "all"}
      data={fc}
      style={(f) => {
        const active = f?.properties.ward_id === activeWard;
        return {
          color: active ? "#0070f3" : "#4f7cc2",
          weight: active ? 2.5 : 0.8,
          opacity: active ? 1 : 0.55,
          fillColor: "#0070f3",
          fillOpacity: active ? 0.12 : 0.02,
          dashArray: active ? undefined : "3 3",
        };
      }}
      onEachFeature={(f, layer) => {
        layer.bindTooltip(`Ward ${f.properties.ward_id} — ${f.properties.name}`, { sticky: true, className: "cc-tooltip" });
        layer.on("click", () => onPick(f.properties.ward_id));
      }}
    />
  );
}

function MapFocus({ ward, issue }: { ward: MapWard | null; issue: MapIssuePoint | null }) {
  const map = useMap();
  useEffect(() => {
    if (ward?.geometry) map.flyToBounds(L.geoJSON(ward.geometry).getBounds(), { padding: [80, 80], maxZoom: 14, duration: 0.8 });
  }, [map, ward]);
  useEffect(() => {
    if (issue) map.panTo([issue.location.lat, issue.location.lon], { animate: true });
  }, [map, issue]);
  return null;
}

function CursorHud() {
  const map = useMap();
  const [pos, setPos] = useState(map.getCenter());
  const [zoom, setZoom] = useState(map.getZoom());
  useMapEvents({ mousemove: (e) => setPos(e.latlng), zoomend: () => setZoom(map.getZoom()) });
  return (
    <div className="absolute bottom-16 left-[360px] z-[500] pointer-events-none flex items-center gap-3 text-ws-surface-variant font-ws-headline text-xs bg-ws-navy/60 backdrop-blur px-3 py-1 rounded">
      <span>LAT: {dms(pos.lat, "N", "S")}</span>
      <span className="text-ws-outline">|</span>
      <span>LNG: {dms(pos.lng, "E", "W")}</span>
      <span className="text-ws-outline">|</span>
      <span>ZOOM: {zoom}</span>
    </div>
  );
}

function Inspector({ issueId, wardName, onClose, onOpen }: {
  issueId: number;
  wardName: (id: number | null) => string | null;
  onClose: () => void;
  onOpen: () => void;
}) {
  const { data: issue, loading, error, reload } = useApi(() => api.issueDetail(issueId), [issueId]);
  const { data: workers } = useApi(() => api.fieldWorkers().catch(() => []), []);
  const [assigning, setAssigning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      reload();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Action failed.");
    } finally {
      setBusy(false);
      setAssigning(false);
    }
  }

  const b = band(issue?.priority_score ?? null);
  const ward = issue ? wardName(issue.ward_id) : null;
  const worker = issue?.assigned_worker_id != null ? workers?.find((w) => w.id === issue.assigned_worker_id) : null;
  const match = issue?.matches[0] ?? null;
  const report = issue?.reports[0] ?? null;
  const gps = issue?.evidence.find((e) => e.evidence_type === "initial_report") ?? issue?.evidence[0] ?? null;

  return (
    <aside className="absolute right-4 top-20 bottom-16 w-96 z-20 flex flex-col rounded-lg bg-white shadow-2xl overflow-hidden font-ws-label">
      <div className="p-3.5 bg-ws-navy text-white flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded font-ws-headline text-[11px] uppercase font-bold whitespace-nowrap ${BAND_CHIP[b].solid}`}>{BAND_CHIP[b].label}</span>
          <div className="flex flex-col">
            <span className="font-ws-headline text-base font-semibold">#PMC-{issueId}</span>
            <span className="text-[11px] font-semibold text-ws-surface-variant">
              {issue?.ward_id != null ? `Ward ${String(issue.ward_id).padStart(2, "0")} • ${ward ?? ""}` : "Ward not resolved"}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            title="Copy link"
            onClick={() => {
              navigator.clipboard?.writeText(`${location.origin}/issues/${issueId}`);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
            className="p-1 rounded hover:bg-white/10 text-ws-surface-variant hover:text-white"
          >
            <Icon name={copied ? "check" : "share"} className="text-[18px]" />
          </button>
          <button onClick={onClose} title="Close" className="p-1 rounded hover:bg-white/10 text-ws-surface-variant hover:text-white">
            <Icon name="close" className="text-[18px]" />
          </button>
        </div>
      </div>

      {issue && <StatusBanner issue={issue} workerName={worker?.display_name ?? null} />}

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loading && !issue && <div className="h-40 rounded bg-ws-surface-low animate-pulse" />}
        {error && <p className="text-xs text-ws-error">Couldn't load issue: {error}</p>}
        {issue && (
          <>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="font-ws-headline text-lg text-ws-on-surface font-semibold">
                  {CATEGORY_LABELS[issue.category] ?? issue.category}
                  {landmark(report?.location_phrase) ? ` near ${report!.location_phrase}` : ""}
                </h2>
              </div>
              {report && (
                <p className="font-ws-body text-xs text-ws-on-surface-variant mt-1 leading-relaxed">
                  {report.translated_text ?? report.raw_text}
                </p>
              )}
              <div className="mt-3 p-2.5 rounded bg-ws-surface-low flex flex-col gap-1.5 font-ws-headline text-[11px] tracking-[0.02em]">
                <Spec k="COORDINATES:" v={issue.location ? `${issue.location.lat.toFixed(4)}° N, ${issue.location.lon.toFixed(4)}° E` : "Not located"} />
                <Spec k="LOCATION BASIS:" v={issue.location_precision === "precise" ? "Precise point" : issue.location_precision === "ward_level" ? "Ward centroid (0.4)" : "Unknown"}
                  cls={issue.location_precision === "precise" ? "text-ws-primary" : "text-amber-700"} />
                <Spec k="GPS CONFIDENCE:" v={gps ? `±${gps.accuracy_m.toFixed(1)} meters (${gps.review_status === "verified" ? "Verified" : gps.review_status === "review_required" ? "Needs review" : "Pending"})` : "No device fix"}
                  cls={gps?.review_status === "verified" ? "text-emerald-600" : "text-ws-on-surface-variant"} />
                <Spec k="PRIORITY SCORE:" v={issue.priority_score?.toFixed(2) ?? "—"} />
              </div>
            </div>

            <PhotoStrip issue={issue} />

            {match?.work ? (
              <div className="p-3 rounded bg-ws-surface-container flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-ws-primary font-bold uppercase tracking-wider">Linked Civil Work Order</span>
                  {match.work.status && (
                    <span className="px-1.5 py-0.5 rounded bg-ws-surface-highest font-ws-headline text-[10px] text-ws-on-surface uppercase">{match.work.status}</span>
                  )}
                </div>
                <div className="font-ws-body text-sm text-ws-on-surface font-semibold">MPLADS-{match.work.work_id}: {match.work.work_name}</div>
                <div className="flex items-center justify-between font-ws-body text-xs text-ws-on-surface-variant mt-1">
                  <span className="truncate">Agency: {match.work.agency ?? "Not recorded"}</span>
                  <span className="font-ws-headline text-ws-on-surface font-semibold">{inr(match.work.cost)}</span>
                </div>
                <p className="font-ws-body text-[11px] text-ws-on-surface-variant leading-snug">{match.match_reason}</p>
              </div>
            ) : (
              <div className="p-3 rounded bg-ws-surface-low font-ws-body text-xs text-ws-on-surface-variant">
                No funded public work matched this issue above the match threshold.
              </div>
            )}

            <div className="p-3 rounded bg-ws-surface-low flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 shrink-0 rounded-full bg-ws-blue text-white flex items-center justify-center font-bold text-xs">
                  {worker?.display_name ? worker.display_name.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase() : <Icon name="engineering" className="text-[18px]" />}
                </div>
                <div className="flex flex-col min-w-0">
                  <span className="font-ws-body text-sm text-ws-on-surface font-semibold truncate">
                    {worker ? worker.display_name ?? `Field worker #${worker.id}` : issue.assigned_worker_id != null ? `Field worker #${issue.assigned_worker_id}` : "No crew assigned"}
                  </span>
                  <span className="text-[11px] font-semibold text-ws-on-surface-variant truncate">
                    {issue.assigned_at ? `Assigned ${fmtTime(issue.assigned_at)}` : issue.routed_agency ? `Routed to ${issue.routed_agency}` : "Awaiting dispatch"}
                  </span>
                </div>
              </div>
            </div>
            {assigning && (
              <select
                autoFocus
                disabled={busy}
                defaultValue=""
                onChange={(e) => e.target.value && run(() => api.assignIssue(issueId, Number(e.target.value)))}
                className="w-full h-9 px-2 rounded border border-ws-surface-highest text-xs"
              >
                <option value="" disabled>{workers?.length ? "Choose a field worker…" : "No field workers yet: add them in Staff & Roles"}</option>
                {workers?.map((w) => <option key={w.id} value={w.id}>{w.display_name ?? `Worker #${w.id}`}</option>)}
              </select>
            )}
            {actionError && <p className="text-xs text-ws-error">{actionError}</p>}
          </>
        )}
      </div>

      <div className="p-3 bg-ws-surface-low flex flex-col gap-2 shadow-inner">
        {issue && !issue.routed_agency && issue.status !== "closed" ? (
          <button disabled={busy} onClick={() => run(() => api.routeIssue(issueId))}
            className="w-full py-2 px-3 rounded bg-ws-blue text-white text-xs font-semibold hover:bg-ws-primary transition-all flex items-center justify-center gap-2 shadow disabled:opacity-60">
            <Icon name="send" className="text-[18px]" />
            Route to Department
          </button>
        ) : (
          <button onClick={onOpen}
            className="w-full py-2 px-3 rounded bg-ws-blue text-white text-xs font-semibold hover:bg-ws-primary transition-all flex items-center justify-center gap-2 shadow">
            <Icon name="verified" className="text-[18px]" />
            Open Evidence Verification
          </button>
        )}
        <div className="grid grid-cols-2 gap-2">
          <button disabled={!issue || busy} onClick={() => setAssigning((a) => !a)}
            className="py-1.5 px-3 rounded bg-ws-surface-container hover:bg-ws-surface-high text-ws-on-surface text-xs font-semibold transition-all disabled:opacity-60">
            {issue?.assigned_worker_id != null ? "Re-route Crew" : "Assign Crew"}
          </button>
          <button onClick={onOpen}
            className="py-1.5 px-3 rounded bg-ws-surface-container hover:bg-ws-surface-high text-ws-on-surface text-xs font-semibold transition-all">
            Full Audit Log
          </button>
        </div>
      </div>
    </aside>
  );
}

function Spec({ k, v, cls = "text-ws-on-surface" }: { k: string; v: string; cls?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 text-ws-on-surface-variant">
      <span>{k}</span>
      <span className={`font-medium text-right ${cls}`}>{v}</span>
    </div>
  );
}

function StatusBanner({ issue, workerName }: { issue: IssueDetailResponse; workerName: string | null }) {
  const days = issue.priority_breakdown?.time_open_days;
  const text =
    issue.status === "closed" ? "Resolved — Awaiting Citizen Sign-off"
    : issue.assigned_worker_id != null ? `Work In Progress — ${workerName ? `${workerName} Dispatched` : "Crew Dispatched"}`
    : issue.routed_agency ? `Routed — ${issue.routed_agency}`
    : "Open — Awaiting Dispatch";
  return (
    <div className="bg-ws-secondary-container px-3.5 py-2 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className={`w-2.5 h-2.5 rounded-full ${issue.status === "closed" ? "bg-emerald-500" : "bg-ws-blue animate-pulse"}`} />
        <span className="font-ws-body text-xs text-ws-on-secondary-container font-semibold">{text}</span>
      </div>
      {days != null && <span className="font-ws-headline text-[11px] text-ws-on-secondary-container">Open: {Math.round(days)}d</span>}
    </div>
  );
}

function PhotoStrip({ issue }: { issue: IssueDetailResponse }) {
  const citizen = issue.evidence.filter((e) => e.actor_type === "citizen");
  const worker = issue.evidence.filter((e) => e.actor_type === "worker");
  const tiles: React.ReactNode[] = [];
  for (const e of [...citizen.slice(0, 1), ...worker.slice(0, 1)]) tiles.push(<EvidenceTile key={e.evidence_id} item={e} />);
  if (tiles.length < 2) {
    for (const r of issue.reports.filter((r) => r.photo_url).slice(0, 2 - tiles.length)) {
      tiles.push(
        <PhotoTile key={`r${r.id}`} src={mediaUrl(r.photo_url!)} title="Citizen Upload"
          sub={`${fmtTime(r.reported_at)} • ${r.geom_confidence === 1 ? "GPS MATCH" : "APPROX"}`} good={r.geom_confidence === 1} />,
      );
    }
  }
  const total = issue.evidence.length + issue.reports.filter((r) => r.photo_url).length;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-ws-body text-xs text-ws-on-surface uppercase tracking-wider font-bold">Spatial Photographic Evidence</span>
        <span className="text-[11px] font-semibold text-ws-primary">{issue.evidence.length} Geo-Tagged</span>
      </div>
      {tiles.length ? (
        <div className="grid grid-cols-2 gap-2">{tiles}</div>
      ) : (
        <p className="p-3 rounded bg-ws-surface-low font-ws-body text-xs text-ws-on-surface-variant">
          No photo evidence on file{total === 0 && issue.report_count ? ` for ${issue.report_count} report(s)` : ""}.
        </p>
      )}
    </div>
  );
}

function EvidenceTile({ item }: { item: EvidenceItem }) {
  const { src, failed } = useEvidencePhoto(item.file_url);
  const verified = item.review_status === "verified";
  const dist = item.distance_from_issue_m != null ? ` • ${Math.round(item.distance_from_issue_m)}m` : "";
  return (
    <PhotoTile
      src={failed ? null : src}
      title={item.actor_type === "citizen" ? "Citizen Ingestion" : "Crew Resolution"}
      sub={`${fmtTime(item.captured_at ?? item.submitted_at)}${dist} • ${verified ? "GPS MATCH" : item.review_status === "review_required" ? "REVIEW" : "PENDING"}`}
      good={verified}
    />
  );
}

function PhotoTile({ src, title, sub, good }: { src: string | null; title: string; sub: string; good: boolean }) {
  return (
    <div className="group relative rounded overflow-hidden shadow-sm bg-ws-surface-container h-28">
      {src ? (
        <img src={src} alt={title} className="w-full h-28 object-cover group-hover:scale-105 transition-all duration-300" />
      ) : (
        <div className="w-full h-28 animate-pulse" />
      )}
      <div className="absolute bottom-0 inset-x-0 p-1.5 bg-ws-navy/80 backdrop-blur text-white text-[10px] font-ws-headline flex flex-col">
        <span className="font-bold uppercase">{title}</span>
        <span className={good ? "text-emerald-400" : "text-ws-surface-variant"}>{sub}</span>
      </div>
    </div>
  );
}

export default CommandCenter;
