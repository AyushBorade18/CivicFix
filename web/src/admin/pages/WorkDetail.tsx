import { useMemo } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CategoryTag, PrecisionTag } from "../../components/Badges";
import { LoadingState, ErrorState, EmptyState } from "../../components/States";
import { WardMap } from "../../components/WardMap";
import { 
  ArrowLeft, 
  MapPin, 
  Layers, 
  ExternalLink
} from "lucide-react";

export function WorkDetail() {
  const { workId } = useParams();
  const navigate = useNavigate();
  const numId = Number(workId);

  // Fetch works and matches
  const { data: works, loading: worksLoading, error: worksError } = useApi(
    () => api.listWorks({ limit: 500 }),
    []
  );
  const { data: matches } = useApi(
    () => api.listMatches({ limit: 500 }),
    []
  );

  const work = useMemo(() => {
    if (!works) return null;
    return works.find((w) => w.work_id === numId) ?? null;
  }, [works, numId]);

  // Find all matches that refer to this work
  const linkedMatches = useMemo(() => {
    if (!matches) return [];
    return matches.filter((m) => m.work_id === numId);
  }, [matches, numId]);

  return (
    <div className="h-full overflow-y-auto bg-gray-50 font-sans p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        
        {/* Back Link */}
        <Link
          to="/works"
          className="inline-flex items-center gap-1.5 text-xs font-mono font-semibold text-gray-500 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Public Works Directory</span>
        </Link>

        {worksLoading && <LoadingState label="Loading public work dossier…" />}
        {worksError && <ErrorState message={worksError} />}
        {!worksLoading && !work && <EmptyState>Work record #{workId} not found.</EmptyState>}

        {work && (
          <>
            {/* Header Card */}
            <div className="ws-panel p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                    MPLADS #{work.work_id}
                  </span>
                  {work.category && <CategoryTag category={work.category} />}
                  {work.location_precision && <PrecisionTag precision={work.location_precision} />}
                </div>
                <span className="text-xs font-mono text-gray-500">Government Contract</span>
              </div>

              <div>
                <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
                  {work.work_name}
                </h1>
                {work.description && (
                  <p className="text-xs text-gray-600 font-sans mt-2 leading-relaxed bg-gray-50 p-3 rounded border border-gray-100">
                    {work.description}
                  </p>
                )}
              </div>

              {/* Metadata Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-gray-50 rounded border border-gray-100 text-xs font-mono">
                <div>
                  <span className="text-[10px] text-gray-400 uppercase block font-semibold">Ward Jurisdiction</span>
                  <strong className="text-gray-900">{work.ward_id ? `Ward ${work.ward_id}` : "Citywide"}</strong>
                </div>
                <div>
                  <span className="text-[10px] text-gray-400 uppercase block font-semibold">Sanctioned Cost</span>
                  <strong className="text-gray-900">{work.cost != null ? `₹${work.cost.toLocaleString()}` : "—"}</strong>
                </div>
                <div>
                  <span className="text-[10px] text-gray-400 uppercase block font-semibold">Executing Agency</span>
                  <strong className="text-blue-700 truncate block">{work.agency ?? "PMC"}</strong>
                </div>
                <div>
                  <span className="text-[10px] text-gray-400 uppercase block font-semibold">Completion Date</span>
                  <strong className="text-gray-900">{work.completed_on ? new Date(work.completed_on).toLocaleDateString() : "—"}</strong>
                </div>
              </div>
            </div>

            {/* Spatial Context Map */}
            {work.location && (
              <div className="ws-panel p-4 space-y-2">
                <div className="flex items-center justify-between border-b border-gray-100 pb-2 text-xs font-mono font-bold text-gray-700">
                  <span className="flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-blue-600" />
                    Geospatial Work Site
                  </span>
                  <span className="text-[10px] text-gray-400">
                    {work.location.lat.toFixed(4)}, {work.location.lon.toFixed(4)}
                  </span>
                </div>

                <div className="h-72 rounded border border-gray-200 overflow-hidden">
                  <WardMap
                    audience="admin"
                    works={[
                      {
                        work_id: work.work_id,
                        category: work.category,
                        work_name: work.work_name,
                        location: work.location,
                        location_precision: work.location_precision ?? "unknown",
                      },
                    ]}
                    center={[work.location.lat, work.location.lon]}
                    zoom={15}
                    height="100%"
                  />
                </div>
              </div>
            )}

            {/* Corroborated Civic Complaints List */}
            <div className="ws-panel p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                <span className="text-xs font-mono uppercase font-bold text-gray-800 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-blue-600" />
                  Corroborating Civic Complaints ({linkedMatches.length})
                </span>
                <span className="text-[10px] font-mono text-gray-400">Proximity &amp; Category Match</span>
              </div>

              {linkedMatches.length === 0 ? (
                <div className="p-8 text-center text-xs font-mono text-gray-500">
                  No citizen complaints have been matched to this public work yet.
                </div>
              ) : (
                <div className="space-y-3">
                  {linkedMatches.map((m) => (
                    <div
                      key={m.match_id}
                      onClick={() => navigate(`/issues/${m.issue_id}`)}
                      className="p-3.5 rounded border border-gray-200 bg-white hover:bg-gray-50 cursor-pointer transition-colors space-y-2 text-xs font-mono"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-blue-600">Issue #{m.issue_id}</span>
                          <CategoryTag category={m.category} />
                        </div>
                        <span className="text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-1 text-[11px]">
                          <span>Inspect Dossier</span>
                          <ExternalLink className="w-3 h-3" />
                        </span>
                      </div>

                      {m.match_reason && (
                        <p className="text-[11px] text-gray-600 italic bg-gray-50 p-2 rounded border border-gray-100">
                          {m.match_reason}
                        </p>
                      )}

                      <div className="grid grid-cols-3 gap-2 text-[10px] pt-1 border-t border-gray-100 text-gray-600">
                        <div>
                          <span>Semantic Similarity: </span>
                          <strong className="text-gray-900">{m.semantic_score.toFixed(2)}</strong>
                        </div>
                        <div>
                          <span>Combined Match Score: </span>
                          <strong className="text-blue-700">{m.combined_score.toFixed(2)}</strong>
                        </div>
                        <div>
                          <span>Proximity Distance: </span>
                          <strong className="text-gray-900">{m.distance_m != null ? `${m.distance_m.toFixed(0)}m` : "—"}</strong>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

      </div>
    </div>
  );
}
export default WorkDetail;
