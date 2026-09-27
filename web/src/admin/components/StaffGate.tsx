import { createContext, useContext } from "react";
import { api } from "../../api/client";
import type { MeResponse } from "../../api/types";
import { SignIn } from "../../components/SignIn";
import { useApi } from "../../hooks/useApi";
import { currentSubject, signOut, useSignedIn } from "../../lib/auth";

const STAFF_ROLES = ["ward_officer", "zonal_commissioner", "department_officer", "system_admin"];

/** PMC titles for each role (app/users.py). */
export const ROLE_TITLES: Record<string, string> = {
  system_admin: "System Administrator",
  zonal_commissioner: "Zonal Deputy Commissioner",
  ward_officer: "Assistant Municipal Commissioner",
  department_officer: "Department Officer",
  field_worker: "Field Worker",
  citizen: "Citizen",
};

const MeContext = createContext<MeResponse | null>(null);

/** The signed-in staff account. Only usable inside StaffGate. */
export function useMe(): MeResponse {
  const me = useContext(MeContext);
  if (!me) throw new Error("useMe outside StaffGate");
  return me;
}

function SignOutButton() {
  return (
    <button
      type="button"
      onClick={() => signOut()}
      className="fixed bottom-3 left-3 z-50 px-3 py-1.5 rounded bg-white border border-gray-300 text-xs font-mono text-gray-700 shadow-sm"
    >
      Sign out
    </button>
  );
}

function RoleCheck({ children }: { children: React.ReactNode }) {
  const { data: me, loading, error } = useApi(() => api.me(), []);
  if (loading) return <p className="p-8 text-sm font-mono text-gray-500">Checking your account…</p>;
  if (me && STAFF_ROLES.includes(me.role)) {
    return (
      <MeContext.Provider value={me}>
        {children}
        <SignOutButton />
      </MeContext.Provider>
    );
  }
  // Roles are granted by a system administrator (Staff & Roles page), never self-assigned.
  const who = currentSubject();
  return (
    <div className="max-w-lg mx-auto py-16 space-y-4 font-mono text-sm text-gray-800">
      <h1 className="text-xl font-bold">This account isn't municipal staff yet</h1>
      {error && <p className="text-red-600">{error}</p>}
      <p>
        Signed in as {who?.email ?? "unknown"} {me && <>(role: {me.role})</>}. Ask a system administrator to
        grant you a role and a ward office, zone or department on the Staff &amp; Roles page. Your account id:
      </p>
      <pre className="p-3 bg-gray-100 rounded text-xs whitespace-pre-wrap break-all">{who?.sub}</pre>
      <button type="button" onClick={() => signOut()} className="px-3 py-2 rounded border border-gray-300">
        Sign out
      </button>
    </div>
  );
}

export function StaffGate({ children }: { children: React.ReactNode }) {
  const signedIn = useSignedIn();
  if (!signedIn) {
    return <SignIn title="WardSentry staff sign-in" blurb="For ward officers, department officers and administrators." />;
  }
  return <RoleCheck>{children}</RoleCheck>;
}
