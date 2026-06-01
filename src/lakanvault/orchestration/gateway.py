from lakanvault.contracts.dtos import SensitiveContext, StatusSummaryDTO
from lakanvault.infrastructure.config_loader import AppConfig
from lakanvault.orchestration.pipeline import Pipeline


class Gateway:
    def __init__(self, config: AppConfig, pipeline: Pipeline | None = None) -> None:
        self._config = config
        self._pipeline = pipeline or Pipeline(config)

    def receive(self, action: str, context: dict) -> StatusSummaryDTO:
        request_id = str(context.get("request_id", ""))
        sensitive = SensitiveContext(
            request_id=request_id,
            model_path=context.get("model_path"),
            prompt_text=context.get("prompt_text"),
        )
        try:
            return self._pipeline.run(sensitive)
        except NotImplementedError:
            return StatusSummaryDTO(
                request_id=request_id,
                overall_status="not_implemented",
                stages_completed=[],
                message=f"action={action!r} pending implementation",
            )
