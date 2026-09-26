import { api } from "../../api/client";
import { SignIn } from "../../components/SignIn";
import { useApi } from "../../hooks/useApi";
import { currentSubject, signOut, useSignedIn } from "../../lib/auth";

const STAFF_ROLES = ["ward_officer", "department_officer", "system_admin"];

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
      <>
        {children}
        <SignOutButton />
      </>
    );
  }
  // Roles are granted only by an operator with database access, never over HTTP.
  const who = currentSubject();
  return (
    <div className="max-w-lg mx-auto py-16 space-y-4 font-mono text-sm text-gray-800">
      <h1 className="text-xl font-bold">This account isn't municipal staff yet</h1>
      {error && <p className="text-red-600">{error}</p>}
      <p>
        Signed in as {who?.email ?? "unknown"} {me && <>(role: {me.role})</>}. Ask an administrator to run:
      </p>
      <pre className="p-3 bg-gray-100 rounded text-xs whitespace-pre-wrap break-all">
        python -m app.users set-role "{who?.sub}" ward_officer{"\n"}python -m app.users assign-ward "{who?.sub}" &lt;ward id&gt;
      </pre>
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
