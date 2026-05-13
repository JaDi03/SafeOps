"""
SafeOps -- Supervisor Agent
Model: Gemini 2.5 Pro
Role: Intelligent workflow orchestration, memory, decision-making.

This replaces the simple Python orchestrator with an AI-powered supervisor
that decides which agents to activate, maintains incident memory,
and prioritizes responses dynamically.

KEY FEATURES:
- Dynamic workflow routing based on risk assessment
- Persistent memory of recent incidents for pattern detection
- Priority escalation for recurring hazards
- Context window management for long operations
"""
from __future__ import annotations

import json
import time
import logging
from collections import deque
from google import genai
from google.genai import types
from config import settings

logger = logging.getLogger("safeops.agent.supervisor")


class SupervisorAgent:
    """
    AI Supervisor powered by Gemini 2.5 Pro.
    Makes intelligent decisions about agent activation and workflow routing.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_PRO_MODEL
        # Circular buffer for recent incident memory
        self.memory = deque(maxlen=settings.MAX_MEMORY_EVENTS)
        self.active_alarms = {}
        self.operation_count = 0
        logger.info("Supervisor Agent initialized | Model: %s", self.model)

    async def decide_workflow(
        self,
        field_report: dict,
        available_agents: list[str] = None,
    ) -> dict:
        """
        Decide the optimal workflow based on field report and historical context.

        Args:
            field_report: Output from Field Operator Agent
            available_agents: List of available agent names

        Returns:
            Workflow decision with agent activation plan
        """
        if available_agents is None:
            available_agents = ["field_operator", "response_agent", "auditor"]

        risk_level = field_report.get("overall_risk_level", "safe")
        risk_score = field_report.get("overall_risk_score", 0)
        hazards = field_report.get("hazards", [])
        instrument_readings = field_report.get("instrument_readings", [])

        # Build context from memory
        recent_incidents = list(self.memory)[-10:]  # Last 10 events
        hazard_types = [h.get("type") for h in hazards]

        # Check for recurring hazards (pattern detection)
        recurring = self._detect_recurring_patterns(hazard_types)

        prompt = f"""You are the SUPERVISOR AGENT of SafeOps -- an industrial safety AI orchestrator.
Your model is Gemini 2.5 Pro. You control which specialized agents activate and when.

CURRENT FIELD REPORT:
- Risk Level: {risk_level.upper()}
- Risk Score: {risk_score}/100
- Hazards Detected: {len(hazards)}
- Instrument Readings: {len(instrument_readings)}
- Hazard Types: {hazard_types}
- Recurring Patterns: {recurring}

AVAILABLE AGENTS:
- field_operator: Already ran (visual analysis complete)
- response_agent: Executes robot safety actions (stop, evacuate, deploy barriers)
- auditor: Legal/compliance analysis, OSHA citations, financial impact

HISTORICAL CONTEXT (last {len(recent_incidents)} operations):
{json.dumps(recent_incidents, indent=2)[:2000]}

ACTIVE ALARMS:
{json.dumps({k: v for k, v in self.active_alarms.items()}, indent=2)[:1000]}

DECISION RULES:
1. If risk_level is "critical" or risk_score >= 90: ACTIVATE ALL AGENTS IMMEDIATELY, skip normal ordering
2. If risk_level is "high" or risk_score >= 75: ACTIVATE response_agent + auditor in parallel
3. If instrument readings show critical values: PRIORITIZE response_agent for emergency shutdown
4. If recurring patterns detected: ESCALATE priority, notify auditor of repeat violations
5. If risk_level is "medium": Activate auditor only (response_agent on standby)
6. If risk_level is "safe" or "low": Minimal workflow, auditor optional
7. Always consider: human safety > equipment protection > compliance documentation

