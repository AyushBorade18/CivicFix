from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel


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
    photo_checks: Optional[dict[str, Any]] = None


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


class MapIssuePoint(BaseModel):
    issue_id: int
    category: str
    status: str
    priority_score: Optional[float]
    location: GeoPoint
    location_precision: str


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


class MapResponse(BaseModel):
    issues: list[MapIssuePoint]
    matched_works: list[MapWorkPoint]
    sensitive_sites: list[MapSitePoint]
    wards: list[MapWard]


class ReportCreateRequest(BaseModel):
    raw_text: str
    ward_id: Optional[int] = None
    photo_url: Optional[str] = None


class PhotoUploadResponse(BaseModel):
    photo_url: str
    photo_checks: dict[str, Any]


class ReportCreateResponse(BaseModel):
    report: ReportInIssue
    issue_id: int
    joined_existing_issue: bool
    category: str
    category_confidence: float
    severity: str
    location_precision: str
    priority_score: Optional[float]
    priority_breakdown: Optional[dict[str, Any]]
    matched_work: Optional[MatchSummary]
    signals: list[SignalSummary]
    is_synthetic: bool
