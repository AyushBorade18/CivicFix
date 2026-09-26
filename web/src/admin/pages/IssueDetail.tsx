import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, ApiError, mediaUrl } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CategoryTag, StatusTag, SyntheticTag, PrecisionTag, LanguageTag } from "../../components/Badges";
import { LoadingState, ErrorState } from "../../components/States";
import { PriorityBreakdownView } from "../../components/PriorityBreakdown";
import { EvidenceChain, type EvidenceChainNode } from "../../components/EvidenceChain";
import { WardMap } from "../../components/WardMap";
import { CATEGORY_LABELS } from "../../api/types";
import type { PhotoChecks } from "../../api/types";
import { hasDistinctDescription } from "../../lib/work";
import { GlowingCard } from "../../components/ui/GlowingCard";
import { 
  ArrowLeft, 
  CheckCircle2, 
  Send, 
  MapPin, 
  Building2, 
  ShieldAlert, 
  FileText, 
  GitBranch, 
  MessageSquare,
  Sparkles
} from "lucide-react";

// Evidence for human review, never a verdict: metadata can be stripped or faked,
// so a clean result does not confirm the photo is genuine.
function PhotoChecksPanel({ checks }: { checks: PhotoChecks | null }) {
  if (!checks) {
    return <p className="text-[11px] text-secondary mt-1">Photo authenticity signals: not checked (uploaded before intake checks).</p>;
  }
  const flagEntries = Object.entries(checks.flags);
  return (
    <div className="text-[11px] text-secondary mt-1 space-y-0.5">
      <p>
        Photo authenticity signals for review:{" "}
        {flagEntries.length === 0 ? "no generator markers found" : `${flagEntries.length} flagged`}
      </p>
      {flagEntries.map(([name, detail]) => (
        <p key={name} className={detail.startsWith("strong") ? "text-amber-700 font-semibold" : ""}>
          • {name.replace(/_/g, " ")}: {detail}
        </p>
      ))}
      <p>
        Original had location data: {checks.had_gps ? "yes (removed)" : "no"} · Stored encrypted:{" "}
        {checks.stored_encrypted ? "yes" : <strong className="text-amber-700">no</strong>}
      </p>
    </div>
  );
}

