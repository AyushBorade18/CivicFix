import { useMemo } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CategoryTag, StatusTag } from "../../components/Badges";
import { LoadingState, ErrorState, EmptyState } from "../../components/States";
import { WardMap } from "../../components/WardMap";
import { 
  ArrowLeft, 
  MapPin, 
  Layers, 
  Building2, 
  ChevronRight
} from "lucide-react";

export function WardDetail() {
  const { wardId } = useParams();
  const navigate = useNavigate();
  const wardNum = Number(wardId);

  const { data: mapData } = useApi(() => api.map(), []);
  const { data: wardIssues, loading: issuesLoading, error: issuesError } = useApi(
    () => api.listAllIssues({ ward_id: wardNum }).then((items) => ({ total: items.length, items })),
    [wardNum]
  );
  const { data: wardWorks, loading: worksLoading } = useApi(
    () => api.listWorks({ ward_id: wardNum, limit: 100 }),
    [wardNum]
  );

  const wardInfo = useMemo(() => {
    if (!mapData) return null;
    return mapData.wards.find((w) => w.ward_id === wardNum) ?? null;
  }, [mapData, wardNum]);

  // Filter map items for this ward
  const wardMapIssues = useMemo(() => {
    if (!mapData || !wardIssues) return [];
    const idSet = new Set(wardIssues.items.map((i) => i.issue_id));
    return mapData.issues.filter((i) => idSet.has(i.issue_id));
  }, [mapData, wardIssues]);

  const wardMapWorks = useMemo(() => {
    if (!mapData) return [];
    return mapData.matched_works;
  }, [mapData]);

  // Center on first issue or default
  const mapCenter: [number, number] = useMemo(() => {
    if (wardMapIssues.length > 0) {
      return [wardMapIssues[0].location.lat, wardMapIssues[0].location.lon];
    }
    return [18.5204, 73.8567];
  }, [wardMapIssues]);

  const highPriorityCount = useMemo(() => {
    if (!wardIssues) return 0;
    return wardIssues.items.filter((i) => (i.priority_score ?? 0) >= 0.7).length;
  }, [wardIssues]);

  return (
    <div className="h-full overflow-y-auto bg-gray-50 font-sans p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Back Link */}
        <Link
          to="/wards"
          className="inline-flex items-center gap-1.5 text-xs font-mono font-semibold text-gray-500 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Ward Explorer</span>
        </Link>

        {/* Ward Header */}
        <div className="ws-panel p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-3">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-gray-900 text-white">
                MUNICIPAL WARD #{wardNum}
              </span>
              <span className="text-xs font-mono text-gray-500">Pune Municipal Corporation</span>
            </div>
            <button
              onClick={() => navigate(`/issues?ward_id=${wardNum}`)}
              className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-mono font-semibold flex items-center gap-1.5"
            >
              <span>Explore Ward Issues</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
              Ward {wardNum} — {wardInfo?.name ?? "Pune Municipal Ward"}
            </h1>
            <p className="text-xs text-gray-500 font-mono mt-1">
              Administrative spatial dossier containing open civic complaints, local government public works, and sensitive infrastructure.
            </p>
          </div>

          {/* Ward Summary Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-gray-50 rounded border border-gray-100 text-xs font-mono">
            <div>
              <span className="text-[10px] text-gray-400 uppercase block font-semibold">Total Issues</span>
              <strong className="text-lg font-bold text-gray-900">{wardIssues?.total ?? "—"}</strong>
            </div>
            <div>
              <span className="text-[10px] text-gray-400 uppercase block font-semibold">High Priority (≥0.70)</span>
              <strong className="text-lg font-bold text-red-600">{highPriorityCount}</strong>
            </div>
            <div>
              <span className="text-[10px] text-gray-400 uppercase block font-semibold">MPLADS Works</span>
              <strong className="text-lg font-bold text-emerald-700">{wardWorks?.length ?? "—"}</strong>
            </div>
            <div>
              <span className="text-[10px] text-gray-400 uppercase block font-semibold">Jurisdiction</span>
              <strong className="text-lg font-bold text-blue-700">PMC Zone Active</strong>
            </div>
          </div>
        </div>

        {/* Spatial Map Canvas */}
        <div className="ws-panel p-4 space-y-2">
          <div className="flex items-center justify-between border-b border-gray-100 pb-2 text-xs font-mono font-bold text-gray-700">
            <span className="flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-blue-600" />
              Ward {wardNum} Geospatial Evidence Canvas
            </span>
            <span className="text-[10px] text-gray-400">{wardMapIssues.length} issues mapped</span>
          </div>

          <div className="h-80 rounded border border-gray-200 overflow-hidden">
            <WardMap
              audience="admin"
              issues={wardMapIssues}
              works={wardMapWorks}
              center={mapCenter}
              zoom={14}
              height="100%"
              onIssueClick={(id) => navigate(`/issues/${id}`)}
            />
          </div>
        </div>

        {/* Two-Column: Active Civic Complaints & Public Works */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Active Issues Table */}
          <div className="ws-panel p-4 space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-gray-100 pb-2">
              <span className="font-bold text-gray-800 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-blue-600" />
                Active Civic Issues ({wardIssues?.items.length ?? 0})
              </span>
            </div>

            {issuesLoading && <LoadingState label="Loading ward issues…" />}
            {issuesError && <ErrorState message={issuesError} />}
            {wardIssues && wardIssues.items.length === 0 && (
              <EmptyState>No active civic complaints logged for Ward {wardNum}.</EmptyState>
            )}

            {wardIssues && wardIssues.items.length > 0 && (
              <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {wardIssues.items.map((i) => (
                  <div
                    key={i.issue_id}
                    onClick={() => navigate(`/issues/${i.issue_id}`)}
                    className="p-3 rounded border border-gray-200 bg-white hover:bg-gray-50 cursor-pointer transition-colors space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-gray-900">#{i.issue_id}</span>
                      <div className="flex items-center gap-1">
                        <CategoryTag category={i.category} />
                        <StatusTag status={i.status} />
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-gray-600 pt-1">
                      <span>{i.report_count} report(s)</span>
                      <span className="font-bold text-blue-700">Priority: {i.priority_score?.toFixed(2) ?? "—"}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right: Public Works */}
          <div className="ws-panel p-4 space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-gray-100 pb-2">
              <span className="font-bold text-gray-800 flex items-center gap-1.5">
                <Building2 className="w-4 h-4 text-emerald-600" />
                Government MPLADS Works ({wardWorks?.length ?? 0})
              </span>
            </div>

            {worksLoading && <LoadingState label="Loading ward public works…" />}
            {wardWorks && wardWorks.length === 0 && (
              <EmptyState>No funded public works recorded specifically in Ward {wardNum}.</EmptyState>
            )}

            {wardWorks && wardWorks.length > 0 && (
              <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {wardWorks.map((w) => (
                  <div
                    key={w.work_id}
                    onClick={() => navigate(`/works/${w.work_id}`)}
                    className="p-3 rounded border border-gray-200 bg-white hover:bg-gray-50 cursor-pointer transition-colors space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-emerald-800">MPLADS #{w.work_id}</span>
                      {w.category && <CategoryTag category={w.category} />}
                    </div>
                    <div className="text-gray-900 font-semibold font-sans text-xs">
                      {w.work_name}
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-gray-500 pt-1">
                      <span>{w.agency ?? "PMC"}</span>
                      {w.cost != null && <span>₹{w.cost.toLocaleString()}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
export default WardDetail;
