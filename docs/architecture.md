## Telemetry Foundation Architecture

### Context and Goals
- Enable product teams to ingest charger telemetry securely and at scale.
- Provide primitives for validation, processing, storage, and querying with minimal coupling.
- Optimize for autonomous feature delivery, observability, and cost-aware scalability.

### High-Level Flow
1. Chargers (or gateway devices) POST telemetry events to a public HTTPS endpoint.
2. API Gateway invokes the **Ingest Lambda** which validates payloads and enqueues accepted events to SQS.
3. The **Processor Lambda** consumes the queue, enriches/normalizes telemetry, and upserts the latest sample per charger into DynamoDB.
4. The **Query Lambda** is exposed via API Gateway to return the most recent telemetry for a given `chargerId`.

```
Charger → API Gateway → Ingest Lambda → SQS Queue → Processor Lambda → DynamoDB
                                            ↘ CloudWatch Logs & Metrics

Client → API Gateway → Query Lambda → DynamoDB
```

### Component Responsibilities
- **API Gateway (HTTP API)**: public entry point, native throttling, request validation (schema + WAF optional).
- **Ingest Lambda (`src/ingest/handler.py`)**:
  - Validates schema with Pydantic.
  - Rejects obviously bad data (4xx) and emits structured logs/metrics.
  - Publishes to SQS with deduplication IDs to avoid duplicates.
- **SQS FIFO Queue**: buffer bursts, decouple ingest from processing, guarantee ordering per `chargerId`.
- **Processor Lambda (`src/processor/handler.py`)**:
  - Batch consumes events, applies business rules, persists to DynamoDB.
  - Emits metrics (successful writes, validation failures) via embedded EMF.
- **DynamoDB Table (`telemetry_latest`)**: stores latest telemetry keyed by `chargerId`, TTL optional for retention.
- **Query Lambda (`src/query/handler.py`)**:
  - Parameter validation.
  - Simple point lookup.
  - Returns 404 when no telemetry found.

### Data Model
- **Telemetry Envelope**
  - `chargerId` (Partition Key)
  - `timestamp` (ISO8601 string)
  - `payload` (map, arbitrary telemetry fields)
  - `ingestedAt` (ISO8601, server time)
  - Future extensions: `chargerStatus`, `locationId`, `firmwareVersion`
- The DynamoDB item stores the latest sample per `chargerId`. Historical retention can be added via DynamoDB Streams → Kinesis / S3.

### Scalability & Reliability
- Lambda + SQS scales linearly with traffic bursts; FIFO queue ensures per-device ordering.
- DynamoDB on-demand mode removes capacity planning for MVP; switch to provisioned with auto-scaling once usage stabilizes.
- Dead-letter queue captures poison pill messages for later triage.
- API Gateway usage plans + WAF protect against abuse.
- CloudWatch Alarms monitor:
  - DLQ message age > 0
  - Error rates for ingest/processor/query lambdas
  - Throttles on API Gateway or SQS

### Security & Compliance
- IAM roles follow least privilege; SQS queue and DynamoDB table encrypted with KMS.
- API Gateway uses JWT authorizer (stubbed) for future integration.
- All data encrypted in transit (TLS 1.2) and at rest (KMS-managed keys).
- CloudTrail enabled on account for auditing (out of scope for sample Terraform but documented).

### Extensibility
- Add Kinesis Data Firehose / S3 sink by enabling DynamoDB Streams, wiring to Lambda or Firehose.
- Swap Processor Lambda with containerized microservice behind SQS without affecting ingest path.
- Introduce schema registry by replacing inline Pydantic models with AWS Glue Schema Registry or JSON Schema service.

### Developer Experience
- `terraform/` provides reproducible environment via Terraform + remote state (S3/dynamodb).
- `scripts/deploy.sh` wraps Terraform apply with environment selection.
- Local tests via `pytest` with `moto` to emulate AWS services.
- CI pipeline (GitHub Actions) runs lint/tests and Terraform plan (not included in sample).

### Trade-offs
- Chose serverless to minimize ops overhead; containerized alternative documented in ADR.
- FIFO SQS adds cost but simplifies ordering semantics per charger.
- Storing only "latest" snapshot meets MVP requirement; historical analytics requires additional modeling.

### Next Steps for Product Team
- Extend Processor Lambda with business rules (e.g., detect anomalies, compute metrics).
- Enable EventBridge notifications from DynamoDB Streams for downstream consumers.
- Harden security posture (WAF rules, JWT authorizer integration).
- Build dashboard leveraging CloudWatch metrics and alarms.

