import logging
from datetime import date
from typing import Any

from anthropic import AnthropicBedrock
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)


class AgendaItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(description="Agenda item title")
    duration_minutes: int | None = Field(default=None, description="Duration in minutes")
    description: str | None = Field(default=None, description="Discussion points")


class ActionItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    task: str = Field(description="Task description")
    assignee: str | None = Field(default=None, description="Person responsible")
    due_date: str | None = Field(default=None, description="Due date")


class ParsedAgenda(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(description="Meeting title")
    starts_at: str | None = Field(
        default=None,
        description="ISO-8601 datetime with timezone",
    )
    duration_minutes: int | None = Field(default=None, description="Duration in minutes")
    items: list[AgendaItem] = Field(default_factory=list, description="Agenda topics")
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="Action items and follow-ups",
    )
    language: str = Field(default="uk", description="Dominant language (uk, en)")


RECORD_AGENDA = {
    "name": "record_agenda",
    "description": "Extract structured meeting agenda.",
    "input_schema": ParsedAgenda.model_json_schema(),
}

SYSTEM_PROMPT = (
    "Extract meeting agenda into record_agenda. "
    "Resolve relative dates/times to ISO-8601 starts_at using provided today date and timezone. "
    "Preserve source language (uk, en). "
    "Return title, starts_at, duration_minutes, items, action_items, language."
)


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
        max_tokens=400,
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
            max_tokens=400,
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
