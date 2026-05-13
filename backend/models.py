"""
SafeOps — Data Models
Pydantic models for the entire system: detections, risk assessments,
alerts, compliance reports, and governance decisions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HazardType(str, Enum):
    PPE_MISSING = "ppe_missing"
    ZONE_INTRUSION = "zone_intrusion"
    PROXIMITY_DANGER = "proximity_danger"
    SPILL_DETECTED = "spill_detected"
    POSTURE_UNSAFE = "posture_unsafe"
    COLLISION_RISK = "collision_risk"
    EXIT_BLOCKED = "exit_blocked"
    GAUGE_ANOMALY = "gauge_anomaly"
    EQUIPMENT_MISUSE = "equipment_misuse"
    FIRE_RISK = "fire_risk"


class ActionType(str, Enum):
    ALERT_OPERATOR = "alert_operator"
    NOTIFY_SUPERVISOR = "notify_supervisor"
    STOP_MACHINERY = "stop_machinery"
    RESTRICT_ZONE = "restrict_zone"
    DEPLOY_BARRIER = "deploy_barrier"
    GENERATE_REPORT = "generate_report"
    ESCALATE = "escalate"


class GovernanceDecision(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"


# ── Detection Models ───────────────────────────────────────────────────

class Point2D(BaseModel):
    """Normalized 2D point (0-1000) as returned by Gemini Robotics-ER."""
    y: int
    x: int


class BoundingBox(BaseModel):
    """Normalized bounding box (0-1000) as returned by Gemini Robotics-ER."""
    ymin: int
    xmin: int
    ymax: int
    xmax: int


class DetectedObject(BaseModel):
    """An object detected in the scene by Gemini Robotics-ER."""
    label: str
    point: Optional[Point2D] = None
    bounding_box: Optional[BoundingBox] = None
    confidence: Optional[float] = None


class TrajectoryPoint(BaseModel):
    """A point in a planned trajectory."""
    step: int
    point: Point2D
    label: str


# ── Hazard & Risk Models ──────────────────────────────────────────────

class Hazard(BaseModel):
    """A detected hazard in the scene."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: HazardType
    description: str
    risk_level: RiskLevel
    risk_score: int = Field(ge=0, le=100)
    location: Optional[Point2D] = None
    bounding_box: Optional[BoundingBox] = None
    related_objects: list[DetectedObject] = []
    reasoning: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProposedAction(BaseModel):
    """An action proposed by the AI in response to a hazard."""
    action_type: ActionType
    description: str
    target: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class GovernanceResult(BaseModel):
    """Result of the internal policy engine validating a proposed action."""
    decision: GovernanceDecision
    reason: str
    policy_rule: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Scene Analysis ────────────────────────────────────────────────────

class SceneAnalysis(BaseModel):
    """Complete analysis result for a single frame/image."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    overall_risk_level: RiskLevel
    overall_risk_score: int = Field(ge=0, le=100)
    scene_description: str
    detected_objects: list[DetectedObject] = []
    hazards: list[Hazard] = []
    proposed_actions: list[ProposedAction] = []
    governance_results: list[GovernanceResult] = []
    financial_impact: Optional[FinancialImpact] = None
    processing_time_ms: int = 0
    ai_reasoning: str = ""


class FinancialImpact(BaseModel):
    """Estimated financial impact of detected risks."""
    potential_fine: float = 0.0
    potential_injury_cost: float = 0.0
    potential_downtime_cost: float = 0.0
    total_risk_cost: float = 0.0
    cumulative_savings: float = 0.0


# Forward reference resolution
SceneAnalysis.model_rebuild()


# ── Gauge Reading ─────────────────────────────────────────────────────

class GaugeReading(BaseModel):
    """Reading from an analog gauge/meter detected in the scene."""
    gauge_type: str  # e.g., "pressure", "temperature", "fluid_level"
    value: float
    unit: str
    min_safe: Optional[float] = None
    max_safe: Optional[float] = None
    is_anomaly: bool = False
    location: Optional[Point2D] = None


# ── Digital Twin ──────────────────────────────────────────────────────

class DigitalTwinEntity(BaseModel):
    """An entity in the 2D digital twin representation."""
    id: str
    label: str
    entity_type: str  # "worker", "machine", "zone", "hazard", "ppe"
    position: Point2D
    bounding_box: Optional[BoundingBox] = None
    status: str = "normal"  # "normal", "warning", "danger"
    metadata: dict = {}


class DigitalTwinState(BaseModel):
    """Complete state of the 2D digital twin."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    entities: list[DigitalTwinEntity] = []
    zones: list[dict] = []  # danger zones, restricted areas
    overall_status: RiskLevel = RiskLevel.SAFE


# ── Compliance Report ─────────────────────────────────────────────────

class ComplianceReport(BaseModel):
    """Auto-generated compliance report (OSHA-ready)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    period_start: datetime
    period_end: datetime
    total_analyses: int = 0
    total_hazards_detected: int = 0
    total_actions_taken: int = 0
    hazards_by_type: dict[str, int] = {}
    risk_timeline: list[dict] = []
    financial_summary: FinancialImpact = FinancialImpact()
    recommendations: list[str] = []
    report_text: str = ""


# ── WebSocket Messages ────────────────────────────────────────────────

class WSMessage(BaseModel):
    """WebSocket message envelope."""
    type: str  # "analysis", "alert", "twin_update", "status"
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
