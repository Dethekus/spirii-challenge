## Spirii Telemetry Foundation

This repository contains a reference implementation for ingesting and serving charger telemetry data. It is designed as an enabling foundation that Spirii product teams can extend independently.

### Capabilities
- **Async ingestion** of telemetry events via HTTP API → Lambda → SQS.
- **Validation & processing** pipeline that enforces schema and stores the freshest sample per charger in DynamoDB.
- **Query API** returning the latest telemetry snapshot for a given `chargerId`.
- Infrastructure-as-code (Terraform) and automated tests for the Lambda handlers.

### Repository Layout
- `docs/` – architecture overview and design trade-offs.
- `src/` – Lambda handler source code shared across ingest, processor, and query flows.
- `terraform/` – AWS infrastructure (API Gateway, Lambda, SQS, DynamoDB, IAM).
- `tests/` – unit tests powered by `pytest` and `moto`.
- `scripts/` – helper scripts for deployment and validation.

### Getting Started
1. **Install tooling**
   - Terraform `>= 1.6`
   - Python `>= 3.11`
   - `pip install -r requirements-dev.txt`
2. **Run tests**
   - `make test`
3. **Configure AWS credentials**
   - Ensure `AWS_PROFILE` or environment variables point to the target account.
4. **Deploy infrastructure**
   - `./scripts/deploy.sh dev`
   - The script runs `terraform init/plan/apply` inside `terraform/`.
5. **Invoke APIs**
   - POST telemetry: `curl -X POST "$API_URL/telemetry" -d '{"chargerId":"abc","timestamp":"2024-01-01T00:00:00Z","payload":{"voltage":230}}'`
   - GET latest telemetry: `curl "$API_URL/telemetry/abc"`

### Extending the Foundation
- Swap SQS → Kinesis for higher throughput or multi-subscriber patterns.
- Enable DynamoDB Streams for historical storage or downstream eventing.
- Add authentication/authorization via API Gateway JWT authorizers.
- Instrument custom metrics/alarms using Embedded Metric Format in Lambda.

Refer to `docs/architecture.md` for detailed design notes and suggested next steps. Contributions should include updated tests and documentation.

# spirii-challenge
