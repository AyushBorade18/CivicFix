import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { Icon } from "../admin/components/ws";

// Shared chrome for the citizen site, ported from the Stitch export
// stitch_wardsentry_citizen_portal ("Sentry Editorial Civic" design system).

export const ADMIN_URL = import.meta.env.VITE_ADMIN_URL ?? "http://localhost:5174";

const NAV: [string, string][] = [
  ["/", "Home"],
  ["/citizen/report", "Report a Problem"],
  ["/citizen/my-reports", "Track My Report"],
  ["/citizen/issues", "Pune Pulse"],
];

function readDismissed() {
  try { return localStorage.getItem("ws-banner-dismissed") === "1"; } catch { return false; }
}

/** Announcement bar + frosted nav, sticky at the top. */
export function SiteHeader() {
  const [bannerOpen, setBannerOpen] = useState(() => !readDismissed());
  const [menuOpen, setMenuOpen] = useState(false);
  const dismiss = () => {
    setBannerOpen(false);
    try { localStorage.setItem("ws-banner-dismissed", "1"); } catch { /* private mode */ }
  };
  const link = ({ isActive }: { isActive: boolean }) =>
    `font-se-sans text-se-sm transition-colors ${isActive ? "text-se-primary font-semibold" : "text-se-variant hover:text-se-on"}`;

  return (
    <header className="sticky top-0 z-[1000]">
      {bannerOpen && (
        <div className="h-10 bg-se-primary-container text-se-surface flex items-center justify-between px-5 md:px-12 font-se-code text-se-code">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-1.5 h-1.5 rounded-full bg-se-surface animate-pulse shrink-0" />
            <span className="truncate">For the people of Pune // Report a problem in under a minute</span>
          </div>
          <div className="flex items-center gap-4 shrink-0">
            <a className="underline hover:text-se-outline-variant transition-colors hidden sm:inline" href="/#watch">Watch how it works →</a>
            <button type="button" onClick={dismiss} aria-label="Dismiss" className="hover:text-se-outline-variant flex items-center">
              <Icon name="close" className="text-[16px]" />
            </button>
          </div>
        </div>
      )}
      <div className="h-16 bg-se-lowest/90 backdrop-blur-xl border-b border-se-outline-variant/40 flex items-center justify-between px-5 md:px-12">
        <Link to="/" className="flex items-center gap-3">
          <span className="w-8 h-8 bg-se-primary text-white flex items-center justify-center"><Icon name="hexagon" className="text-[20px]" /></span>
          <span className="flex flex-col">
            <span className="font-se-code text-se-caps uppercase tracking-wider text-se-on font-semibold">WardSentry</span>
            <span className="font-se-code text-[10px] text-se-secondary tracking-widest uppercase">For the people of Pune</span>
          </span>
        </Link>
        <nav className="hidden lg:flex items-center gap-7">
          {NAV.map(([to, label]) => <NavLink key={to} to={to} end className={link}>{label}</NavLink>)}
        </nav>
        <div className="flex items-center gap-2">
          <Link to="/citizen/report" className="hidden sm:inline-flex items-center px-4 h-9 border border-se-primary text-se-primary hover:bg-se-primary hover:text-white transition-colors font-se-code text-se-caps uppercase tracking-wider">
            Report a Problem
          </Link>
          <Link to="/citizen/issues" aria-label="See reported problems" className="w-9 h-9 border border-se-outline-variant flex items-center justify-center text-se-on hover:border-se-primary transition-colors">
            <Icon name="search" className="text-[18px]" />
          </Link>
          <button type="button" aria-label="Open menu" onClick={() => setMenuOpen((o) => !o)}
            className="w-9 h-9 border border-se-outline-variant flex items-center justify-center text-se-on hover:border-se-primary transition-colors lg:hidden">
            <Icon name={menuOpen ? "close" : "menu"} className="text-[18px]" />
          </button>
          <Link to="/citizen/my-reports" aria-label="My reports" className="w-8 h-8 rounded-full bg-se-primary flex items-center justify-center ml-1">
            <Icon name="person" className="text-white text-[18px]" />
          </Link>
        </div>
      </div>
      {menuOpen && (
        <nav className="lg:hidden bg-se-lowest border-b border-se-outline-variant/40 px-5 py-3 flex flex-col">
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} end onClick={() => setMenuOpen(false)}
              className={({ isActive }) => `py-2.5 font-se-sans text-se-body border-b border-se-container last:border-0 ${isActive ? "font-semibold" : "text-se-variant"}`}>
              {label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}

/** Stitch "Split Two-Column Action Blocks": light left, near-black right. */
export function SplitCTA({ left, right }: {
  left: { to: string; kicker?: string; title: string; text: string; cta?: string };
  right: { to: string; kicker?: string; title: string; text: string; cta?: string };
}) {
  return (
    <section className="w-full bg-se-lowest py-12 px-5 md:px-12">
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-7">
        <CTABlock {...left} dark={false} />
        <CTABlock {...right} dark />
      </div>
    </section>
  );
}

function CTABlock({ to, kicker, title, text, cta, dark }: { to: string; kicker?: string; title: string; text: string; cta?: string; dark: boolean }) {
  const cls = dark ? "bg-se-primary-container hover:bg-se-primary text-white" : "bg-se-high hover:bg-se-dim text-se-on";
  const inner = (
    <>
      <div>
        {kicker && <span className={`font-se-code text-se-caps uppercase tracking-widest block mb-6 ${dark ? "text-white/60" : "text-se-variant"}`}>{kicker}</span>}
        <div className="flex items-start justify-between gap-4">
          <h3 className="font-se-sans text-[26px] leading-8 md:text-se-lg tracking-tight">{title}</h3>
          <Icon name="arrow_forward" className="text-[36px] transform group-hover:translate-x-2 transition-transform duration-300" />
        </div>
      </div>
      <div>
        <p className={`font-se-sans text-se-body ${dark ? "text-se-on-primary-container" : "text-se-variant"}`}>{text}</p>
        {cta && <span className="inline-flex font-se-code text-se-code font-semibold uppercase tracking-wider mt-2">{cta} →</span>}
      </div>
    </>
  );
  const className = `group relative ${cls} transition-all duration-300 p-8 md:p-12 min-h-[260px] flex flex-col justify-between overflow-hidden`;
  return to.startsWith("/#") ? <a href={to} className={className}>{inner}</a> : <Link to={to} className={className}>{inner}</Link>;
}

const FOOT: [string, [string, string][]][] = [
  ["For Residents", [["Report a problem", "/citizen/report"], ["Track my report", "/citizen/my-reports"], ["Pune Pulse", "/citizen/issues"], ["How it works", "/#watch"]]],
  ["Pune Wards", [["Kothrud", "/citizen/issues"], ["Shivajinagar", "/citizen/issues"], ["Aundh-Baner", "/citizen/issues"], ["Viman Nagar", "/citizen/issues"], ["Hadapsar", "/citizen/issues"]]],
  ["Our Promise", [["Proof of every fix", "/#promise"], ["Counted with neighbours", "/#promise"], ["Your final say", "/#promise"]]],
  ["PMC Staff", [["Staff sign-in", ADMIN_URL]]],
];

export function SiteFooter() {
  const a = "text-se-variant hover:text-se-primary transition-colors";
  return (
    <footer className="w-full bg-se-lowest border-t border-se-outline-variant/50 pt-12 pb-7">
      <div className="w-full px-5 md:px-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-12 pb-12 border-b border-se-outline-variant/30">
          <div className="lg:col-span-4 flex flex-col justify-between lg:pr-7">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-se-primary" />
                <span className="font-se-code text-se-caps uppercase tracking-widest text-se-on font-semibold">WardSentry Pune</span>
              </div>
              <p className="font-se-sans text-se-sm text-se-variant max-w-sm">
                Report problems on your street, follow them, and see them fixed — for every ward of Pune.
              </p>
            </div>
            <div className="pt-7 space-y-4">
              <div className="flex items-center gap-2 font-se-code text-se-code text-se-variant">
                <span className="text-se-primary font-semibold">SPEAK IN</span><span className="text-se-outline-variant">|</span>
                <span className="text-se-primary font-semibold">EN</span><span className="text-se-outline-variant">|</span>
                <span>MR</span><span className="text-se-outline-variant">|</span><span>HI</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="px-2 py-0.5 border border-se-outline-variant font-se-code text-[10px] uppercase text-se-variant">All Pune wards</span>
                <span className="px-2 py-0.5 border border-se-outline-variant font-se-code text-[10px] uppercase text-se-variant">Free to use</span>
              </div>
            </div>
          </div>
          {FOOT.map(([title, links]) => (
            <div key={title} className="lg:col-span-2 space-y-4">
              <div className="font-se-code text-se-caps uppercase tracking-wider text-se-secondary font-semibold">{title}</div>
              <ul className="space-y-2 font-se-sans text-se-sm">
                {links.map(([label, to]) => (
                  <li key={label}>
                    {to.startsWith("/") && !to.startsWith("/#") ? <Link to={to} className={a}>{label}</Link> : <a href={to} className={a}>{label}</a>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="pt-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 font-se-code text-se-code text-se-secondary">
          <span>© {new Date().getFullYear()} WardSentry Pune. Made in Pune, for Pune.</span>
          <div className="flex items-center gap-1">
            {([["Report", "/citizen/report"], ["Pune Pulse", "/citizen/issues"], ["PMC Staff", ADMIN_URL]] as [string, string][]).map(([l, to]) => {
              const c = "px-2 py-1 border border-se-outline-variant text-[11px] uppercase tracking-wider hover:bg-se-primary hover:text-white hover:border-se-primary transition-colors";
              return to.startsWith("/") ? <Link key={l} to={to} className={c}>{l}</Link> : <a key={l} href={to} className={c}>{l}</a>;
            })}
          </div>
        </div>
      </div>
    </footer>
  );
}

/** Small uppercase code label, e.g. "PHASE 01 // THE PROBLEM". */
export function Kicker({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <span className={`font-se-code text-se-caps uppercase tracking-widest text-se-variant ${className}`}>{children}</span>;
}
