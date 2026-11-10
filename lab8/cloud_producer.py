from pathlib import Path
import json
import sys
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError

STREAM_NAME = "payments-stream"
REGION_NAME = "eu-north-1"
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
    print(f"[INFO] Ініціалізація клієнта Amazon Kinesis (stream='{STREAM_NAME}', region='{REGION_NAME}')...")

    try:
        kinesis = boto3.client("kinesis", region_name=REGION_NAME)
    except (BotoCoreError, ClientError) as exc:
        print(f"[ERROR] Не вдалося створити клієнт boto3 Kinesis: {exc}", file=sys.stderr)
        sys.exit(1)

    sent_count = 0
    failed_count = 0

    print(f"[INFO] Читання перших {MAX_RECORDS} записів із {events_path.name}...")

    try:
        with events_path.open("r", encoding="utf-8") as file:
            for idx, raw_line in enumerate(file, start=1):
                if idx > MAX_RECORDS:
                    break

                line = raw_line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    invoice_id = str(event.get("invoiceId", f"unknown-{idx}"))

                    # Firehose очікує символ нового рядка в кінці кожного JSON-запису для коректного JSONL у S3
                    payload = (line + "\n").encode("utf-8")

                    response = kinesis.put_record(
                        StreamName=STREAM_NAME,
                        Data=payload,
                        PartitionKey=invoice_id,
                    )

                    shard_id = response.get("ShardId", "N/A")
                    seq_num = response.get("SequenceNumber", "N/A")
                    sent_count += 1
                    print(
                        f"[{sent_count:02d}/{MAX_RECORDS}] Відправлено invoiceId={invoice_id} "
                        f"(status={event.get('status')}) -> Shard={shard_id}, Seq={seq_num[:16]}..."
                    )
                    time.sleep(0.05)

                except json.JSONDecodeError as exc:
                    failed_count += 1
                    print(f"[WARN] Рядок #{idx}: некоректний JSON ({exc})", file=sys.stderr)
                except (BotoCoreError, ClientError) as exc:
                    failed_count += 1
                    print(
                        f"[ERROR] Рядок #{idx} (invoiceId={event.get('invoiceId')}): "
                        f"помилка відправки в Kinesis: {exc}",
                        file=sys.stderr,
                    )

    except OSError as exc:
        print(f"[ERROR] Помилка читання файлу {events_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n--- Підсумок відправки ---")
    print(f"Успішно відправлено: {sent_count}/{MAX_RECORDS}")
    print(f"Помилок:             {failed_count}")


if __name__ == "__main__":
    main()
