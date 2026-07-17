from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional


def normalize_label(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def find_output_by_label(outputs: Iterable[Any], label: str) -> Optional[Mapping[str, Any]]:
    wanted = normalize_label(label)
    for output in outputs or []:
        if isinstance(output, Mapping) and normalize_label(output.get("label")) == wanted:
            return output
    return None


def list_output_labels(outputs: Iterable[Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for output in outputs or []:
        if not isinstance(output, Mapping):
            continue
        output_type = str(output.get("output_type") or "regular").strip().lower()
        if output_type != "regular":
            continue
        label = " ".join(str(output.get("label") or "").split())
        normalized = normalize_label(label)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(
            {
                "label": label,
                "index": output.get("index_id"),
                "gpio_pin": output.get("gpio_pin"),
                "active_low": bool(output.get("active_low", False)),
                "gpio_i2c_enabled": bool(output.get("gpio_i2c_enabled", False)),
                "output_type": output_type,
            }
        )
    return result


def hardware_value(status: bool, active_low: bool) -> bool:
    return not bool(status) if active_low else bool(status)
