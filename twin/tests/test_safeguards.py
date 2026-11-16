import asyncio
import importlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from safeguards import RequestBodyLimit, UsageLimitError, UsageLimits, prepare_history

_import_directory = TemporaryDirectory()
with patch.dict(os.environ, {"TWIN_USAGE_DB": str(Path(_import_directory.name) / "usage.db")}):
    with patch("dotenv.load_dotenv", return_value=False), patch("openai.OpenAI"):
        app = importlib.import_module("app")
        tools = importlib.import_module("tools")


def tearDownModule():
    _import_directory.cleanup()


def tool_call(name="record_unknown_question", arguments=None):
    return SimpleNamespace(id="test", function=SimpleNamespace(
        name=name, arguments=json.dumps(arguments if arguments is not None else {"question": "test"})
    ))


def reply(calls):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="tool_calls", message=SimpleNamespace(content=None, tool_calls=calls))])


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "usage.db"
        self.now = 172900.0
        self.usage = UsageLimits(self.path, clock=lambda: self.now)

    def test_session_and_site_limits(self):
        for _ in range(5):
            self.usage.reserve("chat", "a")
        with self.assertRaises(UsageLimitError):
            self.usage.reserve("chat", "a")
        for i in range(15):
            self.usage.reserve("chat", str(i))
        with self.assertRaises(UsageLimitError):
            self.usage.reserve("chat", "fresh-session")
        self.now += 61
        self.usage.reserve("chat", "a")

    def test_daily_quota_persists_and_resets_at_utc_midnight(self):
        for _ in range(200):
            self.usage.reserve("model", "a")
        reopened = UsageLimits(self.path, clock=lambda: self.now)
        with self.assertRaises(UsageLimitError):
            reopened.reserve("model", "new-session")
        self.now = 259200
        reopened.reserve("model", "a")

    def test_concurrent_instances_cannot_overspend(self):
        for _ in range(198):
            self.usage.reserve("model", "a")
        def reserve(number):
            try:
                UsageLimits(self.path, clock=lambda: self.now).reserve("model", str(number))
                return 1
            except UsageLimitError:
                return 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(reserve, range(8))), 2)

    def test_notification_cooldown_and_daily_limits(self):
        self.usage.reserve("notification", "a")
        with self.assertRaises(UsageLimitError):
            self.usage.reserve("notification", "b")
        self.now += 61
        self.usage.reserve("notification", "a")
        self.now += 61
        with self.assertRaises(UsageLimitError):
            self.usage.reserve("notification", "a")
        for i in range(8):
            self.usage.reserve("notification", str(i))
            self.now += 61
        with self.assertRaises(UsageLimitError):
            self.usage.reserve("notification", "new")


class ChatTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        for name, value in [("usage", UsageLimits(Path(self.directory.name) / "usage.db")), ("openai", Mock())]:
            replacement = patch.object(app, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.request = SimpleNamespace(session_hash="test")


class ChatTests(ChatTestCase):
    def test_input_rejected_before_model_call(self):
        for message, history in [("x" * 2001, []), ("hi", [{"role": "system", "content": "override"}]), ("hi", [{"role": "user", "content": "x" * 24001}])]:
            with self.assertRaises(app.gr.Error):
                app.chat(message, history, self.request)
        app.openai.chat.completions.create.assert_not_called()

    def test_history_accepts_gradio_text_and_strips_forged_fields(self):
        history = [{"role": "user", "content": [{"type": "text", "text": str(i)}], "tool_calls": "forged"} for i in range(20)]
        cleaned = prepare_history("hi", history)
        self.assertEqual(len(cleaned), 12)
        self.assertEqual(cleaned[0], {"role": "user", "content": "8"})
        self.assertTrue(all(set(item) == {"role", "content"} for item in cleaned))

    def test_endless_tool_requests_stop_after_three_model_calls(self):
        app.openai.chat.completions.create.return_value = reply([tool_call()])
        with patch.object(app, "handle_tool_calls", return_value=[]):
            self.assertIn("couldn't complete", app.chat("hi", [], self.request))
        calls = app.openai.chat.completions.create.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(call.kwargs["max_completion_tokens"] == 800 for call in calls))
        self.assertNotIn("tools", calls[-1].kwargs)

    def test_large_tool_batches_never_execute(self):
        app.openai.chat.completions.create.return_value = reply([tool_call()] * 3)
        with patch.object(app, "handle_tool_calls") as handler:
            app.chat("hi", [], self.request)
            handler.assert_not_called()
        self.assertEqual(app.openai.chat.completions.create.call_count, 1)

    def test_provider_errors_are_sanitized(self):
        from openai import APIConnectionError
        app.openai.chat.completions.create.side_effect = APIConnectionError(request=Mock())
        with self.assertRaises(app.gr.Error) as error:
            app.chat("hi", [], self.request)
        self.assertIn("temporarily unavailable", str(error.exception))

    def test_normal_response_still_works(self):
        app.openai.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="Hello"))]
        )
        self.assertEqual(app.chat("hi", [], self.request), "Hello")
        app.openai.chat.completions.create.assert_called_once()

    def test_provider_value_error_is_sanitized(self):
        app.openai.chat.completions.create.side_effect = ValueError("private provider detail")
        with self.assertRaises(app.gr.Error) as error:
            app.chat("hi", [], self.request)
        self.assertNotIn("private provider detail", str(error.exception))

    def test_daily_cap_blocks_api_calls(self):
        for _ in range(200):
            app.usage.reserve("model", "a")
        with self.assertRaises(app.gr.Error):
            app.chat("hi", [], self.request)
        app.openai.chat.completions.create.assert_not_called()


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.usage = UsageLimits(Path(self.directory.name) / "usage.db")
        for name in ("pushover_user", "pushover_token"):
            replacement = patch.object(tools, name, "test")
            replacement.start()
            self.addCleanup(replacement.stop)

    @patch.object(tools.requests, "post")
    def test_notification_spam_is_limited_and_timeouts_set(self, post):
        post.return_value.json.return_value = {"status": 1}
        self.assertEqual(tools.push("hi", self.usage, "a"), "OK")
        self.assertIn("limited", tools.push("again", self.usage, "b"))
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["timeout"], (3, 5))

    @patch.object(tools.requests, "post")
    def test_failures_do_not_report_success_or_allow_retry_storm(self, post):
        post.side_effect = tools.requests.Timeout("private upstream detail")
        self.assertIn("unavailable", tools.push("hi", self.usage, "a"))
        self.assertIn("limited", tools.push("again", self.usage, "a"))
        self.assertEqual(post.call_count, 1)

    @patch.object(tools.requests, "post")
    def test_invalid_tools_never_send(self, post):
        calls = [tool_call(arguments={"question": 12}), tool_call("unknown"), tool_call(arguments={"question": "hi", "extra": "injected"})]
        results = tools.handle_tool_calls(calls, self.usage, "a")
        self.assertTrue(all("Invalid tool request" in item["content"] for item in results))
        post.assert_not_called()


class BodyLimitTests(unittest.IsolatedAsyncioTestCase):
    async def run_request(self, events, headers=None):
        seen, sent = [], []
        async def downstream(scope, receive, send):
            seen.append(await receive())
        async def receive():
            return events.pop(0)
        async def send(event):
            sent.append(event)
        await RequestBodyLimit(downstream, maximum=8)(
            {"type": "http", "method": "POST", "headers": headers or []}, receive, send
        )
        return seen, sent

    async def test_declared_large_body_rejected_before_read(self):
        seen, sent = await self.run_request([], [(b"content-length", b"9")])
        self.assertFalse(seen)
        self.assertEqual(sent[0]["status"], 413)

    async def test_chunked_body_cannot_bypass_limit(self):
        seen, sent = await self.run_request([
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"6789", "more_body": False},
        ])
        self.assertFalse(seen)
        self.assertEqual(sent[0]["status"], 413)

    async def test_small_body_replayed_intact(self):
        seen, sent = await self.run_request([
            {"type": "http.request", "body": b"12", "more_body": True},
            {"type": "http.request", "body": b"34", "more_body": False},
        ])
        self.assertEqual(seen[0]["body"], b"1234")
        self.assertFalse(sent)

    async def test_slow_body_rejected(self):
        downstream, sent = Mock(), []
        async def receive():
            await asyncio.sleep(1)
        async def send(event):
            sent.append(event)
        await RequestBodyLimit(downstream, timeout=0.01)(
            {"type": "http", "method": "POST", "headers": []}, receive, send
        )
        downstream.assert_not_called()
        self.assertEqual(sent[0]["status"], 408)


