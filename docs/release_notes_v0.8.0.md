# Agentic AI Translate v0.8.0

Release date: 2026-05-16

## Summary

Version 0.8.0 turns the original Anthropic-only prototype into a provider-selectable research app that can run with either Anthropic Claude API or OpenAI API. It also adds downloadable run artifacts so that users can inspect and archive the intermediate reasoning and verification steps behind each translation.

## Highlights

- **Anthropic + OpenAI support**: choose the model provider in the sidebar.
- **OpenAI Responses API integration**: OpenAI calls use the current Responses API path.
- **Recommended model documentation**: README now lists the recommended Claude and OpenAI models as of 2026-05-16.
- **Downloadable outputs**: final translation, raw run data, raw run log, and Markdown run report can be downloaded.
- **Partial logs on failure**: if an API call fails midway, the run log collected so far can still be downloaded.
- **Safer auth errors**: authentication failures no longer surface raw provider exception text that may include key fragments.
- **Clearer workflow docs**: README now explains the spec proposal, spec locking, and translation execution sequence.

## Recommended Models

| Provider | Default recommendation | Higher-quality option |
|---|---|---|
| Anthropic Claude API | `claude-sonnet-4-6` | `claude-opus-4-7` |
| OpenAI API | `gpt-5.4-mini` | `gpt-5.4` |

The default recommendations favor a practical balance of quality, speed, and cost for a pipeline that makes multiple model calls per translation.

## Upgrade Notes

1. Pull the latest `main` branch or check out tag `v0.8.0`.
2. Reinstall dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. If using OpenAI, add `OPENAI_API_KEY` and optionally `OPENAI_MODEL` to `.env`, or enter the key in the sidebar.
4. If deploying on Streamlit Community Cloud, redeploy or reboot the app so the new `requirements.txt` is installed.

## Streamlit Community Cloud

The app entrypoint remains:

```text
app.py
```

The deployment should track:

```text
repo: chuckmy/agentic-translator
branch: main
file: app.py
```

No provider API key needs to be stored in Streamlit secrets for the public demo if users are expected to bring their own API key through the sidebar.

## Known Limitations

- Real translation quality depends on the selected provider, model, API availability, and user-supplied spec quality.
- The app stores runtime keys only in the Streamlit browser session, but downloaded logs may include source text, translations, verification findings, and reference-derived content.
- The current implementation does not stream model tokens; stage outputs appear after each call returns.
- The project remains a research prototype and is not hardened as a production translation service.
