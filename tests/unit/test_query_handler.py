import json
import os
from importlib import reload

import boto3
from moto import mock_aws


@mock_aws
def test_query_handler_returns_latest(monkeypatch):
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
    dynamodb.put_item(
        TableName=table_name,
        Item={
            "charger_id": {"S": "charger-1"},
            "timestamp": {"S": "2024-01-01T01:00:00+00:00"},
            "payload": {"S": json.dumps({"voltage": 230})},
            "ingested_at": {"S": "2024-01-01T01:00:01+00:00"},
        },
    )

    monkeypatch.setenv("TELEMETRY_TABLE_NAME", table_name)

    import query.handler as handler

    reload(handler)

    event = {"pathParameters": {"chargerId": "charger-1"}}

    response = handler.lambda_handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["telemetry"]["payload"]["voltage"] == 230


@mock_aws
def test_query_handler_returns_not_found(monkeypatch):
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

    import query.handler as handler

    reload(handler)

    event = {"pathParameters": {"chargerId": "missing"}}

    response = handler.lambda_handler(event, None)

    assert response["statusCode"] == 404

