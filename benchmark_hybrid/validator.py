"""Evidence validation for extracted observations."""

import re


def numeric_tokens(value):
    if isinstance(value, (int, float)):
        return {str(value), f"{value:g}"}
    return {str(value)}


def validate_observation(observation, evidence_text):
    errors = []
    if not observation.get("metric"):
        errors.append("metric missing")
    if observation.get("value") is None and observation.get("low") is None:
        errors.append("numeric value missing")
    if not observation.get("unit"):
        errors.append("unit missing")
    normalized = re.sub(r"\s+", " ", evidence_text or "")
    values = [observation.get("value"), observation.get("low"), observation.get("high")]
    for value in (x for x in values if x is not None):
        if not any(token in normalized for token in numeric_tokens(value)):
            errors.append(f"value {value} not found in evidence")
    return {"valid": not errors, "errors": errors}
