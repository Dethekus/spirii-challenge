import json
import os
from importlib import reload

import boto3
from moto import mock_aws


@mock_aws
def test_processor_handler_upserts_latest(monkeypatch):
    region = "eu-west-1"
    os.environ["AWS_REGION"] = region
    monkeypatch.setenv("AWS_DEFAULT_REGION", region)

    dynamodb = boto3.client("dynamodb", region_name=region)
    table_name = "telemetry-latest"
    dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": "charger_id", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "charger_id", "KeyType": "HASH"}],
    )

    monkeypatch.setenv("TELEMETRY_TABLE_NAME", table_name)

    import processor.handler as handler

    reload(handler)

    payload_newer = {
        "chargerId": "charger-1",
        "timestamp": "2024-01-01T01:00:00Z",
        "payload": {"voltage": 230},
    }

    payload_older = {
        "chargerId": "charger-1",
        "timestamp": "2023-12-31T23:00:00Z",
        "payload": {"voltage": 220},
    }

    event = {
        "Records": [
            {"body": json.dumps(payload_older), "receiptHandle": "1"},
            {"body": json.dumps(payload_newer), "receiptHandle": "2"},
        ]
    }

    result = handler.lambda_handler(event, None)

    assert result["processed"] == 2

    stored = dynamodb.get_item(
        TableName=table_name, Key={"charger_id": {"S": "charger-1"}}, ConsistentRead=True
    )
    assert stored["Item"]["timestamp"]["S"] == "2024-01-01T01:00:00+00:00"

