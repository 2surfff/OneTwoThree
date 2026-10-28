import argparse
import json
import sys
from datetime import date

from app.ai.agenda import parse_agenda


def main():
    parser = argparse.ArgumentParser(
        description="Parse raw meeting text into structured agenda using Bedrock"
    )
    parser.add_argument("text", nargs="?", default="", help="Raw meeting text or notes")
    parser.add_argument("--tz", default="Europe/Kyiv", help="Timezone (default: Europe/Kyiv)")
    parser.add_argument("--date", default=None, help="Today date in YYYY-MM-DD (default: current date)")

    args = parser.parse_args()
    text = args.text
    if not text and not sys.stdin.isatty():
        text = sys.stdin.read()

    if not text:
        print("Error: No text provided. Pass text as argument or via stdin.", file=sys.stderr)
        sys.exit(1)

    today = date.fromisoformat(args.date) if args.date else date.today()
    parsed, usage = parse_agenda(text=text, today=today, tz=args.tz)

    output = {
        "agenda": parsed.model_dump(mode="json"),
        "usage": usage,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
