"""
SafeOps — Agent Orchestrator
Coordinates the hand-off between agents:
  Field Operator (Robotics-ER) → Auditor (Gemini Pro)

Maintains a pipeline log so the frontend can show
exactly which agent did what and when.
"""

from __future__ import annotations

import time
import logging
from datetime import datetime

from .field_operator import FieldOperator
from .auditor import Auditor

logger = logging.getLogger("safeops.orchestrator")


class Orchestrator:
    """
    The glue between agents. Routes data through the pipeline:
    Image → FieldOperator → (if hazards) → Auditor → Combined Result
    """

    def __init__(self):
        self.field_operator = FieldOperator()
        self.auditor = Auditor()
        self.pipeline_history: list[dict] = []
        logger.info("Orchestrator initialized — 2 agents ready")

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg", task: str = "general") -> dict:
        """
        Main entry point. Runs the full agent pipeline.
        
        Args:
            image_bytes: Raw image/video bytes
            mime_type: MIME type of the media
            task: "general" | "trajectory" | "gauge" | "robot_response"
        
        Returns:
            Combined result from all agents + pipeline_log
        """
        pipeline_log = []
        total_start = time.time()

        # ── Step 1: Field Operator ────────────────────────────────────
        step1_start = time.time()
        pipeline_log.append({
            "agent": "FIELD_OPERATOR",
            "model": self.field_operator.MODEL,
            "status": "running",
            "task": task,
            "started_at": datetime.utcnow().isoformat(),
        })

        if task == "trajectory":
            field_report = await self.field_operator.analyze_trajectory(image_bytes, mime_type)
        elif task == "gauge":
            field_report = await self.field_operator.read_gauge(image_bytes, mime_type)
        elif task == "robot_response":
            # First analyze, then plan response
            field_report = await self.field_operator.analyze_scene(image_bytes, mime_type)
            hazards = field_report.get("hazards", [])
            if hazards:
                robot_result = await self.field_operator.plan_robot_response(
                    hazard_data={"hazards": hazards},
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                )
                field_report["function_calls"] = robot_result.get("function_calls", [])
                field_report["robot_reasoning"] = robot_result.get("reasoning", "")
        else:
            field_report = await self.field_operator.analyze_scene(image_bytes, mime_type)

        step1_ms = int((time.time() - step1_start) * 1000)
        pipeline_log[-1]["status"] = "complete"
        pipeline_log[-1]["duration_ms"] = step1_ms
        pipeline_log[-1]["hazards_found"] = len(field_report.get("hazards", []))

        # ── Step 2: Auditor (only if hazards detected) ────────────────
        audit_result = None
        hazards = field_report.get("hazards", [])

        if hazards and len(hazards) > 0:
            step2_start = time.time()
            pipeline_log.append({
                "agent": "AUDITOR",
                "model": self.auditor.MODEL,
                "status": "running",
                "trigger": f"{len(hazards)} hazards from Field Operator",
                "started_at": datetime.utcnow().isoformat(),
            })

            # Prepare history for trend analysis
            recent_reports = [h.get("field_report", {}) for h in self.pipeline_history[-10:]]

            audit_result = await self.auditor.audit_incident(
                field_report=field_report,
                analysis_history=recent_reports,
            )

            step2_ms = int((time.time() - step2_start) * 1000)
            pipeline_log[-1]["status"] = "complete"
            pipeline_log[-1]["duration_ms"] = step2_ms
            pipeline_log[-1]["violations_found"] = len(audit_result.get("violations", []))
        else:
            pipeline_log.append({
                "agent": "AUDITOR",
                "model": self.auditor.MODEL,
                "status": "skipped",
                "reason": "No hazards detected by Field Operator",
            })

        # ── Combine Results ───────────────────────────────────────────
        total_ms = int((time.time() - total_start) * 1000)

        combined = {
            # Field Operator data
            **field_report,
            # Audit data (if available)
            "audit": audit_result,
            # Pipeline metadata
            "pipeline_log": pipeline_log,
            "total_processing_ms": total_ms,
            "agents_used": ["FIELD_OPERATOR"] + (["AUDITOR"] if audit_result else []),
        }

        # Store in history
        self.pipeline_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "task": task,
            "field_report": field_report,
            "audit": audit_result,
            "total_ms": total_ms,
        })
        if len(self.pipeline_history) > 500:
            self.pipeline_history = self.pipeline_history[-250:]

        logger.info(f"Pipeline complete — task={task}, agents={combined['agents_used']}, "
                     f"total={total_ms}ms")

        return combined

    async def generate_report(self) -> dict:
        """Generate compliance report from session history."""
        if not self.pipeline_history:
            return {"report": "No analysis data. Perform at least one analysis first."}

        # Collect all field reports
        field_reports = [h["field_report"] for h in self.pipeline_history[-20:]]

        report_text = await self.auditor.generate_full_report(field_reports)

        return {
            "report": report_text,
            "session_stats": self.get_stats(),
            "generated_at": datetime.utcnow().isoformat(),
            "generated_by": "AUDITOR",
        }

    def get_stats(self) -> dict:
        """Session statistics across all agents."""
        total = len(self.pipeline_history)
        total_hazards = sum(
            len(h.get("field_report", {}).get("hazards", []))
            for h in self.pipeline_history
        )
        total_violations = sum(
            len(h.get("audit", {}).get("violations", []))
            for h in self.pipeline_history
            if h.get("audit")
        )
        total_exposure = sum(
            h.get("audit", {}).get("financial_summary", {}).get("total_exposure", 0)
            for h in self.pipeline_history
            if h.get("audit")
        )

        return {
            "total_analyses": total,
            "total_hazards_detected": total_hazards,
            "total_osha_violations": total_violations,
            "cumulative_savings_usd": round(total_exposure, 2),
            "agents_active": ["FIELD_OPERATOR", "AUDITOR"],
        }