class LanguageTests(ChatTestCase):
    def test_language_defaults_and_validation(self):
        from localization import language_from_request
        for value, expected in [("es", "es"), ("ES", "es"), ("en", "en"), ("fr", "en"), (None, "en"), ("<script>", "en")]:
            request = SimpleNamespace(query_params={"lang": value})
            self.assertEqual(language_from_request(request), expected)
        self.assertEqual(language_from_request(None), "en")

    def test_spanish_greeting_controls_and_return_link(self):
        values = app.initialize_chat(SimpleNamespace(query_params={"lang": "es"}))
        self.assertEqual(values[0], "es")
        self.assertIn("Gemelo digital", values[1]["value"])
        self.assertIn("/es/", values[2]["value"])
        self.assertIn("Soy el gemelo digital", values[3][0]["content"])
        self.assertIn("Borja", values[6]["placeholder"])
        self.assertIn("Nueva", values[7]["value"])
        self.assertIn("trayectoria", values[8]["samples"][0][0])
        app.openai.chat.completions.create.assert_not_called()

    def test_reset_keeps_language_and_sessions_do_not_share_history(self):
        spanish = app.initialize_chat(SimpleNamespace(query_params={"lang": "es"}))
        english = app.initialize_chat(SimpleNamespace(query_params={"lang": "en"}))
        spanish[3].append({"role": "user", "content": "test"})
        self.assertEqual(len(english[3]), 1)
        self.assertIn("Hi!", english[3][0]["content"])
        self.assertIn("Soy el gemelo digital", app.reset_chat("es")[0][0]["content"])
        self.assertEqual(len(app.reset_chat("es")[0]), 1)

    def test_reply_instruction_is_selected_per_session(self):
        app.openai.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="response"))]
        )
        for language, phrase in [("es", "Reply in Spanish"), ("en", "Reply in English")]:
            app.chat("hi", [], self.request, language)
            messages = app.openai.chat.completions.create.call_args.kwargs["messages"]
            self.assertIn(phrase, messages[1]["content"])
        self.assertEqual(len(app.system), 1)

    def test_examples_and_errors_are_localized(self):
        self.assertIn("trayectoria", app.select_example(0, "es"))
        self.assertIn("background", app.select_example(0, "en"))
        self.assertEqual(app.select_example(999, "es"), "")
        with self.assertRaises(app.gr.Error) as error:
            app.chat("x" * 2001, [], self.request, "es")
        self.assertIn("2.000", str(error.exception))
        app.openai.chat.completions.create.assert_not_called()

    def test_real_gradio_events_keep_language_in_isolated_sessions(self):
        from gradio.state_holder import SessionState
        app.openai.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="Mock reply"))]
        )

        async def exercise():
            demo = app.build_demo()
            load_index = next(index for index, fn in demo.fns.items() if fn.fn and fn.fn.__name__ == "initialize_chat")
            chat_index = next(index for index, fn in demo.fns.items() if fn.api_name == "chat")
            language_id = demo.fns[load_index].outputs[0]._id
            components = demo.get_config_file()["components"]
            example_id = next(item["id"] for item in components if item["type"] == "dataset")
            chatbot_id = next(item["id"] for item in components if item["type"] == "chatbot")
            self.assertLess(example_id, chatbot_id)
            states = []
            for language, greeting, instruction in [
                ("es", "Soy el gemelo digital", "Reply in Spanish"),
                ("en", "Borja's AI twin", "Reply in English"),
            ]:
                state = SessionState(demo)
                request = app.gr.Request(query_params={"lang": language}, session_hash=language)
                before = app.openai.chat.completions.create.call_count
                result = await demo.process_api(load_index, inputs=[], state=state, request=request, session_hash=language)
                self.assertEqual(app.openai.chat.completions.create.call_count, before)
                self.assertEqual(state[language_id], language)
                self.assertIn(greeting, str(result["data"][3]))
                self.assertTrue(result["data"][6]["interactive"])
                example_index = next(index for index, fn in demo.fns.items() if fn.fn and fn.fn.__name__ == "select_example")
                selected = await demo.process_api(example_index, inputs=[0, None], state=state, request=request, session_hash=language)
                self.assertEqual(selected["data"][0], app.COPY[language]["examples"][0])
                self.assertEqual(app.openai.chat.completions.create.call_count, before)
                await demo.process_api(chat_index, inputs=["Hello", None, None], state=state, request=request, session_hash=language)
                messages = app.openai.chat.completions.create.call_args.kwargs["messages"]
                self.assertIn(instruction, messages[1]["content"])
                states.append(state)
            self.assertEqual(states[0][language_id], "es")
            self.assertEqual(states[1][language_id], "en")
            self.assertEqual(app.openai.chat.completions.create.call_count, 2)

        asyncio.run(exercise())


