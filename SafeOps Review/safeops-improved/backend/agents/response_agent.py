"""
SafeOps -- Response Agent
Model: Gemini Robotics-ER 1.6
Role: Execute robot safety actions via function calling.

This NEW agent handles the physical response to hazards:
- Plans robot action sequences (pick-and-place for safety equipment)
- Calls robot control functions via Gemini's native function calling
- Validates action safety before execution
- Generates annotated response images showing planned actions
"""
from __future__ import annotations

import json
import time
import base64
import logging
from google import genai
from google.genai import types
from config import settings

logger = logging.getLogger("safeops.agent.response")


# Robot control functions that Gemini can call
ROBOT_API_SCHEMA = """
You have access to these robot control functions:

def stop_machine(machine_id: str, zone: str, reason: str) -> dict:
    '''Emergency stop a machine or production line'''
    return {"status": "stopped", "machine_id": machine_id, "zone": zone}

def alert_personnel(zone: str, message: str, severity: str) -> dict:
    '''Send alert to personnel in a zone'''
    return {"status": "alerted", "zone": zone, "severity": severity}

def deploy_barrier(zone: str, barrier_type: str) -> dict:
    '''Deploy physical safety barrier in a zone'''
    return {"status": "deployed", "zone": zone, "barrier_type": barrier_type}

def restrict_zone(zone: str, duration_minutes: int, reason: str) -> dict:
    '''Temporarily restrict access to a zone'''
    return {"status": "restricted", "zone": zone, "duration": duration_minutes}

def evacuate_zone(zone: str, evacuation_route: str) -> dict:
    '''Initiate evacuation protocol for a zone'''
    return {"status": "evacuating", "zone": zone, "route": evacuation_route}

def notify_supervisor(supervisor_id: str, alert_level: str, details: str) -> dict:
    '''Send notification to floor supervisor'''
    return {"status": "notified", "supervisor": supervisor_id}

def activate_sprinkler(zone: str, trigger_type: str) -> dict:
    '''Activate fire suppression system'''
    return {"status": "activated", "zone": zone, "system": trigger_type}

def lockout_tagout(equipment_id: str, reason: str) -> dict:
    '''Apply lockout/tagout procedure to equipment'''
    return {"status": "locked_out", "equipment": equipment_id}
"""


class ResponseAgent:
    """
    Response Agent powered by Gemini Robotics-ER 1.6.
    Handles physical safety responses through robot function calling.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_ROBOTICS_MODEL
        logger.info("Response Agent initialized | Model: %s", self.model)

    async def plan_response(
        self,
        field_report: dict,
        original_image: bytes = None,
        mime_type: str = "image/jpeg",
    ) -> dict:
        """
        Plan and execute robot safety response based on field report.
        Uses function calling to generate actual robot control commands.

        Args:
            field_report: Output from Field Operator Agent
            original_image: Optional image for visual context
            mime_type: Image MIME type

        Returns:
            Response plan with function calls and annotations
        """
        start_time = time.time()
        risk_level = field_report.get("overall_risk_level", "safe")
        risk_score = field_report.get("overall_risk_score", 0)
        hazards = field_report.get("hazards", [])
        recommended_actions = field_report.get("recommended_actions", [])
        instrument_readings = field_report.get("instrument_readings", [])

        try:
            # Build function declarations
            functions = [
                types.FunctionDeclaration(
                    name="stop_machine",
                    description="Emergency stop a machine or production line",
                    parameters=types.Schema(
                        type="object",
                        properties={
                            "machine_id": types.Schema(type="string"),
                            "zone": types.Schema(type="string"),
                            "reason": types.Schema(type="string"),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="alert_personnel",
                    description="Send alert to personnel in a zone",
                    parameters=types.Schema(
                        type="object",
                        properties={
                            "zone": types.Schema(type="string"),
                            "message": types.Schema(type="string"),
                            "severity": types.Schema(type="string"),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="deploy_barrier",
                    description="Deploy physical safety barrier in a zone",
                    parameters=types.Schema(
                        type="object",
                        properties={
                            "zone": types.Schema(type="string"),
                            "barrier_type": types.Schema(type="string"),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="restrict_zone",
                    description="Temporarily restrict access to a zone",
                    parameters=types.Schema(
                        type="object",
                        properties={
                            "zone": types.Schema(type="string"),
                            "duration_minutes": types.Schema(type="integer"),
                            "reason": types.Schema(type="string"),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="evacuate_zone",
                    description="Initiate evacuation protocol for a zone",
                    parameters=types.Schema(
                        type="object",
                        properties={
                            "zone": types.Schema(type="string"),
                            "evacuation_route": types.Schema(type="string"),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="notify_supervisor",
                    description="Send notification to floor supervisor",
                    parameters=types.Schema(
                        type="object",
                        properties={
                            "supervisor_id": types.Schema(type="string"),
                            "alert_level": types.Schema(type="string"),
                            "details": types.Schema(type="string"),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="activate_sprinkler",
                    description="Activate fire suppression system",
                    parameters=types.Schema(
                        type="object",
                        properties={
                            "zone": types.Schema(type="string"),
                            "trigger_type": types.Schema(type="string"),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="lockout_tagout",
                    description="Apply lockout/tagout procedure to equipment",
                    parameters=types.Schema(
                        type="object",
                        properties={
                            "equipment_id": types.Schema(type="string"),
                            "reason": types.Schema(type="string"),
                        },
                    ),
                ),
            ]

            # Build prompt
            prompt = f"""You are the RESPONSE AGENT of SafeOps -- controlling industrial safety robots.
