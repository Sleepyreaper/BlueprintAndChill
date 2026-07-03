"""Subscription-vending workflow package for BlueprintAndChill.

Houses the discrete, independently-testable slices of the
subscription-vending automation: service principal creation, billing
role assignment, and subscription alias provisioning. Each slice is a
dedicated module with its own typed request/result contracts so the
orchestrator (not yet implemented) can compose them without tight
coupling.
"""

from __future__ import annotations

__all__: list[str] = []