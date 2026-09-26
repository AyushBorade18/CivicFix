import { useState } from "react";
import { api } from "../api/client";
import { finishSignIn, sendCode, supabase, verifyCode } from "../lib/auth";

// Email + 6-digit code: the code is typed into the app itself, so it works
// inside an installed PWA (a magic link would open the browser instead).
export function SignIn({ title, blurb }: { title: string; blurb: string }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"email" | "code">("email");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!supabase) {
    return (
      <div className="max-w-md mx-auto text-center py-12 space-y-3">
        <h1 className="text-2xl font-bold text-foreground">{title}</h1>
        <p className="text-secondary text-sm">
          Development mode: open this page with a sign-in link from{" "}
          <code className="text-xs">python -m scripts.dev_auth token "dev|you"</code> (…#token=&lt;token&gt;).
        </p>
      </div>
    );
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-md mx-auto py-10 space-y-5">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold text-foreground">{title}</h1>
        <p className="text-secondary text-sm">{blurb}</p>
      </div>
      {step === "email" ? (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await sendCode(email.trim());
              setStep("code");
            });
          }}
        >
          <label htmlFor="signin-email" className="text-sm font-semibold text-foreground">
            Email
          </label>
          <input
            id="signin-email"
            type="email"
            required
            autoComplete="email"
            inputMode="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-3.5 border border-border rounded-xl bg-background text-foreground text-base"
            placeholder="you@example.com"
          />
          <button type="submit" disabled={busy} className="btn btn-black w-full py-3.5 rounded-xl font-semibold disabled:opacity-50">
            {busy ? "Sending…" : "Email me a sign-in code"}
          </button>
        </form>
      ) : (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await verifyCode(email.trim(), code.trim());
              try {
                await api.register(); // creates a citizen account on first sign-in; idempotent
              } finally {
                finishSignIn();
              }
            });
          }}
        >
          <label htmlFor="signin-code" className="text-sm font-semibold text-foreground">
            Code sent to {email}
          </label>
          <input
            id="signin-code"
            required
            autoComplete="one-time-code"
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            className="w-full px-4 py-3.5 border border-border rounded-xl bg-background text-foreground text-2xl tracking-[0.5em] text-center font-mono"
            placeholder="••••••"
          />
          <button type="submit" disabled={busy || code.length !== 6} className="btn btn-black w-full py-3.5 rounded-xl font-semibold disabled:opacity-50">
            {busy ? "Checking…" : "Sign in"}
          </button>
          <button type="button" onClick={() => setStep("email")} className="w-full text-sm text-secondary underline">
            Use a different email
          </button>
        </form>
      )}
      {error && (
        <p className="text-sm text-red-700 text-center" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
