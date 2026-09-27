from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    counts: dict[str, int]


class StatsResponse(BaseModel):
    wards: int
    works: int
    reports: int
    issues: int
    matches: int
    sensitive_sites: int
    verification_signals: int


class IssueCloseResponse(BaseModel):
    issue_id: int
    status: str
    closed_at: Optional[datetime]


class IssueRouteResponse(BaseModel):
    issue_id: int
    routed_agency: str
    routed_at: datetime


class FeedbackCreateRequest(BaseModel):
    resolved_confirmed: bool
    comment: Optional[str] = None


class FeedbackSummary(BaseModel):
    feedback_id: int
    issue_id: int
    resolved_confirmed: bool
    comment: Optional[str]
    submitted_at: datetime
    is_synthetic: bool


class FeedbackCreateResponse(BaseModel):
    feedback: FeedbackSummary
    issue_status: str


class ClassifierMetrics(BaseModel):
    model_macro_f1: Optional[float]
    baseline_macro_f1: Optional[float]
    n_train: Optional[int]
    n_test: Optional[int]
    trained: bool
    deployed: bool


class ClusteringMetrics(BaseModel):
    total_issues: int
    singleton_issues: int
    multi_report_issues: int
    largest_cluster_size: int


class LocationMetrics(BaseModel):
    total_reports: int
    precise_resolved: int
    ward_level_resolved: int
    unresolved: int
    resolution_rate: float


class MatcherMetrics(BaseModel):
    total_issues_eligible: int
    matched_issues: int
    match_rate: float
    labeled_cases: int
    labeled_correct: int
    labeled_accuracy: Optional[float]


class MetricsResponse(BaseModel):
    classification: ClassifierMetrics
    clustering: ClusteringMetrics
    location: LocationMetrics
    matcher: MatcherMetrics


class GeoPoint(BaseModel):
    lat: float
    lon: float


class IssueSummary(BaseModel):
    issue_id: int
    category: str
    ward_id: Optional[int]
    report_count: int
    first_reported: Optional[datetime]
    last_reported: Optional[datetime]
    status: str
    recurrence_count: int
    priority_score: Optional[float]
    priority_breakdown: Optional[dict[str, Any]]
    location: Optional[GeoPoint]
    location_precision: str  # "precise" | "ward_level" | "unknown"
    is_synthetic: bool
    routed_agency: Optional[str] = None
    routed_at: Optional[datetime] = None
    # Triage-table extras, filled by GET /api/issues only.
    location_phrase: Optional[str] = None
    evidence_accuracy_m: Optional[float] = None  # best citizen-photo GPS accuracy
    pending_evidence: int = 0
    has_resolution_evidence: bool = False
    assigned_worker_id: Optional[int] = None


class IssueListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[IssueSummary]


class ReportInIssue(BaseModel):
    id: int
    raw_text: str
    reported_at: datetime
    category: Optional[str]
    category_conf: Optional[float]
    severity: Optional[str]
    location_phrase: Optional[str]
    geom_confidence: Optional[float]
    ward_id: Optional[int]
    is_synthetic: bool
    photo_url: Optional[str] = None
    language: Optional[str] = None
    translated_text: Optional[str] = None
    photo_severity_score: Optional[float] = None
    photo_severity_band: Optional[str] = None
    # "submitted" | "alternative_confirmed" | "alternative_in_progress" |
    # "pending" | "not_provided". A missing photo is never read as false.
    evidence_status: Optional[str] = None
    evidence_due_at: Optional[datetime] = None
    photo_checks: Optional[dict[str, Any]] = None
    # LLM triage verdict/reason/model when the classifier couldn't place it (app/nlp/triage.py); staff only.
    triage: Optional[dict[str, Any]] = None


class WorkSummary(BaseModel):
    work_id: int
    work_name: str
    description: Optional[str]
    category: Optional[str]
    status: Optional[str]
    cost: Optional[float]
    completed_on: Optional[date]
    agency: Optional[str]
    ward_id: Optional[int]
    location: Optional[GeoPoint]
    location_precision: Optional[str]  # "precise" | "ward_level" | None if no geom


class MatchSummary(BaseModel):
    match_id: int
    issue_id: int
    work_id: int
    category: str
    semantic_score: float
    combined_score: float
    distance_m: Optional[float]
    days_since_completion: Optional[int]
    match_reason: str
    issue_location_precision: str
    work: Optional[WorkSummary] = None


class SignalSummary(BaseModel):
    signal_id: int
    issue_id: int
    match_id: Optional[int]
    rule_name: str
    explanation: str
    source_record_ids: dict[str, Any]


