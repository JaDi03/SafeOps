"""
SafeOps — Field Operator Agent
Model: Gemini Robotics-ER 1.6
Role: ALL visual perception. Detection, spatial reasoning, trajectories,
      gauge reading, function calling. The beast runs unleashed.
"""

from __future__ import annotations

import json
import time
import base64
import logging
from pathlib import Path

from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger("safeops.agent.field_operator")

POLICY_PATH = Path(__file__).parent.parent / "safety_policy.json"


def _load_policy() -> str:
    """Load safety policy for prompt injection."""
    try:
        if POLICY_PATH.exists():
            with open(POLICY_PATH, "r") as f:
                return json.dumps(json.load(f), indent=2)
    except Exception as e:
        logger.error(f"Policy load error: {e}")
    return "{}"


# ── System Prompts ────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    policy = _load_policy()
    return f"""You are the FIELD OPERATOR AGENT of SafeOps — an industrial safety AI system.
Your model is Gemini Robotics-ER 1.6, specialized in spatial reasoning.

YOUR MISSION: Analyze every pixel. Detect every risk. Save lives.

PLANT SAFETY POLICY (YOUR GROUND TRUTH):
{policy}

You analyze images and video from industrial environments to detect hazards.
You MUST respond ONLY with valid JSON. No markdown fences, no extra text.

Return this exact structure:
{{
  "scene_description": "<brief description>",
  "overall_risk_score": <0-100>,
  "overall_risk_level": "<safe|low|medium|high|critical>",
  "detected_objects": [
    {{
      "label": "<object name>",
      "point": [<y>, <x>],
      "box_2d": [<ymin>, <xmin>, <ymax>, <xmax>],
      "category": "<worker|machine|ppe|zone|obstacle|gauge|vehicle>"
    }}
  ],
  "hazards": [
    {{
      "type": "<ppe_missing|zone_intrusion|proximity_danger|spill_detected|posture_unsafe|collision_risk|exit_blocked|gauge_anomaly|equipment_misuse|fire_risk>",
      "description": "<what is dangerous and why>",
      "risk_level": "<safe|low|medium|high|critical>",
      "risk_score": <0-100>,
      "location": [<y>, <x>],
      "related_objects": ["<label1>", "<label2>"],
      "reasoning": "<spatial reasoning: WHY this is dangerous>"
    }}
  ],
  "proposed_actions": [
    {{
      "action": "<alert_operator|notify_supervisor|stop_machinery|restrict_zone|deploy_barrier|generate_report|escalate>",
      "description": "<what should be done>",
      "target": "<specific machine/area/person>",
      "confidence": <0.0-1.0>
    }}
  ],
  "ai_reasoning": "<overall spatial reasoning about the scene safety>"
}}

RULES:
- Use spatial reasoning: distances, trajectories, proximities.
- Points are [y, x] normalized to 0-1000.
- Bounding boxes are [ymin, xmin, ymax, xmax] normalized to 0-1000.
- Compare gauge readings against the PLANT POLICY thresholds.
- Include ALL detected objects, even safe ones.
- Be specific about WHY something is dangerous."""


GAUGE_PROMPT = """Analyze the gauge/meter in this image with precision.

PLANT POLICY THRESHOLDS:
{policy}

Return JSON only:
{{
  "gauge_type": "<pressure|temperature|fluid_level|voltage|rpm|other>",
  "value": <numeric_reading>,
  "unit": "<psi|°C|°F|%|V|RPM|etc>",
  "min_safe": <from_policy_or_null>,
  "max_safe": <from_policy_or_null>,
  "is_anomaly": <true_if_outside_safe_range>,
  "severity": "<normal|warning|critical>",
  "reasoning": "<how you determined the reading and compared to policy>"
}}"""


