from datetime import datetime, timezone

import pytest

from common.models import TelemetryEvent, ValidationError


def test_telemetry_event_from_payload_success():
    payload = {
        "chargerId": "charger-123",
        "timestamp": "2024-03-03T10:15:00Z",
        "payload": {"voltage": 230.5, "current": 16},
    }

    event = TelemetryEvent.from_payload(payload)

    assert event.charger_id == "charger-123"
    assert event.timestamp == "2024-03-03T10:15:00+00:00"
    assert event.payload == {"voltage": 230.5, "current": 16}
    assert datetime.fromisoformat(event.ingested_at).tzinfo == timezone.utc


@pytest.mark.parametrize(
    "payload, expected_error",
    [
        ({}, "field is required"),
        ({"chargerId": "abc"}, "field is required"),
        ({"chargerId": "abc", "timestamp": "not-a-date"}, "must be ISO8601 format"),
    ],
)
def test_telemetry_event_from_payload_validation_errors(payload, expected_error):
    with pytest.raises(ValidationError) as exc:
        TelemetryEvent.from_payload(payload)

    errors = getattr(exc.value, "errors", {}) or {}
    assert expected_error in str(exc.value) or any(
        expected_error in message for message in errors.values()
    )

