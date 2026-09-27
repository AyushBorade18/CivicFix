import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { GeoJSON, MapContainer, TileLayer, CircleMarker, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CATEGORY_LABELS } from "../../api/types";
import type { MapWard, PublicIssue } from "../../api/types";
import { Icon } from "../../admin/components/ws";
import { Kicker, SplitCTA } from "../Shell";

// Pune Pulse, ported from the Stitch export
// stitch_wardsentry_citizen_portal/pune_pulse_ward_map_metrics.
// Public, no-sign-in data only (/api/public/map); every number is computed here from it.

const PUNE: [number, number] = [18.5204, 73.8567];
const DAY = 86_400_000;
const n = (v: number) => v.toLocaleString("en-IN");
const short = (name: string) => name.split(" - ")[0];

type WardRow = { ward: MapWard; open: number; fixed: number; reports: number; top: string | null };

export function PublicIssues() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const category = params.get("category") ?? "";
  const { data, loading, error, reload } = useApi(() => api.publicMap(), []);
  const [focusId, setFocusId] = useState<number | null>(null);
  const [wardFilter, setWardFilter] = useState<number | null>(null);
  const [sort, setSort] = useState<"open" | "fixed">("open");

  const all = useMemo(() => data?.issues ?? [], [data]);
  const wards = useMemo(() => data?.wards ?? [], [data]);
  const issues = useMemo(() => all.filter((i) => !category || i.category === category), [all, category]);

  const counts = useMemo(() => {
    const c = new Map<string, number>();
    for (const i of all) c.set(i.category, (c.get(i.category) ?? 0) + 1);
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [all]);

  const rows = useMemo<WardRow[]>(() => {
    const by = new Map<number, PublicIssue[]>();
    for (const i of issues) if (i.ward_id != null) by.set(i.ward_id, [...(by.get(i.ward_id) ?? []), i]);
    return [...by.entries()].flatMap(([id, list]) => {
      const ward = wards.find((w) => w.ward_id === id);
      if (!ward) return [];
      const cats = new Map<string, number>();
      for (const i of list) if (i.status !== "closed") cats.set(i.category, (cats.get(i.category) ?? 0) + 1);
      const top = [...cats.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
      const fixed = list.filter((i) => i.status === "closed").length;
      return [{ ward, open: list.length - fixed, fixed, reports: list.reduce((s, i) => s + i.report_count, 0), top }];
    });
  }, [issues, wards]);

  const byOpen = useMemo(() => [...rows].sort((a, b) => b.open - a.open), [rows]);
  const board = sort === "open" ? byOpen : [...rows].sort((a, b) => b.fixed - a.fixed || b.open - a.open);
  const focus = rows.find((r) => r.ward.ward_id === focusId) ?? byOpen[0] ?? null;

  const open = issues.filter((i) => i.status !== "closed").length;
  const fixed = issues.length - open;
  const reports = issues.reduce((s, i) => s + i.report_count, 0);
  const grouped = issues.filter((i) => i.report_count > 1);
  const weeks = useMemo(() => {
    const now = Date.now();
    const w = Array(8).fill(0) as number[];
    for (const i of issues) {
      const t = Date.parse(i.last_reported ?? i.first_reported ?? "");
      const k = Math.floor((now - t) / (7 * DAY));
      if (k >= 0 && k < 8) w[7 - k] += i.report_count;
    }
    return w;
  }, [issues]);
  const list = issues
    .filter((i) => wardFilter == null || i.ward_id === wardFilter)
    .sort((a, b) => Date.parse(b.last_reported ?? "0") - Date.parse(a.last_reported ?? "0"))
    .slice(0, 12);

  const setCategory = (c: string) => setParams(c ? { category: c } : {}, { replace: true });
  const showWard = (id: number) => {
    setWardFilter(id);
    document.getElementById("latest")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <>
      {/* Hero + stats */}
      <section className="w-full bg-se-surface px-5 md:px-12 pt-10 pb-10">
        <Kicker className="flex items-center gap-2"><span className="w-2 h-2 bg-se-primary" />Pune Pulse // Updated live</Kicker>
        <h1 className="mt-4 font-se-sans text-[40px] leading-[46px] md:text-se-xl md:leading-[64px] text-se-on tracking-tight">Pune Civic Pulse &amp; Ward Map</h1>
        <p className="mt-4 max-w-2xl font-se-sans text-se-body-xl text-se-variant">
          See what your neighbours are reporting, which wards need the most attention, and how much has already been fixed.
        </p>
        <div className="mt-10 grid grid-cols-2 md:grid-cols-4 bg-se-lowest border border-se-outline-variant/60">
          {([
            ["Wards with reports", data ? `${rows.length} / ${wards.length}` : "—"],
            ["Problems reported", data ? n(issues.length) : "—"],
            ["Fixed so far", data ? (issues.length ? `${Math.round((fixed / issues.length) * 100)}%` : "0%") : "—"],
            ["Reports from residents", data ? n(reports) : "—"],
          ] as [string, string][]).map(([k, v], i) => (
            <div key={k} className={`p-4 ${i % 2 ? "border-l border-se-outline-variant/60" : ""} ${i === 2 ? "md:border-l md:border-se-outline-variant/60" : ""} ${i >= 2 ? "max-md:border-t" : ""}`}>
              <Kicker>{k}</Kicker>
              <div className="mt-2 font-se-sans text-se-title md:text-se-md text-se-on">{v}</div>
            </div>
          ))}
        </div>
        <a href="#map" className="mt-7 flex flex-col items-center gap-1 text-se-variant hover:text-se-on">
          <Icon name="arrow_downward" className="text-[18px]" />
          <span className="font-se-code text-[10px] uppercase tracking-widest">Scroll to explore</span>
          <span className="w-8 h-0.5 bg-se-outline-variant relative overflow-hidden"><span className="absolute inset-y-0 left-0 w-3 bg-se-primary" /></span>
        </a>
      </section>

      {/* Filter rail */}
      <section className="w-full bg-se-lowest border-y border-se-outline-variant/40 px-5 md:px-12 py-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-1 overflow-x-auto [scrollbar-width:none] font-se-code text-se-code whitespace-nowrap uppercase">
          <button type="button" onClick={() => setCategory("")} className={`px-4 py-2 ${!category ? "bg-se-primary text-white" : "bg-se-container hover:bg-se-high"}`}>
            All problems ({n(all.length)})
          </button>
          {counts.map(([c, count]) => (
            <button key={c} type="button" onClick={() => setCategory(c)}
              className={`px-4 py-2 transition-colors ${category === c ? "bg-se-primary text-white" : "bg-se-container hover:bg-se-high"}`}>
              {CATEGORY_LABELS[c] ?? c} ({count})
            </button>
          ))}
        </div>
        <a href="#latest" className="shrink-0 px-4 py-2 bg-se-container font-se-code text-[11px] uppercase tracking-widest hover:bg-se-primary hover:text-white">See all</a>
      </section>

      {/* Map */}
      <section id="map" className="w-full bg-se-surface px-5 md:px-12 py-12 scroll-mt-28">
        <div className="relative h-[520px] md:h-[600px] border border-se-outline-variant/60 bg-se-high overflow-hidden shadow-sm">
          {loading && <p className="absolute inset-0 flex items-center justify-center text-se-variant">Loading map…</p>}
          {error && <p className="absolute inset-0 flex items-center justify-center text-red-700">{error} <button type="button" onClick={reload} className="underline ml-1">Try again</button></p>}
          {data && (
            <MapContainer center={PUNE} zoom={12} zoomControl={false} scrollWheelZoom={false} attributionControl={false} style={{ height: "100%", background: "#e8e8e9" }}>
              <TileLayer className="se-gray-tiles" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <WardLayer wards={wards} focusId={focus?.ward.ward_id ?? null} onPick={setFocusId} />
              {issues.filter((i) => i.location).map((i) => (
                <CircleMarker key={i.issue_id} center={[i.location!.lat, i.location!.lon]} radius={4}
                  eventHandlers={{ click: () => navigate(`/citizen/issues/${i.issue_id}`) }}
                  pathOptions={{ color: "#fff", weight: 1, fillColor: i.status === "closed" ? "#10b981" : "#000", fillOpacity: 0.9 }} />
              ))}
            </MapContainer>
          )}
          <div className="absolute top-3 left-3 z-[500] px-3 py-2 bg-se-lowest/95 border border-se-outline-variant/60 font-se-code text-[10px] uppercase tracking-wider flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />Pune // Live map
            <span className="text-se-variant normal-case tracking-normal">● waiting <span className="text-emerald-600">●</span> fixed</span>
          </div>
          <div className="absolute top-3 right-3 z-[500] hidden md:flex bg-se-lowest/95 border border-se-outline-variant/60 font-se-code text-[10px] uppercase">
            {byOpen.slice(0, 4).map((r) => (
              <button key={r.ward.ward_id} type="button" onClick={() => setFocusId(r.ward.ward_id)}
                className={`px-3 py-2 ${focus?.ward.ward_id === r.ward.ward_id ? "bg-se-primary text-white" : "hover:bg-se-container"}`}>
                {short(r.ward.name)}
              </button>
            ))}
          </div>
          {focus && (
            <div className="absolute bottom-3 left-3 right-3 md:right-auto md:max-w-md z-[500] p-4 bg-se-lowest border border-se-outline-variant/60 shadow-[0_4px_20px_rgba(0,0,0,0.08)]">
              <div className="flex items-center justify-between gap-2">
                <Kicker>Ward {focus.ward.ward_id} // In focus</Kicker>
                <span className={`px-1.5 py-0.5 font-se-code text-[9px] uppercase border ${focus.open ? "bg-amber-50 text-amber-800 border-amber-200" : "bg-emerald-50 text-emerald-700 border-emerald-200"}`}>
                  {focus.open ? "Needs attention" : "All clear"}
                </span>
              </div>
              <h3 className="mt-1 font-se-sans text-se-title text-se-on">{focus.ward.name}</h3>
              <p className="mt-1 font-se-sans text-se-sm text-se-variant">
                {focus.open} problem{focus.open === 1 ? "" : "s"} waiting to be fixed, {focus.fixed} fixed.
                {focus.top && <> Most reported here: {(CATEGORY_LABELS[focus.top] ?? focus.top).toLowerCase()}.</>}
              </p>
              <div className="mt-3 flex items-center justify-between font-se-code text-[10px] uppercase">
                <span className="flex items-center gap-3 text-se-variant"><span>● {n(focus.reports)} reports</span><span>● {focus.fixed} fixed</span></span>
                <button type="button" onClick={() => showWard(focus.ward.ward_id)} className="underline text-se-on">See this ward →</button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Statement + metric cards */}
      <section className="w-full bg-se-lowest px-5 md:px-12 py-20">
        <h2 className="max-w-5xl font-se-sans text-[32px] leading-[38px] md:text-se-xl md:leading-[64px] text-se-on tracking-tight">
          One map, every ward. What your neighbours report across {wards.length ? `all ${wards.length}` : "all"} wards of Pune, as it happens.
        </h2>
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-4 max-w-6xl">
          <div className="p-6 bg-se-low">
            <Kicker>Reports, last 8 weeks</Kicker>
            <div className="mt-2 font-se-sans text-se-md text-se-on">{n(weeks[7])} <span className="text-se-body text-se-variant">this week</span></div>
            <Spark values={weeks} />
          </div>
          <div className="p-6 bg-se-low">
            <Kicker>Counted together</Kicker>
            <div className="mt-2 font-se-sans text-se-md text-se-on">{n(grouped.length)} problems</div>
            <p className="mt-4 font-se-sans text-se-sm text-se-variant flex items-start gap-2">
              <Icon name="groups" className="text-[18px]" />Reported by more than one resident — shown once, with everyone’s voice counted.
            </p>
          </div>
          <div className="p-6 bg-se-low">
            <Kicker>Proof of every fix</Kicker>
            <div className="mt-2 font-se-sans text-se-md text-se-on">{n(fixed)} fixed</div>
            <p className="mt-4 font-se-code text-[11px] text-emerald-700 flex items-center gap-1">
              <Icon name="check_circle" className="text-[16px]" />Each closed with a photo from the spot
            </p>
          </div>
        </div>
      </section>

      {/* Leaderboard */}
      <section className="w-full bg-se-surface px-5 md:px-12 py-20">
        <Kicker>Ward scorecard</Kicker>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <h2 className="font-se-sans text-se-lg text-se-on tracking-tight">How Each Ward Is Doing</h2>
          <div className="font-se-code text-[11px] uppercase text-se-variant flex items-center gap-2">
            Sort by:
            <button type="button" onClick={() => setSort("open")} className={sort === "open" ? "underline text-se-on" : "hover:text-se-on"}>Most waiting</button>•
            <button type="button" onClick={() => setSort("fixed")} className={sort === "fixed" ? "underline text-se-on" : "hover:text-se-on"}>Most fixed</button>
          </div>
        </div>
        <div className="mt-7 bg-se-lowest border border-se-outline-variant/60 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left">
            <thead className="font-se-code text-[10px] uppercase tracking-wider text-se-variant border-b border-se-outline-variant/60">
              <tr>{["Ward", "Waiting", "Fixed", "Reports", "Share fixed", "Status", ""].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody className="font-se-sans text-se-sm">
              {board.slice(0, 10).map((r) => {
                const pct = r.open + r.fixed ? Math.round((r.fixed / (r.open + r.fixed)) * 100) : 0;
                const busy = r.open > 5;
                return (
                  <tr key={r.ward.ward_id} className="border-b border-se-high last:border-0 hover:bg-se-low">
                    <td className="px-4 py-3"><span className={`inline-block w-1.5 h-1.5 rounded-full mr-2 align-middle ${busy ? "bg-amber-600" : "bg-emerald-500"}`} />{short(r.ward.name)} (Ward {r.ward.ward_id})</td>
                    <td className="px-4 py-3">{r.open}</td>
                    <td className="px-4 py-3">{r.fixed}</td>
                    <td className="px-4 py-3">{n(r.reports)}</td>
                    <td className="px-4 py-3"><span className="flex items-center gap-2"><span className="w-24 h-1 bg-se-high"><span className="block h-full bg-se-primary" style={{ width: `${pct}%` }} /></span>{pct}%</span></td>
                    <td className="px-4 py-3"><span className={`px-1.5 py-0.5 font-se-code text-[9px] uppercase border ${busy ? "bg-amber-50 text-amber-800 border-amber-200" : "bg-emerald-50 text-emerald-700 border-emerald-200"}`}>{busy ? "Needs attention" : "On track"}</span></td>
                    <td className="px-4 py-3 text-right"><button type="button" onClick={() => showWard(r.ward.ward_id)} className="font-se-code text-[11px] underline">See →</button></td>
                  </tr>
                );
              })}
              {data && board.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-se-variant">No reports of this kind yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      {/* Latest problems */}
      <section id="latest" className="w-full bg-se-lowest px-5 md:px-12 py-20 scroll-mt-28">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Kicker>{wardFilter != null ? `Ward ${wardFilter}` : "All wards"} // Latest</Kicker>
            <h2 className="mt-2 font-se-sans text-se-lg text-se-on tracking-tight">Latest Reported Problems</h2>
          </div>
          {wardFilter != null && <button type="button" onClick={() => setWardFilter(null)} className="font-se-code text-[11px] uppercase underline">Show all wards</button>}
        </div>
        <div className="mt-7 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {list.map((i) => (
            <Link key={i.issue_id} to={`/citizen/issues/${i.issue_id}`} className="group p-5 bg-se-low hover:bg-se-container transition-colors flex flex-col gap-2">
              <div className="flex items-center justify-between font-se-code text-[10px] uppercase">
                <span className="text-se-variant">#{i.issue_id}</span>
                <span className={i.status === "closed" ? "text-emerald-700" : "text-se-on"}>{i.status === "closed" ? "Fixed" : "Waiting"}</span>
              </div>
              <div className="font-se-sans text-se-title text-se-on">{CATEGORY_LABELS[i.category] ?? i.category}</div>
              <div className="font-se-sans text-se-sm text-se-variant">{i.ward_name ? `${i.ward_name} (Ward ${i.ward_id})` : "Ward being found"}</div>
              <div className="mt-auto pt-2 flex items-center justify-between font-se-code text-[11px] text-se-variant">
                <span>{i.report_count} resident report{i.report_count === 1 ? "" : "s"}</span>
                <Icon name="arrow_forward" className="text-[18px] group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>
          ))}
          {data && list.length === 0 && <p className="text-se-variant">Nothing reported here yet.</p>}
        </div>
      </section>

      <SplitCTA
        left={{ to: "/citizen/my-reports", kicker: "Your reports", title: "Track My Report", text: "Follow your own complaints step by step, and confirm when they’re fixed." }}
        right={{ to: "/citizen/report", kicker: "Something wrong nearby?", title: "Report a Problem", text: "Photo from the spot, a few words or just your voice — it goes straight to your ward team." }}
      />
    </>
  );
}

/** Ward outlines; the focused ward is filled. Clicking a ward focuses it. */
function WardLayer({ wards, focusId, onPick }: { wards: MapWard[]; focusId: number | null; onPick: (id: number) => void }) {
  const map = useMap();
  const focused = wards.find((w) => w.ward_id === focusId);
  useEffect(() => {
    if (!focused?.geometry) return;
    const b = L.geoJSON(focused.geometry as GeoJSON.GeoJsonObject).getBounds();
    if (b.isValid()) map.flyToBounds(b, { padding: [60, 60], maxZoom: 14, duration: 0.6 });
  }, [focused, map]);
  const fc = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: wards.filter((w) => w.geometry).map((w) => ({ type: "Feature" as const, properties: { id: w.ward_id }, geometry: w.geometry! })),
  }), [wards]);
  return (
    <GeoJSON key={focusId ?? "none"} data={fc}
      style={(f) => f?.properties.id === focusId
        ? { color: "#000", weight: 2, fillColor: "#555f6d", fillOpacity: 0.3 }
        : { color: "#747878", weight: 0.8, fillOpacity: 0.02 }}
      onEachFeature={(f, layer) => layer.on("click", () => onPick(f.properties.id))} />
  );
}

function Spark({ values }: { values: number[] }) {
  const max = Math.max(1, ...values);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 200},${48 - (v / max) * 44}`).join(" ");
  return (
    <svg viewBox="0 0 200 50" className="mt-4 w-full h-12" aria-label="Reports per week, last 8 weeks">
      <polygon points={`0,50 ${pts} 200,50`} fill="#e2e2e3" />
      <polyline points={pts} fill="none" stroke="#000" strokeWidth="1.5" />
    </svg>
  );
}

export default PublicIssues;
