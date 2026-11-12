# abstract ports only no concrete imports
# adapters implement these orchestration just calls them
"""Ports — abstract interfaces that adapters implement. No concrete imports here."""
from __future__ import annotations

from abc import ABC, abstractmethod

from lakanvault.contracts.events import PipelineEvent, StageResult


class PipelineStage(ABC):
    """Every pipeline stage implements this. Orchestration calls run()."""

    @property
    @abstractmethod
    # stage name for ordering / logging
    def name(self) -> str: ...

    @abstractmethod
    # run one stage against the event return a StageResult
    def run(self, event: PipelineEvent) -> StageResult: ...


class AuditWriter(ABC):
    @abstractmethod
    # persist the event somewhere local
    def write(self, event: PipelineEvent) -> None: ...


class CloudForwarder(ABC):
    @abstractmethod
    # try to send redacted telemetry returns whether it went
    def forward(self, event: PipelineEvent) -> bool: ...