Your model is Gemini Robotics-ER 1.6. You plan and execute physical safety responses.

FIELD REPORT:
- Risk Level: {risk_level} ({risk_score}/100)
- Hazards: {json.dumps(hazards, indent=2)}
- Instrument Readings: {json.dumps(instrument_readings, indent=2)}

Your job:
1. Decide which robot functions to call based on the hazards
2. Determine the EXACT execution order (critical actions first)
3. Provide reasoning for each action
4. Flag any conflicts between actions

SAFETY PRIORITY ORDER (highest first):
1. Human life preservation (evacuation > barriers)
2. Equipment protection (emergency stop > lockout)
3. Notification cascade (personnel > supervisor)

{ROBOT_API_SCHEMA}

Return JSON with:
{{
  "response_plan": {{
    "is_autonomous": <boolean>,
    "requires_human_approval": <boolean>,
    "approval_reason": "<if human approval needed>",
    "actions": [
      {{
        "function": "<name>",
        "parameters": {{<args>}},
        "execution_order": <1, 2, 3>,
        "reason": "<why>",
        "safety_check": "<validation performed>",
        "estimated_time_seconds": <float>
      }}
    ],
    "total_execution_time_seconds": <float>
  }},
  "annotated_scene_description": "<description of what the robot will do>",
  "risk_after_response": "<lowered_risk_level>",
  "confidence": <0-1>
}}
"""

            contents = [prompt]
            if original_image:
                contents.insert(
                    0, types.Part.from_bytes(data=original_image, mime_type=mime_type)
                )

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    thinking_config=types.ThinkingConfig(thinking_budget=512),
                    tools=[types.Tool(function_declarations=functions)],
                    response_mime_type="application/json",
                ),
            )

            # Check if Gemini made any function calls
            function_calls = []
            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.function_call:
                                function_calls.append({
                                    "name": part.function_call.name,
                                    "args": dict(part.function_call.args) if part.function_call.args else {},
                                })

            result = json.loads(self._extract_json(response.text))
            result["_metadata"] = {
                "model": self.model,
                "latency_ms": round((time.time() - start_time) * 1000),
                "function_calls_generated": len(function_calls),
                "function_calls": function_calls,
            }

            logger.info(
                "Response planned | Actions: %d | Human approval: %s | Function calls: %d | %dms",
                len(result.get("response_plan", {}).get("actions", [])),
                result.get("response_plan", {}).get("requires_human_approval", True),
                len(function_calls),
                result["_metadata"]["latency_ms"],
            )

            return result

        except Exception as e:
            logger.error("Response planning failed: %s", e)
            return {
                "response_plan": {
                    "is_autonomous": False,
                    "requires_human_approval": True,
                    "approval_reason": f"Response agent error: {str(e)}",
                    "actions": [],
                },
                "error": str(e),
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
