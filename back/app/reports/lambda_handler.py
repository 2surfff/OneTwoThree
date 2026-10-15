"""Report Builder Lambda handler.

Runs inside the VPC, queries Aurora via SQLAlchemy models,
generates a weekly CSV report, and uploads it to S3 through
the VPC Gateway Endpoint.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3

from app.reports.weekly import build_weekly_report, get_report_s3_key, parse_iso_week

log = logging.getLogger("report-builder")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def get_previous_iso_week() -> str:
    """Calculate the previous ISO week string (e.g. '2026-W39')."""
    now = datetime.now(UTC)
    prev = now - timedelta(days=7)
    iso_year, iso_week, _ = prev.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def detect_trigger(event: dict[str, Any]) -> str:
    """Detect trigger type from invocation event."""
    if "Records" in event and event["Records"]:
        record = event["Records"][0]
        if record.get("eventSource") == "aws:sqs":
            try:
                body = json.loads(record.get("body", "{}"))
                if isinstance(body, dict) and body.get("source"):
                    return f"sqs:{body['source']}"
            except Exception:
                pass
            return "sqs"
        if record.get("eventSource") == "aws:s3":
            return "s3"
    if event.get("source"):
        return str(event["source"])
    return "direct"


def _extract_week_and_source(event: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract (week, source) pairs from event (direct or SQS records)."""
    if "Records" in event and event["Records"]:
        results = []
        for record in event["Records"]:
            body_raw = record.get("body", "{}")
            try:
                body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
            except Exception:
                body = {}

            raw_week = body.get("week") if isinstance(body, dict) else None
            source = body.get("source", "sqs") if isinstance(body, dict) else "sqs"

            if not raw_week or str(raw_week).strip().lower() in ("", "null", "none"):
                week = get_previous_iso_week()
            else:
                _, _, week = parse_iso_week(str(raw_week))
            results.append((week, source))
        return results

    # Direct invocation
    raw_week = event.get("week")
    source = event.get("source", "direct")
    if not raw_week or str(raw_week).strip().lower() in ("", "null", "none"):
        week = get_previous_iso_week()
    else:
        _, _, week = parse_iso_week(str(raw_week))
    return [(week, source)]


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Lambda entry point for Report Builder."""
    bucket_name = os.environ.get("REPORTS_BUCKET") or os.environ.get("REPORTS_BUCKET_NAME") or ""
    if not bucket_name:
        raise ValueError("REPORTS_BUCKET environment variable is not configured.")

    items = _extract_week_and_source(event)
    processed = []

    s3 = boto3.client("s3")

    for week, _ in items:
        # Mandatory requirement: log event at start
        log.info(
            "report-builder triggered",
            extra={"trigger": detect_trigger(event), "week": week},
        )

        csv_bytes = build_weekly_report(week)
        s3_key = get_report_s3_key(week)

        s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=csv_bytes,
            ContentType="text/csv",
        )

        log.info(
            "report-builder generated and uploaded report",
            extra={"bucket": bucket_name, "key": s3_key, "week": week},
        )
        processed.append({"week": week, "key": s3_key, "bucket": bucket_name})

    return {
        "statusCode": 200,
        "processed": processed,
    }
