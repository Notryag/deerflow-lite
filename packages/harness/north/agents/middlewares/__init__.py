from .clarification import ClarificationMiddleware
from .loop_detection import LoopDetectionMiddleware
from .summarization import CompactionEvent, CompactionHook, NorthSummarizationMiddleware
from .title import TitleMiddleware, TitleMiddlewareState
from .tool_error import ToolErrorHandlingMiddleware


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
