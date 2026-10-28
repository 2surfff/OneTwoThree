from fastapi.testclient import TestClient


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