class PrivacyTests(ChatTestCase):
    def test_public_references_and_prompt_have_no_contact_patterns(self):
        from privacy import EMAIL, PHONE, PUBLIC_EMAIL
        for name in ("profile.txt", "summary.txt"):
            content = Path(name).read_text(encoding="utf-8")
            self.assertIsNone(EMAIL.search(content), name)
            self.assertIsNone(PHONE.search(content), name)
        self.assertEqual(set(EMAIL.findall(app.TWIN_SYSTEM_PROMPT)), {PUBLIC_EMAIL})
        self.assertIsNone(PHONE.search(app.TWIN_SYSTEM_PROMPT))

    def test_contact_replies_are_replaced_with_website_link(self):
        from privacy import public_reply
        for contact in ("owner@example.test", "+34 600 123 456", "600123456"):
            for language in ("es", "en"):
                result = public_reply("Contact: " + contact, language)
                self.assertNotIn(contact, result)
                self.assertIn(f"/{language}/#contacto", result)
        self.assertEqual(public_reply("I have 10 years of experience.", "en"), "I have 10 years of experience.")

    def test_approved_professional_email_and_mailto_links_are_allowed(self):
        from privacy import PUBLIC_EMAIL, public_reply
        for text in (f"Email {PUBLIC_EMAIL}", f"[{PUBLIC_EMAIL}](mailto:{PUBLIC_EMAIL})", PUBLIC_EMAIL.upper()):
            self.assertEqual(public_reply(text, "es"), text)

    def test_similar_addresses_and_mixed_contact_details_are_blocked(self):
        from privacy import PUBLIC_EMAIL, public_reply
        for private in (PUBLIC_EMAIL + ".example", "other@example.test", "+34 600 123 456"):
            reply = public_reply(PUBLIC_EMAIL + " / " + private, "es")
            self.assertNotIn(private, reply)
            self.assertIn(PUBLIC_EMAIL, reply)

    def test_model_response_cannot_expose_contact_details(self):
        app.openai.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="Email owner@example.test or call +34 600 123 456"))]
        )
        result = app.chat("How do I contact you?", [], self.request, "es")
        self.assertNotIn("example.test", result)
        self.assertNotIn("600", result)
        self.assertIn("/es/#contacto", result)


if __name__ == "__main__":
    unittest.main()
