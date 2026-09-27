import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import { CATEGORY_LABELS } from "../api/types";
import type { PublicIssue } from "../api/types";
import { Icon } from "../admin/components/ws";
import { SplitCTA } from "../citizen/Shell";

// Home page, ported from the Stitch export
// stitch_wardsentry_citizen_portal/wardsentry_home_palantir_template.
// Only public, no-sign-in data: /api/public/map and /api/stats.
// Copy is written for Pune residents: no technical terms on this page.

const VIDEO = "/media/how-it-works.mp4";
const POSTER = "/media/how-it-works.jpg";

async function loadHome() {
  const [map, stats] = await Promise.all([api.publicMap(), api.stats()]);
  return { issues: map.issues, stats };
}

function ago(iso: string | null) {
  if (!iso) return "recently";
  const m = Math.round((Date.now() - Date.parse(iso)) / 60000);
  if (m < 60) return `${Math.max(1, m)} min ago`;
  if (m < 1440) return `${Math.round(m / 60)} h ago`;
  return `${Math.round(m / 1440)} d ago`;
}

const n = (v: number | undefined) => (v == null ? "—" : v.toLocaleString("en-IN"));

export function Landing() {
  const { data } = useApi(loadHome, []);
  const issues = useMemo(() => data?.issues ?? [], [data]);
  const open = issues.filter((i) => i.status !== "closed").length;
  const closed = issues.length - open;

  return (
    <div className="flex flex-col w-full">
      <Hero wards={data?.stats.wards} reports={data?.stats.reports} open={data ? open : undefined} closed={data ? closed : undefined} />
      <FilmSpotlight issues={issues} />
      <Capabilities />
      <FixSplit issues={issues} />
      <SplitCTA
        left={{ to: "/citizen/my-reports", title: "Track a Report", text: "See where your complaint stands — sent to the ward, being fixed, or done with a photo from the spot.", cta: "Track my report" }}
        right={{ to: "/citizen/report", title: "Report a Problem", text: "A pothole, a dark streetlight, a blocked drain or uncollected garbage — tell us in under a minute.", cta: "Start my report" }}
      />
    </div>
  );
}

/* SECTION 1: full-bleed hero video */
function Hero({ wards, reports, open, closed }: { wards?: number; reports?: number; open?: number; closed?: number }) {
  const video = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(true);
  const toggleAudio = () => {
    const v = video.current;
    if (!v) return;
    v.muted = !v.muted;
    if (!v.muted) v.play().catch(() => undefined);
    setMuted(v.muted);
  };

  return (
    <section className="relative w-full h-[calc(100vh-104px)] min-h-[600px] max-h-[980px] bg-se-primary flex flex-col justify-between overflow-hidden select-none">
      <video ref={video} className="absolute inset-0 w-full h-full object-cover scale-105" src={VIDEO} poster={POSTER}
        autoPlay muted loop playsInline preload="metadata" aria-hidden="true" />
      <div className="absolute inset-0 bg-gradient-to-b from-se-primary/80 via-se-primary/45 to-se-primary" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(0,0,0,0.3)_50%,rgba(0,0,0,0.8)_100%)]" />

      <div className="relative z-10 w-full pt-10 px-5 md:px-12 flex items-center justify-between text-white/70 font-se-code text-se-code">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span className="tracking-widest uppercase text-white">{n(wards)} wards covered // {n(reports)} reports from residents</span>
        </div>
        <div className="hidden md:flex items-center gap-4">
          <span className="tracking-widest uppercase">Updates live</span>
          <span className="text-white/40">|</span>
          <span className="tracking-widest uppercase">{n(open)} waiting to be fixed</span>
        </div>
      </div>

      <div className="relative z-10 w-full px-5 md:px-12 my-auto flex flex-col items-center text-center">
        <h1 className="max-w-5xl font-se-sans text-[40px] leading-[46px] md:text-se-hero md:leading-[82px] text-white tracking-tight font-normal drop-shadow-md">
          Spotted a problem on your street?<br className="hidden md:inline" /> Report it. Watch it get fixed.
        </h1>
        <p className="mt-4 max-w-2xl font-se-sans text-se-body-xl text-white/80 tracking-tight">
          Potholes, overflowing drains, dark streetlights, garbage that isn’t picked up — tell us in a minute, in English, हिंदी or मराठी. Your ward team is told straight away.
        </p>
      </div>

      <div className="relative z-10 w-full pb-7 px-5 md:px-12 flex items-end justify-between">
        <div className="w-32">
          <button type="button" onClick={toggleAudio}
            className="group flex items-center gap-1 text-white/75 hover:text-white transition-colors font-se-code text-se-code uppercase tracking-wider py-1 px-2 rounded-full bg-white/10 backdrop-blur-md">
            <Icon name={muted ? "volume_off" : "volume_up"} className="text-[16px] text-white group-hover:scale-110 transition-transform" />
            <span>{muted ? "Audio Off" : "Audio On"}</span>
          </button>
        </div>
        <a href="#watch" className="flex flex-col items-center gap-1 text-white/85 hover:text-white transition-all group">
          <Icon name="arrow_downward" className="text-[20px] transition-transform duration-300 group-hover:translate-y-1" />
          <span className="font-se-code uppercase tracking-widest text-[11px]">Scroll to Explore</span>
          <span className="w-8 h-1 rounded-full bg-white/30 mt-1 overflow-hidden relative">
            <span className="absolute inset-y-0 left-0 w-3 bg-white animate-[pulse_2s_infinite]" />
          </span>
        </a>
        <div className="w-32 flex justify-end">
          <span className="font-se-code text-[11px] text-white/60 uppercase tracking-widest text-right hidden sm:block">
            Pune live<br /><span className="text-white font-semibold">{n(closed)} fixed</span>
          </span>
        </div>
      </div>
    </section>
  );
}

