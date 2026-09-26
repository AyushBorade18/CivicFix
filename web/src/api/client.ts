import type {
  FeedbackCreateRequest,
  FeedbackCreateResponse,
  HealthResponse,
  IssueCloseResponse,
  IssueDetailResponse,
  IssueListResponse,
  IssueRouteResponse,
  MapResponse,
  MatchSummary,
  MetricsResponse,
  PhotoUploadResponse,
  ReportCreateRequest,
  ReportCreateResponse,
  StatsResponse,
  WorkSummary,
} from "./types";

export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// photo_url values from the API are backend paths ("/api/photos/xxx.jpg", or
// "/uploads/xxx.jpg" on older reports), not Vite dev-server paths.
export function mediaUrl(path: string): string {
  return `${BASE_URL}${path}`;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `API error (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

function query(params: object): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      usp.set(key, String(value));
    }
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export interface IssueListParams {
  ward_id?: number;
  category?: string;
  status?: string;
  min_priority?: number;
  sort?: "priority" | "recent";
  limit?: number;
  offset?: number;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  stats: () => request<StatsResponse>("/api/stats"),
  listIssues: (params: IssueListParams = {}) =>
    request<IssueListResponse>(`/api/issues${query(params)}`),
  issueDetail: (issueId: number) => request<IssueDetailResponse>(`/api/issues/${issueId}`),
  listMatches: (params: { limit?: number; offset?: number } = {}) =>
    request<MatchSummary[]>(`/api/matches${query(params)}`),
  listWorks: (params: { ward_id?: number; category?: string; limit?: number; offset?: number } = {}) =>
    request<WorkSummary[]>(`/api/works${query(params)}`),
  map: () => request<MapResponse>("/api/map"),
  createReport: (payload: ReportCreateRequest) =>
    request<ReportCreateResponse>("/api/reports", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  metrics: () => request<MetricsResponse>("/api/metrics"),
  closeIssue: (issueId: number) =>
    request<IssueCloseResponse>(`/api/issues/${issueId}/close`, { method: "POST" }),
  routeIssue: (issueId: number) =>
    request<IssueRouteResponse>(`/api/issues/${issueId}/route`, { method: "POST" }),
  submitFeedback: (issueId: number, payload: FeedbackCreateRequest) =>
    request<FeedbackCreateResponse>(`/api/issues/${issueId}/feedback`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  uploadPhoto: async (file: File): Promise<PhotoUploadResponse> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE_URL}/api/uploads/photo`, { method: "POST", body: form });
    if (!res.ok) {
      let detail: unknown;
      try {
        detail = (await res.json()).detail;
      } catch {
        detail = res.statusText;
      }
      throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<PhotoUploadResponse>;
  },
};
