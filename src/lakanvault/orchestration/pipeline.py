from lakanvault.contracts.dtos import SensitiveContext, StatusSummaryDTO
from lakanvault.infrastructure.config_loader import AppConfig
from lakanvault.shared.exceptions import NotImplementedStageError


class Pipeline:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._order = list(config.pipeline.order)

    @property
    def stage_order(self) -> list[str]:
        return list(self._order)

    def run(self, context: SensitiveContext) -> StatusSummaryDTO:
        raise NotImplementedStageError(
            f"Pipeline stages not implemented (order={self._order!r})"
        )
