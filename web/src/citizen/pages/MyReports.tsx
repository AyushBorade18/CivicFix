import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, mediaUrl, type EvidencePackage } from "../../api/client";
import type { EvidenceStatus, MyReport, PublicIssue } from "../../api/types";
import { CATEGORY_LABELS } from "../../api/types";
import { useApi } from "../../hooks/useApi";
import { signOut, useSignedIn } from "../../lib/auth";
import { SignIn } from "../../components/SignIn";
import { EvidenceCamera, formatTime } from "../../evidence/EvidenceCamera";
import { captureAndUpload, listPending, uploadPending, type PendingUpload } from "../../evidence/pendingUploads";
import { Icon } from "../../admin/components/ws";
import { Kicker, SplitCTA } from "../Shell";

// Track page, ported from the Stitch export
// stitch_wardsentry_citizen_portal/track_report_wardsentry.
// Everything shown is the signed-in resident's own report plus the public
// record of the problem it belongs to.

const EVIDENCE_LABELS: Record<EvidenceStatus, string> = {
  submitted: "Photo received",
  alternative_confirmed: "Confirmed by the ward office",
  alternative_in_progress: "Ward office is checking",
  pending: "No photo yet",
  not_provided: "No photo",
};

function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

function statusLabel(status: string | null) {
  if (status === "closed") return "Fixed";
  if (status === "reopened") return "Reopened";
  if (status === "under_review") return "Under review";
  return "Being worked on";
}

const date = (iso: string | null | undefined) => (iso ? formatTime(iso) : "—");

