// Mirrors app/api/schemas.py exactly. If a field doesn't exist there, it
// must not be invented here - the API is the source of truth.

export interface HealthResponse {
  status: string;
  database_connected: boolean;
  counts: Record<string, number>;
}

export interface StatsResponse {
  wards: number;
  works: number;
  reports: number;
  issues: number;
  matches: number;
  sensitive_sites: number;
  verification_signals: number;
}

export interface IssueCloseResponse {
  issue_id: number;
  status: string;
  closed_at: string | null;
}

export interface ClassifierMetrics {
  model_macro_f1: number | null;
  baseline_macro_f1: number | null;
  n_train: number | null;
  n_test: number | null;
  trained: boolean;
  deployed: boolean;
}

export interface ClusteringMetrics {
  total_issues: number;
  singleton_issues: number;
  multi_report_issues: number;
  largest_cluster_size: number;
}

export interface LocationMetrics {
  total_reports: number;
  precise_resolved: number;
  ward_level_resolved: number;
  unresolved: number;
  resolution_rate: number;
}

export interface MatcherMetrics {
  total_issues_eligible: number;
  matched_issues: number;
  match_rate: number;
  labeled_cases: number;
  labeled_correct: number;
  labeled_accuracy: number | null;
}

export interface MetricsResponse {
  classification: ClassifierMetrics;
  clustering: ClusteringMetrics;
  location: LocationMetrics;
  matcher: MatcherMetrics;
}

export interface GeoPoint {
  lat: number;
  lon: number;
}

export type LocationPrecision = "precise" | "ward_level" | "unknown";

export interface PriorityTerms {
  exposure: number;
  severity: number;
  recurrence: number;
  time_open: number;
}

export interface PriorityWeights {
  exposure: number;
  severity: number;
  recurrence: number;
  time_open: number;
}

export interface ExposureDetail {
  spatial_basis: "precise" | "ward" | string;
  radius_m: number | null;
  matched_site: { kind: string; name: string | null; distance_m: number | null } | null;
  candidate_count: number;
}

export interface PriorityBreakdown {
  total: number;
  weights: PriorityWeights;
  terms: PriorityTerms;
  exposure_detail: ExposureDetail;
  severity_band: string;
  recurrence_count: number;
  time_open_days: number;
  explanation: string;
}

export interface IssueSummary {
  issue_id: number;
  category: string;
  ward_id: number | null;
  report_count: number;
  first_reported: string | null;
  last_reported: string | null;
  status: string;
  recurrence_count: number;
  priority_score: number | null;
  priority_breakdown: PriorityBreakdown | null;
  location: GeoPoint | null;
  location_precision: LocationPrecision;
  is_synthetic: boolean;
  routed_agency: string | null;
  routed_at: string | null;
  location_phrase?: string | null;
  evidence_accuracy_m?: number | null;
  pending_evidence?: number;
  has_resolution_evidence?: boolean;
  assigned_worker_id?: number | null;
}

export interface IssueListResponse {
  total: number;
  limit: number;
  offset: number;
  items: IssueSummary[];
}

export interface ReportInIssue {
  id: number;
  raw_text: string;
  reported_at: string;
  category: string | null;
  category_conf: number | null;
  severity: string | null;
  location_phrase: string | null;
  geom_confidence: number | null;
  ward_id: number | null;
  is_synthetic: boolean;
  photo_url: string | null;
  language: string | null;
  translated_text: string | null;
  photo_severity_score: number | null;
  photo_severity_band: string | null;
  photo_checks?: PhotoChecks | null;
  triage?: Record<string, unknown> | null; // LLM triage verdict/reason, staff only
  evidence_status: EvidenceStatus | null;
  evidence_due_at: string | null;
}

// A report without a photo is "pending" or "not_provided" - never false.
export type EvidenceStatus =
  | "submitted"
  | "alternative_confirmed"
  | "alternative_in_progress"
  | "pending"
  | "not_provided";

export interface EvidenceItem {
  evidence_id: number;
  issue_id: number;
  report_id: number | null;
  submitted_by: number;
  actor_type: "citizen" | "worker";
  evidence_type: "initial_report" | "resolution";
  capture_method: "camera";
  file_url: string;
  mime_type: string;
  byte_size: number;
  sha256: string;
  location: GeoPoint;
  accuracy_m: number;
  captured_at: string | null;
  location_captured_at: string | null;
  submitted_at: string;
  distance_from_issue_m: number | null;
  issue_location_precision: LocationPrecision;
  review_status: "pending_review" | "verified" | "review_required";
  reviewed_by: number | null;
  reviewed_at: string | null;
  review_note: string | null;
}

export interface AlternativeVerification {
  id: number;
  report_id: number;
  channel: "phone" | "whatsapp" | "in_person" | "other";
  status: "initiated" | "confirmed" | "not_confirmed" | "unreachable";
  initiated_by: number;
  initiated_at: string;
  completed_by: number | null;
  completed_at: string | null;
  notes: string | null;
}

export interface FieldWorker {
  id: number;
  display_name: string | null;
}

export interface MeResponse {
  id: number;
  role: string;
  display_name: string | null;
  email: string | null;
  ward_ids: number[];
  departments: string[];
}

