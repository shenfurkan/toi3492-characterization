"""Canonical Stage-3 synthetic-calibration package.

Historical builders, protocols, and forensic evidence remain in their original
locations. Active execution code lives here and receives all revision-specific
state through an immutable RunSpec.
"""

from .contracts import RunSpec, TaskKey

__all__ = ["RunSpec", "TaskKey"]
