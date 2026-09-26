import { useParams, Link } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CategoryTag, StatusTag } from "../../components/Badges";
import { LoadingState, ErrorState } from "../../components/States";
import { WardMap } from "../../components/WardMap";
import { CATEGORY_LABELS } from "../../api/types";
import { GlowingCard } from "../../components/ui/GlowingCard";
import { ArrowLeft, MapPin, CheckCircle2, MessageSquare, Clock, UserCheck } from "lucide-react";

// Public view of one issue: the no-sign-in projection from
// GET /api/public/issues/:id (no report text, location rounded to ~100 m).

export function PublicIssueDetail() {
  const { issueId } = useParams();
  const { data: issue, loading, error, reload } = useApi(() => api.publicIssue(Number(issueId)), [issueId]);

  if (loading) return <LoadingState label="Loading issue…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!issue) return null;

  const closed = issue.status === "closed";
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <Link to="/citizen/issues" className="inline-flex items-center gap-1.5 text-sm font-semibold text-secondary hover:text-foreground transition-colors group">
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
        Back to all reported problems
      </Link>

      <GlowingCard className="border-border">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <div className="flex gap-2 flex-wrap items-center">
            <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">Problem #{issue.issue_id}</span>
            <CategoryTag category={issue.category} />
            <StatusTag status={issue.status} />
          </div>
          <div className="flex items-center gap-1 text-xs text-secondary">
            <MapPin className="w-3.5 h-3.5 text-primary" />
            {issue.ward_id != null ? `Ward ${issue.ward_id}${issue.ward_name ? ` · ${issue.ward_name}` : ""}` : "Ward pending"}
          </div>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground mb-3">{CATEGORY_LABELS[issue.category] ?? issue.category}</h1>
        <div className="flex flex-wrap items-center gap-4 text-xs sm:text-sm text-secondary pt-3 border-t border-border/80">
          <span className="flex items-center gap-1.5"><MessageSquare className="w-4 h-4 text-primary" />{issue.report_count} resident report{issue.report_count === 1 ? "" : "s"}</span>
          {issue.first_reported && <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" />First reported {new Date(issue.first_reported).toLocaleDateString("en-IN")}</span>}
          {issue.closed_at && <span className="flex items-center gap-1.5 text-emerald-700"><CheckCircle2 className="w-4 h-4" />Resolved {new Date(issue.closed_at).toLocaleDateString("en-IN")}</span>}
        </div>
      </GlowingCard>

      {issue.location && (
        <div className="rounded-2xl border border-border p-2 bg-white/80 shadow-xs">
          <WardMap
            issues={[{
              issue_id: issue.issue_id, category: issue.category, status: issue.status, priority_score: null,
              location: issue.location, location_precision: issue.location_precision === "ward_level" ? "ward_level" : "precise",
              ward_id: issue.ward_id, first_reported: issue.first_reported,
            }]}
            center={[issue.location.lat, issue.location.lon]}
            zoom={15}
            height="320px"
          />
          <p className="text-xs text-secondary px-2 pt-2">
            {issue.location_precision === "ward_level" ? "Shown at the centre of the ward." : "The exact spot is hidden slightly to protect the reporter's privacy."}
          </p>
        </div>
      )}

      <GlowingCard className="border-border">
        <div className="flex items-start gap-3">
          <UserCheck className="w-5 h-5 text-primary shrink-0 mt-0.5" />
          <div>
            <h2 className="font-bold text-foreground mb-1">{closed ? "Did you report this issue?" : "Reported this too?"}</h2>
            <p className="text-sm text-secondary leading-relaxed">
              {closed
                ? "If you reported it, go to My Reports to confirm the fix — or tell us it's still broken and it goes back on the list."
                : "Report it too — your report is added to this one, so the ward sees how many residents are affected."}
            </p>
            <div className="flex flex-wrap gap-3 mt-3">
              <Link to="/citizen/my-reports" className="btn btn-black text-xs font-semibold py-2 px-4 rounded-lg">My Reports</Link>
              {!closed && <Link to="/citizen/report" className="btn text-xs font-semibold py-2 px-4 rounded-lg border border-border">Report it too</Link>}
            </div>
          </div>
        </div>
      </GlowingCard>
    </div>
  );
}
export default PublicIssueDetail;
