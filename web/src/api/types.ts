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
}

export interface MapIssuePoint {
  issue_id: number;
  category: string;
  status: string;
  priority_score: number | null;
  location: GeoPoint;
  location_precision: LocationPrecision;
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
  category_confidence: number;
  severity: string;
  location_precision: LocationPrecision;
  priority_score: number | null;
  priority_breakdown: PriorityBreakdown | null;
  matched_work: MatchSummary | null;
  signals: SignalSummary[];
  is_synthetic: boolean;
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
