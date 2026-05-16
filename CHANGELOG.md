# Changelog

## v0.8.0 - 2026-05-16

### Added

- Added provider selection for Anthropic Claude API and OpenAI API.
- Added OpenAI Responses API support through a shared provider abstraction.
- Added recommended model guidance to `README.md` and `README_ja.md`.
- Added runtime API key handling for each provider in the Streamlit sidebar.
- Added final translation download as `.txt`.
- Added full run data download as `.json`.
- Added run-event logging with `.json` and `.md` downloads.
- Added partial run-log download support for failed runs.
- Added safer provider authentication error messages that do not expose API key fragments.

### Changed

- Renamed the visible app title to **Agentic AI Translate**.
- Reworked pipeline, spec chat, and memory update calls to use the shared `api.call_model()` interface.
- Updated local API connectivity test to work with the selected provider.
- Updated documentation workflow steps to describe spec proposal, spec locking, and translation execution more explicitly.

### Fixed

- Hardened Streamlit session-state migration for older sessions that only stored a single API key.
- Hardened Streamlit session-state initialization for missing or invalid provider state.
- Made Markdown run reports more readable instead of embedding raw JSON blocks throughout.

### Notes

- The recommended default models as of 2026-05-16 are `claude-sonnet-4-6` for Anthropic and `gpt-5.4-mini` for OpenAI.
- `.env` remains ignored and must not be committed. Use `.env.example` as the public template.
- The app is still a research prototype, not a production translation service.
