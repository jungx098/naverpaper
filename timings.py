"""Shared sleep and retry constants for browser automation."""

import random

ELEMENT_WAIT = 5
POLL_INTERVAL = 0.25
POPUP_SETTLE = 5
CONFIRM_SETTLE = 5
MISSION_HYDRATE = 1
MISSION_AFTER_CLICK = 2
CALL_TO_ACTION_WAIT = 3
MODAL_SETTLE = 1
QUICK_REWARD_LOAD = 3
MAX_VISIT_RETRIES = 3

DWELL_AFTER_NAV = (1.0, 3.0)
DWELL_AFTER_HANDLER = (6.0, 10.0)


def dwell_after_nav() -> float:
    return random.uniform(*DWELL_AFTER_NAV)


def dwell_after_handler() -> float:
    return random.uniform(*DWELL_AFTER_HANDLER)
