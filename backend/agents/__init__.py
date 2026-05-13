"""
SafeOps — Multi-Agent System
Two specialized agents orchestrated for industrial safety:
  - Field Operator (Robotics-ER 1.6): Visual perception & spatial reasoning
  - Auditor (Gemini 2.5 Pro): OSHA compliance & legal reporting
"""

from .field_operator import FieldOperator
from .auditor import Auditor
from .supervisor import Supervisor
from .orchestrator import Orchestrator

__all__ = ["FieldOperator", "Auditor", "Supervisor", "Orchestrator"]
