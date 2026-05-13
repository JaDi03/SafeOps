"""
SafeOps -- Orchestrator v3.0
Role: Coordinate the multi-agent pipeline with AI-driven decision making.

Previously: Pure Python logic that simply passed data between agents.
Now: AI-powered supervisor decides workflow dynamically based on context.

Pipeline:
1. Supervisor decides which agents to activate and in what order
2. Field Operator analyzes the scene (vision + spatial reasoning)
3. Response Agent plans robot actions (function calling)
4. Auditor analyzes compliance and financial impact
5. VEEA Guard logs all prompts for security audit
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional
from config import settings
from agents.field_operator import FieldOperatorAgent
from agents.response_agent import ResponseAgent
from agents.auditor import AuditorAgent
from agents.supervisor import SupervisorAgent
from agents.veea_guard import veea_guard, VeeaGuard

logger = logging.getLogger("safeops.orchestrator")


class Orchestrator:
    """
    AI-driven orchestrator that coordinates the SafeOps multi-agent squad.
    The Supervisor Agent (Gemini 2.5 Pro) decides the workflow dynamically.
    """

    def __init__(self):
        self.field_operator = FieldOperatorAgent()
        self.response_agent = ResponseAgent()
        self.auditor = AuditorAgent()
        self.supervisor = SupervisorAgent()
        self.veea = veea_guard

        self.stats = {
            "total_operations": 0,
            "total_hazards": 0,
            "total_violations": 0,
            "avg_risk_score": 0.0,
            "last_operation": None,
        }
        logger.info("Orchestrator v3.0 initialized with AI Supervisor")

    async def run_pipeline(
        self,
        media_list: list[dict],
        operation_type: str = "standard",
    ) -> dict:
        """
        Run the complete multi-agent pipeline.

        Args:
            media_list: List of media items (images/video) with 'data' and 'mime_type'
            operation_type: 'standard', 'instrument', 'trajectory', or 'multiview'

        Returns:
            Complete operation result with all agent outputs
        """
        start_time = time.time()
        operation_id = f"op-{int(start_time)}-{self.stats['total_operations']}"
        logger.info("=" * 60)
        logger.info("PIPELINE START | ID: %s | Type: %s | Media: %d", operation_id, operation_type, len(media_list))

        # Step 1: VEEA Guard -- Security inspection of operation context
        if self.veea.enabled:
            guard_result = self.veea.inspect_prompt(
                agent="orchestrator",
                model="pipeline",
                prompt_text=f"Operation: {operation_type} with {len(media_list)} media items",
                context={"operation_id": operation_id},
            )
            if not guard_result["allowed"]:
                logger.error("PIPELINE BLOCKED by VEEA Guard: %s", guard_result["threats"])
                return {
                    "operation_id": operation_id,
                    "status": "blocked",
                    "reason": "Security policy violation",
                    "veea_guard": guard_result,
                }

        # Step 2: Field Operator -- Visual perception
        logger.info("[1/5] Field Operator analyzing scene...")
        if operation_type == "multiview" and len(media_list) > 1:
            field_report = await self.field_operator.analyze_multiview(media_list)
        elif operation_type == "instrument" and len(media_list) == 1:
            field_report = await self.field_operator.read_instrument(
                media_list[0]["data"],
                media_list[0].get("instrument_type", "gauge"),
                media_list[0].get("mime_type", "image/jpeg"),
            )
        elif operation_type == "trajectory" and len(media_list) == 1:
            field_report = await self.field_operator.predict_trajectory(
                media_list[0]["data"],
                media_list[0].get("mime_type", "video/mp4"),
            )
        else:
            # Standard: analyze first image, or multiview if multiple
            if len(media_list) == 1:
                field_report = await self.field_operator.analyze_scene(
                    media_list[0]["data"],
                    media_list[0].get("mime_type", "image/jpeg"),
                )
            else:
                field_report = await self.field_operator.analyze_multiview(media_list)

        # Step 3: Supervisor -- Decide workflow
        logger.info("[2/5] Supervisor deciding workflow...")
        workflow = await self.supervisor.decide_workflow(field_report)

        # Step 4: Response Agent -- Plan robot actions (if activated)
        response_plan = None
        if any(a["agent"] == "response_agent" and a["action"] == "activate"
               for a in workflow.get("agent_plan", [])):
            logger.info("[3/5] Response Agent planning robot actions...")
            original_image = media_list[0]["data"] if media_list else None
            mime = media_list[0].get("mime_type", "image/jpeg") if media_list else "image/jpeg"
            response_plan = await self.response_agent.plan_response(
                field_report,
                original_image,
                mime,
            )

        # Step 5: Auditor -- Compliance analysis (if activated)
        audit_report = None
        if any(a["agent"] == "auditor" and a["action"] == "activate"
               for a in workflow.get("agent_plan", [])):
            logger.info("[4/5] Auditor analyzing compliance...")
            audit_report = await self.auditor.audit(field_report)

        # Step 6: Update supervisor with active alarms
        if field_report.get("hazards"):
            for i, h in enumerate(field_report["hazards"]):
                self.supervisor.update_active_alarms(
                    f"hazard-{i}",
                    "active",
                    {"type": h.get("type"), "risk_level": h.get("risk_level")},
                )

        # Compile final result
        total_time = (time.time() - start_time) * 1000
        result = {
            "operation_id": operation_id,
            "status": "completed",
            "total_latency_ms": round(total_time),
            "workflow": workflow,
            "agents": {
                "field_operator": field_report,
                "response_agent": response_plan,
                "auditor": audit_report,
            },
            "veea_guard": self.veea.get_stats(),
            "supervisor_memory": self.supervisor.get_memory_summary(),
            "_metadata": {
                "version": "3.0",
                "models": {
                    "field_operator": settings.GEMINI_ROBOTICS_MODEL,
                    "response_agent": settings.GEMINI_ROBOTICS_MODEL,
                    "auditor": settings.GEMINI_PRO_MODEL,
                    "supervisor": settings.GEMINI_PRO_MODEL,
                },
                "features": {
                    "agentic_vision": settings.AGENTIC_VISION_ENABLED,
                    "multiview_fusion": settings.MULTIVIEW_FUSION_ENABLED,
                    "function_calling": True,
                    "veea_lobster_trap": self.veea.enabled,
                    "x402": settings.X402_ENABLED,
                },
            },
        }

        # Update stats
        self._update_stats(field_report)

        logger.info(
            "PIPELINE COMPLETE | %s | Risk: %s | Hazards: %d | Agents: %s | %dms",
            operation_id,
            field_report.get("overall_risk_level", "unknown"),
            len(field_report.get("hazards", [])),
            [a for a, v in result["agents"].items() if v is not None],
            total_time,
        )

        return result

    async def run_instrument_reading(self, image_data: bytes, instrument_type: str = "gauge", mime_type: str = "image/jpeg") -> dict:
        """Specialized pipeline for instrument reading only."""
        return await self.run_pipeline(
            [{"data": image_data, "mime_type": mime_type, "instrument_type": instrument_type}],
            operation_type="instrument",
        )

    async def run_trajectory_analysis(self, video_data: bytes, mime_type: str = "video/mp4") -> dict:
        """Specialized pipeline for trajectory prediction from video."""
        return await self.run_pipeline(
            [{"data": video_data, "mime_type": mime_type}],
            operation_type="trajectory",
        )

    async def run_multiview_analysis(self, media_list: list[dict]) -> dict:
        """Specialized pipeline for multi-camera fusion."""
        return await self.run_pipeline(media_list, operation_type="multiview")

    def _update_stats(self, field_report: dict):
        """Update operation statistics."""
        self.stats["total_operations"] += 1
        self.stats["total_hazards"] += len(field_report.get("hazards", []))
        self.stats["avg_risk_score"] = (
            (self.stats["avg_risk_score"] * (self.stats["total_operations"] - 1))
            + field_report.get("overall_risk_score", 0)
        ) / self.stats["total_operations"]
        self.stats["last_operation"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        return {
            **self.stats,
            "supervisor": self.supervisor.get_memory_summary(),
            "veea_security": self.veea.get_stats(),
        }

    def get_audit_trail(self) -> dict:
        """Get complete audit trail for compliance."""
        return {
            "veea_guard_events": self.veea.get_audit_trail(),
            "supervisor_memory": self.supervisor.get_memory_summary(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
