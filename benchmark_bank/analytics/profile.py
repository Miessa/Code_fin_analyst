"""Build a generic analyzed-project profile from Phase 1 validated metrics."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .comparability import ProjectProfile


COUNTRY_LOOKUP = {
    "cameroon": ("CMR", "Sub-Saharan Africa"),
    "cameroun": ("CMR", "Sub-Saharan Africa"),
    "uganda": ("UGA", "Sub-Saharan Africa"),
    "kenya": ("KEN", "Sub-Saharan Africa"),
    "tanzania": ("TZA", "Sub-Saharan Africa"),
    "rwanda": ("RWA", "Sub-Saharan Africa"),
    "gabon": ("GAB", "Sub-Saharan Africa"),
    "congo": ("COG", "Sub-Saharan Africa"),
    "democratic republic of congo": ("COD", "Sub-Saharan Africa"),
    "cote d'ivoire": ("CIV", "Sub-Saharan Africa"),
    "ivory coast": ("CIV", "Sub-Saharan Africa"),
    "senegal": ("SEN", "Sub-Saharan Africa"),
    "ghana": ("GHA", "Sub-Saharan Africa"),
    "nigeria": ("NGA", "Sub-Saharan Africa"),
    "ethiopia": ("ETH", "Sub-Saharan Africa"),
    "zambia": ("ZMB", "Sub-Saharan Africa"),
    "mozambique": ("MOZ", "Sub-Saharan Africa"),
    "south africa": ("ZAF", "Sub-Saharan Africa"),
}


@dataclass(frozen=True)
class ProfileBuildResult:
    project_name: str
    profile: ProjectProfile
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "project_name": self.project_name,
            "profile": asdict(self.profile),
            "warnings": list(self.warnings),
        }


def _number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"[-+]?\d[\d\s\u00a0\u202f]*(?:[.,]\d+)?", value)
    if not match:
        return None
    token = re.sub(r"[\s\u00a0\u202f]", "", match.group()).replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def _metric(registry, key):
    item = next((row for row in registry if row.get("cle") == key), None)
    if not item:
        return None, None
    return _number(item.get("valeur")), str(item.get("unite") or "").casefold()


def _ratio(value, unit):
    if value is None:
        return None
    return value / 100 if "%" in unit or value > 1 else value


def build_project_profile(registry, context=None) -> ProfileBuildResult:
    context = context or {}
    warnings = []
    technology = str(context.get("technology") or "").strip().lower()
    if not technology:
        raise ValueError("phase2 context must define technology")
    geography = str(context.get("geography") or "").strip()
    country_iso3 = context.get("country_iso3")
    region = context.get("region")
    if geography and (not country_iso3 or not region):
        resolved = COUNTRY_LOOKUP.get(geography.casefold())
        if resolved:
            country_iso3 = country_iso3 or resolved[0]
            region = region or resolved[1]
        else:
            warnings.append(
                f"geography '{geography}' was not mapped; set country_iso3 and region in context"
            )

    capacity, capacity_unit = _metric(registry, "puissance")
    if capacity is not None and capacity_unit and "kw" in capacity_unit and "mw" not in capacity_unit:
        capacity /= 1000
    elif capacity is not None and capacity_unit and "gw" in capacity_unit:
        capacity *= 1000
    elif capacity is not None and capacity_unit and "mw" not in capacity_unit:
        warnings.append(f"capacity unit '{capacity_unit}' assumed to be MW")
    contract_period, _ = _metric(registry, "duree_concession")
    gearing, gearing_unit = _metric(registry, "gearing")
    financial_close_year = context.get("financial_close_year")
    if financial_close_year is None and context.get("data_year"):
        financial_close_year = int(context["data_year"])
        warnings.append("data_year used as financial-close proxy; analyst confirmation recommended")
    profile = ProjectProfile(
        technology=technology,
        hydropower_configuration=(
            str(context.get("hydropower_configuration") or "conventional")
            if technology == "hydropower" else None
        ),
        region=region, country_iso3=country_iso3,
        capacity_mw=capacity, financial_close_year=financial_close_year,
        contract_period_years=contract_period, debt_share=_ratio(gearing, gearing_unit),
    )
    return ProfileBuildResult(
        project_name=str(context.get("project_name") or "Projet analysé"),
        profile=profile, warnings=warnings,
    )


def load_project_profile(registry_path, context_path=None):
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8-sig"))
    context = {}
    if context_path and Path(context_path).exists():
        context = json.loads(Path(context_path).read_text(encoding="utf-8-sig"))
    return build_project_profile(registry, context)