export interface MyReport {
  report_id: number;
  raw_text: string;
  reported_at: string;
  category: string | null;
  ward_id: number | null;
  photo_url: string | null;
  language: string | null;
  translated_text: string | null;
  issue_id: number | null;
  issue_status: string | null;
  is_synthetic: boolean;
  evidence_status: EvidenceStatus | null;
  evidence_due_at: string | null;
  issue_reverification_due_at: string | null;
}

/** Public projection of an issue: no report text, no priority, location rounded to ~100 m. */
export interface PublicIssue {
  issue_id: number;
  category: string;
  ward_id: number | null;
  ward_name: string | null;
  status: string;
  report_count: number;
  first_reported: string | null;
  last_reported: string | null;
  closed_at: string | null;
  location: GeoPoint | null;
  location_precision: "approximate" | "ward_level" | "unknown";
}

export interface PublicIssueListResponse {
  total: number;
  limit: number;
  offset: number;
  items: PublicIssue[];
}

export interface PublicMapResponse {
  issues: PublicIssue[];
  wards: MapWard[];
}

export interface PhotoChecks {
  had_exif: boolean;
  had_gps: boolean;
  content_credentials_present: boolean;
  flags: Record<string, string>;
  stored_encrypted: boolean;
}

export interface PhotoUploadResponse {
  photo_url: string;
  photo_checks: PhotoChecks;
}

export interface IssueRouteResponse {
  issue_id: number;
  routed_agency: string;
  routed_at: string;
}

export interface FeedbackSummary {
  feedback_id: number;
  issue_id: number;
  resolved_confirmed: boolean;
  comment: string | null;
  submitted_at: string;
  is_synthetic: boolean;
}

export interface FeedbackCreateRequest {
  resolved_confirmed: boolean;
  comment?: string | null;
}

export interface FeedbackCreateResponse {
  feedback: FeedbackSummary;
  issue_status: string;
}

export interface WorkSummary {
  work_id: number;
  work_name: string;
  description: string | null;
  category: string | null;
  status: string | null;
  cost: number | null;
  completed_on: string | null;
  agency: string | null;
  ward_id: number | null;
  location: GeoPoint | null;
  location_precision: LocationPrecision | null;
}

export interface MatchSummary {
  match_id: number;
  issue_id: number;
  work_id: number;
  category: string;
  semantic_score: number;
  combined_score: number;
  distance_m: number | null;
  days_since_completion: number | null;
  match_reason: string;
  issue_location_precision: LocationPrecision;
  work: WorkSummary | null;
}

export interface SignalSummary {
  signal_id: number;
  issue_id: number;
  match_id: number | null;
  rule_name: string;
  explanation: string;
  source_record_ids: Record<string, unknown>;
}

export interface IssueDetailResponse {
  issue_id: number;
  category: string;
  ward_id: number | null;
  status: string;
  report_count: number;
  first_reported: string | null;
  last_reported: string | null;
  recurrence_count: number;
  location: GeoPoint | null;
  location_precision: LocationPrecision;
  is_synthetic: boolean;
  priority_score: number | null;
  priority_breakdown: PriorityBreakdown | null;
  reports: ReportInIssue[];
  matches: MatchSummary[];
  signals: SignalSummary[];
  feedback: FeedbackSummary[];
  routed_agency: string | null;
  routed_at: string | null;
  evidence: EvidenceItem[];
  alternative_verifications: AlternativeVerification[];
  assigned_worker_id: number | null;
  assigned_at: string | null;
  closed_at: string | null;
  reverification_due_at: string | null;
}

export interface MapIssuePoint {
  issue_id: number;
  category: string;
  status: string;
  priority_score: number | null;
  location: GeoPoint;
  location_precision: LocationPrecision;
  ward_id: number | null;
  first_reported: string | null;
}

export interface MapWorkPoint {
  work_id: number;
  category: string | null;
  work_name: string;
  location: GeoPoint;
  location_precision: LocationPrecision;
}

export interface MapSitePoint {
  site_id: number;
  kind: string;
  location: GeoPoint;
}

export interface MapWard {
  ward_id: number;
  name: string;
  geometry: GeoJSON.Geometry | null;
}

export interface MapResponse {
  issues: MapIssuePoint[];
  matched_works: MapWorkPoint[];
  sensitive_sites: MapSitePoint[];
  wards: MapWard[];
}

export interface ReportCreateRequest {
  raw_text: string;
  ward_id?: number | null;
  photo_url?: string | null;
}

export interface ReportCreateResponse {
  report: ReportInIssue;
  issue_id: number;
  joined_existing_issue: boolean;
  category: string;
  category_confidence: number | null; // null for citizens (internal)
  severity: string | null;
  location_precision: LocationPrecision;
  priority_score: number | null;
  priority_breakdown: PriorityBreakdown | null;
  matched_work: MatchSummary | null;
  signals: SignalSummary[];
  is_synthetic: boolean;
  held_for_review: boolean;
}

export const CIVIC_CATEGORIES = [
  "pothole_road",
  "drainage_sewage",
  "water_supply",
  "streetlight",
  "garbage_waste",
  "footpath",
  "traffic_signage",
  "other",
] as const;

export const CATEGORY_LABELS: Record<string, string> = {
  pothole_road: "Pothole / road",
  drainage_sewage: "Drainage / sewage",
  water_supply: "Water supply",
  streetlight: "Streetlight",
  garbage_waste: "Garbage / waste",
  footpath: "Footpath",
  traffic_signage: "Traffic signage",
  other: "Other",
};