TRAJECTORY_PROMPT = """Analyze movement trajectories of workers and vehicles.
Predict paths for the next 5 seconds. Identify collision points.

Return JSON only:
{{
  "entities": [
    {{
      "label": "<entity name>",
      "current_position": [<y>, <x>],
      "predicted_trajectory": [[<y>, <x>], ...],
      "velocity_direction": "<left|right|up|down|stationary>",
      "collision_risk": <true|false>,
      "collision_with": "<other entity or null>"
    }}
  ],
  "collision_zones": [
    {{
      "zone": [<ymin>, <xmin>, <ymax>, <xmax>],
      "involved_entities": ["<label1>", "<label2>"],
      "time_to_collision_seconds": <estimated_seconds>
    }}
  ],
  "overall_risk_score": <0-100>,
  "overall_risk_level": "<safe|low|medium|high|critical>",
  "ai_reasoning": "<spatial analysis of trajectories>"
}}"""


# ── Robot Function Declarations ───────────────────────────────────────

ROBOT_FUNCTIONS = [
    types.FunctionDeclaration(
        name="move_robot_to",
        description="Move the safety robot to specific coordinates",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate (0-1000)"},
                "y": {"type": "number", "description": "Y coordinate (0-1000)"},
                "speed": {"type": "string", "enum": ["normal", "fast", "emergency"]},
            },
            "required": ["x", "y", "speed"],
        },
    ),
    types.FunctionDeclaration(
        name="activate_barrier",
        description="Deploy a safety barrier at a zone",
        parameters={
            "type": "object",
            "properties": {
                "zone_id": {"type": "string"},
                "barrier_type": {"type": "string", "enum": ["physical", "light_curtain", "alarm"]},
            },
            "required": ["zone_id", "barrier_type"],
        },
    ),
    types.FunctionDeclaration(
        name="stop_machine",
        description="Emergency stop a machine",
        parameters={
            "type": "object",
            "properties": {
                "machine_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["machine_id", "reason"],
        },
    ),
    types.FunctionDeclaration(
        name="sound_alarm",
        description="Activate audible alarm in a zone",
        parameters={
            "type": "object",
            "properties": {
                "zone_id": {"type": "string"},
                "alarm_level": {"type": "string", "enum": ["warning", "danger", "evacuation"]},
            },
            "required": ["zone_id", "alarm_level"],
        },
    ),
    types.FunctionDeclaration(
        name="notify_personnel",
        description="Send notification to personnel",
        parameters={
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": ["supervisor", "safety_officer", "maintenance", "all"]},
                "message": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
            },
            "required": ["role", "message", "priority"],
        },
    ),
]


