import argparse
from collections import defaultdict
from datetime import datetime
import json
import queue
import threading
import time

parser = argparse.ArgumentParser()
parser.add_argument(
    "--fail-30", action="store_true", help="Force 30% payments to fail"
)
parser.add_argument(
    "--waiting-time",
    type=int,
    default=120,
    help="Seconds to wait before closing window",
)
parser.add_argument(
    "--two-consumers",
    action="store_true",
    help="Simulate 2 consumer instances",
)
args = parser.parse_args()

# Симуляція топіка з 3 партиціями
partitions = {0: queue.Queue(), 1: queue.Queue(), 2: queue.Queue()}
stop_event = threading.Event()


def get_partition(key: str) -> int:
    return abs(hash(key)) % 3


def producer():
    print("[PRODUCER] Reading events from events.jsonl...")
    with open("events.jsonl", "r", encoding="utf-8") as f:
        events = [json.loads(line) for line in f]

    # Беремо 3000 подій для швидкого виконання експериментів
    events = events[:3000]
    events.sort(key=lambda x: x.get("receivedAt", ""))
    print(
        f"[PRODUCER] Replaying {len(events)} events (fail_30={args.fail_30})..."
    )

    for idx, ev in enumerate(events):
        if args.fail_30 and idx % 3 == 0:
            ev["status"] = "failure"

        p_id = get_partition(ev["invoiceId"])
        partitions[p_id].put(ev)

        if (idx + 1) % 100 == 0:
            time.sleep(0.05)

    print("[PRODUCER] All events published.")
    stop_event.set()


def consumer(consumer_name: str, assigned_partitions: list):
    print(f"[{consumer_name}] Assigned partitions: {assigned_partitions}")
    seen_events = set()
    windows = defaultdict(lambda: defaultdict(lambda: {"total": 0, "fail": 0}))
    rejected_late = 0

    while not stop_event.is_set() or any(
        not partitions[p].empty() for p in assigned_partitions
    ):
        processed = False
        for p in assigned_partitions:
            try:
                ev = partitions[p].get_nowait()
                processed = True
            except queue.Empty:
                continue

            # Дедуплікація повторних подій
            event_id = (ev["invoiceId"], ev["status"], ev["modifiedDate"])
            if event_id in seen_events:
                continue
            seen_events.add(event_id)

            mod_dt = datetime.fromisoformat(
                ev["modifiedDate"].replace("Z", "+00:00")
            )
            rec_dt = datetime.fromisoformat(
                ev["receivedAt"].replace("Z", "+00:00")
            )

            window_minute = mod_dt.strftime("%Y-%m-%dT%H:%M:00")
            now_ts = rec_dt.timestamp()
            window_close_ts = (
                mod_dt.replace(second=0).timestamp() + 60 + args.waiting_time
            )

            # Перевірка запізнілих подій
            if now_ts > window_close_ts:
                rejected_late += 1
                print(
                    f"[{consumer_name} LATE REJECTED] Total rejected so far: {rejected_late}"
                )
                continue

            method = ev.get("paymentMethod", "unknown")
            windows[window_minute][method]["total"] += 1
            if ev.get("status") == "failure":
                windows[window_minute][method]["fail"] += 1

            stats = windows[window_minute][method]
            fail_rate = stats["fail"] / stats["total"]
            if stats["total"] >= 5 and fail_rate > 0.10:
                print(
                    f"[{consumer_name} ALERT] Window: {window_minute} | Method: {method} | "
                    f"Failure rate: {fail_rate:.1%} ({stats['fail']}/{stats['total']})"
                )

        if not processed:
            time.sleep(0.02)


t_prod = threading.Thread(target=producer)
t_prod.start()

if args.two_consumers:
    t_c1 = threading.Thread(
        target=consumer, args=("Consumer-1", [0, 1]), daemon=True
    )
    t_c2 = threading.Thread(
        target=consumer, args=("Consumer-2", [2]), daemon=True
    )
    t_c1.start()
    t_c2.start()
    t_prod.join()
    t_c1.join(timeout=2)
    t_c2.join(timeout=2)
else:
    t_c = threading.Thread(
        target=consumer, args=("Consumer-Main", [0, 1, 2]), daemon=True
    )
    t_c.start()
    t_prod.join()
    t_c.join(timeout=2)

print("\n--- Summary ---")
print("Streaming processing finished successfully.")