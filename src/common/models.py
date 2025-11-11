from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


class ValidationError(Exception):
    """Raised when telemetry payload validation fails."""

    def __init__(self, message: str, errors: Dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or {}


def _require_field(payload: Dict[str, Any], field_name: str) -> Any:
    if field_name not in payload:
        raise ValidationError("Missing required field", {field_name: "field is required"})
    value = payload[field_name]
    if value in (None, ""):
        raise ValidationError("Invalid field value", {field_name: "value cannot be empty"})
    return value


def _coerce_timestamp(timestamp_raw: Any) -> str:
    if not isinstance(timestamp_raw, str):
        raise ValidationError("Invalid timestamp type", {"timestamp": "must be ISO8601 string"})
    try:
        parsed = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValidationError(
            "Invalid timestamp format", {"timestamp": "must be ISO8601 format"}
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat()


@dataclass(slots=True, frozen=True)
class TelemetryEvent:
    charger_id: str
    timestamp: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ingested_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TelemetryEvent":
        if not isinstance(payload, dict):
            raise ValidationError("Payload must be a JSON object")

        charger_id = _require_field(payload, "chargerId")
        if not isinstance(charger_id, str):
            raise ValidationError("Invalid type", {"chargerId": "must be string"})

        timestamp_raw = _require_field(payload, "timestamp")
        timestamp = _coerce_timestamp(timestamp_raw)

        telemetry_payload = payload.get("payload", {})
        if telemetry_payload is None:
            telemetry_payload = {}
        if not isinstance(telemetry_payload, dict):
            raise ValidationError("Invalid payload section", {"payload": "must be an object"})

        return cls(charger_id=charger_id, timestamp=timestamp, payload=telemetry_payload)

    def as_queue_message(self) -> Dict[str, Any]:
        return {
            "chargerId": self.charger_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "ingestedAt": self.ingested_at,
        }

    def as_dynamodb_item(self) -> Dict[str, Any]:
        return {
            "charger_id": {"S": self.charger_id},
            "timestamp": {"S": self.timestamp},
            "payload": {"S": self.payload_json},
            "ingested_at": {"S": self.ingested_at},
        }

    @property
    def payload_json(self) -> str:
        import json

        return json.dumps(self.payload, separators=(",", ":"), sort_keys=True)

