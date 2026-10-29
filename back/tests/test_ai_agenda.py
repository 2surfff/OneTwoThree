import json
from unittest.mock import MagicMock, patch

from app.ai.agenda import ActionItem, AgendaItem, ParsedAgenda, parse_agenda
from app.ai.agenda_lambda import calculate_cost_usd, handler


def test_parsed_agenda_schema():
    agenda = ParsedAgenda(
        title="Weekly Sync",
        starts_at="2026-10-19T10:00:00+03:00",
        duration_minutes=45,
        items=[AgendaItem(title="Q4 Goals", duration_minutes=30)],
        action_items=[ActionItem(task="Prepare slides", assignee="Alice", due_date="Friday")],
        language="en",
    )
    dumped = agenda.model_dump()
    assert dumped["title"] == "Weekly Sync"
    assert dumped["duration_minutes"] == 45
    assert len(dumped["items"]) == 1
    assert dumped["items"][0]["title"] == "Q4 Goals"
    assert len(dumped["action_items"]) == 1
    assert dumped["action_items"][0]["assignee"] == "Alice"


def test_calculate_cost_usd():
    # Haiku 4.5
    cost_haiku = calculate_cost_usd("us.anthropic.claude-haiku-4-5-20251001-v1:0", 1000, 200)
    assert cost_haiku == round(1000 * 0.000001 + 200 * 0.000005, 6)

    # Sonnet
    cost_sonnet = calculate_cost_usd("us.anthropic.claude-sonnet-4-5-20250929-v1:0", 1000, 200)
    assert cost_sonnet == round(1000 * 0.000003 + 200 * 0.000015, 6)


def test_parse_agenda_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.input = {
        "title": "Pricing sync",
        "starts_at": "2026-10-19T10:00:00+03:00",
        "duration_minutes": 30,
        "items": [{"title": "Discuss enterprise tiers"}],
        "action_items": [{"task": "Send deck", "assignee": "Anton"}],
        "language": "uk",
    }
    mock_response.content = [mock_tool_block]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 100
    mock_client.messages.create.return_value = mock_response

    agenda, usage = parse_agenda("Пн 10:00 синк", client=mock_client)
    assert agenda.title == "Pricing sync"
    assert agenda.duration_minutes == 30
    assert len(agenda.items) == 1
    assert usage == {"input_tokens": 500, "output_tokens": 100}
    assert mock_client.messages.create.call_args[1]["max_tokens"] == 400


def test_parse_agenda_retry_on_validation_error():
    mock_client = MagicMock()

    # First attempt: invalid input (duration_minutes as string instead of int)
    bad_tool_block = MagicMock()
    bad_tool_block.type = "tool_use"
    bad_tool_block.id = "tool_1"
    # Missing title which is required
    bad_tool_block.input = {"duration_minutes": 30}
    bad_response = MagicMock()
    bad_response.content = [bad_tool_block]
    bad_response.usage.input_tokens = 400
    bad_response.usage.output_tokens = 50

    # Second attempt: corrected input
    good_tool_block = MagicMock()
    good_tool_block.type = "tool_use"
    good_tool_block.id = "tool_2"
    good_tool_block.input = {"title": "Corrected title", "duration_minutes": 30}
    good_response = MagicMock()
    good_response.content = [good_tool_block]
    good_response.usage.input_tokens = 450
    good_response.usage.output_tokens = 60

    mock_client.messages.create.side_effect = [bad_response, good_response]

    agenda, usage = parse_agenda("Some meeting text", client=mock_client)
    assert agenda.title == "Corrected title"
    assert mock_client.messages.create.call_count == 2
    assert usage == {"input_tokens": 850, "output_tokens": 110}


def test_lambda_options_preflight():
    event = {
        "requestContext": {"http": {"method": "OPTIONS"}},
        "headers": {"origin": "https://d1y19dbl226ufk.cloudfront.net"},
    }
    res = handler(event)
    assert res["statusCode"] == 200
    assert "Access-Control-Allow-Origin" in res["headers"]
    assert "Access-Control-Allow-Methods" in res["headers"]


@patch("app.ai.agenda_lambda.parse_agenda")
def test_lambda_without_auth_continues(mock_parse):
    parsed = ParsedAgenda(title="Anonymous meeting", duration_minutes=30)
    mock_parse.return_value = (parsed, {"input_tokens": 50, "output_tokens": 20})
    event = {
        "requestContext": {"http": {"method": "POST"}},
        "headers": {},
        "body": json.dumps({"text": "Quick call at 10am"}),
    }
    res = handler(event)
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["agenda"]["title"] == "Anonymous meeting"


@patch("app.ai.agenda_lambda.verify_cognito_token")
def test_lambda_payload_too_large(mock_verify):
    mock_verify.return_value = {"sub": "user-123"}
    event = {
        "requestContext": {"http": {"method": "POST"}},
        "headers": {"authorization": "Bearer valid_token"},
        "body": json.dumps({"text": "x" * 10001}),
    }
    res = handler(event)
    assert res["statusCode"] == 413
    assert "Payload too large" in res["body"]


@patch("app.ai.agenda_lambda.verify_cognito_token")
@patch("app.ai.agenda_lambda.parse_agenda")
def test_lambda_success(mock_parse, mock_verify, capsys):
    mock_verify.return_value = {"sub": "user-456"}
    parsed = ParsedAgenda(title="Standup", duration_minutes=15)
    mock_parse.return_value = (parsed, {"input_tokens": 100, "output_tokens": 50})

    event = {
        "requestContext": {"http": {"method": "POST"}},
        "headers": {"authorization": "Bearer valid_token"},
        "body": json.dumps({"text": "Standup tomorrow 10am"}),
    }
    res = handler(event)
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["agenda"]["title"] == "Standup"
    assert body["prompt_version"] == "agenda-v1"

    # Verify structured CloudWatch logging
    captured = capsys.readouterr()
    log_line = json.loads(captured.out.strip())
    assert log_line["event"] == "agenda_parsed"
    assert log_line["user"] == "user-456"
    assert log_line["input_tokens"] == 100
    assert log_line["output_tokens"] == 50
    assert "latency_ms" in log_line
    assert "cost_usd" in log_line
