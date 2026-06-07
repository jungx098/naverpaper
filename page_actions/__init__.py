"""Page-interaction primitives for Naver campaign and Quick Reward flows."""

from page_actions.campaign import VISIT_HANDLERS
from page_actions.common import (
    QUICK_REWARD_LINK,
    Status,
    TextToChange,
    dump_page,
    process_error,
    run_handlers,
    run_quick_reward_handlers,
    safe_click,
)

__all__ = (
    "QUICK_REWARD_LINK",
    "Status",
    "TextToChange",
    "VISIT_HANDLERS",
    "dump_page",
    "process_error",
    "run_handlers",
    "run_quick_reward_handlers",
    "safe_click",
)