export function MyReports() {
  const signedIn = useSignedIn();
  const { data: reports, loading, error, reload } = useApi(
    () => (signedIn ? api.myReports() : Promise.resolve([] as MyReport[])),
    [signedIn],
  );
  const online = useOnline();
  const [pending, setPending] = useState<PendingUpload[]>([]);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [cameraFor, setCameraFor] = useState<MyReport | null>(null);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const refreshPending = useCallback(() => listPending().then(setPending), []);

  const sendPending = useCallback(async () => {
    const queue = await listPending();
    if (!queue.length) return;
    setSending(true);
    let sent = 0;
    let lastError: string | null = null;
    for (const entry of queue) {
      const result = await uploadPending(entry);
      if (result.ok) sent += 1;
      else lastError = result.message;
    }
    setSending(false);
    await refreshPending();
    if (sent) reload();
    setNotice(lastError ? { kind: "error", text: lastError } : { kind: "ok", text: "Saved photos sent." });
  }, [refreshPending, reload]);

  useEffect(() => {
    refreshPending();
  }, [refreshPending]);

  // Back online: send anything captured while offline. Via a ref so this runs
  // on connectivity changes only (useApi's reload is a new function each render).
  const sendRef = useRef(sendPending);
  sendRef.current = sendPending;
  useEffect(() => {
    if (online) sendRef.current();
  }, [online]);

  async function onCapture(pkg: EvidencePackage) {
    const report = cameraFor!;
    setCameraFor(null);
    setSending(true);
    const result = await captureAndUpload(report.issue_id!, pkg, report.report_id);
    setSending(false);
    await refreshPending();
    if (result.ok) {
      setNotice({ kind: "ok", text: "Photo received - your ward officer will look at it." });
      reload();
    } else {
      setNotice({ kind: "error", text: result.message });
    }
  }

  const hero = (
    <section className="w-full bg-se-surface px-5 md:px-12 pt-10 pb-10">
      <h1 className="max-w-4xl font-se-sans text-[40px] leading-[46px] md:text-se-xl text-se-on tracking-tight">Track Your Report, Step by Step.</h1>
      <p className="mt-4 max-w-2xl font-se-sans text-se-body-xl text-se-variant">
        See whether your complaint has reached your ward, how many neighbours reported it too, and when it’s fixed.
      </p>
    </section>
  );

  if (!signedIn) {
    return (
      <>
        {hero}
        <section className="bg-se-lowest border-t border-se-outline-variant/40 px-5 md:px-12 py-12">
          <SignIn title="Sign in to see your reports" blurb="Your reports, photos and fix confirmations appear here once you're signed in." />
        </section>
      </>
    );
  }

  const list = reports ?? [];
  const selected = list.find((r) => r.report_id === selectedId) ?? list[0] ?? null;

  function find(e: React.FormEvent) {
    e.preventDefault();
    const num = Number(query.replace(/[^0-9]/g, ""));
    const hit = list.find((r) => r.report_id === num || r.issue_id === num);
    if (hit) { setSelectedId(hit.report_id); setNotice(null); }
    else setNotice({ kind: "error", text: `No report #${query.trim()} in your reports.` });
  }

  return (
    <>
      {hero}
      <section className="w-full bg-se-surface px-5 md:px-12 pb-12">
        <form onSubmit={find} className="flex flex-col sm:flex-row gap-2 max-w-3xl">
          <div className="flex-1 h-12 flex items-center gap-2 px-3 bg-se-lowest border border-se-outline-variant focus-within:border-se-primary">
            <Icon name="search" className="text-[18px] text-se-variant" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Report or problem number, e.g. 1074"
              className="flex-1 bg-transparent outline-none font-se-sans text-se-body" aria-label="Report number" />
            {selected?.ward_id != null && <span className="px-2 py-0.5 bg-se-container font-se-code text-[10px] uppercase">Ward {selected.ward_id}</span>}
          </div>
          <button type="submit" className="h-12 px-6 bg-se-primary text-white font-se-code text-se-code uppercase tracking-wider font-semibold flex items-center justify-center gap-2 hover:bg-se-primary-container">
            Find report <Icon name="arrow_forward" className="text-[18px]" />
          </button>
        </form>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 max-w-3xl font-se-code text-[11px] text-se-variant">
          <span>{list.length ? `You have ${list.length} report${list.length === 1 ? "" : "s"}` : "Your reports appear here"}</span>
          <button type="button" onClick={() => signOut()} className="underline hover:text-se-on">Sign out</button>
        </div>
        {list.length > 1 && (
          <div className="mt-4 flex gap-1 overflow-x-auto [scrollbar-width:none] font-se-code text-se-code whitespace-nowrap">
            {list.map((r) => (
              <button key={r.report_id} type="button" onClick={() => setSelectedId(r.report_id)}
                className={`px-4 py-2 transition-colors ${selected?.report_id === r.report_id ? "bg-se-primary text-white" : "bg-se-container hover:bg-se-high"}`}>
                #{r.report_id} · {r.category ? CATEGORY_LABELS[r.category] ?? r.category : "Report"}
              </button>
            ))}
          </div>
        )}
      </section>

      <div className="px-5 md:px-12 space-y-2">
        {!online && <Banner kind="warn" icon="wifi_off">You’re offline. Photos you take are kept on this device until you reconnect.</Banner>}
        {pending.length > 0 && (
          <Banner kind="warn" icon="cloud_upload">
            {pending.length} photo{pending.length > 1 ? "s" : ""} saved on this device, not sent yet.{" "}
            <button type="button" onClick={sendPending} disabled={sending || !online} className="underline font-semibold disabled:opacity-50">
              {sending ? "Sending…" : "Send now"}
            </button>
          </Banner>
        )}
        {notice && <Banner kind={notice.kind === "error" ? "error" : "ok"} icon={notice.kind === "error" ? "error" : "check_circle"}>{notice.text}</Banner>}
      </div>

      {loading && <p className="px-5 md:px-12 py-12 text-se-variant">Loading your reports…</p>}
      {error && (
        <p className="px-5 md:px-12 py-12 text-red-700">{error} <button type="button" onClick={reload} className="underline">Try again</button></p>
      )}
      {reports && list.length === 0 && (
        <section className="px-5 md:px-12 py-12">
          <div className="p-12 bg-se-lowest border border-se-outline-variant text-center">
            <p className="font-se-sans text-se-title text-se-on">You haven’t reported anything yet.</p>
            <Link to="/citizen/report" className="inline-flex mt-4 h-12 px-6 items-center gap-2 bg-se-primary text-white font-se-code text-se-code uppercase tracking-wider">
              Report a problem <Icon name="arrow_forward" className="text-[18px]" />
            </Link>
          </div>
        </section>
      )}

      {selected && (
        <TrackedReport key={selected.report_id} report={selected}
          photoQueued={pending.some((p) => p.reportId === selected.report_id)} busy={sending}
          onAddPhoto={() => setCameraFor(selected)} onChanged={reload} />
      )}

      <section className="w-full bg-se-surface px-5 md:px-12 py-20 text-center">
        <Kicker>Our promise to Pune</Kicker>
        <h2 className="mt-4 max-w-4xl mx-auto font-se-sans text-[32px] leading-[38px] md:text-se-xl text-se-on tracking-tight">
          No hidden complaints. Every fix is checked by the people who reported it.
        </h2>
        <p className="mt-4 max-w-2xl mx-auto font-se-sans text-se-body text-se-variant">
          A problem is only marked fixed with a photo from the spot — and if it isn’t really fixed, you can reopen it.
        </p>
      </section>

      <SplitCTA
        left={{ to: "/citizen/report", kicker: "Something new?", title: "Need to Report Another Problem?", text: "It takes under a minute — type it or just speak it." }}
        right={{ to: "/citizen/issues", kicker: "Pune Pulse // All wards", title: "See What’s Fixed Across Pune", text: "Every reported problem on one map, ward by ward." }}
      />

      {cameraFor && (
        <EvidenceCamera title={`Photo for report #${cameraFor.report_id}`} onCancel={() => setCameraFor(null)} onConfirm={onCapture} />
      )}
    </>
  );
}