class EvidenceItem(BaseModel):
    """One location-verified capture: photo + device location + both clocks.
    A verification signal for human review, not proof."""
    evidence_id: int
    issue_id: int
    report_id: Optional[int]
    submitted_by: int
    actor_type: str  # "citizen" | "worker"
    evidence_type: str  # "initial_report" | "resolution"
    capture_method: str  # "camera"
    file_url: str  # authorized endpoint, never a public path
    mime_type: str
    byte_size: int
    sha256: str
    location: GeoPoint  # as reported by the device
    accuracy_m: float  # device-reported radius, not a guarantee
    captured_at: Optional[datetime]  # device clock
    location_captured_at: Optional[datetime]  # device clock
    submitted_at: datetime  # server clock
    distance_from_issue_m: Optional[float]
    issue_location_precision: str  # what the distance was measured against
    review_status: str  # "pending_review" | "verified" | "review_required"
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    review_note: Optional[str]  # staff-only; None for citizens


class EvidenceReviewRequest(BaseModel):
    review_status: Literal["verified", "review_required"]
    note: Optional[str] = None


class FieldWorker(BaseModel):
    id: int
    display_name: Optional[str]


class IssueAssignRequest(BaseModel):
    worker_user_id: int


class IssueAssignResponse(BaseModel):
    issue_id: int
    assigned_worker_id: int
    assigned_at: datetime


class AlternativeVerificationCreateRequest(BaseModel):
    channel: Literal["phone", "whatsapp", "in_person", "other"]
    notes: Optional[str] = None


class AlternativeVerificationCompleteRequest(BaseModel):
    status: Literal["confirmed", "not_confirmed", "unreachable"]
    notes: Optional[str] = None


class AlternativeVerification(BaseModel):
    id: int
    report_id: int
    channel: str
    status: str
    initiated_by: int
    initiated_at: datetime
    completed_by: Optional[int]
    completed_at: Optional[datetime]
    notes: Optional[str]


class IssueDetailResponse(BaseModel):
    issue_id: int
    category: str
    ward_id: Optional[int]
    status: str
    report_count: int
    first_reported: Optional[datetime]
    last_reported: Optional[datetime]
    recurrence_count: int
    location: Optional[GeoPoint]
    location_precision: str
    is_synthetic: bool
    priority_score: Optional[float]
    priority_breakdown: Optional[dict[str, Any]]
    reports: list[ReportInIssue]
    matches: list[MatchSummary]
    signals: list[SignalSummary]
    feedback: list[FeedbackSummary] = []
    routed_agency: Optional[str] = None
    routed_at: Optional[datetime] = None
    evidence: list[EvidenceItem] = []  # chronological: before, then after
    alternative_verifications: list[AlternativeVerification] = []
    assigned_worker_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    reverification_due_at: Optional[datetime] = None


class MapIssuePoint(BaseModel):
    issue_id: int
    category: str
    status: str
    priority_score: Optional[float]
    location: GeoPoint
    location_precision: str
    ward_id: Optional[int] = None
    first_reported: Optional[datetime] = None


class MapWorkPoint(BaseModel):
    work_id: int
    category: Optional[str]
    work_name: str
    location: GeoPoint
    location_precision: str


class MapSitePoint(BaseModel):
    site_id: int
    kind: str
    location: GeoPoint


class MapWard(BaseModel):
    ward_id: int
    name: str
    geometry: Optional[dict] = None  # simplified GeoJSON boundary


class MapResponse(BaseModel):
    issues: list[MapIssuePoint]
    matched_works: list[MapWorkPoint]
    sensitive_sites: list[MapSitePoint]
    wards: list[MapWard]


class ReportCreateRequest(BaseModel):
    raw_text: str
    ward_id: Optional[int] = None
    photo_url: Optional[str] = None
    # Device GPS or a dropped map pin. Must fall inside a PMC ward. Preferred
    # over a geocoded text landmark: the citizen pointed at the spot.
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    # The citizen looked at the matching open issue and said "different
    # problem": start a new issue instead of joining it. Recurrence still applies.
    separate_issue: bool = False


class PhotoUploadResponse(BaseModel):
    photo_url: str
    photo_checks: dict[str, Any]


