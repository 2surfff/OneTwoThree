import logging
from datetime import date
from typing import Any

from anthropic import AnthropicBedrock
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)


class AgendaItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(description="Title or topic of the agenda item")
    duration_minutes: int | None = Field(default=None, description="Estimated duration in minutes")
    description: str | None = Field(default=None, description="Details or discussion points")


class ActionItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    task: str = Field(description="Action item description or task")
    assignee: str | None = Field(default=None, description="Name or role of person responsible")
    due_date: str | None = Field(default=None, description="Due date or timeframe if specified")


class ParsedAgenda(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(description="Clear and concise meeting title")
    starts_at: str | None = Field(
        default=None,
        description="ISO-8601 formatted datetime with timezone (e.g. '2026-10-19T10:00:00+03:00')",
    )
    duration_minutes: int | None = Field(
        default=None, description="Total planned duration of the meeting in minutes"
    )
    items: list[AgendaItem] = Field(
        default_factory=list, description="List of agenda discussion topics/items in order"
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="Follow-up action items, deliverables, and tasks with assignees if mentioned",
    )
    language: str = Field(default="uk", description="Dominant language of the agenda (e.g. 'uk', 'en')")


RECORD_AGENDA = {
    "name": "record_agenda",
    "description": (
        "Extract and record structured meeting title, start time, duration, agenda items, and action items."
    ),
    "input_schema": ParsedAgenda.model_json_schema(),
}

SYSTEM_PROMPT = """You are an expert executive meeting assistant.
Your task is to analyze raw meeting text, notes, email, or chat messages, and extract a structured agenda.
Always call the record_agenda tool with the extracted data.
Preserve the language of the source text (Ukrainian, English, etc.).
If the text contains relative day/time references (such as 'Пн 10:00', 'завтра о 14:00', 'Friday at 3pm'),
calculate the exact starts_at ISO-8601 string based on the provided today date and timezone.
If duration is mentioned or implied, set duration_minutes.
Extract individual agenda discussion items and any action items / follow-ups with assignees."""


def parse_agenda(
    text: str,
    today: date | None = None,
    tz: str = "Europe/Kyiv",
    client: AnthropicBedrock | None = None,
) -> tuple[ParsedAgenda, dict[str, int]]:
    """Parse unstructured meeting text into a structured ParsedAgenda using Claude on Amazon Bedrock.

    Returns:
        (ParsedAgenda, usage_dict) where usage_dict contains 'input_tokens' and 'output_tokens'.
    """
    if today is None:
        today = date.today()

    if client is None:
        client = AnthropicBedrock(aws_region=settings.parser_region)

    weekday_name = today.strftime("%A")
    user_content = (
        f"Today is {weekday_name} {today.isoformat()} in timezone {tz}.\n\n"
        f"Please parse this meeting text and record the structured agenda:\n\n{text}"
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

    total_input_tokens = 0
    total_output_tokens = 0

    response = client.messages.create(
        model=settings.PARSER_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
        tools=[RECORD_AGENDA],
        tool_choice={"type": "tool", "name": "record_agenda"},
    )

    if response.usage:
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

    # Find the tool use block
    tool_use_block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_use_block is None:
        raise ValueError("Model did not call the record_agenda tool.")

    try:
        parsed = ParsedAgenda.model_validate(tool_use_block.input)
        return parsed, {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
    except ValidationError as exc:
        logger.warning("First validation attempt failed: %s. Retrying once with error feedback...", exc)
        # Attempt 1 retry with error feedback
        retry_messages = [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "is_error": True,
                        "content": (
                            f"Validation failed against the expected schema:\n{exc}\n"
                            "Please correct the data and call record_agenda with valid parameters."
                        ),
                    }
                ],
            },
        ]

        retry_response = client.messages.create(
            model=settings.PARSER_MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=retry_messages,
            tools=[RECORD_AGENDA],
            tool_choice={"type": "tool", "name": "record_agenda"},
        )

        if retry_response.usage:
            total_input_tokens += retry_response.usage.input_tokens
            total_output_tokens += retry_response.usage.output_tokens

        retry_block = next(
            (b for b in retry_response.content if getattr(b, "type", None) == "tool_use"), None
        )
        if retry_block is None:
            raise ValueError("Model did not call record_agenda on retry.") from exc

        parsed = ParsedAgenda.model_validate(retry_block.input)
        return parsed, {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
