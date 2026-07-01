from __future__ import annotations

import json
from pathlib import Path

from blueprintandchill.models.subscription_request import SubscriptionRequestRecord


class RequestStore:
    """Simple file-backed store for local demo requests.

    This is intentionally minimal and safe for the scaffold.
    TODO: Replace with durable persistence for production deployment.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[SubscriptionRequestRecord]:
        records: list[SubscriptionRequestRecord] = []
        for file_path in sorted(self._data_dir.glob("*.json")):
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            records.append(SubscriptionRequestRecord.model_validate(payload))
        return records

    def save(self, record: SubscriptionRequestRecord) -> None:
        file_path = self._data_dir / f"{record.request_id}.json"
        file_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
