import asyncio
from contextlib import closing
import hashlib
import sqlite3
import time
from pathlib import Path

MAX_MESSAGE_CHARS = 2000
MAX_HISTORY_MESSAGES = 24
MAX_HISTORY_CHARS = 24000
MAX_CONTEXT_MESSAGES = 12
MAX_CONTEXT_CHARS = 12000
MAX_MODEL_CALLS_PER_TURN = 3
MAX_TOOL_CALLS_PER_ROUND = 2
MAX_OUTPUT_TOKENS = 800


class UsageLimitError(Exception):
    pass


class UsageLimits:
    """Atomic quotas shared by all threads and retained across restarts."""

    def __init__(self, path, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS usage "
                "(kind TEXT NOT NULL, visitor TEXT NOT NULL, created REAL NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS usage_lookup ON usage(kind, created)"
            )

    def reserve(self, kind, visitor):
        now = self.clock()
        day_start = now - now % 86400
        rules = {
            "chat": [(now - 60, 20, None), (now - 60, 5, visitor)],
            "model": [(day_start, 200, None)],
            "notification": [
                (now - 60, 1, None),
                (day_start, 10, None),
                (day_start, 2, visitor),
            ],
        }
        with closing(sqlite3.connect(self.path, timeout=5)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM usage WHERE created < ?", (day_start - 86400,))
            for since, maximum, client in rules[kind]:
                query = "SELECT count(*) FROM usage WHERE kind = ? AND created >= ?"
                params = [kind, since]
                if client is not None:
                    query += " AND visitor = ?"
                    params.append(client)
                count = connection.execute(query, params).fetchone()[0]
                if count >= maximum:
                    if kind == "model":
                        raise UsageLimitError(
                            "The twin has reached today's usage limit. Please try again tomorrow."
                        )
                    raise UsageLimitError("Too many requests. Please try again later.")
            connection.execute(
                "INSERT INTO usage VALUES (?, ?, ?)", (kind, visitor, now)
            )


def visitor_key(request):
    # Session IDs are only a fairness measure. Global quotas do not trust them.
    session = getattr(request, "session_hash", None) or "unknown"
    return hashlib.sha256(str(session)[:128].encode()).hexdigest()


def text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(
        isinstance(part, dict)
        and part.get("type") == "text"
        and isinstance(part.get("text"), str)
        for part in content
    ):
        return "\n".join(part["text"] for part in content)
    raise ValueError("Only text messages are supported.")


def prepare_history(message, history):
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Please enter a message.")
    if len(message) > MAX_MESSAGE_CHARS:
        raise ValueError("Please keep your message under 2,000 characters.")
    if not isinstance(history, list) or len(history) > MAX_HISTORY_MESSAGES:
        raise ValueError("Please start a new conversation to continue.")
    cleaned = []
    total = 0
    for item in history:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
            raise ValueError("Please start a new conversation to continue.")
        content = text_content(item.get("content"))
        total += len(content)
        if total > MAX_HISTORY_CHARS:
            raise ValueError("Please start a new conversation to continue.")
        # Copy only the fields the model should receive from browser history.
        cleaned.append({"role": item["role"], "content": content})
    kept = []
    remaining = MAX_CONTEXT_CHARS
    for item in reversed(cleaned[-MAX_CONTEXT_MESSAGES:]):
        if len(item["content"]) > remaining:
            break
        kept.append(item)
        remaining -= len(item["content"])
    return list(reversed(kept))


class RequestBodyLimit:
    """Reject large or slow request bodies before Gradio parses them."""

    def __init__(self, app, maximum=65536, timeout=10):
        self.app = app
        self.maximum = maximum
        self.timeout = timeout

    async def reject(self, send, status):
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b"Request rejected."})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    size = int(value)
                except ValueError:
                    return await self.reject(send, 400)
                if size < 0:
                    return await self.reject(send, 400)
                if size > self.maximum:
                    return await self.reject(send, 413)
        body = bytearray()
        try:
            async with asyncio.timeout(self.timeout):
                while True:
                    event = await receive()
                    if event["type"] == "http.disconnect":
                        return
                    body.extend(event.get("body", b""))
                    if len(body) > self.maximum:
                        return await self.reject(send, 413)
                    if not event.get("more_body", False):
                        break
        except TimeoutError:
            return await self.reject(send, 408)
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
