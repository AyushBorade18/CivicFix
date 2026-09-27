import { useSyncExternalStore } from "react";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Who the API should see. Two modes, one interface:
// - Hosted: VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY set. Supabase Auth
//   signs people in with an emailed 6-digit code and keeps the access token
//   fresh; the API verifies it against Supabase's public keys.
// - Local dev: no Supabase. Open the app once at /#token=<jwt>
//   (scripts/dev_auth.py prints one); it's stored and stripped from the URL.
// Either way the token only proves identity - roles live in our database.

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const supabase: SupabaseClient | null =
  SUPABASE_URL && SUPABASE_ANON_KEY ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;

const DEV_KEY = "civicfix_token";
let token: string | null = null;
// Between verifying a code and the account existing (POST /api/me/register),
// pages must not start calling the API yet, or a first sign-in sees 403s.
let registering = false;
const listeners = new Set<() => void>();

function set(next: string | null): void {
  if (next === token) return;
  token = next;
  listeners.forEach((l) => l());
}

export function currentToken(): string | null {
  return token;
}

export function useSignedIn(): boolean {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => token !== null && !registering,
  );
}

/** Identity subject ("sub") of the current token: what an administrator
 * passes to `python -m app.users set-role` to promote a staff account. */
export function currentSubject(): { sub: string; email: string | null } | null {
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return { sub: payload.sub, email: payload.email ?? null };
  } catch {
    return null;
  }
}

function readDevToken(): string | null {
  try {
    return localStorage.getItem(DEV_KEY);
  } catch {
    return null;
  }
}

function writeDevToken(value: string | null): void {
  try {
    if (value) localStorage.setItem(DEV_KEY, value);
    else localStorage.removeItem(DEV_KEY);
  } catch {
    /* storage blocked: keep it in memory for this page */
  }
}

/** Call once before rendering. Returns true if a dev token arrived in the URL. */
export async function initAuth(): Promise<boolean> {
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    set(data.session?.access_token ?? null);
    supabase.auth.onAuthStateChange((_event, session) => set(session?.access_token ?? null));
    return false;
  }
  const fromUrl = takeDevTokenFromUrl();
  set(fromUrl ?? readDevToken());
  // A link pasted into an open tab changes only the #fragment - no reload.
  window.addEventListener("hashchange", () => {
    const next = takeDevTokenFromUrl();
    if (next) set(next);
  });
  return fromUrl !== null;
}

function takeDevTokenFromUrl(): string | null {
  const match = window.location.hash.match(/(?:^#|&)token=([^&]+)/);
  if (!match) return null;
  const value = decodeURIComponent(match[1]);
  writeDevToken(value);
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  return value;
}

export async function sendCode(email: string): Promise<void> {
  if (!supabase) throw new Error("Sign-in isn't configured on this server.");
  const { error } = await supabase.auth.signInWithOtp({ email, options: { shouldCreateUser: true } });
  if (error) throw error;
}

export async function verifyCode(email: string, code: string): Promise<void> {
  if (!supabase) throw new Error("Sign-in isn't configured on this server.");
  registering = true;
  const { error } = await supabase.auth.verifyOtp({ email, token: code, type: "email" });
  if (error) {
    registering = false;
    throw error;
  }
}

/** Email + password sign-in, or account creation. Sends no email as long as
 * "Confirm email" is off in Supabase (Authentication -> Sign In / Providers
 * -> Email); with it on, Supabase would email a confirmation link instead. */
export async function passwordSignIn(email: string, password: string, create: boolean): Promise<void> {
  if (!supabase) throw new Error("Sign-in isn't configured on this server.");
  registering = true;
  const { data, error } = create
    ? await supabase.auth.signUp({ email, password })
    : await supabase.auth.signInWithPassword({ email, password });
  if (error || !data.session) {
    registering = false;
    throw error ?? new Error(
      "Account created, but this server still requires email confirmation. Ask the administrator to turn off " +
      "\"Confirm email\" in Supabase, then sign in with this email and password.",
    );
  }
}

/** Ends the post-verification hold; call once registration has settled. */
export function finishSignIn(): void {
  registering = false;
  listeners.forEach((l) => l());
}

export async function signOut(): Promise<void> {
  if (supabase) await supabase.auth.signOut();
  writeDevToken(null);
  set(null);
}
