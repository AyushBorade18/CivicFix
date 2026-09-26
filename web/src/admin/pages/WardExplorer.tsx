import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { LoadingState, ErrorState } from "../../components/States";
import { WardMap } from "../../components/WardMap";
import { 
  MapPin, 
  Search, 
  ChevronRight, 
  ExternalLink
} from "lucide-react";

export function WardExplorer() {
  const navigate = useNavigate();
  const { data: mapData, loading: mapLoading, error: mapError, reload } = useApi(() => api.map(), []);
  const { data: allIssues } = useApi(() => api.listAllIssues().then((items) => ({ items })), []);

  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"id" | "issues" | "priority">("issues");
  const [selectedWardId, setSelectedWardId] = useState<number | null>(null);

  // Group issues & works by ward_id
  const wardStats = useMemo(() => {
    if (!mapData) return new Map<number, { count: number; highPriority: number; avgPriority: number }>();
    const statsMap = new Map<number, { count: number; highPriority: number; avgPriority: number }>();

    // Initialize map
    for (const w of mapData.wards) {
      statsMap.set(w.ward_id, { count: 0, highPriority: 0, avgPriority: 0 });
    }

    if (allIssues) {
      const totals = new Map<number, { totalScore: number }>();
      for (const issue of allIssues.items) {
        if (issue.ward_id != null) {
          const cur = statsMap.get(issue.ward_id) ?? { count: 0, highPriority: 0, avgPriority: 0 };
          const curTotal = totals.get(issue.ward_id) ?? { totalScore: 0 };
          const score = issue.priority_score ?? 0;
          cur.count += 1;
          if (score >= 0.7) cur.highPriority += 1;
          curTotal.totalScore += score;
          totals.set(issue.ward_id, curTotal);
          statsMap.set(issue.ward_id, cur);
        }
      }
      for (const [wId, cur] of statsMap.entries()) {
        const tot = totals.get(wId);
        if (tot && cur.count > 0) {
          cur.avgPriority = tot.totalScore / cur.count;
        }
      }
    }
    return statsMap;
  }, [mapData, allIssues]);


  // Filter and sort wards
  const filteredWards = useMemo(() => {
    if (!mapData) return [];
    return mapData.wards
      .filter((w) => {
        if (!search) return true;
        const q = search.toLowerCase();
        return w.name.toLowerCase().includes(q) || w.ward_id.toString().includes(q);
      })
      .sort((a, b) => {
        if (sortBy === "id") return a.ward_id - b.ward_id;
        const statA = wardStats.get(a.ward_id) ?? { count: 0, avgPriority: 0 };
        const statB = wardStats.get(b.ward_id) ?? { count: 0, avgPriority: 0 };
        if (sortBy === "issues") return statB.count - statA.count;
        if (sortBy === "priority") return statB.avgPriority - statA.avgPriority;
        return 0;
      });
  }, [mapData, search, sortBy, wardStats]);

  const selectedWard = useMemo(() => {
    if (!mapData || !selectedWardId) return null;
    return mapData.wards.find((w) => w.ward_id === selectedWardId) ?? null;
  }, [mapData, selectedWardId]);

  return (
    <div className="h-full flex flex-col overflow-hidden bg-gray-50 font-sans">
      {/* Header Bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 shrink-0 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-gray-900 font-mono flex items-center gap-2">
            <MapPin className="w-5 h-5 text-blue-600" />
            <span>PUNE MUNICIPAL WARD EXPLORER</span>
          </h1>
          <p className="text-xs text-gray-500 font-mono mt-0.5">
            Geographic profiles, issue concentration, and public works distribution across Pune wards.
          </p>
        </div>

        {/* Search & Sort Controls */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search Ward Name or ID…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 border border-gray-200 rounded text-xs bg-white font-mono focus:outline-none focus:border-gray-400 w-56"
            />
          </div>

          <div className="flex items-center gap-1 text-xs font-mono text-gray-600">
            <span>Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as "id" | "issues" | "priority")}
              className="px-2 py-1 border border-gray-200 rounded text-xs bg-white font-bold"
            >
              <option value="issues">Issue Density (Highest)</option>
              <option value="priority">Priority Score (Highest)</option>
              <option value="id">Ward Number (1-58)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Content: Split List and Ward Map Profile */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Ward Cards Grid */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {mapLoading && <LoadingState label="Loading Pune municipal wards dataset…" />}
          {mapError && <ErrorState message={mapError} onRetry={reload} />}

          {filteredWards.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5">
              {filteredWards.map((w) => {
                const stat = wardStats.get(w.ward_id) ?? { count: 0, highPriority: 0, avgPriority: 0 };
                const isSelected = selectedWardId === w.ward_id;
                return (
                  <div
                    key={w.ward_id}
                    onClick={() => setSelectedWardId(w.ward_id)}
                    className={`ws-panel p-4 cursor-pointer transition-all hover:border-gray-400 ${
                      isSelected ? "border-blue-600 ring-2 ring-blue-500/20 bg-blue-50/20" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-gray-900 text-white">
                          Ward {w.ward_id}
                        </span>
                        <h3 className="font-bold text-sm text-gray-900 truncate max-w-[160px]" title={w.name}>
                          {w.name}
                        </h3>
                      </div>
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    </div>

                    <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-gray-100 text-[11px] font-mono">
                      <div>
                        <span className="text-gray-400 block text-[10px] uppercase">Issues</span>
                        <strong className="text-gray-900 font-bold text-sm">{stat.count}</strong>
                      </div>
                      <div>
                        <span className="text-gray-400 block text-[10px] uppercase">Priority ≥0.7</span>
                        <strong className="text-red-600 font-bold text-sm">{stat.highPriority}</strong>
                      </div>
                      <div>
                        <span className="text-gray-400 block text-[10px] uppercase">Avg Priority</span>
                        <strong className="text-blue-700 font-bold text-sm">
                          {stat.avgPriority > 0 ? stat.avgPriority.toFixed(2) : "—"}
                        </strong>
                      </div>
                    </div>

                    <div className="mt-3 pt-2.5 flex items-center justify-between text-xs font-mono">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/wards/${w.ward_id}`);
                        }}
                        className="text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-1 text-[11px]"
                      >
                        <span>Spatial Profile</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/issues?ward_id=${w.ward_id}`);
                        }}
                        className="text-gray-500 hover:text-gray-800 text-[11px]"
                      >
                        Inspect Issues →
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: Selected Ward Geographic Context Map */}
        <div className="w-[440px] hidden lg:flex flex-col bg-white border-l border-gray-200 overflow-hidden">
          <div className="p-3.5 border-b border-gray-200 bg-gray-50 flex items-center justify-between font-mono text-xs">
            <span className="font-bold text-gray-800 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-blue-600" />
              <span>Ward Geospatial Map</span>
            </span>
            {selectedWard && (
              <span className="font-semibold text-blue-600">
                Ward {selectedWard.ward_id} — {selectedWard.name}
              </span>
            )}
          </div>

          <div className="flex-1 relative">
            {mapData && (
              <WardMap
                audience="admin"
                issues={mapData.issues}
                works={mapData.matched_works}
                sites={mapData.sensitive_sites}
                height="100%"
                onIssueClick={(id) => navigate(`/issues/${id}`)}
              />
            )}
          </div>

          {selectedWard ? (
            <div className="p-4 border-t border-gray-200 bg-white space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[10px] text-gray-500 uppercase font-semibold">Municipal Ward Profile</div>
                  <div className="text-base font-bold text-gray-900">
                    Ward {selectedWard.ward_id} — {selectedWard.name}
                  </div>
                </div>
                <button
                  onClick={() => navigate(`/wards/${selectedWard.ward_id}`)}
                  className="px-3 py-1.5 rounded bg-gray-900 hover:bg-gray-800 text-white font-semibold flex items-center gap-1.5"
                >
                  <span>Full Profile</span>
                  <ExternalLink className="w-3 h-3" />
                </button>
              </div>

              <p className="text-[11px] text-gray-600 font-sans leading-relaxed">
                Click "Full Profile" to inspect all open complaints, matched MPLADS public works, and spatial sensitive infrastructure for this ward.
              </p>
            </div>
          ) : (
            <div className="p-4 border-t border-gray-200 bg-gray-50 text-center text-xs font-mono text-gray-500">
              Select a ward card on the left to inspect its boundaries, issues, and works.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
export default WardExplorer;
