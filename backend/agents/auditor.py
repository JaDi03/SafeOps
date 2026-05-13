"""
SafeOps — Auditor Agent
Model: Gemini 2.5 Pro
Role: OSHA compliance analysis, legal reporting, financial impact,
      and trend detection. Activated ONLY when the Field Operator
      sends a report with detected hazards.
"""

from __future__ import annotations

import json
import time
import logging
from pathlib import Path

from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger("safeops.agent.auditor")

OSHA_KB_PATH = Path(__file__).parent.parent / "osha_knowledge_base.md"


def _load_osha_kb() -> str:
    """Load OSHA knowledge base for context injection."""
    try:
        if OSHA_KB_PATH.exists():
            return OSHA_KB_PATH.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"OSHA KB load error: {e}")
    return "No OSHA knowledge base available."


AUDIT_SYSTEM_PROMPT = """You are the AUDITOR AGENT of SafeOps — a legal compliance AI.
Your model is Gemini 2.5 Pro, specialized in regulatory analysis.

YOUR MISSION: Determine the EXACT OSHA violation, calculate the real financial 
impact, and generate audit-grade documentation.

You will receive a Field Report from the Field Operator Agent containing detected
hazards, risk scores, and spatial analysis. Your job is to:

1. Cross-reference each hazard against the OSHA regulations provided below.
2. Cite the SPECIFIC regulation number (e.g., 29 CFR 1910.132(a)).
3. Calculate the potential fine based on OSHA's penalty structure.
4. Provide a clear, actionable recommendation.
5. Assess if this is a recurring pattern.

OSHA REGULATIONS KNOWLEDGE BASE:
{osha_kb}

You MUST respond ONLY with valid JSON:
{{
  "audit_id": "<short unique id>",
  "timestamp": "<ISO timestamp>",
  "severity": "<low|medium|high|critical>",
  "violations": [
    {{
      "hazard_type": "<from field report>",
      "osha_standard": "<29 CFR XXXX.XXX>",
      "standard_title": "<official name of the standard>",
      "violation_class": "<other|serious|willful|repeat>",
      "description": "<specific violation description citing the regulation>",
      "estimated_fine_usd": <number>,
      "recommendation": "<specific corrective action>"
    }}
  ],
  "financial_summary": {{
    "total_potential_fines": <sum of all fines>,
    "potential_injury_liability": <estimated based on severity>,
    "potential_downtime_cost": <estimated>,
    "total_exposure": <grand total>
  }},
  "executive_summary": "<2-3 sentence summary for plant management>",
  "trend_analysis": "<any patterns observed or 'No recurring patterns detected'>",
  "auditor_reasoning": "<detailed legal reasoning>"
}}"""


class Auditor:
    """
    The Auditor Agent — Gemini 2.5 Pro.
    Performs OSHA compliance analysis on Field Operator reports.
    Only activated when hazards are detected.
    """

    AGENT_NAME = "AUDITOR"
    MODEL = settings.GEMINI_PRO_MODEL

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.osha_kb = _load_osha_kb()
        self.audit_history: list[dict] = []
        logger.info(f"Auditor agent initialized — model={self.MODEL}, "
                     f"OSHA KB loaded={len(self.osha_kb)} chars")

    async def audit_incident(self, field_report: dict, analysis_history: list = None) -> dict:
        """
        Receive a Field Operator report and produce an OSHA audit.
        This is the core hand-off from Agent 1 → Agent 2.
        """
        start = time.time()

        # Build context with history for trend detection
        history_context = ""
        if analysis_history and len(analysis_history) > 1:
            recent = analysis_history[-10:]
            history_context = f"\n\nRECENT INCIDENT HISTORY (for trend analysis):\n{json.dumps([{'risk_score': a.get('overall_risk_score'), 'hazards': [h.get('type') for h in a.get('hazards', [])]} for a in recent], indent=2)}"

        prompt = AUDIT_SYSTEM_PROMPT.format(osha_kb=self.osha_kb)

        user_content = f"""FIELD OPERATOR REPORT (from Gemini Robotics-ER 1.6):
{json.dumps(field_report, indent=2, default=str)}
{history_context}

Perform your OSHA compliance audit now."""

        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=[prompt, user_content],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    thinking_config=types.ThinkingConfig(thinking_budget=1024),
                ),
            )

            result = self._parse_json(response.text)
            result["processing_time_ms"] = int((time.time() - start) * 1000)
            result["agent"] = self.AGENT_NAME

            # Track audit history
            self.audit_history.append(result)
            if len(self.audit_history) > 100:
                self.audit_history = self.audit_history[-50:]

            logger.info(f"[{self.AGENT_NAME}] Audit complete — "
                        f"violations={len(result.get('violations', []))}, "
                        f"exposure=${result.get('financial_summary', {}).get('total_exposure', 0):,.0f}, "
                        f"time={result['processing_time_ms']}ms")
            return result

        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Audit failed: {e}")
            return {
                "audit_id": "error",
                "severity": "unknown",
                "violations": [],
                "financial_summary": {},
                "executive_summary": f"Audit failed: {e}",
                "auditor_reasoning": str(e),
                "agent": self.AGENT_NAME,
                "processing_time_ms": int((time.time() - start) * 1000),
            }

    async def generate_full_report(self, all_field_reports: list[dict]) -> str:
        """Generate a comprehensive compliance report from all session data."""
        prompt = f"""You are a senior industrial safety compliance officer.
Based on the following safety analysis data from a multi-agent monitoring session,
generate a comprehensive OSHA-ready compliance report.

OSHA KNOWLEDGE BASE:
{self.osha_kb}

SESSION DATA:
{json.dumps(all_field_reports, indent=2, default=str)}

Generate a professional report including:
1. Executive Summary
2. Incidents Detected (with OSHA references)
3. Actions Taken by the AI Safety System
4. Financial Exposure Analysis
5. Trend Analysis
6. Recommendations for Improvement
7. Compliance Status Assessment

Format in clear, professional English. This report may be submitted to regulators."""

        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=[prompt],
                config=types.GenerateContentConfig(temperature=0.2),
            )
            return response.text
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Report generation failed: {e}")
            return f"Error generating compliance report: {e}"

    def _parse_json(self, text: str) -> dict:
        """Parse JSON from response."""
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
            return {"raw_text": cleaned, "parse_error": True}
