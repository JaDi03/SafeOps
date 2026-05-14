"""
SafeOps — Supervisor Agent
Model: Gemini 2.5 Pro
Role: Central Brain. Orchestrates Field Operator and Auditor.
      Manages session memory and multi-view prioritization.
"""

from __future__ import annotations

import json
import time
import logging
from datetime import datetime

from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger("safeops.agent.supervisor")

SUPERVISOR_PROMPT = """You are the STRATEGIC SUPERVISOR of SafeOps — an industrial safety AI.
Your model is Gemini 2.5 Pro. You manage a squad of specialized agents:
1. FIELD OPERATOR (ER 1.6): Visual/Spatial expert.
2. AUDITOR (2.5 Pro): Legal/OSHA expert.

YOUR MISSION: Orchestrate the safest and most efficient response to industrial scenes.

You will receive metadata about multiple camera feeds and the current session state.
Your job is to decide the orchestration strategy.

SESSION MEMORY (Last events):
{memory}

PLANT CONTEXT:
Multiple camera slots are active. You must fuse their information.

You MUST respond ONLY with valid JSON:
{{
  "orchestration_plan": {{
    "priority_zones": ["<cam_id1>", "<cam_id2>"],
    "focus_areas": ["<ppe|machinery|spills|gauges>"],
    "reasoning": "<why this strategy was chosen>"
  }},
  "situational_awareness": {{
    "pattern_detected": "<any recurring risks detected from memory>",
    "overall_plant_risk": <0-100>,
    "critical_alert": <true|false>
  }},
  "instructions_for_field_operator": "<specific spatial fusion instructions>"
}}"""

class Supervisor:
    AGENT_NAME = "SUPERVISOR"
    MODEL = settings.GEMINI_PRO_MODEL

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.memory: list[dict] = []
        logger.info(f"Supervisor agent initialized — model={self.MODEL}")

    async def orchestrate(self, slots_metadata: list[dict]) -> dict:
        """Decide the analysis strategy based on available slots and memory."""
        start = time.time()
        
        # Prepare memory string
        mem_str = json.dumps(self.memory[-5:], indent=2) if self.memory else "No prior events."
        
        prompt = SUPERVISOR_PROMPT.format(memory=mem_str)
        user_content = f"CURRENT SLOTS STATUS:\n{json.dumps(slots_metadata, indent=2)}"

        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=[prompt, user_content],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                ),
            )
            
            result = self._parse_json(response.text)
            result["processing_time_ms"] = int((time.time() - start) * 1000)
            result["agent"] = self.AGENT_NAME
            
            # Store in memory
            self.memory.append({
                "timestamp": datetime.utcnow().isoformat(),
                "plan": result.get("orchestration_plan"),
                "risk": result.get("situational_awareness", {}).get("overall_plant_risk")
            })
            
            return result
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Orchestration failed: {e}")
            return {"error": str(e), "agent": self.AGENT_NAME}

    def _parse_json(self, text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join([l for l in cleaned.split("\n") if not l.strip().startswith("```")]).strip()
        try:
            return json.loads(cleaned)
        except:
            return {"parse_error": True, "raw": text}
