import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { LoadingState, ErrorState } from "../../components/States";
import { CATEGORY_LABELS } from "../../api/types";
import { 
  BarChart3, 
  MapPin, 
  PieChart, 
  Flame, 
  ArrowRight 
} from "lucide-react";

export function Analytics() {
  const navigate = useNavigate();
  const { data: stats, loading: statsLoading, error: statsError, reload } = useApi(() => api.stats(), []);
  const { data: mapData } = useApi(() => api.map(), []);
  const { data: issuesData } = useApi(() => api.listAllIssues().then((items) => ({ total: items.length, items })), []);

  // Category distribution
  const categoryCounts = useMemo(() => {
    if (!issuesData) return new Map<string, number>();
    const map = new Map<string, number>();
    for (const i of issuesData.items) {
      map.set(i.category, (map.get(i.category) ?? 0) + 1);
    }
    return map;
  }, [issuesData]);

  // Priority distribution
  const priorityBands = useMemo(() => {
    if (!issuesData) return { high: 0, medium: 0, low: 0, total: 0 };
    let high = 0, medium = 0, low = 0;
    for (const i of issuesData.items) {
      const score = i.priority_score ?? 0;
      if (score >= 0.7) high += 1;
      else if (score >= 0.4) medium += 1;
      else low += 1;
    }
    return { high, medium, low, total: issuesData.items.length };
  }, [issuesData]);

  // Ward ranking by volume
  const topWards = useMemo(() => {
    if (!issuesData || !mapData) return [];
    const counts = new Map<number, number>();
    for (const i of issuesData.items) {
      if (i.ward_id != null) {
        counts.set(i.ward_id, (counts.get(i.ward_id) ?? 0) + 1);
      }
    }
    const list = Array.from(counts.entries()).map(([ward_id, count]) => {
      const ward = mapData.wards.find((w) => w.ward_id === ward_id);
      return {
        ward_id,
        name: ward?.name ?? `Ward ${ward_id}`,
        count,
      };
    });
    list.sort((a, b) => b.count - a.count);
    return list.slice(0, 8);
  }, [issuesData, mapData]);

  // Total issues
  const totalIssues = issuesData?.total ?? 0;

  return (
    <div className="h-full overflow-y-auto bg-gray-50 font-sans p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 font-mono flex items-center gap-2">
              <BarChart3 className="w-6 h-6 text-blue-600" />
              <span>SPATIAL ANALYTICS &amp; MUNICIPAL TRENDS</span>
            </h1>
            <p className="text-xs text-gray-500 font-mono mt-0.5">
              Empirical distributions of citizen complaints, priority severity bands, and public works corroboration.
            </p>
          </div>
          <div className="text-xs font-mono text-gray-500 bg-white px-3 py-1.5 rounded border border-gray-200">
            <span>Aggregated from Live PostGIS Database</span>
          </div>
        </div>

        {statsLoading && <LoadingState label="Computing spatial analytics…" />}
        {statsError && <ErrorState message={statsError} onRetry={reload} />}

        {stats && (
          <>
            {/* Top Operational Overview */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="ws-panel p-3.5 space-y-1 font-mono text-xs">
                <span className="text-[10px] text-gray-400 uppercase font-semibold">Total Issues</span>
                <div className="text-xl font-bold text-gray-900">{stats.issues.toLocaleString()}</div>
              </div>
              <div className="ws-panel p-3.5 space-y-1 font-mono text-xs">
                <span className="text-[10px] text-gray-400 uppercase font-semibold">Citizen Reports</span>
                <div className="text-xl font-bold text-gray-900">{stats.reports.toLocaleString()}</div>
              </div>
              <div className="ws-panel p-3.5 space-y-1 font-mono text-xs">
                <span className="text-[10px] text-gray-400 uppercase font-semibold">Pune Wards</span>
                <div className="text-xl font-bold text-blue-600">{stats.wards}</div>
              </div>
              <div className="ws-panel p-3.5 space-y-1 font-mono text-xs">
                <span className="text-[10px] text-gray-400 uppercase font-semibold">MPLADS Works</span>
                <div className="text-xl font-bold text-emerald-700">{stats.works.toLocaleString()}</div>
              </div>
              <div className="ws-panel p-3.5 space-y-1 font-mono text-xs">
                <span className="text-[10px] text-gray-400 uppercase font-semibold">Matched Pairs</span>
                <div className="text-xl font-bold text-blue-700">{stats.matches.toLocaleString()}</div>
              </div>
              <div className="ws-panel p-3.5 space-y-1 font-mono text-xs">
                <span className="text-[10px] text-gray-400 uppercase font-semibold">Sensitive Sites</span>
                <div className="text-xl font-bold text-gray-900">{stats.sensitive_sites.toLocaleString()}</div>
              </div>
            </div>

            {/* Category Distribution & Priority Spectrum */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Category Breakdown */}
              <div className="ws-panel p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                  <span className="text-xs font-mono uppercase font-bold text-gray-800 flex items-center gap-1.5">
                    <PieChart className="w-4 h-4 text-blue-600" />
                    Civic Category Distribution
                  </span>
                  <span className="text-[10px] font-mono text-gray-400">Share of Total</span>
                </div>

                <div className="space-y-3 font-mono text-xs">
                  {Object.entries(CATEGORY_LABELS).map(([catKey, catLabel]) => {
                    const count = categoryCounts.get(catKey) ?? 0;
                    const pct = totalIssues > 0 ? (count / totalIssues) * 100 : 0;
                    return (
                      <div key={catKey} className="space-y-1">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-gray-800 font-semibold">{catLabel}</span>
                          <span className="text-gray-500">{count} issues ({pct.toFixed(1)}%)</span>
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-600 rounded-full transition-all"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Priority Severity Spectrum */}
              <div className="ws-panel p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                  <span className="text-xs font-mono uppercase font-bold text-gray-800 flex items-center gap-1.5">
                    <Flame className="w-4 h-4 text-red-500" />
                    Mathematical Priority Spectrum
                  </span>
                  <span className="text-[10px] font-mono text-gray-400">Formula Weights</span>
                </div>

                <div className="space-y-4 font-mono text-xs">
                  {/* High Priority */}
                  <div className="p-3.5 rounded border border-red-200 bg-red-50/50 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-red-800 flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-red-600" />
                        High Severity (Score ≥ 0.70)
                      </span>
                      <strong className="text-base text-red-900 font-mono">{priorityBands.high}</strong>
                    </div>
                    <p className="text-[11px] text-red-700 font-sans">
                      High public danger, close proximity to schools/hospitals, or persistent unresolved recurrence.
                    </p>
                  </div>

                  {/* Medium Priority */}
                  <div className="p-3.5 rounded border border-amber-200 bg-amber-50/50 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-amber-800 flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-amber-500" />
                        Moderate Priority (Score 0.40 – 0.69)
                      </span>
                      <strong className="text-base text-amber-900 font-mono">{priorityBands.medium}</strong>
                    </div>
                    <p className="text-[11px] text-amber-700 font-sans">
                      Standard civic maintenance issues with moderate public exposure.
                    </p>
                  </div>

                  {/* Low Priority */}
                  <div className="p-3.5 rounded border border-blue-200 bg-blue-50/50 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-blue-800 flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-blue-500" />
                        Low Severity (Score &lt; 0.40)
                      </span>
                      <strong className="text-base text-blue-900 font-mono">{priorityBands.low}</strong>
                    </div>
                    <p className="text-[11px] text-blue-700 font-sans">
                      Routine minor defects, isolated locations, or recently reported complaints.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Ward Concentration Table */}
            <div className="ws-panel p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                <span className="text-xs font-mono uppercase font-bold text-gray-800 flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-blue-600" />
                  Top Wards by Civic Defect Density
                </span>
                <Link to="/wards" className="text-xs font-mono text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-1">
                  <span>View All 58 Wards</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs">
                {topWards.map((w, idx) => (
                  <div
                    key={w.ward_id}
                    onClick={() => navigate(`/wards/${w.ward_id}`)}
                    className="p-3.5 rounded border border-gray-200 bg-white hover:bg-gray-50 cursor-pointer transition-colors space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-[11px] text-gray-400">
                      <span>RANK #{idx + 1}</span>
                      <span className="font-bold text-blue-600">Ward {w.ward_id}</span>
                    </div>
                    <div className="font-bold text-gray-900 font-sans text-sm truncate" title={w.name}>
                      {w.name}
                    </div>
                    <div className="text-gray-600 text-xs">
                      <strong>{w.count}</strong> complaints recorded
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

      </div>
    </div>
  );
}
export default Analytics;
