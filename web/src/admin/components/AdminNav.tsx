import { Link, useLocation } from "react-router-dom";
import { useApi } from "../../hooks/useApi";
import { api } from "../../api/client";
import { Icon } from "./ws";
import { ROLE_TITLES, useMe } from "./StaffGate";

// Stitch export: WardSentry-UI-References/admin-stitch/wardsentry_admin_command_center

// `roles` limits an item to those roles; the API enforces the same limits.
const NAV_ITEMS: { path: string; label: string; icon: string; roles?: string[] }[] = [
  { path: "/", label: "My Dashboard", icon: "space_dashboard" },
  { path: "/command", label: "Command Center", icon: "radar" },
  { path: "/overview", label: "Overview", icon: "dashboard" },
  { path: "/issues", label: "Issues Triage", icon: "report_problem" },
  { path: "/wards", label: "Wards Directory", icon: "location_city" },
  { path: "/works", label: "Civil Works", icon: "engineering" },
  { path: "/verification", label: "Field Verification", icon: "verified" },
  { path: "/held", label: "Held for Review", icon: "gpp_maybe" },
  { path: "/analytics", label: "Spatial Analytics", icon: "analytics" },
  { path: "/staff", label: "Staff & Roles", icon: "manage_accounts", roles: ["system_admin"] },
  { path: "/audit", label: "Audit Log", icon: "history", roles: ["system_admin"] },
];

function scopeSummary(me: { role: string; ward_ids: number[]; departments: string[] }) {
  if (me.role === "system_admin") return "All of PMC";
  if (me.role === "department_officer") return me.departments.join(", ") || "No department assigned";
  return me.ward_ids.length ? `${me.ward_ids.length} prabhag${me.ward_ids.length === 1 ? "" : "s"}` : "No wards assigned";
}


function useHealth() {
  return useApi(() => api.health().catch(() => null), []);
}

export function AdminSidebar() {
  const location = useLocation();
  const { data: health, loading: healthLoading } = useHealth();
  const me = useMe();
  const up = !!health?.database_connected;
  const isActive = (path: string) => (path === "/" ? location.pathname === "/" : location.pathname.startsWith(path));

  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-ws-surface-low z-50 flex flex-col pt-4 pb-6 shadow-[0_1px_8px_rgba(0,0,0,0.04)] font-ws-label">
      <Link to="/" className="px-4 mb-4 flex items-center gap-1">
        <Icon name="hexagon" className="text-[26px] text-ws-blue" />
        <span className="font-ws-headline text-base font-semibold text-ws-on-surface uppercase tracking-tight">WardSentry</span>
      </Link>
      <div className="px-4 mb-2">
        <div className="p-2.5 rounded bg-ws-surface-container flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[11px] font-semibold tracking-[0.06em] text-ws-on-surface-variant uppercase">{ROLE_TITLES[me.role] ?? me.role}</span>
            <span className="font-ws-body text-sm text-ws-on-surface">{scopeSummary(me)}</span>
          </div>
          <span className="w-2 h-2 rounded-full bg-ws-blue" />
        </div>
      </div>
      <nav className="flex-1 px-2 space-y-1">
        {NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(me.role)).map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`flex items-center gap-3 px-3 py-2 rounded transition-all text-xs font-semibold tracking-[0.04em] ${
              isActive(item.path)
                ? "bg-ws-blue text-white"
                : "text-ws-on-surface-variant hover:bg-ws-surface-high hover:text-ws-on-surface"
            }`}
          >
            <Icon name={item.icon} className="text-[20px]" />
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
      <div className="px-4 pt-2 pb-10">
        <div className="p-3 rounded bg-ws-navy text-ws-surface text-[11px] font-semibold">
          <div className="flex items-center justify-between text-ws-tertiary-fixed mb-1">
            <span>GIS Backend</span>
            <span className="font-ws-headline">:8000 {up ? "UP" : healthLoading ? "…" : "DOWN"}</span>
          </div>
          <div className="text-ws-surface-variant text-[11px]">
            Issues indexed: {health?.counts?.issues ?? "—"}
          </div>
        </div>
      </div>
    </aside>
  );
}

export function AdminTopBar() {
  const { data: health, loading: healthLoading } = useHealth();
  const me = useMe();
  const chip = "px-2 py-1 rounded bg-ws-inverse/60 font-ws-headline text-xs font-medium tracking-[0.02em] text-ws-tertiary-fixed";

  return (
    <header className="fixed top-0 left-64 right-0 h-16 bg-ws-navy z-40 flex items-center justify-between px-6 shadow-[0_1px_8px_rgba(0,0,0,0.18)] font-ws-label">
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1 text-white">
          <Icon name="hexagon" className="text-[24px] text-ws-blue" />
          <span className="font-ws-headline text-sm font-semibold uppercase tracking-tight">WardSentry</span>
        </span>
        <span className="px-2.5 py-0.5 rounded-full bg-ws-tertiary/30 text-ws-tertiary-fixed text-[11px] font-semibold uppercase tracking-wider">
          PMC Intelligence Cockpit
        </span>
        <div className="hidden md:flex items-center gap-2 text-ws-surface-variant text-[11px] font-semibold">
          <Icon name="chevron_right" className="text-[16px]" />
          <span>{ROLE_TITLES[me.role] ?? me.role}</span>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div className="hidden lg:flex items-center gap-1">
          <span className={chip}>Citizen :5173</span>
          <span className={chip}>Admin :5174</span>
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-ws-inverse/40 font-ws-headline text-xs text-ws-surface-high">
            <span className={`w-2 h-2 rounded-full ${health?.database_connected ? "bg-ws-blue animate-pulse" : healthLoading ? "bg-ws-surface-variant" : "bg-amber-500"}`} />
            API :8000 {health?.database_connected ? "OK" : healthLoading ? "…" : "DOWN"}
          </div>
        </div>
        <button
          onClick={() => window.dispatchEvent(new Event("ws:sync-layers"))}
          className="px-3 py-1.5 rounded bg-ws-blue text-white text-xs font-semibold hover:bg-ws-primary transition-all"
        >
          Sync Layers
        </button>
        <div
          className="w-8 h-8 rounded-full bg-ws-primary flex items-center justify-center"
          title={me.display_name ?? me.email ?? "Signed in"}
        >
          <Icon name="person" className="text-white text-[18px]" />
        </div>
      </div>
    </header>
  );
}
