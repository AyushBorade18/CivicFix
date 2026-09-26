import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CategoryTag } from "../../components/Badges";
import { LoadingState, ErrorState, EmptyState } from "../../components/States";
import { CATEGORY_LABELS } from "../../api/types";
import { hasDistinctDescription } from "../../lib/work";
import { 
  Building2, 
  ChevronLeft, 
  ChevronRight, 
  Search
} from "lucide-react";

const PAGE_SIZE = 25;

export function PublicWorks() {
  const navigate = useNavigate();
  const [category, setCategory] = useState("");
  const [ward, setWard] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  const { data: mapData } = useApi(() => api.map(), []);
  const { data: matches } = useApi(() => api.listMatches({ limit: 500 }), []);

  // Map of work_id -> matched count
  const matchCountByWork = useMemo(() => {
    if (!matches) return new Map<number, number>();
    const map = new Map<number, number>();
    for (const m of matches) {
      map.set(m.work_id, (map.get(m.work_id) ?? 0) + 1);
    }
    return map;
  }, [matches]);

  const { data: works, loading, error, reload } = useApi(
    () =>
      api.listWorks({
        category: category || undefined,
        ward_id: ward ? Number(ward) : undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    [category, ward, offset]
  );

  const filteredWorks = useMemo(() => {
    if (!works) return [];
    if (!search) return works;
    const q = search.toLowerCase();
    return works.filter((w) => {
      const matchName = w.work_name.toLowerCase().includes(q);
      const matchAgency = w.agency ? w.agency.toLowerCase().includes(q) : false;
      const matchId = w.work_id.toString().includes(q);
      return matchName || matchAgency || matchId;
    });
  }, [works, search]);

  const resetPage = () => setOffset(0);

  return (
    <div className="h-full flex flex-col overflow-hidden bg-gray-50 font-sans">
      {/* Top Header & Filters */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 shrink-0 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-bold text-gray-900 font-mono flex items-center gap-2">
              <Building2 className="w-5 h-5 text-blue-600" />
              <span>PUBLIC WORKS &amp; MPLADS DIRECTORY</span>
            </h1>
            <p className="text-xs text-gray-500 font-mono mt-0.5">
              Government infrastructure contracts used to corroborate civic complaints and prevent duplicate or neglected works.
            </p>
          </div>
          <div className="text-xs font-mono text-gray-500 bg-gray-50 px-2.5 py-1 rounded border border-gray-200">
            <span>{matches?.length ?? 0} Evidence Matches Computed</span>
          </div>
        </div>

        {/* Filter Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-1">
          {/* Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search by Title, Agency, ID…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 border border-gray-200 rounded text-xs bg-white font-mono focus:outline-none focus:border-gray-400"
            />
          </div>

          {/* Ward Select */}
          <select
            value={ward}
            onChange={(e) => { setWard(e.target.value); resetPage(); }}
            className="px-2.5 py-1.5 border border-gray-200 rounded text-xs bg-white font-mono focus:outline-none focus:border-gray-400"
          >
            <option value="">All Wards (Pune)</option>
            {mapData?.wards.map((w) => (
              <option key={w.ward_id} value={w.ward_id}>
                Ward {w.ward_id} — {w.name}
              </option>
            ))}
          </select>

          {/* Category Select */}
          <select
            value={category}
            onChange={(e) => { setCategory(e.target.value); resetPage(); }}
            className="px-2.5 py-1.5 border border-gray-200 rounded text-xs bg-white font-mono focus:outline-none focus:border-gray-400"
          >
            <option value="">All Civic Categories</option>
            {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>

          {/* Reset button */}
          {(category || ward || search) && (
            <button
              onClick={() => {
                setCategory("");
                setWard("");
                setSearch("");
                resetPage();
              }}
              className="px-3 py-1.5 rounded border border-gray-200 text-xs font-mono text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Main Table Content */}
      <div className="flex-1 flex flex-col overflow-hidden p-6">
        <div className="ws-panel flex-1 flex flex-col overflow-hidden shadow-sm">
          <div className="flex-1 overflow-y-auto">
            {loading && (
              <div className="p-8">
                <LoadingState label="Loading government public works database…" />
              </div>
            )}
            {error && (
              <div className="p-8">
                <ErrorState message={error} onRetry={reload} />
              </div>
            )}
            {works && filteredWorks.length === 0 && (
              <div className="p-8">
                <EmptyState>No public works match the current filter criteria.</EmptyState>
              </div>
            )}

            {filteredWorks.length > 0 && (
              <table className="w-full border-collapse text-left font-mono text-xs">
                <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 text-[10px] uppercase text-gray-500 z-10">
                  <tr>
                    <th className="py-2.5 px-3.5 font-semibold">Work ID</th>
                    <th className="py-2.5 px-3.5 font-semibold">Title &amp; Scope</th>
                    <th className="py-2.5 px-3.5 font-semibold">Category</th>
                    <th className="py-2.5 px-3.5 font-semibold">Ward</th>
                    <th className="py-2.5 px-3.5 font-semibold">Executing Agency</th>
                    <th className="py-2.5 px-3.5 font-semibold">Sanctioned Cost</th>
                    <th className="py-2.5 px-3.5 font-semibold">Completion</th>
                    <th className="py-2.5 px-3.5 font-semibold text-right">Linked Issues</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {filteredWorks.map((work) => {
                    const matchCount = matchCountByWork.get(work.work_id) ?? 0;
                    return (
                      <tr
                        key={work.work_id}
                        onClick={() => navigate(`/works/${work.work_id}`)}
                        className="hover:bg-gray-50 cursor-pointer transition-colors"
                      >
                        <td className="py-2.5 px-3.5 font-bold text-gray-900">
                          #{work.work_id}
                        </td>
                        <td className="py-2.5 px-3.5 max-w-sm">
                          <div className="font-semibold text-gray-900 font-sans text-xs truncate" title={work.work_name}>
                            {work.work_name}
                          </div>
                          {hasDistinctDescription(work.work_name, work.description) && (
                            <p className="text-[11px] text-gray-500 font-sans truncate mt-0.5" title={work.description ?? ""}>
                              {work.description}
                            </p>
                          )}
                        </td>
                        <td className="py-2.5 px-3.5">
                          {work.category ? <CategoryTag category={work.category} /> : <span className="text-gray-400">—</span>}
                        </td>
                        <td className="py-2.5 px-3.5 text-gray-600">
                          {work.ward_id != null ? `Ward ${work.ward_id}` : "—"}
                        </td>
                        <td className="py-2.5 px-3.5 text-gray-600 truncate max-w-[140px]" title={work.agency ?? "PMC"}>
                          {work.agency ?? "PMC"}
                        </td>
                        <td className="py-2.5 px-3.5 text-gray-900 font-semibold">
                          {work.cost != null ? `₹${work.cost.toLocaleString()}` : "—"}
                        </td>
                        <td className="py-2.5 px-3.5 text-gray-600">
                          {work.completed_on ? new Date(work.completed_on).toLocaleDateString() : "—"}
                        </td>
                        <td className="py-2.5 px-3.5 text-right">
                          {matchCount > 0 ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                              {matchCount} Matched
                            </span>
                          ) : (
                            <span className="text-gray-400 text-[11px]">0</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination Controls */}
          {works && (
            <div className="p-3 bg-white border-t border-gray-200 flex items-center justify-between text-xs font-mono">
              <button
                type="button"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                className="px-2.5 py-1 rounded border border-gray-200 text-gray-700 hover:bg-gray-50 disabled:opacity-40 flex items-center gap-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Previous
              </button>

              <span className="text-gray-500 text-[11px]">
                Showing {offset + 1}–{offset + (works?.length ?? 0)} records
              </span>

              <button
                type="button"
                disabled={(works?.length ?? 0) < PAGE_SIZE}
                onClick={() => setOffset(offset + PAGE_SIZE)}
                className="px-2.5 py-1 rounded border border-gray-200 text-gray-700 hover:bg-gray-50 disabled:opacity-40 flex items-center gap-1"
              >
                Next
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
export default PublicWorks;
