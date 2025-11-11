import json
import os
from importlib import reload

import boto3
import pytest
from moto import mock_aws


@mock_aws
def test_ingest_handler_accepts_valid_payload(monkeypatch):
    region = "eu-west-1"
    os.environ["AWS_REGION"] = region
    monkeypatch.setenv("AWS_DEFAULT_REGION", region)
    sqs = boto3.client("sqs", region_name=region)
    queue = sqs.create_queue(
        QueueName="test-ingest.fifo",
        Attributes={
            "FifoQueue": "true",
            "ContentBasedDeduplication": "true",
        },
    )
    monkeypatch.setenv("TELEMETRY_QUEUE_URL", queue["QueueUrl"])

    import ingest.handler as handler

    reload(handler)

    event = {
        "body": json.dumps(
            {
                "chargerId": "charger-1",
                "timestamp": "2024-01-01T00:00:00Z",
                "payload": {"voltage": 231},
            }
        )
    }

    response = handler.lambda_handler(event, None)

    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert body["status"] == "accepted"

    messages = sqs.receive_message(
        QueueUrl=queue["QueueUrl"], MaxNumberOfMessages=1, WaitTimeSeconds=1
    )
    assert len(messages.get("Messages", [])) == 1


@mock_aws
def test_ingest_handler_rejects_invalid_payload(monkeypatch):
    region = "eu-west-1"
    os.environ["AWS_REGION"] = region
    monkeypatch.setenv("AWS_DEFAULT_REGION", region)
    sqs = boto3.client("sqs", region_name=region)
    queue = sqs.create_queue(
        QueueName="test-ingest-invalid.fifo",
        Attributes={
            "FifoQueue": "true",
            "ContentBasedDeduplication": "true",
        },
    )
    monkeypatch.setenv("TELEMETRY_QUEUE_URL", queue["QueueUrl"])

    import ingest.handler as handler

    reload(handler)

    event = {"body": json.dumps({"timestamp": "2024-01-01T00:00:00Z"})}

    response = handler.lambda_handler(event, None)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["status"] == "rejected"

