output "api_endpoint" {
  description = "Base URL for the telemetry HTTP API."
  value       = aws_apigatewayv2_api.telemetry.api_endpoint
}

output "telemetry_queue_url" {
  description = "URL of the SQS queue receiving validated telemetry events."
  value       = aws_sqs_queue.telemetry_fifo.url
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table storing latest telemetry snapshots."
  value       = aws_dynamodb_table.telemetry_latest.name
}

