import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { OrgResponse, StaffUser, UserScope } from "../../api/types";
import { Card, Icon, Page, SectionLabel, Skeleton, fmtTime } from "../components/ws";
import { ROLE_TITLES, useMe } from "../components/StaffGate";

// system_admin only (the API refuses everyone else). Grants PMC roles and
// scope: an AMC gets a ward office, a zonal commissioner a zone, a department
// officer a department. Every change lands in the audit log.

function Header({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="px-6 py-3 bg-ws-surface-low flex flex-wrap items-center justify-between gap-3 font-ws-label">
      <div className="flex items-center gap-2 text-xs text-[#535f74]">
        <span className="px-1.5 py-0.5 rounded bg-ws-blue text-white text-[11px] font-bold">PMC-ADMIN</span>
        <span>/</span>
        <span className="font-ws-body text-sm text-ws-on-surface font-semibold">{title}</span>
      </div>
      {right}
    </div>
  );
}

export function StaffRoles() {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const { data: org } = useApi(() => api.org(), []);
  const { data: users, loading, error, reload } = useApi(() => api.adminUsers({ q, role }), [q, role]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = users?.find((u) => u.id === selectedId) ?? null;

  return (
    <Page>
      <Header title="Staff & Roles" right={
        <span className="px-2.5 py-1 rounded-full bg-ws-primary/10 text-ws-primary text-[11px] font-semibold">
          {users ? `${users.length} accounts` : "…"}
        </span>} />
      <div className="px-6 py-4 grid lg:grid-cols-[minmax(0,1fr)_420px] gap-4 font-ws-label items-start">
        <Card className="p-4 flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, email or account id"
              className="flex-1 min-w-48 px-3 py-2 rounded border border-ws-surface-high text-sm" />
            <select value={role} onChange={(e) => setRole(e.target.value)}
              className="px-3 py-2 rounded border border-ws-surface-high text-sm">
              <option value="">All roles</option>
              {org?.roles.map((r) => <option key={r} value={r}>{ROLE_TITLES[r] ?? r}</option>)}
            </select>
          </div>
          {error && <p className="text-sm text-ws-error">Couldn't load accounts: {error}</p>}
          {loading && !users && <Skeleton className="h-48" />}
          <table className="w-full text-xs">
            <thead className="text-left text-[#535f74]">
              <tr><th className="py-1">Name</th><th>Role</th><th>Scope</th><th>Status</th></tr>
            </thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.id} onClick={() => setSelectedId(u.id)}
                  className={`border-t border-ws-surface-high cursor-pointer ${u.id === selectedId ? "bg-ws-blue/10" : "hover:bg-ws-surface-low"}`}>
                  <td className="py-2">
                    <div className="font-semibold">{u.display_name ?? "(no name)"}</div>
                    <div className="text-[#535f74]">{u.email ?? u.external_auth_id}</div>
                  </td>
                  <td>{ROLE_TITLES[u.role] ?? u.role}</td>
                  <td>{org ? scopeText(u, org) : "…"}</td>
                  <td>{u.is_active ? "Active" : <span className="text-ws-error">Deactivated</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        {selected && org ? (
          <UserEditor key={selected.id} user={selected} org={org} onSaved={reload} />
        ) : (
          <Card className="p-6 text-sm text-[#535f74]">
            Select an account to change its role or scope. New staff sign in once first (they start as citizens),
            then appear here to be promoted.
          </Card>
        )}
      </div>
    </Page>
  );
}

function scopeText(u: StaffUser, org: OrgResponse): string {
  const zones = org.zones.filter((z) => u.zone_ids.includes(z.id)).map((z) => z.name);
  const offices = org.zones.flatMap((z) => z.ward_offices).filter((o) => u.ward_office_ids.includes(o.id)).map((o) => o.name);
  const parts = [...zones, ...offices, ...u.departments];
  if (u.ward_ids.length) parts.push(`prabhag ${u.ward_ids.join(", ")}`);
  return parts.join(" · ") || "—";
}

function toggle<T>(list: T[], v: T): T[] {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

function UserEditor({ user, org, onSaved }: { user: StaffUser; org: OrgResponse; onSaved: () => void }) {
  const me = useMe();
  const [role, setRole] = useState(user.role);
  const [active, setActive] = useState(user.is_active);
  const [scope, setScope] = useState<UserScope>({
    ward_ids: user.ward_ids, ward_office_ids: user.ward_office_ids, zone_ids: user.zone_ids, departments: user.departments,
  });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => setMsg(null), [role, active, scope]);
  const isSelf = user.id === me.id;

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const patch: { role?: string; is_active?: boolean } = {};
      if (role !== user.role) patch.role = role;
      if (active !== user.is_active) patch.is_active = active;
      if (Object.keys(patch).length) await api.updateUser(user.id, patch);
      // Send only the scope this role uses, so a role change leaves nothing stale behind.
      const wardScoped = role === "ward_officer" || role === "zonal_commissioner";
      await api.updateUserScope(user.id, {
        ward_ids: wardScoped ? scope.ward_ids : [],
        ward_office_ids: wardScoped ? scope.ward_office_ids : [],
        zone_ids: role === "zonal_commissioner" ? scope.zone_ids : [],
        departments: role === "department_officer" ? scope.departments : [],
      });
      setMsg({ ok: true, text: "Saved. Takes effect on their next request." });
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof ApiError ? e.message : "Save failed." });
    } finally {
      setBusy(false);
    }
  }

  const box = "flex items-center gap-2 text-xs py-0.5";
  return (
    <Card className="p-4 flex flex-col gap-4 lg:sticky lg:top-4">
      <div>
        <div className="font-ws-body text-base font-semibold">{user.display_name ?? "(no name)"}</div>
        <div className="text-[11px] text-[#535f74] break-all">{user.email} · {user.external_auth_id}</div>
      </div>

      <label className="flex flex-col gap-1 text-xs">
        <SectionLabel>Role</SectionLabel>
        <select value={role} onChange={(e) => setRole(e.target.value)} disabled={isSelf}
          className="px-3 py-2 rounded border border-ws-surface-high text-sm">
          {org.roles.map((r) => <option key={r} value={r}>{ROLE_TITLES[r] ?? r}</option>)}
        </select>
      </label>
      <label className={box}>
        <input type="checkbox" checked={active} disabled={isSelf} onChange={(e) => setActive(e.target.checked)} />
        Account active
      </label>
      {isSelf && <p className="text-[11px] text-[#535f74]">You can't change your own role or deactivate yourself.</p>}

      {role === "zonal_commissioner" && (
        <div className="flex flex-col gap-1">
          <SectionLabel>Zones</SectionLabel>
          {org.zones.map((z) => (
            <label key={z.id} className={box}>
              <input type="checkbox" checked={scope.zone_ids.includes(z.id)}
                onChange={() => setScope({ ...scope, zone_ids: toggle(scope.zone_ids, z.id) })} />
              {z.name} <span className="text-[#535f74]">({z.ward_offices.map((o) => o.name).join(", ")})</span>
            </label>
          ))}
        </div>
      )}

      {(role === "ward_officer" || role === "zonal_commissioner") && (
        <div className="flex flex-col gap-1 max-h-72 overflow-auto">
          <SectionLabel>Ward offices</SectionLabel>
          {org.zones.map((z) => (
            <div key={z.id} className="flex flex-col">
              <span className="text-[10px] uppercase text-[#535f74] mt-1">{z.name}</span>
              {z.ward_offices.map((o) => (
                <label key={o.id} className={box} title={o.wards.map((w) => `${w.id} ${w.name}`).join("\n")}>
                  <input type="checkbox" checked={scope.ward_office_ids.includes(o.id)}
                    onChange={() => setScope({ ...scope, ward_office_ids: toggle(scope.ward_office_ids, o.id) })} />
                  {o.name} <span className="text-[#535f74]">· {o.wards.length} prabhags</span>
                </label>
              ))}
            </div>
          ))}
        </div>
      )}

      {role === "department_officer" && (
        <div className="flex flex-col gap-1">
          <SectionLabel>Departments</SectionLabel>
          {org.departments.map((d) => (
            <label key={d} className={box}>
              <input type="checkbox" checked={scope.departments.includes(d)}
                onChange={() => setScope({ ...scope, departments: toggle(scope.departments, d) })} />
              {d}
            </label>
          ))}
        </div>
      )}

      {(role === "citizen" || role === "system_admin" || role === "field_worker") && (
        <p className="text-[11px] text-[#535f74]">
          {role === "system_admin" ? "System administrators see all of PMC; no scope needed."
            : role === "field_worker" ? "Field workers see only issues assigned to them."
            : "Citizens have no staff scope."}
        </p>
      )}

      <button onClick={save} disabled={busy}
        className="px-4 py-2 rounded bg-ws-blue hover:bg-ws-primary text-white text-xs font-semibold flex items-center justify-center gap-1.5 disabled:opacity-50">
        <Icon name="save" className="text-[18px]" /> {busy ? "Saving…" : "Save changes"}
      </button>
      {msg && <p className={`text-xs ${msg.ok ? "text-ws-primary" : "text-ws-error"}`}>{msg.text}</p>}
    </Card>
  );
}

