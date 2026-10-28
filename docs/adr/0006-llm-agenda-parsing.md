# ADR 0006: Serverless LLM Agenda Parsing with Amazon Bedrock

## Status
Accepted

## Date
2026-10-20

## Context
Users frequently schedule meetings by copying unstructured notes, chat messages (Slack/Telegram), or calendar invitations in Ukrainian or English (e.g., *"Пн 10:00, синк по прайсингу на півгодини. Обговорити знижки для ентерпрайз клієнтів. Антон готує таблицю до п'ятниці"*).

Extracting structured data (meeting title, exact date/time relative to current day, duration, agenda items, and action items with assignees) manually is tedious. We need an LLM in the product to automate this extraction.

Key technical requirements and constraints:
1. **Model & Region**: Amazon Bedrock with Anthropic Claude in `us-east-1` (high availability, lowest latency, and cost-effective models).
2. **Cost at Idle**: $0 at idle. No dedicated always-on LLM worker containers or VPC NAT Gateways.
3. **Security & Authentication**: Direct access via Lambda Function URL must be strictly authenticated using the existing Cognito User Pool JWT tokens (`Authorization: Bearer <token>`).
4. **Safety & Human in the Loop**: The LLM must **never** directly write to the database. The model returns structured suggestions to the frontend, which highlights them with visual **"suggested"** badges. The user reviews/edits the fields, and only then saves them through the existing backend API.
5. **Auditability**: When saving, the database records the raw LLM output, model identifier, and prompt version alongside the user-approved agenda as an audit trail.

---

## Decision

1. **Serverless Architecture Outside VPC**:
   - Deploy a dedicated Lambda function (`meetings-agenda-parser`) outside the VPC with direct public Internet access.
   - The Lambda function executes with an IAM role granting `bedrock:InvokeModel` in `us-east-1`.
   - Expose the Lambda function via **Lambda Function URL** with `AuthType: NONE` and CORS enabled.

2. **JWT Verification at the Edge**:
   - The Lambda handler intercepts incoming requests and extracts the `Authorization: Bearer <token>` header.
   - It fetches and caches the Cognito User Pool JWKS public keys over HTTPS, verifies token signature and expiration, and extracts the user's `sub`.
   - Missing or invalid tokens immediately yield HTTP 401 Unauthorized before any LLM invocation.

3. **Input Validation and Guardrails**:
   - Maximum input text length is capped at 10,000 characters (returns HTTP 413 Payload Too Large if exceeded).

4. **Structured Output via Tool Calling**:
   - We utilize Anthropic Tool Use (`record_agenda`) backed by a strict Pydantic schema (`ParsedAgenda`).
   - The prompt dynamically injects the current date, weekday, and timezone (e.g. `Today is Monday 2026-10-19 in timezone Europe/Kyiv`).
   - If a `ValidationError` occurs, the parser performs at most 1 automatic retry by feeding the validation error message back to the model.

5. **CloudWatch Telemetry**:
   - Each successful parse logs a single structured JSON line with `event`, `user`, `model`, `prompt_version`, `input_tokens`, `output_tokens`, `latency_ms`, and `cost_usd`.

6. **Human-in-the-Loop Frontend UX**:
   - The meeting form contains an interactive "Paste an agenda" panel with a textarea, loading spinner, and an `AbortController`-backed "Cancel" button.
   - Fields populated by the model display an amber **"suggested"** badge.
   - Modifying any field removes its badge immediately.
   - Saving sends the structured agenda and `ai_suggestion` audit metadata to `POST /meetings/{id}/agenda`.

---

## Alternatives Considered

1. **Direct Invocation from Frontend via AWS SDK**:
   - *Rejected*: Requires exposing AWS credentials or issuing STS temporary credentials with Bedrock permissions to web clients, posing security and cost exploitation risks.
2. **Handling LLM Parsing inside the ECS Fargate Backend Service**:
   - *Rejected*: Incurring LLM generation latency (2–8 seconds) inside backend HTTP workers ties up application threads and requires either NAT Gateways ($32+/month) or VPC Endpoints for Bedrock.
3. **Allowing the LLM to write directly to the database**:
   - *Rejected*: High risk of hallucinated data corrupting database state. Human review is mandatory.

---

## Consequences

### Positive:
- **Zero Idle Cost**: Lambda and Bedrock only bill for actual invocations ($0 at idle).
- **Sub-2-second Response Time**: Claude Haiku 4.5 delivers swift extraction with high Ukrainian language comprehension.
- **Data Integrity**: Human-in-the-loop validation prevents unwanted or malformed entries.
- **Auditability**: `ai_suggestion` column retains original suggestions, model version, and prompt version for debugging and fine-tuning.

### Negative:
- First-time cold start for Lambda Docker container may add 1-2 seconds of initial latency.
- Dependent on AWS Bedrock availability in `us-east-1`.