/* SECTION 2: chip rail + featured film card */
function FilmSpotlight({ issues }: { issues: PublicIssue[] }) {
  const [playing, setPlaying] = useState(false);
  const chips = useMemo(() => {
    const c = new Map<string, number>();
    for (const i of issues) c.set(i.category, (c.get(i.category) ?? 0) + 1);
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [issues]);

  return (
    <section id="watch" className="w-full bg-se-surface py-12 px-5 md:px-12 flex flex-col scroll-mt-28">
      <div className="w-full flex items-center justify-between gap-4 pb-7">
        <div className="flex items-center gap-1 whitespace-nowrap font-se-code text-se-code overflow-x-auto [scrollbar-width:none]">
          <span className="px-4 py-2 bg-se-primary text-white font-medium">How it works</span>
          {chips.map(([cat, count]) => (
            <Link key={cat} to={`/citizen/issues?category=${cat}`} className="px-4 py-2 bg-se-container text-se-on font-medium hover:bg-se-high transition-colors">
              {CATEGORY_LABELS[cat] ?? cat} ({count})
            </Link>
          ))}
        </div>
        <Link to="/citizen/issues" className="shrink-0 px-4 py-2 bg-se-surface text-se-on font-se-code text-[11px] tracking-widest uppercase hover:bg-se-primary hover:text-white transition-colors">
          See all
        </Link>
      </div>

      <div className="relative w-full overflow-hidden bg-se-primary min-h-[460px] md:min-h-[560px] flex items-end p-4 md:p-12">
        {playing ? (
          <video className="absolute inset-0 w-full h-full object-contain bg-black" src={VIDEO} poster={POSTER} controls autoPlay playsInline />
        ) : (
          <>
            <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url(${POSTER})` }}>
              <div className="absolute inset-0 bg-gradient-to-t from-se-primary via-se-primary/80 to-transparent" />
              <div className="absolute inset-0 bg-se-primary/40" />
            </div>
            <div className="absolute right-4 top-1/2 -translate-y-1/2 select-none pointer-events-none opacity-20 font-se-sans text-[140px] md:text-[220px] font-bold text-transparent [-webkit-text-stroke:2px_#22c55e] leading-none whitespace-nowrap">
              Pune
            </div>
            <div className="relative z-10 max-w-2xl bg-se-primary-container/85 backdrop-blur-xl p-7 md:p-12 shadow-2xl flex flex-col justify-between">
              <div>
                <span className="font-se-code text-se-code tracking-widest uppercase text-white/70 font-semibold mb-1 block">Watch // From your phone to a fixed road</span>
                <h2 className="font-se-sans text-se-md md:text-se-lg text-white tracking-tight font-normal leading-tight">
                  See what happens after you report a problem — your ward team is told, a crew is sent, and the fix is checked on the spot ↗
                </h2>
              </div>
              <div className="mt-7 flex items-center justify-between pt-4 text-white/75 font-se-code text-se-code">
                <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-emerald-400" /><span>A short film for Punekars</span></div>
                <button type="button" onClick={() => setPlaying(true)} className="underline text-white hover:text-se-outline-variant transition-colors flex items-center gap-1">
                  <span>Watch with sound</span><Icon name="arrow_outward" className="text-[16px]" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}

/* SECTION 3: statement + indexed rows */
function Capabilities() {
  const rows: [string, string, string][] = [
    ["Report", "Take a photo, type what’s wrong or just speak it. We find your ward for you — no forms, no office visits.", "/0.1"],
    ["Track", "Follow your complaint step by step: sent to your ward, counted with your neighbours’ reports, fixed.", "/0.2"],
    ["Confirm", "Nothing is marked fixed without a photo from the exact spot. If it isn’t really fixed, you reopen it.", "/0.3"],
  ];
  return (
    <section id="promise" className="w-full bg-se-lowest pt-12 md:pt-32 pb-12 px-5 md:px-12 scroll-mt-28">
      <div className="max-w-6xl mx-auto mb-12 md:mb-32">
        <h2 className="font-se-sans text-se-lg md:text-se-xl text-se-on tracking-tight leading-[1.12] font-normal text-left md:text-center">
          WardSentry helps Pune fix what’s broken, <span className="text-se-secondary">counting every neighbour’s voice</span> — from your street corner to your ward office.
        </h2>
      </div>
      <div className="max-w-5xl mx-auto pt-7">
        <div className="mb-7"><span className="font-se-sans text-se-body text-se-variant font-medium">What you can do</span></div>
        {rows.map(([title, text, idx], i) => (
          <div key={title}>
            {i > 0 && <div className="w-full h-px bg-se-high my-1" />}
            <div className="group py-12 flex flex-col md:flex-row md:items-baseline justify-between transition-colors hover:bg-se-low/40 px-2">
              <div className="flex flex-col gap-1 max-w-2xl">
                <h3 className="font-se-sans text-[44px] md:text-[60px] tracking-tight text-se-on font-light uppercase leading-none">{title}</h3>
                <p className="font-se-sans text-se-body-xl text-se-variant mt-2">{text}</p>
              </div>
              <div className="mt-4 md:mt-0 font-se-code text-se-code text-se-secondary tracking-widest uppercase">{idx}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* SECTION 4: photo split + what residents are reporting (real, public data) */
function FixSplit({ issues }: { issues: PublicIssue[] }) {
  const latest = useMemo(
    () => [...issues].sort((a, b) => Date.parse(b.last_reported ?? "0") - Date.parse(a.last_reported ?? "0")).slice(0, 3),
    [issues],
  );
  return (
    <section className="w-full bg-se-surface py-12 md:py-24 px-5 md:px-12">
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        <div className="lg:col-span-6 overflow-hidden shadow-md group">
          <div className="w-full h-[400px] md:h-[520px] bg-cover bg-center transition-transform duration-700 group-hover:scale-105" style={{ backgroundImage: `url(${POSTER})` }} />
        </div>
        <div className="lg:col-span-6 flex flex-col items-start lg:pl-12">
          <h2 className="font-se-sans text-[32px] leading-[38px] md:text-se-xl md:leading-[64px] text-se-on font-normal tracking-tight mb-4">There is so much left to fix</h2>
          <p className="font-se-sans text-se-body-xl text-se-variant leading-relaxed max-w-xl mb-12">
            Every report helps. When you and your neighbours report the same pothole, your ward team sees how many people it affects — and the worst problems get fixed first.
          </p>
          <Link to="/citizen/issues" className="inline-flex items-center justify-center px-7 py-2.5 bg-se-lowest text-se-on hover:bg-se-primary hover:text-white transition-colors font-se-code text-[12px] uppercase tracking-wider shadow-sm">
            See Pune Pulse
          </Link>
        </div>
      </div>

      <div className="max-w-7xl mx-auto mt-12 pt-12">
        <h2 className="font-se-sans text-se-lg md:text-se-xl text-se-on font-normal tracking-tight">What Punekars are reporting</h2>
        <div className="mt-7 grid grid-cols-1 md:grid-cols-3 gap-7">
          {latest.length === 0 && <p className="text-se-variant">Reports from your neighbours will appear here.</p>}
          {latest.map((i) => (
            <Link key={i.issue_id} to={`/citizen/issues/${i.issue_id}`} className="p-7 bg-se-low hover:bg-se-container transition-colors flex flex-col justify-between">
              <p className="font-se-sans text-se-body text-se-on italic leading-relaxed">
                “{CATEGORY_LABELS[i.category] ?? i.category}{i.ward_name ? ` in ${i.ward_name.split(" - ")[0]}` : ""}. {i.report_count} {i.report_count === 1 ? "resident has" : "residents have"} reported this{i.status === "closed" ? " — and it’s been fixed." : "."}”
              </p>
              <div className="mt-4 pt-2">
                <span className="font-se-code text-se-caps uppercase tracking-wider text-se-primary font-semibold block">
                  {i.ward_id != null ? `Ward ${i.ward_id}` : "Ward being found"}
                </span>
                <span className="font-se-code text-[11px] text-se-secondary">
                  Reported {ago(i.last_reported)} · {i.status === "closed" ? "Fixed" : "Waiting to be fixed"}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

export default Landing;