class ReportCreateResponse(BaseModel):
    report: ReportInIssue
    issue_id: int
    joined_existing_issue: bool
    category: str
    # None for citizens: model confidence and severity feed the internal
    # priority formula, so only staff receive them (see create_report).
    category_confidence: Optional[float]
    severity: Optional[str]
    location_precision: str
    priority_score: Optional[float]
    priority_breakdown: Optional[dict[str, Any]]
    matched_work: Optional[MatchSummary]
    signals: list[SignalSummary]
    is_synthetic: bool
    # True when LLM triage held it as likely spam: off every board until staff release it.
    held_for_review: bool = False


class HeldReport(BaseModel):
    """A report LLM triage held as likely spam, waiting for a human."""
    report_id: int
    issue_id: int
    raw_text: str
    translated_text: Optional[str]
    reported_at: datetime
    ward_id: Optional[int]
    triage: dict[str, Any]


class MeResponse(BaseModel):
    id: int
    role: str
    display_name: Optional[str]
    email: Optional[str]
    ward_ids: list[int]
    departments: list[str]
    ward_office_ids: list[int] = []
    zone_ids: list[int] = []


# --- RBAC administration (system_admin) ----------------------------------------

class OrgWard(BaseModel):
    id: int
    name: str
    verified: bool


class OrgWardOffice(BaseModel):
    id: int
    name: str
    wards: list[OrgWard]


class OrgZone(BaseModel):
    id: int
    name: str
    ward_offices: list[OrgWardOffice]


class OrgResponse(BaseModel):
    """PMC structure: zones -> ward offices -> prabhags, plus the fixed roles
    and departments an administrator can assign."""
    zones: list[OrgZone]
    unmapped_wards: list[OrgWard]
    roles: list[str]
    departments: list[str]


class StaffUser(BaseModel):
    id: int
    external_auth_id: str
    email: Optional[str]
    display_name: Optional[str]
    role: str
    is_active: bool
    ward_ids: list[int]          # direct prabhag assignments only
    ward_office_ids: list[int]
    zone_ids: list[int]
    departments: list[str]
    effective_ward_count: int    # prabhags reachable through all of the above


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserScopeRequest(BaseModel):
    ward_ids: list[int] = []
    ward_office_ids: list[int] = []
    zone_ids: list[int] = []
    departments: list[str] = []


class AuditEntry(BaseModel):
    id: int
    at: datetime
    actor_user_id: Optional[int]
    actor_name: Optional[str]
    action: str
    target_type: str
    target_id: str
    details: dict[str, Any]


class DashboardWardRow(BaseModel):
    ward_id: Optional[int]
    ward_name: Optional[str]
    ward_office_id: Optional[int]
    ward_office: Optional[str]
    zone_id: Optional[int]
    zone: Optional[str]
    open: int
    closed: int
    unrouted: int
    avg_open_age_days: Optional[float]


class DashboardIssue(BaseModel):
    issue_id: int
    category: str
    ward_id: Optional[int]
    ward_name: Optional[str]
    priority_score: Optional[float]
    report_count: int
    first_reported: Optional[datetime]
    routed_agency: Optional[str]


class DashboardResponse(BaseModel):
    """Everything below is limited to the caller's ward/office/zone/department
    scope - the same predicate the issue list uses."""
    role: str
    scope_label: str
    by_ward: list[DashboardWardRow]
    by_category: dict[str, int]
    top_open_issues: list[DashboardIssue]


class MyReport(BaseModel):
    """A citizen's own report: their own words back, plus the public status
    of the issue it joined. No model scores, no priority, no signals."""
    report_id: int
    raw_text: str
    reported_at: datetime
    category: Optional[str]
    ward_id: Optional[int]
    photo_url: Optional[str]
    language: Optional[str]
    translated_text: Optional[str]
    issue_id: Optional[int]
    issue_status: Optional[str]
    is_synthetic: bool
    evidence_status: Optional[str] = None
    evidence_due_at: Optional[datetime] = None
    issue_reverification_due_at: Optional[datetime] = None


class PublicIssue(BaseModel):
    """Public projection of an issue. Built field by field from the issues
    table - never from IssueDetailResponse - so internal fields can't leak
    by accident. Location is rounded to ~100 m (3 decimal places)."""
    issue_id: int
    category: str
    ward_id: Optional[int]
    ward_name: Optional[str]
    status: str
    report_count: int
    first_reported: Optional[datetime]
    last_reported: Optional[datetime]
    closed_at: Optional[datetime]
    location: Optional[GeoPoint]
    location_precision: str  # "approximate" | "ward_level" | "unknown"
    is_synthetic: bool


class PublicIssueListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[PublicIssue]


class PublicMapResponse(BaseModel):
    issues: list[PublicIssue]
    wards: list[MapWard]
