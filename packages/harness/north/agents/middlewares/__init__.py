from .clarification import ClarificationMiddleware
from .loop_detection import LoopDetectionMiddleware
from .tool_error import ToolErrorHandlingMiddleware
from .summarization import CompactionEvent, CompactionHook, NorthSummarizationMiddleware
from .title import TitleMiddleware, TitleMiddlewareState


def get_default_middlewares():
    return [
        ToolErrorHandlingMiddleware(),
        LoopDetectionMiddleware(),
        ClarificationMiddleware(),
    ]


__all__ = [
    "ClarificationMiddleware",
    "LoopDetectionMiddleware",
    "ToolErrorHandlingMiddleware",
    "CompactionEvent",
    "CompactionHook",
    "NorthSummarizationMiddleware",
    "TitleMiddleware",
    "TitleMiddlewareState",
    "get_default_middlewares",
]
