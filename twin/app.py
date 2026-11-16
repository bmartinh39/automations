from pathlib import Path
import os
import sqlite3
from openai import OpenAI, OpenAIError
from context import TWIN_SYSTEM_PROMPT
from tools import tools, handle_tool_calls
from styles import CSS, JS
from privacy import public_reply
from dotenv import load_dotenv
import gradio as gr
from starlette.middleware import Middleware
from localization import (
    COPY, error_text, initial_history, language_from_request,
    language_instruction, normalize_language,
)
from safeguards import (
    MAX_MODEL_CALLS_PER_TURN, MAX_OUTPUT_TOKENS, MAX_TOOL_CALLS_PER_ROUND,
    RequestBodyLimit, UsageLimitError, UsageLimits, prepare_history, visitor_key,
)

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

MODEL_NAME = "gpt-5.4-mini"

openai = OpenAI(timeout=20.0, max_retries=0)
usage = UsageLimits(
    os.environ.get("TWIN_USAGE_DB", Path(__file__).resolve().parent / "data" / "usage.sqlite3")
)

system = [{"role": "system", "content": TWIN_SYSTEM_PROMPT}]


def chat(message, history, request: gr.Request, language="en"):
    language = normalize_language(language)
    copy = COPY[language]
    try:
        history = prepare_history(message, history)
    except ValueError as error:
        raise gr.Error(error_text(str(error), language)) from None
    try:
        visitor = visitor_key(request)
        usage.reserve("chat", visitor)
        messages = system + [
            {"role": "system", "content": language_instruction(language)}
        ] + history + [{"role": "user", "content": message}]
        for attempt in range(MAX_MODEL_CALLS_PER_TURN):
            usage.reserve("model", visitor)
            options = {
                "model": MODEL_NAME,
                "messages": messages,
                "max_completion_tokens": MAX_OUTPUT_TOKENS,
            }
            # The final request must answer without requesting more tools.
            if attempt < MAX_MODEL_CALLS_PER_TURN - 1:
                options["tools"] = tools
                options["parallel_tool_calls"] = False
            response = openai.chat.completions.create(**options)
            choice = response.choices[0]
            if choice.finish_reason != "tool_calls":
                return public_reply(choice.message.content or copy["incomplete"], language)
            calls = choice.message.tool_calls or []
            if attempt == MAX_MODEL_CALLS_PER_TURN - 1 or len(calls) > MAX_TOOL_CALLS_PER_ROUND:
                return copy["failed"]
            results = handle_tool_calls(calls, usage, visitor)
            messages.append(choice.message)
            messages.extend(results)
    except UsageLimitError as error:
        raise gr.Error(error_text(str(error), language)) from None
    except (OpenAIError, sqlite3.Error, ValueError):
        # Do not expose provider errors, credentials or database paths to visitors.
        raise gr.Error(copy["unavailable"]) from None


def description(language):
    language = normalize_language(language)
    copy = COPY[language]
    return (
        copy["description"] + "<br>"
        + f'<a href="https://borjamartin.com/{language}/" target="_self">{copy["back"]}</a>'
    )


def initialize_chat(request: gr.Request):
    language = language_from_request(request)
    copy = COPY[language]
    history = initial_history(language)
    return (
        language,
        gr.update(value="# " + copy["title"]),
        gr.update(value=description(language)),
        history, history, history,
        gr.update(placeholder=copy["placeholder"], interactive=True),
        gr.update(value=copy["new_chat"]),
        gr.update(samples=[[example] for example in copy["examples"]], label=copy["examples_label"]),
    )


def reset_chat(language):
    history = initial_history(language)
    return history, history, history, gr.update(value="", interactive=True)


def select_example(index, language):
    examples = COPY[normalize_language(language)]["examples"]
    if isinstance(index, int) and 0 <= index < len(examples):
        return examples[index]
    return ""


def build_demo():
    copy = COPY["en"]
    with gr.Blocks(title="Digital Twin", analytics_enabled=False) as demo:
        language = gr.State("en")
        heading = gr.Markdown("# " + copy["title"])
        intro = gr.Markdown(description("en"))
        examples = gr.Dataset(
            components=["textbox"],
            samples=[[example] for example in copy["examples"]],
            type="index", label=copy["examples_label"], elem_classes=["examples"],
        )
        interface = gr.ChatInterface(
            chat,
            chatbot=gr.Chatbot(show_label=False),
            textbox=gr.Textbox(
                placeholder=copy["placeholder"], show_label=False,
                interactive=False, submit_btn=True, stop_btn=True,
            ),
            additional_inputs=[language],
            concurrency_limit=2,
            api_visibility="private",
            analytics_enabled=False,
        )
        new_chat = gr.Button(copy["new_chat"], size="sm")
        demo.load(
            initialize_chat,
            outputs=[
                language, heading, intro,
                interface.chatbot, interface.chatbot_state, interface.chatbot_value,
                interface.textbox, new_chat, examples,
            ],
            queue=False, api_visibility="private",
        )
        new_chat.click(
            reset_chat, inputs=[language],
            outputs=[interface.chatbot, interface.chatbot_state, interface.chatbot_value, interface.textbox],
            queue=False, api_visibility="private",
        )
        examples.click(
            select_example, inputs=[examples, language], outputs=[interface.textbox],
            queue=False, api_visibility="private",
        )
    return demo.queue(max_size=8)


if __name__ == "__main__":
    build_demo().launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=False,
        app_kwargs={"middleware": [Middleware(RequestBodyLimit)]},
        css=CSS,
        js=JS,
        theme=gr.themes.Base(),
    )
