from pathlib import Path
import json
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

BUCKET_NAME = "onetwothree-analytics-2surf"
S3_KEY = "stream-data/events_stream.jsonl"
REGION_NAME = "us-east-1"
MAX_RECORDS = 50


def resolve_events_file() -> Path:
    """Знаходить файл events.jsonl незалежно від поточної робочої директорії."""
    local_path = Path(__file__).resolve().parent / "events.jsonl"
    if local_path.exists():
        return local_path
    cwd_path = Path("events.jsonl")
    if cwd_path.exists():
        return cwd_path
    raise FileNotFoundError(f"Файл events.jsonl не знайдено за шляхом: {local_path}")


def main() -> None:
    events_path = resolve_events_file()
    print(f"[INFO] Читання перших {MAX_RECORDS} подій із {events_path.name}...")

    valid_lines: list[str] = []
    with events_path.open("r", encoding="utf-8") as file:
        for idx, raw_line in enumerate(file, start=1):
            if idx > MAX_RECORDS:
                break
            line = raw_line.strip()
            if not line:
                continue
            event = json.loads(line)
            valid_lines.append(json.dumps(event, ensure_ascii=False))

    payload_bytes = ("\n".join(valid_lines) + "\n").encode("utf-8")
    print(
        f"[INFO] Сформовано мікро-батч: {len(valid_lines)} подій "
        f"({len(payload_bytes)} байт)."
    )

    try:
        s3 = boto3.client("s3", region_name=REGION_NAME)
        print(f"[INFO] Завантаження у s3://{BUCKET_NAME}/{S3_KEY} (region={REGION_NAME})...")
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=S3_KEY,
            Body=payload_bytes,
            ContentType="application/x-ndjson",
        )
        head = s3.head_object(Bucket=BUCKET_NAME, Key=S3_KEY)
        print(
            f"[SUCCESS] Файл успішно доставлено у S3! "
            f"ETag={head.get('ETag')}, ContentLength={head.get('ContentLength')} bytes."
        )
    except (BotoCoreError, ClientError) as exc:
        print(f"[ERROR] Помилка під час завантаження у S3: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
