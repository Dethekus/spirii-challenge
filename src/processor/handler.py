from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

from common.models import TelemetryEvent, ValidationError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

DYNAMO_TABLE = os.environ["TELEMETRY_TABLE_NAME"]
DDB_CLIENT = boto3.client("dynamodb")


def _upsert_latest(event: TelemetryEvent) -> None:
    try:
        DDB_CLIENT.put_item(
            TableName=DYNAMO_TABLE,
            Item={
                "charger_id": {"S": event.charger_id},
                "timestamp": {"S": event.timestamp},
                "payload": {"S": event.payload_json},
                "ingested_at": {"S": event.ingested_at},
            },
            ConditionExpression="attribute_not_exists(#ts) OR #ts < :ts",
            ExpressionAttributeNames={"#ts": "timestamp"},
            ExpressionAttributeValues={":ts": {"S": event.timestamp}},
        )
        LOGGER.info(
            "Upserted telemetry event",
            extra={"chargerId": event.charger_id, "timestamp": event.timestamp},
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            LOGGER.debug(
                "Ignored older telemetry event",
                extra={"chargerId": event.charger_id, "timestamp": event.timestamp},
            )
            return
        raise


def lambda_handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    successes: List[str] = []
    failures: List[str] = []

    for record in event.get("Records", []):
        body = record.get("body")
        receipt_handle = record.get("receiptHandle")
        try:
            if not body:
                raise ValidationError("Empty record body")
            payload = json.loads(body)
            telemetry_event = TelemetryEvent.from_payload(payload)
            _upsert_latest(telemetry_event)
            successes.append(receipt_handle or telemetry_event.charger_id)
        except (ValidationError, json.JSONDecodeError) as exc:
            LOGGER.warning(
                "Skipping invalid message",
                extra={"error": str(exc), "body": body},
            )
            failures.append(receipt_handle or "unknown")
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception("Processor failure")
            raise exc

    return {
        "status": "ok",
        "processed": len(successes),
        "failed": len(failures),
        "success_ids": successes,
        "failed_ids": failures,
    }

