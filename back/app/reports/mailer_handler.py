"""Report Mailer Lambda handler.

Runs outside the VPC (in the public internet), triggered by S3 ObjectCreated events,
fetches the report CSV, and delivers it via Amazon SES (sesv2).
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from email.message import EmailMessage
from typing import Any

import boto3

log = logging.getLogger("report-mailer")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Lambda entry point for Report Mailer."""
    records = event.get("Records", [])
    if not records:
        log.warning("No records found in event")
        return {"statusCode": 200, "message": "No records to process"}

    recipient_email = os.environ.get("RECIPIENT_EMAIL", "").strip()
    sender_email = os.environ.get("SENDER_EMAIL", recipient_email).strip()

    if not recipient_email:
        raise ValueError("RECIPIENT_EMAIL environment variable is not configured.")

    s3 = boto3.client("s3")
    ses = boto3.client("sesv2")

    sent = []

    for record in records:
        s3_data = record.get("s3", {})
        bucket = s3_data.get("bucket", {}).get("name", "")
        raw_key = s3_data.get("object", {}).get("key", "")
        key = urllib.parse.unquote_plus(raw_key)

        # Mandatory requirement: log event at start
        log.info("report-mailer triggered", extra={"trigger": "s3", "bucket": bucket, "key": key})

        if not key.endswith(".csv"):
            log.info("Skipping non-CSV object: %s", key, extra={"key": key})
            continue

        filename = os.path.basename(key)
        response = s3.get_object(Bucket=bucket, Key=key)
        csv_bytes = response["Body"].read()

        msg = EmailMessage()
        msg["Subject"] = f"Weekly Meetings Report: {filename}"
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg.set_content(
            f"Hello,\n\nPlease find attached the weekly meetings report: {filename}.\n\n"
            f"Generated automatically by Meetings App."
        )
        msg.add_attachment(
            csv_bytes,
            maintype="text",
            subtype="csv",
            filename=filename,
        )

        ses.send_email(
            FromEmailAddress=sender_email,
            Destination={"ToAddresses": [recipient_email]},
            Content={"Raw": {"Data": msg.as_bytes()}},
        )
        log.info(
            "report-mailer sent email: %s",
            filename,
            extra={"recipient": recipient_email, "file": filename},
        )
        sent.append({"bucket": bucket, "key": key, "recipient": recipient_email})

    return {
        "statusCode": 200,
        "sent": sent,
    }
