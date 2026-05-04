import json
import os
from typing import Type, TypeVar

from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

T = TypeVar("T", bound=BaseModel)


def call_llm(
    messages: list[dict],
    model: str = "gpt-5.4-nano",
    temperature: float = 0,
) -> str:
    """Call the OpenAI API and return the response content."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


def call_with_tool(
    messages: list[dict],
    schema: Type[T],
    model: str = "gpt-5.4-nano",
    temperature: float = 0,
    tool_name: str = "emit",
    tool_description: str = "Emit the structured result.",
) -> T:
    """Force the model to call a tool whose arguments match `schema`.

    Tool-calling guarantees the model returns JSON conforming to the supplied
    JSON schema. We then validate it with Pydantic for an extra safety net.
    """
    json_schema = schema.model_json_schema()
    tool = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": tool_description,
            "parameters": json_schema,
        },
    }
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": tool_name}},
    )
    tool_calls = response.choices[0].message.tool_calls or []
    if not tool_calls:
        raise RuntimeError(f"Model did not call required tool '{tool_name}'.")
    arguments = json.loads(tool_calls[0].function.arguments or "{}")
    return schema.model_validate(arguments)
