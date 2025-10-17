from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Tuple

from ..extensions import db
from ..models import Configuration

_DEFAULT_CONFIGURATION: dict[str, Any] = {
    "tmdb": {"apiKey": "", "language": "pt-BR", "region": "BR"},
    "importer": {"movieDelayMs": 250, "seriesDelayMs": 500, "maxParallelJobs": 2},
    "notifications": {"emailAlerts": True, "webhookUrl": None},
}


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_effective_config(configuration: Configuration | None) -> dict[str, Any]:
    if not configuration or not configuration.data:
        return deepcopy(_DEFAULT_CONFIGURATION)
    return _deep_merge(_DEFAULT_CONFIGURATION, configuration.data)


def get_config(tenant_id: str) -> dict[str, Any]:
    configuration = Configuration.query.filter_by(tenant_id=tenant_id).first()
    return get_effective_config(configuration)


def save_config(tenant_id: str, payload: dict[str, Any]) -> Tuple[dict[str, Any], bool]:
    if not isinstance(payload, dict):
        raise ValueError("Payload de configuração inválido")

    configuration = Configuration.query.filter_by(tenant_id=tenant_id).first()
    previous_effective = get_effective_config(configuration)

    merged = _deep_merge(_DEFAULT_CONFIGURATION, payload)
    requires_restart = (
        previous_effective.get("importer", {}).get("maxParallelJobs")
        != merged.get("importer", {}).get("maxParallelJobs")
    )

    if configuration is None:
        configuration = Configuration(tenant_id=tenant_id, data=merged, updated_at=datetime.utcnow())
        db.session.add(configuration)
    else:
        configuration.data = merged
        configuration.updated_at = datetime.utcnow()

    db.session.commit()
    return merged, requires_restart
