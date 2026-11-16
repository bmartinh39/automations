from pathlib import Path
import json
import os
import re
import sqlite3
import requests
from dotenv import load_dotenv
from safeguards import UsageLimitError

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

pushover_user = os.getenv("PUSHOVER_USER")
pushover_token = os.getenv("PUSHOVER_TOKEN")

pushover_url = "https://api.pushover.net/1/messages.json"


def push(text, usage, visitor):
    if not pushover_user or not pushover_token:
        return "Notification unavailable."
    try:
        # Reserve before sending; failures still consume a slot to prevent retry storms.
        usage.reserve("notification", visitor)
        response = requests.post(
            pushover_url,
            data={"token": pushover_token, "user": pushover_user, "message": text[:1000]},
            timeout=(3, 5),
        )
        response.raise_for_status()
        if response.json().get("status") != 1:
            return "Notification unavailable."
    except (UsageLimitError, requests.RequestException, ValueError, sqlite3.Error):
        return "Notification unavailable or temporarily limited."
    return "OK"


def record_user_details(email, name="Name not provided", notes="not provided", *, usage, visitor):
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return "Please provide a valid email address."
    return push(f"Interest from {name[:100]}, email {email}, notes {notes[:500]}", usage, visitor)


def record_unknown_question(question, *, usage, visitor):
    return push(f"Unanswered question: {question[:500]}", usage, visitor)


record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The email address of this user"},
            "name": {"type": "string", "description": "The user's name, if they provided it"},
            "notes": {
                "type": "string",
                "description": "Any additional info about the conversation that's worth recording to give context",
            },
        },
        "required": ["email"],
        "additionalProperties": False,
    },
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question that couldn't be answered"},
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}

tools = [
    {"type": "function", "function": record_user_details_json},
    {"type": "function", "function": record_unknown_question_json},
]

tool_map = {
    "record_user_details": record_user_details,
    "record_unknown_question": record_unknown_question,
}


def handle_tool_calls(tool_calls, usage, visitor):
    results = []
    for tool_call in tool_calls:
        name = tool_call.function.name
        schema = next((item["function"] for item in tools if item["function"]["name"] == name), None)
        result = "Invalid tool request."
        try:
            raw = tool_call.function.arguments
            if schema is None or not isinstance(raw, str) or len(raw) > 2000:
                raise ValueError("Invalid arguments")
            arguments = json.loads(raw)
            parameters = schema["parameters"]
            if (
                not isinstance(arguments, dict)
                or not set(arguments).issubset(parameters["properties"])
                or not set(parameters["required"]).issubset(arguments)
                or not all(isinstance(value, str) and len(value) <= 1000 for value in arguments.values())
            ):
                raise ValueError("Invalid arguments")
            result = tool_map[name](**arguments, usage=usage, visitor=visitor)
        except (ValueError, TypeError):
            pass
        results.append({"role": "tool", "content": json.dumps(result), "tool_call_id": tool_call.id})
    return results