class FieldOperator:
    """
    The Field Operator Agent — Gemini Robotics-ER 1.6.
    Handles ALL visual perception and spatial reasoning.
    """

    AGENT_NAME = "FIELD_OPERATOR"
    MODEL = settings.GEMINI_ROBOTICS_MODEL

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info(f"FieldOperator agent initialized — model={self.MODEL}")

    async def analyze_scene(self, images: list[dict], task: str = "general") -> dict:
        """
        Analyze one or multiple images with spatial reasoning.
        Automatically disables code execution if video is present to avoid API conflicts.
        """
        start = time.time()
        try:
            content_parts = []
            has_video = False
            
            # 1. Filter and normalize parts
            for img in images:
                orig_mime = img.get("mime_type", "image/jpeg")
                valid_mime = None
                
                if "video" in orig_mime:
                    valid_mime = "video/mp4"
                    has_video = True
                elif "image" in orig_mime:
                    valid_mime = "image/jpeg"
                
                if valid_mime:
                    content_parts.append(types.Part.from_bytes(data=img["bytes"], mime_type=valid_mime))

            if not content_parts:
                return _error_result("No valid images/videos provided after filtering", 0, self.AGENT_NAME)

            # 2. Configure Tools (Safety guard for video + code_execution)
            tools = []
            if not has_video:
                tools.append(types.Tool(code_execution=types.ToolCodeExecution))
                logger.info(f"[{self.AGENT_NAME}] Code Execution ENABLED")
            else:
                logger.info(f"[{self.AGENT_NAME}] Code Execution DISABLED (Video mode)")

            # 3. Add system prompt
            prompt = _build_system_prompt()
            if len(content_parts) > 1:
                prompt += "\n\nMULTI-VIEW ANALYSIS: You are receiving multiple camera feeds. Fuse them into a single spatial understanding."
            
            content_parts.append(prompt)

            # 4. Generate content
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=content_parts,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    thinking_config=types.ThinkingConfig(thinking_budget=1024),
                    tools=tools,
                ),
            )

            # 5. Parse and return
            result = _parse_json(response.text)
            result["processing_time_ms"] = int((time.time() - start) * 1000)
            result["agent"] = self.AGENT_NAME
            logger.info(f"[{self.AGENT_NAME}] Scene analyzed ({len(content_parts)} views) — risk={result.get('overall_risk_score')}, time={result['processing_time_ms']}ms")
            return result
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Scene analysis failed: {e}")
            return _error_result(str(e), time.time() - start, self.AGENT_NAME)

    async def analyze_trajectory(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        """Predict movement trajectories and collision risks."""
        start = time.time()
        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    TRAJECTORY_PROMPT,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.5,
                    thinking_config=types.ThinkingConfig(thinking_budget=2048),
                ),
            )
            result = _parse_json(response.text)
            result["processing_time_ms"] = int((time.time() - start) * 1000)
            result["agent"] = self.AGENT_NAME
            return result
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Trajectory analysis failed: {e}")
            return {"entities": [], "collision_zones": [], "agent": self.AGENT_NAME}

    async def read_gauge(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        """Read analog gauge using code execution."""
        start = time.time()
        policy = _load_policy()
        prompt = GAUGE_PROMPT.format(policy=policy)
        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.5,
                    tools=[types.Tool(code_execution=types.ToolCodeExecution)],
                ),
            )
            result = _parse_json(response.text)
            result["processing_time_ms"] = int((time.time() - start) * 1000)
            result["agent"] = self.AGENT_NAME
            return result
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Gauge reading failed: {e}")
            return {"error": str(e), "agent": self.AGENT_NAME}

    async def plan_robot_response(self, hazard_data: dict, image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        """Plan robot response using function calling."""
        prompt = f"""You are controlling a safety robot in an industrial environment.
A hazard has been detected:
{json.dumps(hazard_data, indent=2, default=str)}

Analyze the image and plan the optimal response using available robot functions.
Consider: 1) Immediate safety 2) Alert personnel 3) Move robot 4) Safe perimeter.
Explain your reasoning before calling functions."""

        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    tools=[types.Tool(function_declarations=ROBOT_FUNCTIONS)],
                ),
            )
            result = {"reasoning": "", "function_calls": [], "agent": self.AGENT_NAME}
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        result["reasoning"] += part.text
                    if hasattr(part, "function_call") and part.function_call:
                        result["function_calls"].append({
                            "function": part.function_call.name,
                            "args": dict(part.function_call.args) if part.function_call.args else {},
                        })
            return result
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Robot response failed: {e}")
            return {"error": str(e), "reasoning": "", "function_calls": [], "agent": self.AGENT_NAME}


# ── Utilities ─────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict | list:
    """Parse JSON from Gemini response, handling markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        for sc, ec in [("{", "}"), ("[", "]")]:
            si = cleaned.find(sc)
            ei = cleaned.rfind(ec)
            if si != -1 and ei != -1 and ei > si:
                try:
                    return json.loads(cleaned[si:ei + 1])
                except json.JSONDecodeError:
                    continue
        logger.warning(f"Could not parse JSON: {cleaned[:200]}...")
        return {"raw_text": cleaned, "parse_error": True}


def _error_result(error: str, elapsed: float, agent: str) -> dict:
    return {
        "scene_description": "Analysis failed",
        "overall_risk_score": -1,
        "overall_risk_level": "unknown",
        "detected_objects": [],
        "hazards": [],
        "proposed_actions": [],
        "ai_reasoning": f"Error: {error}",
        "processing_time_ms": int(elapsed * 1000),
        "agent": agent,
    }
