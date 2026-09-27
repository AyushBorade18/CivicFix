import { currentToken } from "../lib/auth";
import type {
  AuditEntry,
  DashboardResponse,
  OrgResponse,
  StaffUser,
  UserScope,
  HeldReport,
  AlternativeVerification,
  EvidenceItem,
  FieldWorker,
  MeResponse,
  MyReport,
  PublicMapResponse,
  PublicIssue,
  PublicIssueListResponse,
  FeedbackCreateRequest,
  FeedbackCreateResponse,
  HealthResponse,
  IssueCloseResponse,
  IssueDetailResponse,
  IssueListResponse,
  IssueSummary,
  IssueRouteResponse,
  MapResponse,
  MatchSummary,
  MetricsResponse,
  PhotoUploadResponse,
  ReportCreateRequest,
  ReportCreateResponse,
  ChatTurnRequest,
  ChatTurnResponse,
  StatsResponse,
  WorkSummary,
} from "./types";

// Same origin by default: the Vite dev server proxies /api and /uploads to the
// backend, so a phone on https://<laptop-ip>:5173 reaches it without mixed
// content or CORS.
export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

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

function authHeaders(json: boolean): Record<string, string> {
  const headers: Record<string, string> = json ? { "Content-Type": "application/json" } : {};
  const token = currentToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function raw(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: authHeaders(typeof init?.body === "string"),
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
  return res;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return (await raw(path, init)).json() as Promise<T>;
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
}

/** One camera capture, sent as a unit. The id is generated on the device at
 * capture time, so re-sending after a network drop can't duplicate it. */
export interface EvidencePackage {
  clientSubmissionId: string;
  photo: Blob;
  latitude: number;
  longitude: number;
  accuracyM: number;
  capturedAt: string;
  locationCapturedAt: string;
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
  queue?: "verification_pending" | "assigned" | "signoff";
  limit?: number;
  offset?: number;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  stats: () => request<StatsResponse>("/api/stats"),
  listIssues: (params: IssueListParams = {}) =>
    request<IssueListResponse>(`/api/issues${query(params)}`),
  /** Every matching issue: /api/issues caps a page at 200, so walk the pages. */
  listAllIssues: async (params: Omit<IssueListParams, "limit" | "offset"> = {}): Promise<IssueSummary[]> => {
    const out: IssueSummary[] = [];
    for (let offset = 0; ; offset += 200) {
      const page = await request<IssueListResponse>(`/api/issues${query({ ...params, limit: 200, offset })}`);
      out.push(...page.items);
      if (out.length >= page.total || page.items.length === 0) return out;
    }
  },
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
  uploadPhoto: (file: File): Promise<PhotoUploadResponse> => {
    const form = new FormData();
    form.append("file", file);
    return request<PhotoUploadResponse>("/api/uploads/photo", { method: "POST", body: form });
  },

  chatTurn: (turn: ChatTurnRequest) => post<ChatTurnResponse>("/api/chat/turn", turn),

  register: () => post<MeResponse>("/api/me/register"),
  me: () => request<MeResponse>("/api/me"),
  myReports: () => request<MyReport[]>("/api/me/reports"),
  publicMap: () => request<PublicMapResponse>("/api/public/map"),
  publicIssues: (params: { ward_id?: number; category?: string; status?: string; limit?: number; offset?: number } = {}) =>
    request<PublicIssueListResponse>(`/api/public/issues${query(params)}`),
  publicIssue: (issueId: number) => request<PublicIssue>(`/api/public/issues/${issueId}`),

  submitEvidence: (issueId: number, pkg: EvidencePackage, reportId?: number): Promise<EvidenceItem> => {
    const form = new FormData();
    form.append("file", pkg.photo, "capture.jpg");
    form.append("client_submission_id", pkg.clientSubmissionId);
    form.append("latitude", String(pkg.latitude));
    form.append("longitude", String(pkg.longitude));
    form.append("accuracy_m", String(pkg.accuracyM));
    form.append("captured_at", pkg.capturedAt);
    form.append("location_captured_at", pkg.locationCapturedAt);
    if (reportId !== undefined) form.append("report_id", String(reportId));
    return request<EvidenceItem>(`/api/issues/${issueId}/evidence`, { method: "POST", body: form });
  },
  listEvidence: (issueId: number) => request<EvidenceItem[]>(`/api/issues/${issueId}/evidence`),
  /** Every capture in the caller's scope, newest first. */
  evidenceQueue: (review_status?: EvidenceItem["review_status"]) =>
    request<EvidenceItem[]>(`/api/evidence${query({ review_status })}`),
  /** Evidence photos need the bearer token, which an <img src> can't send. */
  evidencePhotoUrl: async (fileUrl: string): Promise<string> =>
    URL.createObjectURL(await (await raw(fileUrl)).blob()),
  reviewEvidence: (evidenceId: number, review_status: "verified" | "review_required", note?: string) =>
    post<EvidenceItem>(`/api/evidence/${evidenceId}/review`, { review_status, note: note || null }),
  dashboard: () => request<DashboardResponse>("/api/dashboard"),
  org: () => request<OrgResponse>("/api/admin/org"),
  adminUsers: (params: { role?: string; q?: string } = {}) =>
    request<StaffUser[]>(`/api/admin/users${query(params)}`),
  updateUser: (userId: number, patch: { role?: string; is_active?: boolean }) =>
    request<StaffUser>(`/api/admin/users/${userId}`, { method: "PATCH", body: JSON.stringify(patch) }),
  updateUserScope: (userId: number, scope: UserScope) =>
    request<StaffUser>(`/api/admin/users/${userId}/scope`, { method: "PUT", body: JSON.stringify(scope) }),
  auditLog: (params: { limit?: number; target_type?: string } = {}) =>
    request<AuditEntry[]>(`/api/admin/audit${query(params)}`),
  heldReports: () => request<HeldReport[]>("/api/held-reports"),
  releaseHeldReport: (reportId: number) =>
    post<{ report_id: number; issue_id: number; released: boolean }>(`/api/held-reports/${reportId}/release`),
  fieldWorkers: () => request<FieldWorker[]>("/api/field-workers"),
  assignIssue: (issueId: number, worker_user_id: number) =>
    post<{ issue_id: number; assigned_worker_id: number; assigned_at: string }>(
      `/api/issues/${issueId}/assign`, { worker_user_id }),
  startAlternativeVerification: (reportId: number, channel: AlternativeVerification["channel"], notes?: string) =>
    post<AlternativeVerification>(`/api/reports/${reportId}/alternative-verifications`, { channel, notes: notes || null }),
  completeAlternativeVerification: (
    id: number, status: "confirmed" | "not_confirmed" | "unreachable", notes?: string,
  ) => post<AlternativeVerification>(`/api/alternative-verifications/${id}/complete`, { status, notes: notes || null }),
};