function Banner({ kind, icon, children }: { kind: "ok" | "warn" | "error"; icon: string; children: React.ReactNode }) {
  const cls = kind === "error" ? "bg-red-50 border-red-200 text-red-800" : kind === "warn" ? "bg-amber-50 border-amber-300 text-amber-900" : "bg-emerald-50 border-emerald-200 text-emerald-900";
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`p-3 border font-se-sans text-se-sm flex items-start gap-2 ${cls}`}>
      <Icon name={icon} className="text-[18px] shrink-0" /><span>{children}</span>
    </div>
  );
}

function TrackedReport({ report, photoQueued, busy, onAddPhoto, onChanged }: {
  report: MyReport; photoQueued: boolean; busy: boolean; onAddPhoto: () => void; onChanged: () => void;
}) {
  const { data: issue } = useApi<PublicIssue | null>(
    () => (report.issue_id != null ? api.publicIssue(report.issue_id) : Promise.resolve(null)),
    [report.issue_id],
  );
  const now = Date.now();
  const closed = report.issue_status === "closed";
  const canAddPhoto =
    report.issue_id !== null && report.evidence_status === "pending" && !photoQueued &&
    (!report.evidence_due_at || new Date(report.evidence_due_at).getTime() > now);
  const reverificationOpen =
    closed && report.issue_id !== null &&
    (!report.issue_reverification_due_at || new Date(report.issue_reverification_due_at).getTime() > now);
  const category = report.category ? CATEGORY_LABELS[report.category] ?? report.category : "Being sorted";
  const count = issue?.report_count ?? 1;

  const stages: { title: string; text: string; foot: string; done: boolean; current: boolean }[] = [
    { title: "Report received", text: "Your report and your words were saved.", foot: date(report.reported_at), done: true, current: false },
    { title: "Sent to your ward", text: report.ward_id != null ? `Your ward team${issue?.ward_name ? ` in ${issue.ward_name.split(" - ")[0]}` : ""} can see it.` : "We’re finding which ward it belongs to.", foot: report.ward_id != null ? `Ward ${report.ward_id}` : "Ward being found", done: report.ward_id != null, current: report.ward_id == null },
    { title: "Neighbours counted", text: count > 1 ? `${count} residents reported this same problem.` : "You’re the first to report it so far.", foot: `${count} report${count === 1 ? "" : "s"}`, done: report.issue_id != null, current: false },
    { title: "Fixed with proof", text: "The crew sends a photo from the spot and a ward officer checks it.", foot: closed ? date(issue?.closed_at) : "Waiting for the crew", done: closed, current: report.ward_id != null && !closed },
    { title: "Your final say", text: "You confirm it’s fixed, or reopen it.", foot: reverificationOpen ? "Action needed below" : closed ? "Window closed" : "After the fix", done: false, current: reverificationOpen },
  ];

  return (
    <section className="w-full bg-se-surface px-5 md:px-12 pb-12 space-y-7">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <Card k="Report number" v={`#${report.report_id}`} s={report.ward_id != null ? `Ward ${report.ward_id}` : "Ward being found"} />
        <Card k="Kind of problem" v={category} s={issue?.ward_name?.split(" - ")[0] ?? "Pune"} />
        <Card k="Status" v={statusLabel(report.issue_status)} s={`Reported ${date(report.reported_at)}`} />
        <Card k="Residents affected" v={`${count} ${count === 1 ? "report" : "reports"}`} s="Same problem, counted together" />
      </div>

      <div className="p-7 bg-se-lowest border border-se-outline-variant/60">
        <div className="flex flex-wrap items-end justify-between gap-2 mb-7">
          <div><Kicker>Your report // Step by step</Kicker><h2 className="mt-2 font-se-sans text-se-title md:text-se-md text-se-on">Where Your Report Is Now</h2></div>
          <span className="px-2 py-1 border border-se-outline-variant font-se-code text-[10px] uppercase">{statusLabel(report.issue_status)}</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
          {stages.map((s, i) => (
            <div key={s.title} className={`p-4 flex flex-col gap-2 min-h-[180px] ${s.current ? "bg-se-high" : s.done ? "bg-se-low" : "bg-se-low opacity-60"}`}>
              <div className="flex items-center justify-between">
                <span className={`px-1.5 py-0.5 font-se-code text-[10px] uppercase ${s.done || s.current ? "bg-se-primary text-white" : "bg-se-container text-se-variant"}`}>Step 0{i + 1}</span>
                {s.current ? <span className="px-1.5 py-0.5 bg-se-primary text-white font-se-code text-[9px] uppercase flex items-center gap-1"><span className="w-1 h-1 rounded-full bg-white" />In progress</span>
                  : <Icon name={s.done ? "check_circle" : "radio_button_unchecked"} className="text-[18px]" />}
              </div>
              <div className="font-se-sans text-se-body font-medium text-se-on">{s.title}</div>
              <p className="font-se-sans text-se-sm text-se-variant flex-1">{s.text}</p>
              <div className="font-se-code text-[10px] uppercase text-se-variant">{s.foot}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-7">
        <div className="lg:col-span-7 p-7 bg-se-lowest border border-se-outline-variant/60">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div><Kicker>Before & after</Kicker><h2 className="mt-2 font-se-sans text-se-title text-se-on">Photos From the Spot</h2></div>
            <span className="px-2 py-1 border border-se-outline-variant font-se-code text-[10px] uppercase">{photoQueued ? "Photo waiting to send" : EVIDENCE_LABELS[report.evidence_status ?? "not_provided"]}</span>
          </div>
          <p className="mt-1 font-se-sans text-se-sm text-se-variant">Your photo on the left; the crew’s photo of the finished work appears on the right once it’s checked.</p>
          <div className="mt-4 grid grid-cols-2 gap-1">
            <Pane label="Your photo (before)">
              {report.photo_url ? <img src={mediaUrl(report.photo_url)} alt="Your photo of the problem" className="w-full h-full object-cover" />
                : canAddPhoto ? (
                  <button type="button" onClick={onAddPhoto} disabled={busy} className="flex flex-col items-center gap-2 text-white disabled:opacity-50">
                    <Icon name="photo_camera" className="text-[32px]" /><span className="font-se-code text-se-caps uppercase">Add a photo</span>
                  </button>
                ) : <Empty icon="no_photography" text={photoQueued ? "Saved on this device" : "No photo added"} />}
            </Pane>
            <Pane label="Crew’s fix (after)" dark>
              <Empty icon={closed ? "task_alt" : "construction"} text={closed ? "Fixed — checked by your ward officer" : "Appears here after the fix"} />
            </Pane>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 p-3 bg-se-low font-se-sans text-se-sm">
            <div><Kicker>Reported</Kicker><div className="text-se-on mt-1">{date(report.reported_at)}</div></div>
            <div><Kicker>First seen</Kicker><div className="text-se-on mt-1">{date(issue?.first_reported)}</div></div>
            <div><Kicker>Fixed on</Kicker><div className="text-se-on mt-1">{closed ? date(issue?.closed_at) : "—"}</div></div>
          </div>
          {canAddPhoto && report.evidence_due_at && <p className="mt-2 font-se-code text-[11px] text-se-variant">You can add a photo until {formatTime(report.evidence_due_at)}.</p>}
        </div>

        <div className="lg:col-span-5 flex flex-col gap-7">
          <div className="p-7 bg-se-lowest border border-se-outline-variant/60">
            <Kicker className="flex items-center gap-1"><Icon name="how_to_reg" className="text-[16px]" />Step 05 {reverificationOpen ? "// Action needed" : ""}</Kicker>
            <h2 className="mt-2 font-se-sans text-se-title text-se-on">Your Final Say</h2>
            {reverificationOpen ? (
              <Reverification issueId={report.issue_id!} dueAt={report.issue_reverification_due_at} onDone={onChanged} />
            ) : (
              <>
                <p className="mt-2 font-se-sans text-se-sm text-se-variant">
                  {closed ? "This problem was marked fixed and the time to respond has passed." : "Once the crew marks this fixed, you’ll confirm it here — or tell us it’s still a problem."}
                </p>
                <div className="mt-4 flex gap-2 opacity-40 pointer-events-none" aria-hidden="true">
                  <span className="flex-1 h-11 bg-se-primary text-white font-se-code text-se-caps uppercase flex items-center justify-center gap-1"><Icon name="thumb_up" className="text-[16px]" />It’s fixed</span>
                  <span className="flex-1 h-11 border border-se-outline-variant font-se-code text-se-caps uppercase flex items-center justify-center gap-1"><Icon name="warning" className="text-[16px]" />Still a problem</span>
                </div>
              </>
            )}
          </div>
          <div className="p-7 bg-se-lowest border border-se-outline-variant/60 flex-1 flex flex-col">
            <div className="flex items-center justify-between"><Kicker>Updates</Kicker><span className="w-1.5 h-1.5 rounded-full bg-se-primary" /></div>
            <ul className="mt-4 space-y-2 font-se-code text-se-code">
              {closed && issue?.closed_at && <Update t={issue.closed_at} text="Marked fixed after a photo check" tag="Fixed" />}
              {count > 1 && issue?.last_reported && <Update t={issue.last_reported} text={`${count} residents have now reported this`} tag="Neighbours" />}
              {report.ward_id != null && <Update t={report.reported_at} text={`Sent to Ward ${report.ward_id}`} tag="Ward" />}
              <Update t={report.reported_at} text="Your report was received" tag="You" />
            </ul>
            <div className="mt-auto pt-4 flex justify-between font-se-code text-[11px] text-se-variant">
              <span>Updates as your ward works on it</span>
              {report.issue_id != null && <Link to={`/citizen/issues/${report.issue_id}`} className="underline hover:text-se-on">See public page →</Link>}
            </div>
          </div>
        </div>
      </div>
      <p className="font-se-sans text-se-sm text-se-variant max-w-3xl"><span className="text-se-on font-medium">What you wrote:</span> “{report.raw_text}”</p>
    </section>
  );
}

function Card({ k, v, s }: { k: string; v: string; s: string }) {
  return (
    <div className="p-4 bg-se-lowest border border-se-outline-variant/60">
      <Kicker>{k}</Kicker>
      <div className="mt-2 font-se-sans text-se-title text-se-on truncate">{v}</div>
      <div className="font-se-code text-[11px] text-se-variant truncate">{s}</div>
    </div>
  );
}

function Pane({ label, dark = false, children }: { label: string; dark?: boolean; children: React.ReactNode }) {
  return (
    <div className={`relative aspect-[4/3] flex items-center justify-center overflow-hidden ${dark ? "bg-se-primary" : "bg-se-primary-container"}`}>
      {children}
      <span className={`absolute top-2 left-2 px-2 py-1 font-se-code text-[10px] uppercase ${dark ? "bg-white text-se-on" : "bg-black/70 text-white"}`}>{label}</span>
    </div>
  );
}

function Empty({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="flex flex-col items-center gap-2 text-white/70 px-4 text-center">
      <Icon name={icon} className="text-[32px]" /><span className="font-se-code text-se-caps uppercase">{text}</span>
    </div>
  );
}

function Update({ t, text, tag }: { t: string; text: string; tag: string }) {
  return (
    <li className="flex items-center gap-3 p-2 border border-se-high">
      <span className="text-se-variant shrink-0">[{new Date(t).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}]</span>
      <span className="flex-1 text-se-on font-se-sans text-se-sm">{text}</span>
      <span className="text-[10px] uppercase text-se-variant">{tag}</span>
    </li>
  );
}

function Reverification({ issueId, dueAt, onDone }: { issueId: number; dueAt: string | null; onDone: () => void }) {
  const [disputing, setDisputing] = useState(false);
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "confirmed" | "reopened">("idle");
  const [error, setError] = useState<string | null>(null);

  async function send(resolved: boolean) {
    setState("sending");
    setError(null);
    try {
      const res = await api.submitFeedback(issueId, {
        resolved_confirmed: resolved,
        comment: resolved ? null : comment.trim() || null,
      });
      setState(res.issue_status === "reopened" ? "reopened" : "confirmed");
      onDone();
    } catch (err) {
      setState("idle");
      setError(err instanceof ApiError ? err.message : "Couldn't send your answer. Try again.");
    }
  }

  if (state === "confirmed") return <p className="mt-2 font-se-sans text-se-sm text-emerald-700">Thanks — you confirmed the fix.</p>;
  if (state === "reopened") return <p className="mt-2 font-se-sans text-se-sm text-amber-700">Thanks — it’s back on your ward team’s list.</p>;

  const btn = "flex-1 h-11 font-se-code text-se-caps uppercase flex items-center justify-center gap-1 disabled:opacity-50";
  return (
    <div className="mt-2 space-y-3">
      <p className="font-se-sans text-se-sm text-se-variant">Is the problem really fixed? Your answer is added to the public record.</p>
      {!disputing ? (
        <div className="flex gap-2">
          <button type="button" disabled={state === "sending"} onClick={() => send(true)} className={`${btn} bg-se-primary text-white`}>
            <Icon name="thumb_up" className="text-[16px]" />It’s fixed
          </button>
          <button type="button" disabled={state === "sending"} onClick={() => setDisputing(true)} className={`${btn} border border-se-outline-variant hover:border-se-primary`}>
            <Icon name="warning" className="text-[16px]" />Still a problem
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <label htmlFor={`remains-${issueId}`} className="block font-se-code text-se-caps uppercase text-se-variant">What’s still wrong? (no photo needed)</label>
          <textarea id={`remains-${issueId}`} rows={3} value={comment} onChange={(e) => setComment(e.target.value)}
            className="w-full p-3 border border-se-outline-variant bg-se-lowest font-se-sans text-se-sm focus:outline-none focus:border-se-primary"
            placeholder="e.g. The pothole was filled but has sunk again after the rain." />
          <div className="flex gap-2">
            <button type="button" onClick={() => setDisputing(false)} className={`${btn} border border-se-outline-variant`}>Back</button>
            <button type="button" disabled={state === "sending"} onClick={() => send(false)} className={`${btn} bg-se-primary text-white`}>Reopen it</button>
          </div>
        </div>
      )}
      {dueAt && <p className="font-se-code text-[11px] text-se-variant">You can answer until {formatTime(dueAt)}.</p>}
      {error && <p className="font-se-sans text-se-sm text-red-700" role="alert">{error}</p>}
    </div>
  );
}

export default MyReports;
