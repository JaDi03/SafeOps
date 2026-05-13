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
from .supervisor import Supervisor

logger = logging.getLogger("safeops.orchestrator")


class Orchestrator:
    """
    The brain of SafeOps v3.0.
    Supervisor (Pro) -> Field Operator (ER 1.6) -> Auditor (Pro)
    """

    def __init__(self):
        self.field_operator = FieldOperator()
        self.auditor = Auditor()
        self.supervisor = Supervisor()
        self.pipeline_history: list[dict] = []
        logger.info("Orchestrator v3.0 initialized — 3 agents ready")

    async def analyze(self, image_data_list: list[dict], task: str = "general") -> dict:
        """
        Main entry point. Runs the full agent pipeline with Multi-View Fusion.
        
        Args:
            image_data_list: list of {"bytes": raw_bytes, "mime_type": "...", "slot_id": "..."}
            task: "general" | "trajectory" | "gauge" | "robot_response"
        """
        pipeline_log = []
        total_start = time.time()

        # ── Step 1: Supervisor (Strategic Orchestration) ──────────────
        step0_start = time.time()
        pipeline_log.append({
            "agent": "SUPERVISOR",
            "model": self.supervisor.MODEL,
            "status": "running",
            "task": "orchestration",
            "started_at": datetime.utcnow().isoformat(),
        })
        
        slots_meta = [{"id": img.get("slot_id"), "mime": img.get("mime_type")} for img in image_data_list]
        strat_plan = await self.supervisor.orchestrate(slots_meta)
        
        pipeline_log[-1]["status"] = "complete"
        pipeline_log[-1]["duration_ms"] = int((time.time() - step0_start) * 1000)

        # ── Step 2: Field Operator (Spatial Analysis) ─────────────────
        step1_start = time.time()
        pipeline_log.append({
            "agent": "FIELD_OPERATOR",
            "model": self.field_operator.MODEL,
            "status": "running",
            "task": task,
            "started_at": datetime.utcnow().isoformat(),
        })

        # Process as multi-view fusion
        field_report = await self.field_operator.analyze_scene(image_data_list, task=task)

        pipeline_log[-1]["status"] = "complete"
        pipeline_log[-1]["duration_ms"] = int((time.time() - step1_start) * 1000)
        pipeline_log[-1]["hazards_found"] = len(field_report.get("hazards", []))

        # ── Step 3: Auditor (Compliance) ──────────────────────────────
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

            audit_result = await self.auditor.audit_incident(
                field_report=field_report,
                analysis_history=[h.get("field_report", {}) for h in self.pipeline_history[-5:]]
            )

            pipeline_log[-1]["status"] = "complete"
            pipeline_log[-1]["duration_ms"] = int((time.time() - step2_start) * 1000)
        else:
            pipeline_log.append({
                "agent": "AUDITOR",
                "model": self.auditor.MODEL,
                "status": "skipped",
                "reason": "No hazards detected",
            })

        # ── Combine Results ───────────────────────────────────────────
        total_ms = int((time.time() - total_start) * 1000)
        combined = {
            **field_report,
            "audit": audit_result,
            "supervisor_plan": strat_plan,
            "pipeline_log": pipeline_log,
            "total_processing_ms": total_ms,
            "agents_used": ["SUPERVISOR", "FIELD_OPERATOR"] + (["AUDITOR"] if audit_result else []),
        }

        self.pipeline_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "field_report": field_report,
            "audit": audit_result,
            "total_ms": total_ms,
        })

        return combined

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
