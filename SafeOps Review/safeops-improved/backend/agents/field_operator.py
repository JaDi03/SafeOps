"""
SafeOps -- Field Operator Agent
Model: Gemini Robotics-ER 1.6
Role: Visual perception, spatial reasoning, instrument reading,
      multi-view fusion, trajectory prediction, function calling.

KEY IMPROVEMENTS for Hackathon:
1. Agentic Vision with Code Execution (93% instrument reading accuracy)
2. Multi-View Spatial Fusion (4 cameras as one coherent scene)
3. Real Function Calling for robot actions
4. Thinking Config for deep spatial reasoning
5. Trajectory prediction with time-based analysis
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


# -- System Prompts -------------------------------------------------------

def _build_system_prompt() -> str:
    policy = _load_policy()
    return f"""You are the FIELD OPERATOR AGENT of SafeOps -- an industrial safety AI system.
Your model is Gemini Robotics-ER 1.6, specialized in spatial reasoning and embodied intelligence.
YOUR MISSION: Analyze every pixel. Detect every risk. Save lives.

You have access to CODE EXECUTION tools. Use them to:
- Zoom into gauges for precise reading (instrument reading at 93% accuracy)
- Crop regions of interest for better analysis
- Perform mathematical calculations on spatial coordinates
- Compute distances, velocities, and collision probabilities

PLANT SAFETY POLICY (YOUR GROUND TRUTH):
{policy}

You analyze images and video from industrial environments to detect hazards.
You MUST respond ONLY with valid JSON. No markdown fences, no extra text.