const ACTION_LABELS: Record<string, string> = {
  "user.update": "Changed account",
  "user.scope": "Changed scope",
  "issue.close": "Closed issue",
  "issue.route": "Routed issue",
  "issue.assign_worker": "Assigned field worker",
  "report.release_held": "Released held report",
};

export function AuditLog() {
  const [type, setType] = useState("");
  const { data, loading, error } = useApi(() => api.auditLog({ limit: 200, target_type: type || undefined }), [type]);
  return (
    <Page>
      <Header title="Audit Log" right={
        <select value={type} onChange={(e) => setType(e.target.value)}
          className="px-2 py-1 rounded border border-ws-surface-high text-xs">
          <option value="">All actions</option>
          <option value="user">Accounts &amp; roles</option>
          <option value="issue">Issues</option>
          <option value="report">Reports</option>
        </select>} />
      <div className="px-6 py-4 font-ws-label">
        <Card className="p-4">
          {error && <p className="text-sm text-ws-error">Couldn't load the audit log: {error}</p>}
          {loading && !data && <Skeleton className="h-48" />}
          {data && data.length === 0 && <p className="text-sm text-[#535f74]">Nothing recorded yet.</p>}
          {data && data.length > 0 && (
            <table className="w-full text-xs">
              <thead className="text-left text-[#535f74]">
                <tr><th className="py-1">When</th><th>Who</th><th>Action</th><th>Target</th><th>Details</th></tr>
              </thead>
              <tbody>
                {data.map((e) => (
                  <tr key={e.id} className="border-t border-ws-surface-high align-top">
                    <td className="py-1.5 whitespace-nowrap">{fmtTime(e.at)}</td>
                    <td>{e.actor_name ?? (e.actor_user_id != null ? `user ${e.actor_user_id}` : "deleted user")}</td>
                    <td>{ACTION_LABELS[e.action] ?? e.action}</td>
                    <td className="font-ws-headline">{e.target_type} #{e.target_id}</td>
                    <td className="font-ws-headline text-[11px] text-[#535f74] break-all">{JSON.stringify(e.details)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </Page>
  );
}
