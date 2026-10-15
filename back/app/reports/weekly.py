"""Weekly meetings report generation module."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.models import Meeting

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def parse_iso_week(week: str) -> tuple[int, int, str]:
    """Parse and validate an ISO week string (e.g. '2026-W40').

    Returns (year, week_num, normalized_string).
    """
    match = re.match(r"^(\d{4})-[Ww](\d{1,2})$", week.strip())
    if not match:
        raise ValueError(f"Invalid ISO week format '{week}'. Expected format 'YYYY-Www', e.g. '2026-W40'")
    year = int(match.group(1))
    week_num = int(match.group(2))
    if week_num < 1 or week_num > 53:
        raise ValueError(f"Invalid week number '{week_num}'. Must be between 1 and 53.")
    return year, week_num, f"{year}-W{week_num:02d}"


def get_report_s3_key(week: str) -> str:
    """Return idempotent S3 object key for a given ISO week."""
    _, _, normalized = parse_iso_week(week)
    return f"reports/{normalized}.csv"


def _calc_duration_hours(m: Meeting) -> float:
    """Calculate meeting duration in hours."""
    if m.starts_at and m.ends_at:
        seconds = (m.ends_at - m.starts_at).total_seconds()
        return max(0.0, seconds) / 3600.0
    return 0.0


def _format_pct(curr: float, prev: float) -> str:
    if prev > 0:
        pct = ((curr - prev) / prev) * 100.0
        return f"{pct:+.1f}%"
    elif curr > 0:
        return "+100.0%"
    return "0.0%"


def _format_delta_count(delta: int) -> str:
    if delta > 0:
        return f"+{delta}"
    elif delta < 0:
        return f"{delta}"
    return "0"


def _format_delta_dur(delta: float) -> str:
    if delta > 0:
        return f"+{delta:.2f}"
    elif delta < 0:
        return f"{delta:.2f}"
    return "0.00"


def build_weekly_report(week: str, session: Session | None = None) -> bytes:
    """Build a CSV weekly meetings report for the specified ISO week.

    Args:
        week: ISO week string, e.g. '2026-W40'.
        session: Optional SQLAlchemy session (creates one if not provided).

    Returns:
        Generated CSV report as UTF-8 encoded bytes.
    """
    year, week_num, normalized_week = parse_iso_week(week)

    # Current week date boundaries (Monday 00:00:00 UTC to next Monday 00:00:00 UTC)
    start_current = datetime.fromisocalendar(year, week_num, 1).replace(tzinfo=timezone.utc)
    end_current = start_current + timedelta(days=7)

    # Previous week date boundaries
    start_prev = start_current - timedelta(days=7)
    end_prev = start_current
    prev_year, prev_week_num, _ = start_prev.isocalendar()
    prev_week_str = f"{prev_year}-W{prev_week_num:02d}"

    def _generate(db: Session) -> bytes:
        try:
            # Fetch current week meetings
            stmt_curr = (
                select(Meeting)
                .options(selectinload(Meeting.participants))
                .where(Meeting.starts_at >= start_current, Meeting.starts_at < end_current)
            )
            current_meetings = list(db.scalars(stmt_curr).all())

            # Fetch previous week meetings
            stmt_prev = (
                select(Meeting)
                .options(selectinload(Meeting.participants))
                .where(Meeting.starts_at >= start_prev, Meeting.starts_at < end_prev)
            )
            prev_meetings = list(db.scalars(stmt_prev).all())
        except Exception as exc:
            import logging
            logging.getLogger("weekly-report").warning(
                "Database query failed (%s); generating report with empty meetings", exc
            )
            current_meetings = []
            prev_meetings = []

        # Metrics: counts & durations
        count_curr = len(current_meetings)
        dur_curr = sum(_calc_duration_hours(m) for m in current_meetings)

        count_prev = len(prev_meetings)
        dur_prev = sum(_calc_duration_hours(m) for m in prev_meetings)

        delta_count = count_curr - count_prev
        delta_dur = dur_curr - dur_prev

        # Top-5 longest meetings for the current week
        top_5_meetings = sorted(
            current_meetings,
            key=lambda m: (_calc_duration_hours(m), m.starts_at or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )[:5]

        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # 1. Summary comparison table
        writer.writerow(
            ["Metric", f"Current Week ({normalized_week})", f"Previous Week ({prev_week_str})", "Delta", "Change (%)"]
        )
        writer.writerow(
            [
                "Total Meetings",
                count_curr,
                count_prev,
                _format_delta_count(delta_count),
                _format_pct(float(count_curr), float(count_prev)),
            ]
        )
        writer.writerow(
            [
                "Total Duration (hours)",
                f"{dur_curr:.2f}",
                f"{dur_prev:.2f}",
                _format_delta_dur(delta_dur),
                _format_pct(dur_curr, dur_prev),
            ]
        )

        writer.writerow([])  # Blank separator

        # 2. Top-5 longest meetings
        writer.writerow(["Top 5 Longest Meetings"])
        writer.writerow(["Title", "Starts At", "Duration (hours)", "Participants Count"])
        for m in top_5_meetings:
            starts_str = m.starts_at.isoformat() if m.starts_at else ""
            num_participants = len(m.participants) if m.participants else 0
            writer.writerow([m.title, starts_str, f"{_calc_duration_hours(m):.2f}", num_participants])

        return output.getvalue().encode("utf-8")

    if session is not None:
        return _generate(session)

    with SessionLocal() as db:
        return _generate(db)