export function IssueDetail() {
  const { issueId } = useParams();
  const { data: issue, loading, error, reload } = useApi(() => api.issueDetail(Number(issueId)), [issueId]);
  const [closing, setClosing] = useState(false);
  const [closeError, setCloseError] = useState<string | null>(null);
  const [routing, setRouting] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);

  if (loading) return <LoadingState label="Loading evidence dossier…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!issue) return null;

  const topMatch = issue.matches[0] ?? null;
  const canClose = issue.status === "open" || issue.status === "reopened";

  async function handleClose() {
    if (!issue) return;
    setClosing(true);
    setCloseError(null);
    try {
      await api.closeIssue(issue.issue_id);
      await reload();
    } catch (e) {
      setCloseError(e instanceof ApiError ? e.message : "Failed to close issue.");
    } finally {
      setClosing(false);
    }
  }

  async function handleRoute() {
    if (!issue) return;
    setRouting(true);
    setRouteError(null);
    try {
      await api.routeIssue(issue.issue_id);
      await reload();
    } catch (e) {
      setRouteError(e instanceof ApiError ? e.message : "Failed to route issue.");
    } finally {
      setRouting(false);
    }
  }

  const chainNodes: EvidenceChainNode[] = [
    {
      label: `${issue.report_count} citizen report${issue.report_count === 1 ? "" : "s"}`,
      present: issue.report_count > 0,
    },
    { label: `Civic issue #${issue.issue_id}`, present: true },
    {
      label: issue.priority_score != null ? `Priority ${issue.priority_score.toFixed(2)}` : "Priority not yet computed",
      detail: issue.priority_breakdown?.exposure_detail.matched_site
        ? `Exposure: ${issue.priority_breakdown.exposure_detail.matched_site.kind}`
        : undefined,
      present: issue.priority_score != null,
    },
    {
      label: topMatch ? `MPLADS work #${topMatch.work_id}` : "No qualifying public-work match found",
      detail: topMatch?.work?.work_name,
      present: !!topMatch,
    },
    {
      label: issue.signals.length > 0 ? `${issue.signals.length} verification signal${issue.signals.length === 1 ? "" : "s"}` : "No verification signals",
      present: issue.signals.length > 0,
    },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <Link
        to="/admin/issues"
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-secondary hover:text-foreground transition-colors group"
      >
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
        Back to Issue Explorer
      </Link>

      {/* Main Dossier Header in GlowingCard */}
      <GlowingCard className="border-border">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <div className="flex gap-2 flex-wrap items-center">
            <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
              Dossier #{issue.issue_id}
            </span>
            <CategoryTag category={issue.category} />
            <StatusTag status={issue.status} />
            <PrecisionTag precision={issue.location_precision} />
            {issue.is_synthetic && <SyntheticTag />}
          </div>
          <div className="text-xs font-mono text-secondary flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5 text-primary" />
            Ward {issue.ward_id ?? "—"}
          </div>
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground mb-6">
          {CATEGORY_LABELS[issue.category] ?? issue.category}
        </h1>

        <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 p-4 bg-muted/40 rounded-xl border border-border/80 text-xs mb-6">
          <div>
            <dt className="text-secondary font-mono uppercase mb-1">Ward</dt>
            <dd className="font-bold text-foreground text-sm">{issue.ward_id ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-secondary font-mono uppercase mb-1">Reports</dt>
            <dd className="font-bold text-foreground text-sm">{issue.report_count}</dd>
          </div>
          <div>
            <dt className="text-secondary font-mono uppercase mb-1">First Reported</dt>
            <dd className="font-bold text-foreground text-sm">
              {issue.first_reported ? new Date(issue.first_reported).toLocaleDateString() : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-secondary font-mono uppercase mb-1">Last Reported</dt>
            <dd className="font-bold text-foreground text-sm">
              {issue.last_reported ? new Date(issue.last_reported).toLocaleDateString() : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-secondary font-mono uppercase mb-1">Recurrence</dt>
            <dd className="font-bold text-foreground text-sm">{issue.recurrence_count}</dd>
          </div>
          <div>
            <dt className="text-secondary font-mono uppercase mb-1">Routed Agency</dt>
            <dd className="font-bold text-primary text-sm truncate" title={issue.routed_agency ?? "Not yet routed"}>
              {issue.routed_agency ?? "Unrouted"}
            </dd>
          </div>
        </dl>

        {/* Admin action buttons */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          {canClose && (
            <button
              type="button"
              onClick={handleClose}
              disabled={closing}
              className="btn btn-black text-xs font-semibold py-2 px-4 rounded-lg flex items-center gap-1.5 disabled:opacity-50"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              {closing ? "Marking resolved…" : "Mark as Resolved"}
            </button>
          )}

          {!issue.routed_agency && (
            <button
              type="button"
              onClick={handleRoute}
              disabled={routing}
              className="btn py-2 px-4 rounded-lg border border-border text-xs font-semibold hover:bg-muted text-foreground flex items-center gap-1.5 disabled:opacity-50 transition-colors"
            >
              <Send className="w-3.5 h-3.5 text-primary" />
              {routing ? "Routing…" : "Route to PMC Department"}
            </button>
          )}

          {closeError && <span className="text-red-600 text-xs font-medium">{closeError}</span>}
          {routeError && <span className="text-red-600 text-xs font-medium">{routeError}</span>}
        </div>
      </GlowingCard>

      {/* Citizen Evidence Reports in GlowingCard */}
      <GlowingCard className="border-border">
        <h2 className="text-xl font-bold text-foreground mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary" />
          <span>Corroborating Citizen Reports ({issue.reports.length})</span>
        </h2>

        <div className="space-y-4">
          {issue.reports.map((report) => (
            <div
              key={report.id}
              className="p-4 bg-muted/40 rounded-xl border border-border/80 space-y-2.5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono text-secondary">
                <span className="font-bold text-primary">Report #{report.id}</span>
                <span>{new Date(report.reported_at).toLocaleString()}</span>
                {report.severity && (
                  <span className="px-2 py-0.5 rounded bg-background border border-border font-semibold">
                    {report.severity}
                  </span>
                )}
                {report.is_synthetic && <SyntheticTag />}
                {report.language && report.language !== "en" && <LanguageTag language={report.language} />}
              </div>

              <p className="text-foreground text-sm font-sans leading-relaxed">
                {report.raw_text}
              </p>

              {report.translated_text && (
                <p className="text-xs text-secondary italic bg-background p-2 rounded-lg border border-border/60">
                  Translated: &ldquo;{report.translated_text}&rdquo;
                </p>
              )}

              {report.location_phrase && (
                <div className="flex items-center gap-1 text-xs text-secondary">
                  <MapPin className="w-3.5 h-3.5 text-primary" />
                  <span>Detected landmark: &ldquo;{report.location_phrase}&rdquo;</span>
                </div>
              )}

              {report.photo_url && (
                <div className="mt-3 p-2 bg-background rounded-lg border border-border inline-block max-w-sm">
                  <img
                    src={mediaUrl(report.photo_url)}
                    alt="Reported evidence"
                    className="max-h-48 rounded object-cover"
                  />
                  {report.photo_severity_band && (
                    <p className="text-[11px] text-secondary mt-1 font-mono">
                      Photo analysis: <strong>{report.photo_severity_band}</strong>
                      {report.photo_severity_score != null && ` (score ${report.photo_severity_score.toFixed(2)})`}
                    </p>
                  )}
                  <PhotoChecksPanel checks={report.photo_checks ?? null} />
                </div>
              )}
            </div>
          ))}
        </div>
      </GlowingCard>

      {/* Priority Breakdown in GlowingCard */}
      {issue.priority_breakdown && (
        <GlowingCard className="border-border">
          <h2 className="text-xl font-bold text-foreground mb-4 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-600" />
            <span>Priority Score Mathematical Formula</span>
          </h2>
          <PriorityBreakdownView breakdown={issue.priority_breakdown} />
        </GlowingCard>
      )}

      {/* Spatial Context Map in GlowingCard */}
      {issue.location && (
        <div className="rounded-2xl border border-border p-2 bg-white/80 shadow-xs space-y-2">
          <div className="px-4 py-2 flex items-center gap-2 text-foreground font-bold text-sm">
            <MapPin className="w-4 h-4 text-primary" />
            <span>Spatial Geographic Context</span>
          </div>
          <WardMap
            audience="admin"
            focusMarker={{ lat: issue.location.lat, lon: issue.location.lon, label: `Issue #${issue.issue_id}` }}
            works={topMatch?.work?.location ? [{ work_id: topMatch.work_id, category: topMatch.category, work_name: topMatch.work.work_name, location: topMatch.work.location, location_precision: topMatch.work.location_precision ?? "unknown" }] : []}
            center={[issue.location.lat, issue.location.lon]}
            zoom={topMatch?.distance_m != null ? 16 : 13}
            height="360px"
          />
        </div>
      )}

      {/* Public Work Connection in GlowingCard */}
      <GlowingCard className="border-border">
        <h2 className="text-xl font-bold text-foreground mb-3 flex items-center gap-2">
          <Building2 className="w-5 h-5 text-indigo-600" />
          <span>MPLADS Public Works Record Links</span>
        </h2>

        {issue.matches.length === 0 ? (
          <p className="text-sm text-secondary">No qualifying public-works records match this issue's coordinates or category.</p>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-secondary">
              Surfaced {issue.matches.length} government public-works record{issue.matches.length === 1 ? "" : "s"} relevant to this site.
            </p>
            {issue.matches.map((match) => (
              <div
                key={match.match_id}
                className="p-4 bg-muted/40 rounded-xl border border-border/80 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-foreground text-sm">
                    {match.work?.work_name}
                  </span>
                  <span className="font-mono text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                    MPLADS #{match.work_id}
                  </span>
                </div>

                {match.work && hasDistinctDescription(match.work.work_name, match.work.description) && (
                  <p className="text-xs text-secondary leading-relaxed">{match.work.description}</p>
                )}

                {match.match_reason && (
                  <p className="text-xs text-secondary italic bg-background p-2 rounded-lg border border-border/60">
                    Match reason: {match.match_reason}
                  </p>
                )}

                <dl className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono pt-2 border-t border-border/60">
                  <div>
                    <dt className="text-secondary">Semantic Score</dt>
                    <dd className="font-bold text-foreground">{match.semantic_score.toFixed(2)}</dd>
                  </div>
                  <div>
                    <dt className="text-secondary">Combined Score</dt>
                    <dd className="font-bold text-primary">{match.combined_score.toFixed(2)}</dd>
                  </div>
                  {match.distance_m != null && (
                    <div>
                      <dt className="text-secondary">Distance</dt>
                      <dd className="font-bold text-foreground">{match.distance_m.toFixed(0)}m</dd>
                    </div>
                  )}
                  {match.days_since_completion != null && (
                    <div>
                      <dt className="text-secondary">Days Since Finish</dt>
                      <dd className="font-bold text-foreground">{match.days_since_completion} days</dd>
                    </div>
                  )}
                </dl>
              </div>
            ))}
          </div>
        )}
      </GlowingCard>

      {/* Evidence Chain in GlowingCard */}
      <GlowingCard className="border-border">
        <h2 className="text-xl font-bold text-foreground mb-4 flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-primary" />
          <span>Deterministic Evidence Chain</span>
        </h2>
        <EvidenceChain nodes={chainNodes} />
      </GlowingCard>

      {/* Verification Signals in GlowingCard */}
      {issue.signals.length > 0 && (
        <GlowingCard className="border-border">
          <h2 className="text-xl font-bold text-foreground mb-4 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-amber-600" />
            <span>Verification Signals ({issue.signals.length})</span>
          </h2>
          <ul className="space-y-3">
            {issue.signals.map((signal) => (
              <li
                key={signal.signal_id}
                className="p-4 bg-muted/40 rounded-xl border border-border/80 space-y-2"
              >
                <div className="font-mono text-xs font-bold text-primary">
                  {signal.rule_name}
                </div>
                <p className="text-xs sm:text-sm text-foreground leading-relaxed">
                  {signal.explanation}
                </p>
                <details className="text-xs pt-1">
                  <summary className="cursor-pointer text-secondary hover:text-foreground font-mono">
                    Show source records
                  </summary>
                  <pre className="mt-2 p-2.5 bg-background rounded-lg text-[11px] font-mono overflow-auto border border-border">
                    {JSON.stringify(signal.source_record_ids, null, 2)}
                  </pre>
                </details>
              </li>
            ))}
          </ul>
        </GlowingCard>
      )}

      {/* Resident Feedback Loop in GlowingCard */}
      {issue.feedback.length > 0 && (
        <GlowingCard className="border-border">
          <h2 className="text-xl font-bold text-foreground mb-4 flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-emerald-600" />
            <span>Citizen Verification Feedback</span>
          </h2>
          <ul className="space-y-3">
            {issue.feedback.map((fb) => (
              <li
                key={fb.feedback_id}
                className="p-3.5 bg-muted/40 rounded-xl border border-border/70 flex items-start gap-3 text-sm"
              >
                {fb.resolved_confirmed ? (
                  <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0 mt-0.5" />
                ) : (
                  <ShieldAlert className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                )}
                <div>
                  <span className="font-semibold text-foreground">
                    {fb.resolved_confirmed ? "Confirmed Resolved by Citizen" : "Disputed — Citizen reports issue still active"}
                  </span>
                  {fb.comment && <p className="text-xs text-secondary mt-1">&ldquo;{fb.comment}&rdquo;</p>}
                  {fb.is_synthetic && (
                    <span className="inline-block mt-1">
                      <SyntheticTag />
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </GlowingCard>
      )}
    </div>
  );
}
export default IssueDetail;
