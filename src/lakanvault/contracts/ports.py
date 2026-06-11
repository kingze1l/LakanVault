"""Ports — abstract interfaces that adapters implement. No concrete imports here."""
from __future__ import annotations

from abc import ABC, abstractmethod

from lakanvault.contracts.events import PipelineEvent, StageResult


class PipelineStage(ABC):
    """Every pipeline stage implements this. Orchestration calls run()."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, event: PipelineEvent) -> StageResult: ...


class AuditWriter(ABC):
    @abstractmethod
    def write(self, event: PipelineEvent) -> None: ...


class CloudForwarder(ABC):
    @abstractmethod
    def forward(self, event: PipelineEvent) -> bool: ...