Return this exact structure:
{{
  "scene_description": "<brief description>",
  "overall_risk_score": <0-100>,
  "overall_risk_level": "<safe|low|medium|high|critical>",
  "instrument_readings": [
    {{
      "type": "<gauge|thermometer|sight_glass|digital_display>",
      "value": <numeric>,
      "unit": "<unit>",
      "is_critical": <boolean>,
      "confidence": <0-1>,
      "reading_method": "<agentic_vision|direct>"
    }}
  ],
  "detected_objects": [
    {{
      "label": "<object name>",
      "point": [<y>, <x>],
      "box_2d": [<ymin>, <xmin>, <ymax>, <xmax>],
      "confidence": <0-1>,
      "object_type": "<person|vehicle|equipment|hazard|ppe|instrument>",
      "attributes": {{}}
    }}
  ],
  "hazards": [
    {{
      "type": "<ppe_missing|zone_intrusion|proximity_danger|spill_detected|collision_risk|gauge_anomaly|equipment_misuse|fire_risk>",
      "description": "<what is wrong>",
      "risk_score": <0-100>,
      "risk_level": "<safe|low|medium|high|critical>",
      "affected_objects": ["<labels>"],
      "spatial_relation": "<relationship between objects>",
      "predicted_trajectory": {{
        "start_point": [<y>, <x>],
        "end_point": [<y>, <x>],
        "time_seconds": <estimated>,
        "collision_imminent": <boolean>
      }}
    }}
  ],
  "spatial_analysis": {{
    "distances": [{{"from": "<label>", "to": "<label>", "distance_units": <normalized 0-1000>}}],
    "zones_breached": ["<zone names>"],
    "evacuation_paths_clear": <boolean>,
    "congestion_level": "<low|medium|high>"
  }},
  "recommended_actions": [
    {{
      "action": "<alert_operator|stop_machinery|restrict_zone|deploy_barrier|evacuate|none>",
      "target": "<what/who>",
      "urgency": "<immediate|urgent|routine>",
      "robot_function_call": {{
        "function": "<function_name>",
        "parameters": {{}}
      }}
    }}
  ],
  "timestamp": "<ISO8601>"
}}"""


# -- Available robot functions for Gemini to call --------------------------

ROBOT_FUNCTIONS = {
    "stop_machine": {
        "description": "Emergency stop a machine or production line",
        "parameters": {"machine_id": "string", "zone": "string", "reason": "string"}
    },
    "alert_personnel": {
        "description": "Send alert to personnel in a zone",
        "parameters": {"zone": "string", "message": "string", "severity": "string"}
    },
    "deploy_barrier": {
        "description": "Deploy physical safety barrier in a zone",
        "parameters": {"zone": "string", "barrier_type": "string"}
    },
    "restrict_zone": {
        "description": "Temporarily restrict access to a zone",
        "parameters": {"zone": "string", "duration_minutes": "number", "reason": "string"}
    },
    "evacuate_zone": {
        "description": "Initiate evacuation protocol for a zone",
        "parameters": {"zone": "string", "evacuation_route": "string"}
    },
    "notify_supervisor": {
        "description": "Send notification to floor supervisor",
        "parameters": {"supervisor_id": "string", "alert_level": "string", "details": "string"}
    }
}


def _build_function_declarations() -> list[types.Tool]:
    """Build function declarations for Gemini function calling."""
    declarations = []
    for name, info in ROBOT_FUNCTIONS.items():
        # Build parameters schema
        properties = {}
        for param_name, param_type in info["parameters"].items():
            json_type = "string" if param_type == "string" else ("number" if param_type == "number" else "string")
            properties[param_name] = {"type": json_type}

        declarations.append(
            types.FunctionDeclaration(
                name=name,
                description=info["description"],
                parameters=types.Schema(
                    type="object",
                    properties=properties,
                ),
            )
        )
    return [types.Tool(function_declarations=declarations)]


class FieldOperatorAgent:
    """
    Field Operator powered by Gemini Robotics-ER 1.6.
    Handles: visual perception, spatial reasoning, instrument reading,
             multi-view fusion, trajectory prediction, function calling.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_ROBOTICS_MODEL
        self.system_prompt = _build_system_prompt()
        logger.info("Field Operator Agent initialized | Model: %s", self.model)

    # -- Core analysis with agentic vision --------------------------------

    async def analyze_scene(self, image_data: bytes, mime_type: str = "image/jpeg") -> dict:
        """
        Analyze a single image with full agentic vision capabilities.
        Uses code execution for instrument reading and spatial calculations.
        """
        start_time = time.time()

        try:
            image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)
            prompt = (
                self.system_prompt
                + "\n\nAnalyze this industrial scene. Use code execution to zoom into "
                "any gauges, meters, or instruments for precise reading. "
                "Calculate distances between workers and hazards mathematically. "
                "Predict any collision trajectories."
            )

            tools = []
            if settings.AGENTIC_VISION_ENABLED:
                tools.append(types.Tool(code_execution=types.ToolCodeExecution()))
                tools.extend(_build_function_declarations())

            response = self.client.models.generate_content(
                model=self.model,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    thinking_config=types.ThinkingConfig(thinking_budget=1024),
                    tools=tools if tools else None,
                    response_mime_type="application/json",
                ),
            )

            result = self._parse_response(response.text)
            result["_metadata"] = {
                "model": self.model,
                "agentic_vision": settings.AGENTIC_VISION_ENABLED,
                "function_calling": True,
                "latency_ms": round((time.time() - start_time) * 1000),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            logger.info(
                "Scene analyzed | Risk: %s (%d) | Objects: %d | Hazards: %d | Instruments: %d | %dms",
                result.get("overall_risk_level", "unknown"),
                result.get("overall_risk_score", 0),
                len(result.get("detected_objects", [])),
                len(result.get("hazards", [])),
                len(result.get("instrument_readings", [])),
                result["_metadata"]["latency_ms"],
            )
            return result

        except Exception as e:
            logger.error("Scene analysis failed: %s", e)
            return self._fallback_response(str(e))

    # -- Multi-view spatial fusion ----------------------------------------

    async def analyze_multiview(self, media_list: list[dict]) -> dict:
        """
        Analyze multiple camera views as a SINGLE COHERENT SCENE.
        ER 1.6 fuses images from multiple angles into unified 3D spatial reasoning.

        Args:
            media_list: List of dicts with 'data' (bytes) and 'mime_type' (str)
        Returns:
            Fused scene analysis with cross-view tracking and trajectory prediction.
        """
        if not settings.MULTIVIEW_FUSION_ENABLED or len(media_list) < 2:
            # Fallback: analyze first view only
            if media_list:
                return await self.analyze_scene(media_list[0]["data"], media_list[0]["mime_type"])
            return self._fallback_response("No media provided")

        start_time = time.time()

        try:
            # Build contents array with all images + fusion prompt
            contents = []
            for i, media in enumerate(media_list[:4]):  # Max 4 views
                contents.append(
                    types.Part.from_bytes(data=media["data"], mime_type=media["mime_type"])
                )

            multiview_prompt = f"""
{self.system_prompt}

You are analyzing {len(media_list)} synchronized camera views of the SAME industrial area.
Fuse these views into a SINGLE UNIFIED SCENE understanding.

CRITICAL: Track the SAME objects across different camera angles.
Use spatial reasoning to infer 3D positions from multiple 2D views.

For each person/equipment detected:
- Identify if it appears in multiple views (cross-view tracking)
- Calculate more accurate 3D position from triangulation
- Predict movement trajectory using multi-perspective data

If a hazard is visible in one view but not another, use occlusion reasoning
to determine if it's hidden or genuinely not present.

Predict potential collisions by analyzing trajectories across views:
- Worker in Camera 1 moving toward hazard zone visible in Camera 2
- Forklift path intersecting with pedestrian walkway

Return fused scene analysis with cross-view tracking IDs.
"""
            contents.append(multiview_prompt)

            tools = []
            if settings.AGENTIC_VISION_ENABLED:
                tools.append(types.Tool(code_execution=types.ToolCodeExecution()))
                tools.extend(_build_function_declarations())

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    thinking_config=types.ThinkingConfig(thinking_budget=2048),  # Higher for multi-view
                    tools=tools if tools else None,
                    response_mime_type="application/json",
                ),
            )

            result = self._parse_response(response.text)
            result["_metadata"] = {
                "model": self.model,
                "agentic_vision": settings.AGENTIC_VISION_ENABLED,
                "multiview_fusion": True,
                "num_views": len(media_list),
                "latency_ms": round((time.time() - start_time) * 1000),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            logger.info(
                "Multi-view fused | Views: %d | Risk: %s | %dms",
                len(media_list),
                result.get("overall_risk_level", "unknown"),
                result["_metadata"]["latency_ms"],
            )
            return result

        except Exception as e:
            logger.error("Multi-view analysis failed: %s", e)
            # Fallback to single view
            if media_list:
                return await self.analyze_scene(media_list[0]["data"], media_list[0]["mime_type"])
            return self._fallback_response(str(e))

    # -- Specialized instrument reading -----------------------------------

    async def read_instrument(self, image_data: bytes, instrument_type: str = "gauge", mime_type: str = "image/jpeg") -> dict:
        """
        Specialized instrument reading with maximum accuracy.
        Uses agentic vision with aggressive code execution for sub-tick precision.
        This is the killer feature validated by Boston Dynamics Spot.
        """
        start_time = time.time()

        try:
            image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)
            prompt = f"""
You are an expert industrial instrument reader. Analyze this {instrument_type} with maximum precision.

Use code execution to:
1. Zoom into the instrument image (crop to relevant region)
2. Detect the needle pointer, liquid level, or digital readout
3. Identify all tick marks, labels, and scale boundaries
4. Use mathematical interpolation to determine the exact value
5. Account for perspective distortion if present

For analog gauges:
- Identify the minimum and maximum scale values
- Count the number of divisions between major ticks
- Use linear interpolation: value = min + (needle_position / total_range) * (max - min)
- If multiple needles, identify which is the primary indicator

For sight glasses:
- Identify top and bottom of the glass window
- Locate the liquid level precisely
- Calculate percentage fill

Return ONLY a JSON object:
{{
  "instrument_type": "{instrument_type}",
  "value": <numeric reading>,
  "unit": "<detected unit from labels>",
  "min_scale": <number>,
  "max_scale": <number>,
  "confidence": <0.0 to 1.0>,
  "is_critical": <boolean, exceeds safe thresholds>,
  "reading_details": "<explanation of the calculation method>",
  "subtick_precision": <boolean, whether reading exceeds major tick resolution>
}}
"""

            response = self.client.models.generate_content(
                model=self.model,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temp for precision
                    thinking_config=types.ThinkingConfig(thinking_budget=2048),
                    tools=[types.Tool(code_execution=types.ToolCodeExecution())],
                    response_mime_type="application/json",
                ),
            )

            result = json.loads(self._extract_json(response.text))
            result["_metadata"] = {
                "model": self.model,
                "instrument_type": instrument_type,
                "latency_ms": round((time.time() - start_time) * 1000),
                "method": "agentic_vision_with_code_execution",
            }

            logger.info(
                "Instrument read | Type: %s | Value: %.2f %s | Confidence: %.2f | %dms",
                instrument_type,
                result.get("value", 0),
                result.get("unit", "?"),
                result.get("confidence", 0),
                result["_metadata"]["latency_ms"],
            )
            return result

        except Exception as e:
            logger.error("Instrument reading failed: %s", e)
            return {
                "instrument_type": instrument_type,
                "value": None,
                "confidence": 0,
                "error": str(e),
            }

    # -- Trajectory prediction (video input) ------------------------------

    async def predict_trajectory(self, video_data: bytes, mime_type: str = "video/mp4") -> dict:
        """
        Predict object trajectories from video input.
        ER 1.6 can track objects across frames and predict future positions.
        """
        start_time = time.time()

        try:
            video_part = types.Part.from_bytes(data=video_data, mime_type=mime_type)
            prompt = f"""
{self.system_prompt}

Analyze this video sequence for MOTION and TRAJECTORY PREDICTION.

For each moving object (workers, forklifts, vehicles):
1. Track its position across all frames
2. Calculate velocity and direction vectors
3. Extrapolate trajectory for the next 5-10 seconds
4. Identify if any trajectories will INTERSECT with hazard zones or other objects
5. Flag IMMINENT COLLISIONS (intersection within < 3 seconds)

Return JSON with:
{{
  "tracked_objects": [
    {{
      "label": "<name>",
      "track_id": "<unique id>",
      "current_position": [<y>, <x>],
      "velocity": {{"dy": <float>, "dx": <float>}},
      "predicted_path": [[<y>, <x>], ...],
      "collision_risk": "<none|low|medium|high|imminent>",
      "time_to_collision_seconds": <float or null>
    }}
  ],
  "collision_alerts": [{{"object_a": "<>", "object_b": "<>", "time_to_impact": <float>}}],
  "overall_risk_score": <0-100>,
  "overall_risk_level": "<safe|low|medium|high|critical>"
}}
"""

            response = self.client.models.generate_content(
                model=self.model,
                contents=[video_part, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    thinking_config=types.ThinkingConfig(thinking_budget=1024),
                    tools=[types.Tool(code_execution=types.ToolCodeExecution())],
                    response_mime_type="application/json",
                ),
            )

            result = self._parse_response(response.text)
            result["_metadata"] = {
                "model": self.model,
                "input_type": "video",
                "latency_ms": round((time.time() - start_time) * 1000),
            }
            return result

        except Exception as e:
            logger.error("Trajectory prediction failed: %s", e)
            return self._fallback_response(str(e))

    # -- Helpers -----------------------------------------------------------

    def _parse_response(self, text: str) -> dict:
        """Extract and validate JSON from Gemini response."""
        try:
            cleaned = self._extract_json(text)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("JSON parse failed, attempting fallback extraction from: %s...", text[:200])
            # Try to find any JSON-like structure
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            return self._fallback_response("JSON parse error", text[:500])

    @staticmethod
    def _extract_json(text: str) -> str:
        """Remove markdown fences and extract clean JSON."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    @staticmethod
    def _fallback_response(error: str, context: str = "") -> dict:
        return {
            "scene_description": f"Analysis failed: {error}",
            "overall_risk_score": 0,
            "overall_risk_level": "safe",
            "instrument_readings": [],
            "detected_objects": [],
            "hazards": [],
            "spatial_analysis": {},
            "recommended_actions": [],
            "_metadata": {"error": error, "context": context, "fallback": True},
        }
