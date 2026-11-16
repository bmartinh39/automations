# Digital twin

Run locally from this directory with `uv sync --locked --no-dev` and `uv run --locked app.py`.
Secrets stay in the ignored local `.env`, or in `/opt/secrets/twin.env` on the VPS.
Do not print or commit secret values.

## Public profile and privacy

The model reads `profile.txt` and `summary.txt`; these must contain only approved public information.
The original LinkedIn PDF is preserved locally under the ignored `private/` directory and is never
loaded or included in the Docker build context. Contact lines have been removed from the public profile.
The only approved public email is `borja@borjamartin.com`, defined in `privacy.py` and supplied to the
system prompt. The response filter allows that exact address and its mailto link; other email/phone
patterns redirect to the approved professional email and website contact section. Phone numbers remain
blocked. This also filters visitor contact details from assistant replies rather than guessing ownership.
Removing the PDF in a new commit does not erase earlier Git commits or previously built images.

## Website language

Open `http://127.0.0.1:7860/?lang=es` or `?lang=en` after restarting the local server.
The greeting, heading, return link, input placeholder, new-conversation button, examples,
and application errors follow the selected language. Missing/unsupported values default to English.
The language lives in Gradio session state; simultaneous visitors do not change each other's language.
Replies default to the page language, while explicit requests to switch language are allowed.
The greeting is predefined and uses no model request. New conversation restores it without resetting quotas.
Example clicks fill the input; they make no paid request until submitted.

## Public usage safeguards

- 5 chat submissions per session per rolling minute; 20 site-wide.
- 200 model requests per UTC day, including failed requests; SDK retries disabled.
- 3 model requests per turn; the final request offers no tools.
- 2 tool calls per intermediate response; validated names and bounded text arguments.
- 800 completion tokens per model request; 20-second SDK timeout.
- User messages: 2,000 characters. Submitted history: 24 messages / 24,000 characters.
  Only user/assistant text is accepted. The model gets the latest 12 messages fitting 12,000 characters.
- 2 concurrent queued callbacks; 8 waiting requests.
- HTTP bodies: 64 KiB maximum, read within 10 seconds, before Gradio parses them.
- Pushover: 1 per rolling minute, 10 per UTC day, 2 per session per day; failed attempts count.
  Connection/read timeouts are set and failed notifications never report success.
- Provider/database errors return generic messages; application logs omit keys and visitor details.

Atomic SQLite quotas live at `/app/data/usage.sqlite3` in the `twin_usage` Compose volume.
Rebuilds/restarts preserve counters. Do not delete the volume during deployment.
`TWIN_USAGE_DB` selects an isolated local test file. The image gives UID 10001 ownership of the data directory.
Session IDs are client-controlled fairness measures; changing them cannot bypass site-wide caps.
These caps bound request/token volume, not currency spending or every denial-of-service attack.
Queue/concurrency limits assume one application process/container. Review shared state before adding replicas.

## Verification

From `twin/`, run `uv run --locked python -m unittest discover -s tests -v`.
Tests mock dotenv, OpenAI and notification requests; no real keys or paid API calls are used.
From the repository root, build with `docker build -t borja-twin:local ./twin`.
Production deployment remains through GitHub Actions after an approved merge to main.

## Proposed public Caddy route

Apply as a separate authorized infrastructure step after deploying the safeguards:

```caddy
twin.borjamartin.com {
    request_body {
        max_size 64KiB
    }
    reverse_proxy twin:7860
}
```

No visitor password is required. Validate the complete Caddyfile before reloading.
The proxy body limit adds early rejection; the application independently enforces it.
