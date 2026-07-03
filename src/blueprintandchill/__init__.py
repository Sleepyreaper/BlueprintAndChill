"""BlueprintAndChill package root.

Azure Landing Zone + subscription-vending accelerator for Landmark,
built on Microsoft's Cloud Adoption Framework (CAF) and Azure Landing
Zones (ALZ) patterns.

This package is intentionally side-effect free at import time: no
network calls, no Azure SDK client construction, no environment
validation happens just by importing `blueprintandchill`. Settings
and models are plain, testable Python objects. Live Azure calls are
wired up in later tasks (clients, routers, CLI) and are clearly
marked with TODO comments where they are stubbed.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]