You MUST respond with ONLY valid JSON:
{{
  "workflow_id": "<unique id>",
  "decision_reasoning": "<why this workflow was chosen>",
  "priority": "<emergency|urgent|normal|low>",
  "agent_plan": [
    {{
      "agent": "<name>",
      "action": "<activate|skip|standby>",
      "reason": "<why>",
      "execution_order": <1, 2, 3>,
      "parallel": <true|false>
    }}
  ],
  "execution_mode": "<sequential|parallel|emergency>",
  "escalation": {{
    "is_escalated": <boolean>,
    "escalation_reason": "<reason or null>",
    "notify_humans": ["<roles>"]
  }},
  "special_instructions": "<any special context for agents>",
  "estimated_time_seconds": <float>
}}
"""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    thinking_config=types.ThinkingConfig(thinking_budget=512),
                    response_mime_type="application/json",
                ),
            )

            decision = json.loads(self._extract_json(response.text))

            # Store in memory
            self.memory.append({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "risk_level": risk_level,
                "risk_score": risk_score,
                "hazard_types": hazard_types,
                "decision": decision.get("priority"),
                "escalated": decision.get("escalation", {}).get("is_escalated", False),
            })

            self.operation_count += 1

            logger.info(
                "Supervisor decided | Priority: %s | Mode: %s | Agents: %s | Escalated: %s",
                decision.get("priority"),
                decision.get("execution_mode"),
                [a["agent"] for a in decision.get("agent_plan", []) if a["action"] == "activate"],
                decision.get("escalation", {}).get("is_escalated", False),
            )

            return decision

        except Exception as e:
            logger.error("Supervisor decision failed: %s", e)
            # Emergency fallback: activate all agents
            return self._emergency_fallback(risk_level, risk_score, str(e))

    def _detect_recurring_patterns(self, current_hazards: list[str]) -> dict:
        """Detect if current hazards have appeared recently."""
        if not current_hazards or len(self.memory) < 3:
            return {"is_recurring": False, "matches": []}

        recent_hazard_types = []
        for event in list(self.memory)[-10:]:
            if isinstance(event.get("hazard_types"), list):
                recent_hazard_types.extend(event["hazard_types"])

        matches = []
        for h in current_hazards:
            count = recent_hazard_types.count(h)
            if count >= 2:  # Appeared at least 2 times in recent history
                matches.append({"hazard": h, "recent_count": count})

        return {
            "is_recurring": len(matches) > 0,
            "matches": matches,
            "total_recent_incidents": len(self.memory),
        }

    def update_active_alarms(self, hazard_id: str, status: str, details: dict = None):
        """Track active alarms for the supervisor's context."""
        if status == "resolved":
            self.active_alarms.pop(hazard_id, None)
        else:
            self.active_alarms[hazard_id] = {
                "status": status,
                "details": details or {},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

    def get_memory_summary(self) -> dict:
        """Get a summary of recent operations for external reporting."""
        return {
            "total_operations": self.operation_count,
            "memory_size": len(self.memory),
            "active_alarms": len(self.active_alarms),
            "recent_events": list(self.memory)[-5:],
            "recurring_patterns": self._detect_recurring_patterns([]),
        }

    @staticmethod
    def _extract_json(text: str) -> str:
        """Remove markdown fences from response."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    @staticmethod
    def _emergency_fallback(risk_level: str, risk_score: int, error: str) -> dict:
        """Emergency fallback: activate all agents."""
        return {
            "workflow_id": f"emergency-{int(time.time())}",
            "decision_reasoning": f"Supervisor decision failed: {error}. Activating all agents as emergency fallback.",
            "priority": "emergency",
            "agent_plan": [
                {"agent": "response_agent", "action": "activate", "reason": "Emergency fallback", "execution_order": 1, "parallel": False},
                {"agent": "auditor", "action": "activate", "reason": "Emergency fallback", "execution_order": 2, "parallel": True},
            ],
            "execution_mode": "emergency",
            "escalation": {
                "is_escalated": True,
                "escalation_reason": "Supervisor failure + high risk detected",
                "notify_humans": ["supervisor", "safety_officer"],
            },
            "special_instructions": "EMERGENCY MODE: All agents activated. Immediate human notification required.",
            "estimated_time_seconds": 5.0,
            "_fallback": True,
        }
