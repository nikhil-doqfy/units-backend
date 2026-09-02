# constants.py — backward-compatible re-export.
# New code should import directly from utilities.messages or utilities.choices.
# Existing code using `from utilities import constants` continues to work unchanged.

from utilities.messages import *  # noqa: F401, F403
from utilities.choices import *   # noqa: F401, F403
