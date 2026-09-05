"""Source-specific adapters producing canonical benchmark-bank documents."""

from .worldbank_ppi import PPIIngestionReport, WorldBankPPIAdapter
from .irena_tabular import IRENATabularAdapter, IRENATabularReport

__all__ = ["IRENATabularAdapter", "IRENATabularReport", "PPIIngestionReport", "WorldBankPPIAdapter"]
