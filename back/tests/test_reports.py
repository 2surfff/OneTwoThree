"""Unit tests for Lab 5 weekly reports generator and Lambda handlers."""

import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Meeting, Participant, User
from app.reports.lambda_handler import (
    detect_trigger,
    get_previous_iso_week,
    handler as builder_handler,
)
from app.reports.mailer_handler import handler as mailer_handler
from app.reports.weekly import (
    build_weekly_report,
    get_report_s3_key,
    parse_iso_week,
)


@pytest.fixture
def sqlite_session():
    """Create an isolated in-memory SQLite database session for unit tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_parse_iso_week():
    year, week_num, norm = parse_iso_week("2026-W40")
    assert year == 2026
    assert week_num == 40
    assert norm == "2026-W40"

    year, week_num, norm = parse_iso_week("2025-w1")
    assert year == 2025
    assert week_num == 1
    assert norm == "2025-W01"

    with pytest.raises(ValueError):
        parse_iso_week("invalid")

    with pytest.raises(ValueError):
        parse_iso_week("2026-W00")

    with pytest.raises(ValueError):
        parse_iso_week("2026-W54")


def test_get_report_s3_key():
    assert get_report_s3_key("2026-W40") == "reports/2026-W40.csv"
    assert get_report_s3_key("2026-w5") == "reports/2026-W05.csv"


def test_build_weekly_report_empty(sqlite_session):
    csv_bytes = build_weekly_report("2026-W40", session=sqlite_session)
    assert isinstance(csv_bytes, bytes)
    content = csv_bytes.decode("utf-8")
    assert "Metric,Current Week (2026-W40),Previous Week (2026-W39),Delta,Change (%)" in content
    assert "Total Meetings,0,0,0,0.0%" in content
    assert "Total Duration (hours),0.00,0.00,0.00,0.0%" in content
    assert "Top 5 Longest Meetings" in content
    assert "Title,Starts At,Duration (hours),Participants Count" in content


def test_build_weekly_report_with_meetings(sqlite_session):
    # 2026-W40 starts Monday 2026-09-28 and ends Monday 2026-10-05
    # 2026-W39 starts Monday 2026-09-21 and ends Monday 2026-09-28
    user = User(cognito_sub="sub-test", email="user@example.com", name="User")
    sqlite_session.add(user)
    sqlite_session.flush()

    p1 = Participant(name="Alice", email="alice@example.com")
    p2 = Participant(name="Bob", email="bob@example.com")
    sqlite_session.add_all([p1, p2])
    sqlite_session.flush()

    # Previous week meeting: 1 hour
    m_prev = Meeting(
        title="Prev Planning",
        starts_at=datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 22, 11, 0, tzinfo=timezone.utc),
        owner_id=user.id,
    )
    sqlite_session.add(m_prev)

    # Current week meeting 1: 2 hours, 2 participants
    m1 = Meeting(
        title="Architecture Review",
        starts_at=datetime(2026, 9, 29, 14, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 29, 16, 0, tzinfo=timezone.utc),
        owner_id=user.id,
        participants=[p1, p2],
    )
    # Current week meeting 2: 3 hours, 1 participant
    m2 = Meeting(
        title="Deep Dive Workshop",
        starts_at=datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
        owner_id=user.id,
        participants=[p1],
    )
    sqlite_session.add_all([m1, m2])
    sqlite_session.commit()

    csv_bytes = build_weekly_report("2026-W40", session=sqlite_session)
    content = csv_bytes.decode("utf-8")

    # Current week: 2 meetings, 5.00 hours. Prev: 1 meeting, 1.00 hour.
    # Delta count = +1, % = +100.0%
    # Delta duration = +4.00, % = +400.0%
    assert "Total Meetings,2,1,+1,+100.0%" in content
    assert "Total Duration (hours),5.00,1.00,+4.00,+400.0%" in content

    # Top-5 should have Deep Dive Workshop first (3.00 hours, 1 participant),
    # then Architecture Review (2.00 hours, 2 participants)
    lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
    workshop_line = next(line for line in lines if "Deep Dive Workshop" in line)
    arch_line = next(line for line in lines if "Architecture Review" in line)

    assert "3.00,1" in workshop_line
    assert "2.00,2" in arch_line
    assert lines.index(workshop_line) < lines.index(arch_line)


def test_detect_trigger():
    assert detect_trigger({}) == "direct"
    assert detect_trigger({"source": "schedule"}) == "schedule"
    assert detect_trigger({"source": "on-demand"}) == "on-demand"

    sqs_event_schedule = {
        "Records": [
            {
                "eventSource": "aws:sqs",
                "body": json.dumps({"week": None, "source": "schedule"}),
            }
        ]
    }
    assert detect_trigger(sqs_event_schedule) == "sqs:schedule"

    sqs_event_ondemand = {
        "Records": [
            {
                "eventSource": "aws:sqs",
                "body": json.dumps({"week": "2026-W40", "source": "on-demand"}),
            }
        ]
    }
    assert detect_trigger(sqs_event_ondemand) == "sqs:on-demand"


def test_builder_handler():
    with (
        patch.dict("os.environ", {"REPORTS_BUCKET": "test-reports-bucket"}),
        patch("boto3.client") as mock_boto,
        patch("app.reports.lambda_handler.build_weekly_report") as mock_build,
    ):
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3
        mock_build.return_value = b"test,csv,data\n"

        # Direct invocation with explicit week
        res = builder_handler({"week": "2026-W40", "source": "direct"})
        assert res["statusCode"] == 200
        assert res["processed"][0]["week"] == "2026-W40"
        assert res["processed"][0]["key"] == "reports/2026-W40.csv"
        mock_s3.put_object.assert_called_once_with(
            Bucket="test-reports-bucket",
            Key="reports/2026-W40.csv",
            Body=b"test,csv,data\n",
            ContentType="text/csv",
        )

        mock_s3.reset_mock()
        mock_build.reset_mock()

        # SQS invocation with null week (falls back to previous week)
        sqs_event = {
            "Records": [
                {
                    "eventSource": "aws:sqs",
                    "body": json.dumps({"week": None, "source": "schedule"}),
                }
            ]
        }
        res = builder_handler(sqs_event)
        expected_week = get_previous_iso_week()
        assert res["statusCode"] == 200
        assert res["processed"][0]["week"] == expected_week
        assert res["processed"][0]["key"] == f"reports/{expected_week}.csv"
        mock_s3.put_object.assert_called_once()


def test_mailer_handler():
    with (
        patch.dict("os.environ", {"RECIPIENT_EMAIL": "test@example.com"}),
        patch("boto3.client") as mock_boto,
    ):
        mock_s3 = MagicMock()
        mock_ses = MagicMock()

        def client_side_effect(service, **kwargs):
            if service == "s3":
                return mock_s3
            if service == "sesv2":
                return mock_ses
            return MagicMock()

        mock_boto.side_effect = client_side_effect

        mock_body = MagicMock()
        mock_body.read.return_value = b"Metric,Total\n"
        mock_s3.get_object.return_value = {"Body": mock_body}

        s3_event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-reports-bucket"},
                        "object": {"key": "reports/2026-W40.csv"},
                    }
                }
            ]
        }

        res = mailer_handler(s3_event)
        assert res["statusCode"] == 200
        assert len(res["sent"]) == 1
        assert res["sent"][0]["key"] == "reports/2026-W40.csv"

        mock_s3.get_object.assert_called_once_with(
            Bucket="test-reports-bucket",
            Key="reports/2026-W40.csv",
        )
        mock_ses.send_email.assert_called_once()
        call_kwargs = mock_ses.send_email.call_args[1]
        assert call_kwargs["Destination"]["ToAddresses"] == ["test@example.com"]
        assert b"Weekly Meetings Report: 2026-W40.csv" in call_kwargs["Content"]["Raw"]["Data"]

