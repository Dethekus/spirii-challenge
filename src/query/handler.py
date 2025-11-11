from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import boto3

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

DYNAMO_TABLE = os.environ["TELEMETRY_TABLE_NAME"]
DDB_CLIENT = boto3.client("dynamodb")


def _build_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    path_params = event.get("pathParameters") or {}
    charger_id = path_params.get("chargerId")

    if not charger_id:
        return _build_response(400, {"status": "error", "reason": "chargerId is required"})

    result = DDB_CLIENT.get_item(
        TableName=DYNAMO_TABLE,
        Key={"charger_id": {"S": charger_id}},
        ConsistentRead=True,
    )

    item = result.get("Item")
    if not item:
        return _build_response(404, {"status": "not_found", "chargerId": charger_id})

    telemetry = {
        "chargerId": charger_id,
        "timestamp": item["timestamp"]["S"],
        "payload": json.loads(item["payload"]["S"]),
        "ingestedAt": item["ingested_at"]["S"],
    }

    LOGGER.info("Fetched telemetry", extra={"chargerId": charger_id})
    return _build_response(200, {"status": "ok", "telemetry": telemetry})

