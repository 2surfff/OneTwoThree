from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.ai.agenda import ParsedAgenda
from app.config import settings


def meeting_payload(**overrides) -> dict:
    payload = {
        "title": "Strategy Sync",
        "description": "Discuss future directions",
        "call_link": "https://meet.google.com/abc-defg-hij",
        "place": "Online",
        "starts_at": "2026-10-20T10:00:00+03:00",
        "ends_at": "2026-10-20T11:00:00+03:00",
        "participant_ids": [],
    }
    payload.update(overrides)
    return payload


def test_create_meeting_with_agenda_and_ai_suggestion(client: TestClient):
    agenda_data = {
        "title": "Strategy Sync",
        "starts_at": "2026-10-20T10:00:00+03:00",
        "duration_minutes": 60,
        "items": [{"title": "Review Q3", "duration_minutes": 20}],
        "action_items": [{"task": "Prepare report", "assignee": "Oleh"}],
    }
    ai_suggestion_data = {
        "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "prompt_version": "agenda-v1",
        "raw_text": "Review Q3 and prepare report",
    }
    res = client.post(
        "/api/meetings",
        json=meeting_payload(agenda=agenda_data, ai_suggestion=ai_suggestion_data),
    )
    assert res.status_code == 201, res.text
    meeting = res.json()
    assert meeting["agenda"] == agenda_data
    assert meeting["ai_suggestion"] == ai_suggestion_data


def test_save_meeting_agenda_endpoint(client: TestClient):
    # 1. Create a basic meeting
    create_res = client.post("/api/meetings", json=meeting_payload())
    assert create_res.status_code == 201
    meeting_id = create_res.json()["id"]

    # 2. Save agenda via POST /meetings/{id}/agenda
    agenda_data = {
        "title": "Updated from AI",
        "duration_minutes": 45,
        "items": [{"title": "Item 1"}, {"title": "Item 2"}],
    }
    ai_suggestion_data = {
        "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "prompt_version": "agenda-v1",
    }
    save_res = client.post(
        f"/api/meetings/{meeting_id}/agenda",
        json={"agenda": agenda_data, "ai_suggestion": ai_suggestion_data},
    )
    assert save_res.status_code == 200, save_res.text
    updated = save_res.json()
    assert updated["id"] == meeting_id
    assert updated["agenda"] == agenda_data
    assert updated["ai_suggestion"] == ai_suggestion_data

    # 3. Verify retrieval via GET /meetings/{id}
    get_res = client.get(f"/api/meetings/{meeting_id}")
    assert get_res.status_code == 200
    assert get_res.json()["agenda"] == agenda_data
    assert get_res.json()["ai_suggestion"] == ai_suggestion_data


def test_parse_agenda_via_external_lambda(client: TestClient):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = {
        "agenda": {"title": "Team Sync", "duration_minutes": 30, "items": [], "action_items": []},
        "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "prompt_version": "agenda-v1",
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        res = client.post(
            "/api/meetings/parse-agenda",
            json={"text": "Team Sync tomorrow 10am", "tz": "Europe/Kyiv"},
            headers={"Authorization": "Bearer test-token-123"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["agenda"]["title"] == "Team Sync"
        mock_post.assert_called_once()
        call_url, call_kwargs = mock_post.call_args
        assert call_url[0] == settings.AGENDA_PARSER_URL
        assert call_kwargs["json"] == {"text": "Team Sync tomorrow 10am", "tz": "Europe/Kyiv"}
        # Ensure Authorization is NOT forwarded to Lambda Function URL to avoid SigV4 conflicts
        assert "Authorization" not in call_kwargs.get("headers", {})
        assert "X-User-ID" in call_kwargs.get("headers", {})


def test_parse_agenda_lambda_failure_fallback_to_local(client: TestClient):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Lambda error"

    mock_parsed = ParsedAgenda(title="Fallback parsed title", duration_minutes=20)

    with (
        patch("httpx.Client.post", return_value=mock_resp),
        patch(
            "app.ai.agenda.parse_agenda",
            return_value=(mock_parsed, {"input_tokens": 10, "output_tokens": 5}),
        ),
    ):
        res = client.post(
            "/api/meetings/parse-agenda",
            json={"text": "Fallback sync", "tz": "Europe/Kyiv"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["agenda"]["title"] == "Fallback parsed title"


def test_parse_agenda_local_fallback(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "agenda_parser_url", "")
    mock_parsed = ParsedAgenda(title="Local parsed title", duration_minutes=15)

    with patch(
        "app.ai.agenda.parse_agenda", return_value=(mock_parsed, {"input_tokens": 10, "output_tokens": 5})
    ) as mock_parse:
        res = client.post(
            "/api/meetings/parse-agenda",
            json={"text": "Quick sync 15 min", "tz": "Europe/Kyiv"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["agenda"]["title"] == "Local parsed title"
        mock_parse.assert_called_once()


def test_parse_agenda_payload_too_large(client: TestClient):
    res = client.post(
        "/api/meetings/parse-agenda",
        json={"text": "A" * 10001, "tz": "Europe/Kyiv"},
    )
    assert res.status_code == 413
