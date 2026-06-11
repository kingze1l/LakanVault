"""Event bus — the ONLY egress point toward cloud (ADR-001).
Never hand-rolls dicts; always goes through contracts.policies.redact_for_cloud().
"""
from __future__ import annotations

import logging

from lakanvault.contracts.events import PipelineEvent
from lakanvault.contracts.policies import redact_for_cloud

logger = logging.getLogger(__name__)


class EventBus:
    """
    Receives a completed pipeline event.
    If cloud is enabled, redacts and forwards.
    If cloud is disabled, logs and stops — nothing leaves the machine.
    """

    def __init__(self, cloud_enabled: bool = False, analytics_endpoint: str = ""):
        self._cloud_enabled = cloud_enabled
        self._analytics_endpoint = analytics_endpoint

    def publish(self, event: PipelineEvent, duration_ms: float = 0.0) -> bool:
        """Returns True if forwarded, False otherwise."""
        if not self._cloud_enabled:
            logger.info(
                "Cloud disabled — event %s not forwarded (fail-safe default)",
                event.run_id,
            )
            return False

        dto = redact_for_cloud(event, duration_ms)
        logger.info(
            "Forwarding redacted telemetry for run %s to %s",
            dto.run_id, self._analytics_endpoint,
        )
        # Real HTTP call would go here when cloud is wired up
        # import httpx; httpx.post(self._analytics_endpoint, json=dto.model_dump())
        return True
