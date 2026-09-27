import { useParams, Link } from "react-router-dom";
import { MapContainer, TileLayer, CircleMarker } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CATEGORY_LABELS } from "../../api/types";
import { Icon } from "../../admin/components/ws";
import { Kicker, SplitCTA } from "../Shell";

// Public view of one problem, in the Stitch "Sentry Editorial Civic" style: the
// no-sign-in projection from GET /api/public/issues/:id (no report text,
// location rounded to ~100 m).

const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—");

export function PublicIssueDetail() {
  const { issueId } = useParams();
  const { data: issue, loading, error, reload } = useApi(() => api.publicIssue(Number(issueId)), [issueId]);

  if (loading) return <p className="px-5 md:px-12 py-20 text-se-variant">Loading…</p>;
  if (error) return <p className="px-5 md:px-12 py-20 text-red-700">{error} <button type="button" onClick={reload} className="underline">Try again</button></p>;
  if (!issue) return null;

  const closed = issue.status === "closed";
  const facts: [string, string][] = [
    ["Problem number", `#${issue.issue_id}`],
    ["Status", closed ? "Fixed" : issue.status === "reopened" ? "Reopened" : "Waiting to be fixed"],
    ["Residents who reported it", String(issue.report_count)],
    ["First reported", day(issue.first_reported)],
  ];
  const timeline: [string, string | null][] = [
    ["First reported", issue.first_reported],
    ...(issue.report_count > 1 ? [["Latest report", issue.last_reported] as [string, string | null]] : []),
    ...(closed ? [["Fixed, with a photo from the spot", issue.closed_at] as [string, string | null]] : []),
  ];

  return (
    <>
      <section className="w-full bg-se-surface px-5 md:px-12 pt-10 pb-10">
        <Link to="/citizen/issues" className="inline-flex items-center gap-1 font-se-code text-se-code uppercase text-se-variant hover:text-se-on group">
          <Icon name="arrow_back" className="text-[16px] group-hover:-translate-x-1 transition-transform" />Pune Pulse
        </Link>
        <Kicker className="block mt-6">{issue.ward_id != null ? `Ward ${issue.ward_id} // ${issue.ward_name ?? ""}` : "Ward being found"}</Kicker>
        <h1 className="mt-3 font-se-sans text-[40px] leading-[46px] md:text-se-xl md:leading-[64px] text-se-on tracking-tight">{CATEGORY_LABELS[issue.category] ?? issue.category}</h1>
        <div className="mt-10 grid grid-cols-2 md:grid-cols-4 bg-se-lowest border border-se-outline-variant/60">
          {facts.map(([k, v], i) => (
            <div key={k} className={`p-4 ${i % 2 ? "border-l border-se-outline-variant/60" : ""} ${i === 2 ? "md:border-l md:border-se-outline-variant/60" : ""} ${i >= 2 ? "max-md:border-t" : ""}`}>
              <Kicker>{k}</Kicker>
              <div className={`mt-2 font-se-sans text-se-title ${i === 1 && closed ? "text-emerald-700" : "text-se-on"}`}>{v}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="w-full bg-se-surface px-5 md:px-12 pb-12 grid grid-cols-1 lg:grid-cols-12 gap-7">
        <div className="lg:col-span-7">
          {issue.location ? (
            <div className="relative h-[380px] border border-se-outline-variant/60 bg-se-high">
              <MapContainer center={[issue.location.lat, issue.location.lon]} zoom={15} zoomControl={false} scrollWheelZoom={false} attributionControl={false} style={{ height: "100%", background: "#e8e8e9" }}>
                <TileLayer className="se-gray-tiles" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <CircleMarker center={[issue.location.lat, issue.location.lon]} radius={issue.location_precision === "ward_level" ? 40 : 14}
                  pathOptions={{ color: "#000", weight: 1.5, fillColor: closed ? "#10b981" : "#000", fillOpacity: 0.25 }} />
              </MapContainer>
              <span className="absolute bottom-2 left-2 z-[500] px-2 py-1 bg-se-primary text-white font-se-code text-[10px] uppercase tracking-wider">
                {issue.location_precision === "ward_level" ? "Shown at the centre of the ward" : "Approximate spot — hidden slightly for privacy"}
              </span>
            </div>
          ) : (
            <div className="h-[380px] border border-se-outline-variant/60 bg-se-low flex items-center justify-center text-se-variant font-se-sans text-se-sm">
              The exact spot hasn’t been placed on the map yet.
            </div>
          )}
        </div>

        <div className="lg:col-span-5 flex flex-col gap-7">
          <div className="p-7 bg-se-lowest border border-se-outline-variant/60">
            <Kicker>Timeline</Kicker>
            <ul className="mt-4 space-y-4">
              {timeline.map(([label, t]) => (
                <li key={label} className="flex gap-3">
                  <span className="mt-1.5 w-2 h-2 rounded-full bg-se-primary shrink-0" />
                  <span>
                    <span className="block font-se-sans text-se-body text-se-on">{label}</span>
                    <span className="font-se-code text-[11px] text-se-variant">{day(t)}</span>
                  </span>
                </li>
              ))}
              {!closed && (
                <li className="flex gap-3 opacity-60">
                  <span className="mt-1.5 w-2 h-2 rounded-full border border-se-primary shrink-0" />
                  <span className="font-se-sans text-se-body text-se-on">Waiting for the crew’s fix</span>
                </li>
              )}
            </ul>
          </div>
          <div className="p-7 bg-se-primary-container text-white">
            <Kicker className="text-white/60">{closed ? "Did you report this?" : "Seen this too?"}</Kicker>
            <p className="mt-2 font-se-sans text-se-title">
              {closed ? "Confirm the fix — or reopen it if it isn’t really fixed." : "Report it too. Every report shows your ward how many people are affected."}
            </p>
            <Link to={closed ? "/citizen/my-reports" : "/citizen/report"}
              className="mt-6 h-12 px-5 bg-white text-se-on flex items-center justify-between font-se-code text-se-code uppercase tracking-wider font-semibold">
              {closed ? "Track my report" : "Report it too"} <Icon name="arrow_forward" className="text-[18px]" />
            </Link>
          </div>
        </div>
      </section>

      <SplitCTA
        left={{ to: "/citizen/issues", kicker: "Pune Pulse", title: "Explore Your Ward", text: "Every reported problem on one map, and how each ward is doing." }}
        right={{ to: "/citizen/report", kicker: "Something wrong nearby?", title: "Report a Problem", text: "It takes under a minute — type it or just speak it." }}
      />
    </>
  );
}
export default PublicIssueDetail;
