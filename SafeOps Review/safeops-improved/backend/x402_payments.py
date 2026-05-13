"""
SafeOps -- X402 Machine-to-Machine Payment Module (Optional)
Role: Autonomous safety-economics for robot-to-robot payments.

This module is OPTIONAL and demonstrates the future vision where autonomous
safety robots operate as economic entities. It uses the x402 protocol for:
1. Robot-to-robot payment for inspection services
2. Priority alert micropayments
3. Compliance report access payments

Usage: Enable via X402_ENABLED=true in .env
This is NOT part of the core safety pipeline -- it's a value-add for demos.
"""
from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass
from typing import Optional
from config import settings

logger = logging.getLogger("safeops.x402")


@dataclass
class X402Payment:
    """An X402 payment request."""
    amount: float
    currency: str = "USDC"
    network: str = "base"
    recipient: str = ""
    description: str = ""
    resource_url: str = ""


class X402PaymentHandler:
    """
    X402 payment handler for SafeOps.
    Demonstrates machine-to-machine payments for safety services.
    """

    def __init__(self):
        self.enabled = settings.X402_ENABLED
        self.wallet_address = settings.X402_WALLET_ADDRESS
        self.network = settings.X402_NETWORK
        self.total_payments = 0
        self.total_volume = 0.0
        logger.info(
            "X402 Handler | Enabled: %s | Network: %s",
            self.enabled, self.network,
        )

    async def charge_inspection_service(
        self,
        inspector_id: str,
        zone: str,
        severity: str,
    ) -> dict:
        """
        Charge for a cross-robot inspection service.
        Example: Spot robot A pays Spot robot B to verify a hazard zone.
        """
        if not self.enabled:
            return {"enabled": False, "message": "X402 payments disabled"}

        # Pricing tier based on severity
        pricing = {
            "low": 0.01,
            "medium": 0.05,
            "high": 0.10,
            "critical": 0.25,
        }
        amount = pricing.get(severity, 0.01)

        payment = X402Payment(
            amount=amount,
            network=self.network,
            recipient=self.wallet_address,
            description=f"Inspection service: {inspector_id} -> Zone {zone} ({severity})",
            resource_url=f"safeops://inspection/{zone}",
        )

        self.total_payments += 1
        self.total_volume += amount

        logger.info(
            "X402 | Inspection charge | $%.2f | %s -> Zone %s | Total: %d payments",
            amount, inspector_id, zone, self.total_payments,
        )

        return {
            "enabled": True,
            "type": "inspection_service",
            "payment": payment.__dict__,
            "status": "authorized",
            "settlement": "pending",
            "note": "Demo mode -- actual settlement requires x402 facilitator",
        }

    async def charge_priority_alert(
        self,
        alert_level: str,
        zone: str,
    ) -> dict:
        """
        Charge for priority alert escalation.
        Higher severity = higher priority = higher fee.
        """
        if not self.enabled:
            return {"enabled": False}

        pricing = {"low": 0.001, "medium": 0.005, "high": 0.01, "critical": 0.05}
        amount = pricing.get(alert_level, 0.001)

        self.total_payments += 1
        self.total_volume += amount

        return {
            "enabled": True,
            "type": "priority_alert",
            "amount": amount,
            "currency": "USDC",
            "network": self.network,
            "status": "authorized",
        }

    async def charge_compliance_report_access(
        self,
        report_id: str,
        requester: str,
    ) -> dict:
        """
        Charge for access to compliance audit reports.
        External auditors or regulators pay per-report access.
        """
        if not self.enabled:
            return {"enabled": False}

        amount = 0.50  # Fixed price per report

        self.total_payments += 1
        self.total_volume += amount

        return {
            "enabled": True,
            "type": "report_access",
            "report_id": report_id,
            "amount": amount,
            "requester": requester,
            "status": "authorized",
        }

    def get_stats(self) -> dict:
        """Get payment statistics."""
        return {
            "enabled": self.enabled,
            "network": self.network,
            "total_payments": self.total_payments,
            "total_volume_usd": round(self.total_volume, 4),
            "wallet_address": self.wallet_address[:10] + "..." if self.wallet_address else "not configured",
            "supported_networks": ["base", "solana", "polygon", "ethereum"],
            "note": "X402 optional demo feature -- not part of core safety pipeline",
        }


# Singleton
x402_handler = X402PaymentHandler()
