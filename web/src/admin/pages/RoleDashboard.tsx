import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CATEGORY_LABELS } from "../../api/types";
import type { DashboardResponse, DashboardWardRow } from "../../api/types";
import { BandChip, Card, Icon, Page, SectionLabel, Skeleton, fmtDate, issueCode } from "../components/ws";
import { ROLE_TITLES, useMe } from "../components/StaffGate";

// Home page, shaped by the PMC role of whoever signs in. Every number comes
// from GET /api/dashboard, which is already limited to the caller's scope.
//   ward_officer       (AMC)    -> my prabhags + the priority queue
//   zonal_commissioner (DMC)    -> ward offices in my zone, side by side
//   department_officer          -> my department's backlog by category and office
//   system_admin                -> zones city-wide + staff coverage gaps

interface Rollup { key: string; label: string; sub?: string; open: number; closed: number; unrouted: number; avgAge: number | null }

/** Group ward rows, averaging open age weighted by open issues. */
function rollup(rows: DashboardWardRow[], key: (r: DashboardWardRow) => string, label: (r: DashboardWardRow) => string,
                sub?: (r: DashboardWardRow) => string): Rollup[] {
  const out = new Map<string, Rollup & { ageSum: number }>();
  for (const r of rows) {
    const k = key(r);
    const g = out.get(k) ?? { key: k, label: label(r), sub: sub?.(r), open: 0, closed: 0, unrouted: 0, avgAge: null, ageSum: 0 };
    g.open += r.open;
    g.closed += r.closed;
    g.unrouted += r.unrouted;
    g.ageSum += (r.avg_open_age_days ?? 0) * r.open;
    out.set(k, g);
  }
  return [...out.values()]
    .map(({ ageSum, ...g }) => ({ ...g, avgAge: g.open ? Math.round((ageSum / g.open) * 10) / 10 : null }))
    .sort((a, b) => b.open - a.open);
}

const byOffice = (rows: DashboardWardRow[]) =>
  rollup(rows, (r) => String(r.ward_office_id ?? "none"), (r) => r.ward_office ?? "No ward office", (r) => r.zone ?? "");
const byZone = (rows: DashboardWardRow[]) => rollup(rows, (r) => String(r.zone_id ?? "none"), (r) => r.zone ?? "Unmapped");

export function RoleDashboard() {
  const me = useMe();
  const { data, loading, error } = useApi(() => api.dashboard(), []);

  return (
    <Page>
      <div className="px-6 py-3 bg-ws-surface-low flex flex-wrap items-center justify-between gap-3 font-ws-label">
        <div className="flex items-center gap-2 text-xs text-[#535f74]">
          <span className="px-1.5 py-0.5 rounded bg-ws-blue text-white text-[11px] font-bold">PMC</span>
          <span>/</span>
          <span className="font-ws-body text-sm text-ws-on-surface font-semibold">{ROLE_TITLES[me.role] ?? me.role}</span>
        </div>
        <span className="px-2.5 py-1 rounded-full bg-ws-primary/10 text-ws-primary text-[11px] font-semibold">
          {data?.scope_label ?? "…"}
        </span>
      </div>

      <div className="px-6 py-4 flex flex-col gap-4 font-ws-label">
        <p className="font-ws-body text-sm text-ws-on-surface">
          Welcome{me.display_name ? `, ${me.display_name}` : ""}. Everything here is limited to your scope.
        </p>
        {error && <Card className="p-4 text-sm text-ws-error">Couldn't load your dashboard: {error}</Card>}
        {loading && !data && <Skeleton className="h-64" />}
        {data && <Kpis data={data} />}
        {data && me.role === "ward_officer" && <WardOfficerView data={data} />}
        {data && me.role === "zonal_commissioner" && <ZonalView data={data} />}
        {data && me.role === "department_officer" && <DepartmentView data={data} />}
        {data && me.role === "system_admin" && <AdminView data={data} />}
      </div>
    </Page>
  );
}

function Kpis({ data }: { data: DashboardResponse }) {
  const [all] = rollup(data.by_ward, () => "all", () => "all");
  const tiles = [
    { label: "Open issues", value: all?.open ?? 0, icon: "report_problem" },
    { label: "Open, not yet routed", value: all?.unrouted ?? 0, icon: "alt_route" },
    { label: "Closed", value: all?.closed ?? 0, icon: "task_alt" },
    { label: "Avg. open age", value: all?.avgAge != null ? `${all.avgAge} d` : "—", icon: "schedule" },
  ];
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {tiles.map((t) => (
        <Card key={t.label} className="p-4 flex items-center gap-3">
          <Icon name={t.icon} className="text-[24px] text-ws-blue" />
          <div className="flex flex-col">
            <span className="font-ws-headline text-xl font-semibold text-ws-on-surface">{t.value}</span>
            <span className="text-[11px] text-[#535f74]">{t.label}</span>
          </div>
        </Card>
      ))}
    </div>
  );
}

