from __future__ import annotations

import json
import logging
import os
from hashlib import sha256
from typing import Any, Dict

import boto3

from common.models import TelemetryEvent, ValidationError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

SQS_QUEUE_URL = os.environ["TELEMETRY_QUEUE_URL"]
SQS_CLIENT = boto3.client("sqs")


def _parse_event(event: Dict[str, Any]) -> Dict[str, Any]:
    if event.get("isBase64Encoded"):
        raise ValidationError("Base64 encoded payloads are not supported")
    try:
        body = event.get("body") or "{}"
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValidationError("Body must be valid JSON") from exc


def lambda_handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    LOGGER.debug("Received event: %s", json.dumps(event))
    try:
        payload = _parse_event(event)
        telemetry_event = TelemetryEvent.from_payload(payload)
        message = telemetry_event.as_queue_message()

        deduplication_id = sha256(
            f"{telemetry_event.charger_id}:{telemetry_event.timestamp}".encode("utf-8")
        ).hexdigest()

        SQS_CLIENT.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message),
            MessageGroupId=telemetry_event.charger_id,
            MessageDeduplicationId=deduplication_id,
        )

        LOGGER.info(
            "Accepted telemetry event",
            extra={"chargerId": telemetry_event.charger_id, "timestamp": telemetry_event.timestamp},
        )
        response_body = {"status": "accepted", "chargerId": telemetry_event.charger_id}
        status_code = 202
    except ValidationError as error:
        LOGGER.warning("Validation error: %s", error, exc_info=False)
        response_body = {"status": "rejected", "reason": str(error), "details": error.errors}
        status_code = 400
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.exception("Unhandled error during ingestion")
        response_body = {"status": "error", "reason": "internal server error"}
        status_code = 500
        raise exc

    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response_body),
    }

