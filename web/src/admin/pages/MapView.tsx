import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { WardMap } from "../../components/WardMap";
import { CategoryTag, StatusTag, PrecisionTag } from "../../components/Badges";
import { CATEGORY_LABELS } from "../../api/types";
import { 
  Compass, 
  ExternalLink, 
  X,
  Sparkles,
  Building2,
  MapPin
} from "lucide-react";

export function MapView() {
  const navigate = useNavigate();
  const { data, loading, error, reload } = useApi(() => api.map(), []);

  // Layer Visibility Toggles
  const [showIssues, setShowIssues] = useState(true);
  const [showWorks, setShowWorks] = useState(true);
  const [showSites, setShowSites] = useState(true);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [minPriority, setMinPriority] = useState<number>(0);

  // Selected map entity for inspector
  const [selectedIssueId, setSelectedIssueId] = useState<number | null>(null);
  const [selectedWorkId, setSelectedWorkId] = useState<number | null>(null);

  // Load selected issue detail if clicked
  const { data: issueDetail, loading: issueLoading } = useApi(
    () => (selectedIssueId ? api.issueDetail(selectedIssueId) : Promise.resolve(null)),
    [selectedIssueId]
  );

  // Filtered issues
  const filteredIssues = useMemo(() => {
    if (!data || !showIssues) return [];
    return data.issues.filter((i) => {
      if (selectedCategory && i.category !== selectedCategory) return false;
      if (minPriority > 0 && (i.priority_score ?? 0) < minPriority) return false;
      return true;
    });
  }, [data, showIssues, selectedCategory, minPriority]);

  const filteredWorks = useMemo(() => {
    if (!data || !showWorks) return [];
    return data.matched_works.filter((w) => {
      if (selectedCategory && w.category && w.category !== selectedCategory) return false;
      return true;
    });
  }, [data, showWorks, selectedCategory]);

  const filteredSites = useMemo(() => {
    if (!data || !showSites) return [];
    return data.sensitive_sites;
  }, [data, showSites]);

  const selectedWork = useMemo(() => {
    if (!data || !selectedWorkId) return null;
    return data.matched_works.find((w) => w.work_id === selectedWorkId) ?? null;
  }, [data, selectedWorkId]);

  return (
    <div className="relative w-full h-full overflow-hidden bg-gray-100 font-sans">
      
      {/* 1. Full Screen Spatial Map Canvas */}
      <div className="absolute inset-0 z-0">
        {data && (
          <WardMap
            audience="admin"
            issues={filteredIssues}
            works={filteredWorks}
            sites={filteredSites}
            onIssueClick={(id) => {
              setSelectedWorkId(null);
              setSelectedIssueId(id);
            }}
            onWorkClick={(id) => {
              setSelectedIssueId(null);
              setSelectedWorkId(id);
            }}
            height="100%"
          />
        )}
      </div>

      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/40 backdrop-blur-xs">
          <div className="ws-panel p-5 flex items-center gap-3 shadow-lg">
            <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs font-mono font-medium text-gray-700">Loading Geospatial Layers…</span>
          </div>
        </div>
      )}

      {error && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 ws-panel p-4 flex items-center gap-3 bg-red-50 border-red-200 text-red-800 text-xs font-mono">
          <span>Error loading spatial layers: {error}</span>
          <button onClick={reload} className="underline font-bold">Retry</button>
        </div>
      )}

      {/* 2. Top-Left: CARTO-style Geospatial Layer & Filter Manager */}
      <div className="absolute top-3 left-3 z-20 w-80 space-y-2 animate-reveal">
        <div className="ws-panel p-4 space-y-3.5 shadow-md">
          <div className="flex items-center justify-between border-b border-gray-100 pb-2">
            <div className="flex items-center gap-2">
              <Compass className="w-4 h-4 text-blue-600" />
              <span className="text-xs font-mono uppercase tracking-wider font-bold text-gray-800">
                Spatial Explorer
              </span>
            </div>
            {(selectedCategory || minPriority > 0) && (
              <button
                onClick={() => {
                  setSelectedCategory("");
                  setMinPriority(0);
                }}
                className="text-[10px] font-mono text-blue-600 hover:text-blue-800 underline"
              >
                Reset
              </button>
            )}
          </div>

          {/* Layer Visibility Toggles */}
          <div className="space-y-2">
            <label className="text-[10px] font-mono uppercase text-gray-400 font-semibold block tracking-wider">
              Layer Controls
            </label>
            <div className="space-y-1.5 font-mono text-xs">
              <label className="flex items-center justify-between p-1.5 rounded hover:bg-gray-50 cursor-pointer">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={showIssues}
                    onChange={(e) => setShowIssues(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-0"
                  />
                  <span className="flex items-center gap-1.5 text-gray-800 font-medium">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#0f766e]" />
                    Civic Issues
                  </span>
                </div>
                <span className="text-[11px] text-gray-500 font-bold">{filteredIssues.length}</span>
              </label>

              <label className="flex items-center justify-between p-1.5 rounded hover:bg-gray-50 cursor-pointer">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={showWorks}
                    onChange={(e) => setShowWorks(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-0"
                  />
                  <span className="flex items-center gap-1.5 text-gray-800 font-medium">
                    <span className="w-2.5 h-2.5 rotate-45 bg-[#2563eb]" />
                    MPLADS Works
                  </span>
                </div>
                <span className="text-[11px] text-gray-500 font-bold">{filteredWorks.length}</span>
              </label>

              <label className="flex items-center justify-between p-1.5 rounded hover:bg-gray-50 cursor-pointer">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={showSites}
                    onChange={(e) => setShowSites(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-0"
                  />
                  <span className="flex items-center gap-1.5 text-gray-800 font-medium">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#64748b]" />
                    Sensitive Sites
                  </span>
                </div>
                <span className="text-[11px] text-gray-500 font-bold">{filteredSites.length}</span>
              </label>
            </div>
          </div>

          {/* Category Filter */}
          <div className="space-y-1">
            <label className="text-[10px] font-mono uppercase text-gray-400 font-semibold block tracking-wider">
              Category Focus
            </label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-gray-200 rounded text-xs bg-white font-mono"
            >
              <option value="">All Civic Categories</option>
              {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>

          {/* Min Priority */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] font-mono">
              <span className="text-gray-400 uppercase font-semibold">Min Priority</span>
              <span className="font-bold text-gray-900">{minPriority.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={minPriority}
              onChange={(e) => setMinPriority(Number(e.target.value))}
              className="w-full cursor-pointer h-1.5 accent-blue-600 bg-gray-200 rounded-lg"
            />
          </div>
        </div>

        {/* Legend Panel */}
        <div className="ws-panel p-3 shadow-md space-y-1.5 text-[11px] font-mono">
          <div className="text-[10px] font-mono uppercase tracking-wider font-bold text-gray-400 mb-1">
            Cartographic Legend
          </div>
          <div className="flex items-center gap-2 text-gray-700">
            <span className="w-2.5 h-2.5 rounded-full bg-[#0f766e]" />
            <span>Circle: Civic Issue (Radius = Priority Score)</span>
          </div>
          <div className="flex items-center gap-2 text-gray-700">
            <span className="w-2.5 h-2.5 rotate-45 bg-[#2563eb]" />
            <span>Diamond: Matched MPLADS Public Work</span>
          </div>
          <div className="flex items-center gap-2 text-gray-700">
            <span className="w-2.5 h-2.5 rounded-full bg-[#64748b]" />
            <span>Cluster: Sensitive Sites (Schools, Hospitals)</span>
          </div>
        </div>
      </div>

      {/* 3. Top-Right: Entity Inspector Drawer */}
      {selectedIssueId && (
        <div className="absolute right-3 top-3 bottom-3 z-20 w-96 ws-panel shadow-2xl flex flex-col overflow-hidden animate-panel border-gray-300">
          <div className="p-3.5 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                #{selectedIssueId}
              </span>
              <span className="text-xs font-mono font-semibold text-gray-700">Spatial Feature</span>
            </div>
            <button
              onClick={() => setSelectedIssueId(null)}
              className="text-gray-400 hover:text-gray-700 p-1 rounded hover:bg-gray-200"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {issueLoading ? (
              <div className="py-12 flex flex-col items-center justify-center gap-2 text-xs font-mono text-gray-500">
                <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span>Loading Issue Coordinates…</span>
              </div>
            ) : issueDetail ? (
              <>
                <div>
                  <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
                    <CategoryTag category={issueDetail.category} />
                    <StatusTag status={issueDetail.status} />
                    <PrecisionTag precision={issueDetail.location_precision} />
                  </div>
                  <h3 className="text-base font-bold text-gray-900">
                    {CATEGORY_LABELS[issueDetail.category] ?? issueDetail.category}
                  </h3>
                </div>

                {/* Priority */}
                <div className="p-3 rounded bg-gray-50 border border-gray-200 space-y-1 font-mono text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-500 font-semibold flex items-center gap-1">
                      <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                      Priority Score:
                    </span>
                    <strong className="text-gray-900">{issueDetail.priority_score?.toFixed(2) ?? "—"}</strong>
                  </div>
                  {issueDetail.priority_breakdown && (
                    <p className="text-[11px] text-gray-600 mt-1">
                      {issueDetail.priority_breakdown.explanation}
                    </p>
                  )}
                </div>

                {/* Reports Text */}
                {issueDetail.reports.length > 0 && (
                  <div className="space-y-1.5 font-mono text-xs">
                    <span className="text-gray-500 uppercase text-[10px] block font-semibold">
                      Citizen Report ({issueDetail.reports.length})
                    </span>
                    <p className="font-sans text-xs text-gray-800 bg-gray-50 p-2.5 rounded border border-gray-100">
                      &ldquo;{issueDetail.reports[0].raw_text}&rdquo;
                    </p>
                    {issueDetail.reports[0].location_phrase && (
                      <div className="text-[11px] text-gray-600 flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-blue-600" />
                        <span>Landmark: {issueDetail.reports[0].location_phrase}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Matched MPLADS Work */}
                {issueDetail.matches.length > 0 && (
                  <div className="p-3 rounded bg-blue-50 border border-blue-200 text-xs font-mono space-y-1">
                    <span className="text-blue-900 font-bold block flex items-center gap-1">
                      <Building2 className="w-3.5 h-3.5 text-blue-700" />
                      Linked MPLADS Work:
                    </span>
                    <div className="font-semibold text-gray-900">{issueDetail.matches[0].work?.work_name}</div>
                    <div className="text-[10px] text-blue-700">
                      Distance: {issueDetail.matches[0].distance_m?.toFixed(0)}m · Match score: {issueDetail.matches[0].combined_score.toFixed(2)}
                    </div>
                  </div>
                )}
              </>
            ) : null}
          </div>

          <div className="p-3 bg-gray-50 border-t border-gray-200">
            <button
              onClick={() => navigate(`/issues/${selectedIssueId}`)}
              className="w-full py-2 px-3 bg-gray-900 hover:bg-gray-800 text-white rounded text-xs font-mono font-semibold flex items-center justify-center gap-1.5"
            >
              <span>Inspect Full Evidence Dossier</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Selected Work Inspector Drawer */}
      {selectedWork && (
        <div className="absolute right-3 top-3 bottom-3 z-20 w-96 ws-panel shadow-2xl flex flex-col overflow-hidden animate-panel border-gray-300 font-mono text-xs">
          <div className="p-3.5 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                MPLADS #{selectedWork.work_id}
              </span>
              <span className="text-xs font-mono font-semibold text-gray-700">Public Work</span>
            </div>
            <button
              onClick={() => setSelectedWorkId(null)}
              className="text-gray-400 hover:text-gray-700 p-1 rounded hover:bg-gray-200"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div>
              <div className="text-[10px] text-gray-400 uppercase font-semibold">Government Public Work</div>
              <h3 className="text-sm font-bold text-gray-900 mt-1 font-sans">
                {selectedWork.work_name}
              </h3>
            </div>

            <div className="p-3 rounded bg-gray-50 border border-gray-200 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-gray-500">Category:</span>
                <span className="font-semibold text-gray-900">{selectedWork.category ?? "General Civic"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Coordinates:</span>
                <span className="font-semibold text-gray-900">{selectedWork.location.lat.toFixed(4)}, {selectedWork.location.lon.toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Precision:</span>
                <span className="font-semibold text-gray-900">{selectedWork.location_precision}</span>
              </div>
            </div>

            <p className="text-gray-600 text-[11px] leading-relaxed">
              This municipal public work was matched to nearby citizen complaints using spatial coordinates and natural language semantic similarity.
            </p>
          </div>

          <div className="p-3 bg-gray-50 border-t border-gray-200">
            <button
              onClick={() => navigate(`/works/${selectedWork.work_id}`)}
              className="w-full py-2 px-3 bg-gray-900 hover:bg-gray-800 text-white rounded text-xs font-mono font-semibold flex items-center justify-center gap-1.5"
            >
              <span>View Public Work Record</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
export default MapView;