function RollupTable({ title, rows, link }: { title: string; rows: Rollup[]; link?: (r: Rollup) => string | null }) {
  const worstAge = Math.max(...rows.map((r) => r.avgAge ?? 0));
  return (
    <Card className="p-4 flex flex-col gap-2">
      <SectionLabel>{title}</SectionLabel>
      {rows.length === 0 ? (
        <p className="text-xs text-[#535f74]">No issues in scope yet.</p>
      ) : (
        <table className="w-full text-xs">
          <thead className="text-[#535f74] text-left">
            <tr><th className="py-1">Name</th><th>Open</th><th>Not routed</th><th>Closed</th><th>Avg. open age</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const href = link?.(r);
              return (
                <tr key={r.key} className="border-t border-ws-surface-high">
                  <td className="py-1.5">
                    {href ? <Link to={href} className="font-semibold text-ws-blue hover:underline">{r.label}</Link>
                      : <span className="font-semibold">{r.label}</span>}
                    {r.sub && <span className="ml-1 text-[#535f74]">· {r.sub}</span>}
                  </td>
                  <td className="font-ws-headline">{r.open}</td>
                  <td className="font-ws-headline">{r.unrouted}</td>
                  <td className="font-ws-headline">{r.closed}</td>
                  <td className={`font-ws-headline ${r.avgAge && r.avgAge === worstAge && rows.length > 1 ? "text-amber-700 font-semibold" : ""}`}>
                    {r.avgAge != null ? `${r.avgAge} d` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {rows.length > 1 && <p className="text-[11px] text-[#535f74]">Longest average open age highlighted for review, not as a finding.</p>}
    </Card>
  );
}

function PriorityQueue({ data, title = "Priority queue" }: { data: DashboardResponse; title?: string }) {
  return (
    <Card className="p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <SectionLabel>{title}</SectionLabel>
        <Link to="/issues" className="text-[11px] text-ws-blue font-semibold hover:underline">All issues →</Link>
      </div>
      {data.top_open_issues.length === 0 && <p className="text-xs text-[#535f74]">No open issues.</p>}
      {data.top_open_issues.map((i) => (
        <Link key={i.issue_id} to={`/issues/${i.issue_id}`}
          className="flex items-center gap-3 p-2 rounded hover:bg-ws-surface-low text-xs">
          <BandChip score={i.priority_score} soft />
          <span className="font-ws-headline font-semibold">{issueCode(i.issue_id)}</span>
          <span>{CATEGORY_LABELS[i.category] ?? i.category}</span>
          <span className="text-[#535f74]">{i.ward_name ?? "Ward unknown"}</span>
          <span className="ml-auto text-[#535f74]">{i.report_count} report{i.report_count === 1 ? "" : "s"} · since {fmtDate(i.first_reported)}</span>
          {!i.routed_agency && <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-semibold">Not routed</span>}
        </Link>
      ))}
    </Card>
  );
}

function CategoryBars({ data }: { data: DashboardResponse }) {
  const entries = Object.entries(data.by_category);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <Card className="p-4 flex flex-col gap-2">
      <SectionLabel>Open issues by category</SectionLabel>
      {entries.length === 0 && <p className="text-xs text-[#535f74]">No open issues.</p>}
      {entries.map(([cat, n]) => (
        <div key={cat} className="flex items-center gap-2 text-xs">
          <span className="w-40 shrink-0">{CATEGORY_LABELS[cat] ?? cat}</span>
          <div className="flex-1 h-2 rounded bg-ws-surface-high">
            <div className="h-2 rounded bg-ws-blue" style={{ width: `${(n / max) * 100}%` }} />
          </div>
          <span className="w-8 text-right font-ws-headline">{n}</span>
        </div>
      ))}
    </Card>
  );
}

function QuickLinks({ links }: { links: { to: string; label: string; icon: string }[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {links.map((l) => (
        <Link key={l.to} to={l.to}
          className="px-3 py-2 rounded bg-white shadow-sm text-xs font-semibold text-ws-on-surface flex items-center gap-1.5 hover:bg-ws-surface-low">
          <Icon name={l.icon} className="text-[18px] text-ws-blue" /> {l.label}
        </Link>
      ))}
    </div>
  );
}

function WardOfficerView({ data }: { data: DashboardResponse }) {
  const prabhags = rollup(data.by_ward, (r) => String(r.ward_id), (r) => r.ward_name ?? "Ward unknown",
    (r) => (r.ward_id != null ? `Prabhag ${r.ward_id}` : ""));
  return (
    <>
      <QuickLinks links={[
        { to: "/held", label: "Held for review", icon: "gpp_maybe" },
        { to: "/verification", label: "Field verification", icon: "verified" },
        { to: "/map", label: "Map", icon: "map" },
      ]} />
      <PriorityQueue data={data} title="Your priority queue" />
      <RollupTable title="Your prabhags" rows={prabhags}
        link={(r) => (r.key !== "null" ? `/wards/${r.key}` : null)} />
    </>
  );
}

function ZonalView({ data }: { data: DashboardResponse }) {
  return (
    <>
      <RollupTable title="Ward offices in your zone" rows={byOffice(data.by_ward)} />
      <div className="grid lg:grid-cols-2 gap-4">
        <PriorityQueue data={data} title="Highest-priority open issues in the zone" />
        <CategoryBars data={data} />
      </div>
    </>
  );
}

function DepartmentView({ data }: { data: DashboardResponse }) {
  return (
    <>
      <div className="grid lg:grid-cols-2 gap-4">
        <CategoryBars data={data} />
        <RollupTable title="Your backlog by zone" rows={byZone(data.by_ward)} />
      </div>
      <RollupTable title="Your backlog by ward office" rows={byOffice(data.by_ward)} />
      <PriorityQueue data={data} />
    </>
  );
}

function AdminView({ data }: { data: DashboardResponse }) {
  return (
    <>
      <QuickLinks links={[
        { to: "/staff", label: "Staff & Roles", icon: "manage_accounts" },
        { to: "/audit", label: "Audit log", icon: "history" },
        { to: "/command", label: "Command Center", icon: "radar" },
      ]} />
      <StaffCoverage />
      <RollupTable title="Zones" rows={byZone(data.by_ward)} />
      <RollupTable title="Ward offices" rows={byOffice(data.by_ward)} />
      <PriorityQueue data={data} title="City-wide priority queue" />
    </>
  );
}

/** Which ward offices and zones have nobody assigned, and how much of the
 * prabhag -> office mapping is still a draft. */
function StaffCoverage() {
  const { data: org } = useApi(() => api.org(), []);
  const { data: users } = useApi(() => api.adminUsers(), []);
  if (!org || !users) return <Skeleton className="h-24" />;

  const active = users.filter((u) => u.is_active);
  const coveredOffices = new Set(active.filter((u) => u.role === "ward_officer").flatMap((u) => u.ward_office_ids));
  const coveredZones = new Set(active.filter((u) => u.role === "zonal_commissioner").flatMap((u) => u.zone_ids));
  const offices = org.zones.flatMap((z) => z.ward_offices);
  const wards = offices.flatMap((o) => o.wards).concat(org.unmapped_wards);
  const unverified = wards.filter((w) => !w.verified).length;
  const counts = active.reduce<Record<string, number>>((acc, u) => ({ ...acc, [u.role]: (acc[u.role] ?? 0) + 1 }), {});

  return (
    <Card className="p-4 flex flex-col gap-3">
      <SectionLabel>Staff coverage</SectionLabel>
      <div className="flex flex-wrap gap-2 text-xs">
        {["zonal_commissioner", "ward_officer", "department_officer", "field_worker", "system_admin"].map((r) => (
          <span key={r} className="px-2 py-1 rounded bg-ws-surface-low">
            {ROLE_TITLES[r]}: <b className="font-ws-headline">{counts[r] ?? 0}</b>
          </span>
        ))}
      </div>
      <div className="grid md:grid-cols-2 gap-3 text-xs">
        <div>
          <span className="font-semibold">Zones without a zonal commissioner: </span>
          {org.zones.filter((z) => !coveredZones.has(z.id)).map((z) => z.name).join(", ") || "none"}
        </div>
        <div>
          <span className="font-semibold">Ward offices without an AMC: </span>
          {offices.filter((o) => !coveredOffices.has(o.id)).map((o) => o.name).join(", ") || "none"}
        </div>
      </div>
      {unverified > 0 && (
        <p className="text-[11px] text-amber-800 flex items-center gap-1">
          <Icon name="warning" className="text-[16px]" />
          {unverified} of {wards.length} prabhag → ward office assignments are a draft and still need human verification.
        </p>
      )}
    </Card>
  );
}

export default RoleDashboard;
