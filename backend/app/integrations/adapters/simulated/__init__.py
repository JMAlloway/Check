"""Simulated core-banking adapters (Fiserv, Jack Henry).

These adapters run entirely on synthetic data - no credentials or network
access required - while faithfully exercising each vendor's wire-format
translation layer. See ``base.py`` for the design rationale.
"""

from app.integrations.adapters.simulated.fiserv import FiservAdapter
from app.integrations.adapters.simulated.jackhenry import JackHenryAdapter

__all__ = ["FiservAdapter", "JackHenryAdapter"]
