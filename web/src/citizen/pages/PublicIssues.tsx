import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { WardMap } from "../../components/WardMap";
import { CategoryTag, StatusTag } from "../../components/Badges";
import { LoadingState, ErrorState, EmptyState } from "../../components/States";
import { CATEGORY_LABELS } from "../../api/types";
import type { MapIssuePoint } from "../../api/types";
import { GlowingCard } from "../../components/ui/GlowingCard";
import { Filter, MapPin, Layers, ArrowRight } from "lucide-react";

export function PublicIssues() {
  const navigate = useNavigate();
  const [category, setCategory] = useState("");
  // Public, no-sign-in endpoints only.
  const { data: mapData, loading: mapLoading } = useApi(() => api.publicMap(), []);
  const { data: issueList, loading, error, reload } = useApi(
    () => api.publicIssues({ category: category || undefined, limit: 50 }),
    [category]
  );

  const filteredMapIssues = useMemo<MapIssuePoint[]>(() => {
    if (!mapData) return [];
    return mapData.issues
      .filter((i) => i.location && (!category || i.category === category))
      .map((i) => ({
        issue_id: i.issue_id, category: i.category, status: i.status, priority_score: null, location: i.location!,
        location_precision: i.location_precision === "ward_level" ? "ward_level" : "precise",
        ward_id: i.ward_id, first_reported: i.first_reported,
      }));
  }, [mapData, category]);

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground mb-2">
          Reported problems in Pune
        </h1>
        <p className="text-secondary text-base sm:text-lg leading-relaxed">
          See what your neighbours have reported. When many people report the same problem, it's shown once with the number of reports.
        </p>
      </div>

      {/* Filter Control Bar in GlowingCard */}
      <GlowingCard borderWidth={1} spread={30} className="border-border">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Filter className="w-4 h-4 text-primary" />
            <span>Show only:</span>
          </div>
          <div className="w-full sm:w-auto">
            <select
              id="category-filter"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full sm:w-64 px-3.5 py-2 border border-border rounded-xl bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All problems ({mapData?.issues.length ?? "…"})</option>
              {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </GlowingCard>

      {/* Map in styled frame */}
      <div className="rounded-2xl border border-border p-2 bg-white/80 shadow-xs">
        {mapLoading ? (
          <div className="h-96 flex items-center justify-center">
            <LoadingState label="Loading map…" />
          </div>
        ) : (
          <WardMap
            issues={filteredMapIssues}
            onIssueClick={(id) => navigate(`/citizen/issues/${id}`)}
            height="440px"
          />
        )}
      </div>

      {/* Issues List with GlowingCards */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
            <Layers className="w-5 h-5 text-primary" />
            <span>Latest problems</span>
          </h2>
          {issueList && (
            <span className="text-xs text-secondary">
              Showing {issueList.items.length} of {issueList.total}
            </span>
          )}
        </div>

        {loading && <LoadingState label="Loading issues…" />}
        {error && <ErrorState message={error} onRetry={reload} />}
        {issueList && issueList.items.length === 0 && (
          <EmptyState>Nothing reported of this kind yet.</EmptyState>
        )}

        {issueList && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {issueList.items.map((issue) => (
              <GlowingCard
                key={issue.issue_id}
                onClick={() => navigate(`/citizen/issues/${issue.issue_id}`)}
                className="hover:border-primary/40 transition-all cursor-pointer group"
                innerClassName="p-4 sm:p-5 justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                      #{issue.issue_id}
                    </span>
                    <div className="flex gap-1.5 flex-wrap">
                      <CategoryTag category={issue.category} />
                      <StatusTag status={issue.status} />
                    </div>
                  </div>

                  <div className="mb-3">
                    <div className="text-xs text-secondary font-mono mb-1 flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-secondary" />
                      {issue.ward_id != null ? `Ward ${issue.ward_id}${issue.ward_name ? ` · ${issue.ward_name}` : ""}` : "Ward pending"}
                    </div>
                    <div className="font-bold text-foreground text-base group-hover:text-primary transition-colors line-clamp-1">
                      {CATEGORY_LABELS[issue.category] ?? issue.category}
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-border/80 flex items-center justify-between text-xs text-secondary">
                  <span>
                    {issue.report_count} resident report{issue.report_count === 1 ? "" : "s"}
                  </span>
                  <span className="text-primary font-semibold flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                    View Details
                    <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </GlowingCard>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
export default PublicIssues;
