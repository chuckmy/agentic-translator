# Agentic Translator

A research prototype implementing the four-stage agentic translation cycle described in Yamada (2026, forthcoming, *The Routledge Handbook of Translation and Technology*): **Identification → Prompting → Generation → Verification**, with interactive specification, document-level memory, and MQM-based quality verification.

## What it does

- **Stage 1 — Identification.** The model extracts skopos / audience / register / genre / stance from the source text as JSON.
- **Stage 2 — Prompting.** A deterministic prompt is assembled from the spec, references (glossary / paired examples / parallel texts / style guide), the situational analysis, and (for documents) running memory.
- **Stage 3 — Generation.** A single LLM call produces the draft translation.
- **Stage 4 — Verification.** A second LLM call returns MQM-style error spans (Freitag et al. 2021 categories: Accuracy / Fluency / Terminology / Style / Locale_convention / Other) with `critical / major / minor` severity. The verdict (`accept` / `revise`) is computed deterministically from `score = -25·critical -5·major -1·minor` against a configurable threshold (default −2). On `revise`, the error list is fed back as targeted refinement instructions for a second Stage 3 attempt (max 2 iterations).
- **Document-level memory (DelTA-lite, after Wang et al. ICLR 2025).** For multi-paragraph inputs, the document is chunked, and a proper-noun ledger + running bilingual summary persist across chunks for terminological and tonal consistency.
- **Interactive spec.** The model proposes an initial specification (markdown, ten sections grounded in Translation Studies); the user can edit it directly or refine it through chat; locking the spec enables the translation step.

## Architecture

```
app.py            — Streamlit UI (English / Japanese toggle)
pipeline.py       — 4-stage cycle + run_document_pipeline
spec_chat.py      — propose_spec + interactive refinement
memory.py         — DocumentMemory + update_memory
chunker.py        — paragraph splitting
references.py    — 4-category reference materials
api.py            — centralized API key handling (UI input or .env)
i18n.py           — UI translations (en / ja)
prompts/          — system prompts for each stage
specs/            — example style specifications
test_set/         — bilingual test set with glossaries, paired examples, style guides
```

## Requirements

- Python 3.9+ (tested on 3.9.6)
- An Anthropic API key (https://console.anthropic.com)

## Setup

```bash
git clone <this repo>
cd agentic_translator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You can supply your API key in either of two ways:

1. **Via the UI** (recommended for any deployment): leave `.env` empty or absent; the app will prompt you for the key in the sidebar (kept only in the browser session).
2. **Via `.env`** (developer convenience): copy `.env.example` to `.env` and fill in your key:
   ```
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ANTHROPIC_MODEL=claude-sonnet-4-6
   ```

## Run

```bash
source .venv/bin/activate
streamlit run app.py
```

Open http://localhost:8501/.

## Usage

1. (Optional) Upload reference materials in the **① Reference materials** section: glossary (TSV/CSV), paired examples (TSV/CSV), parallel target-language texts (TXT/MD), and a style guide (MD/TXT).
2. Paste the source text into **② Source text**. Multi-paragraph inputs activate document-level memory.
3. Click **Propose spec** (③) to draft a specification. Edit directly or refine through chat. Click **Use this spec** to lock.
4. Click **Translate** (④). Stage panels populate live, and the running terminology ledger appears between chunks.

A pre-made bilingual test set lives at `test_set/` — see `test_set/README.md` for suggested experiments.

## Citing the underlying ideas

The architecture draws on:

- **Yamada (2026, forthcoming)** — *The Routledge Handbook of Translation and Technology*, chapter on agentic translation and metalanguage as instruction code.
- **Kayano & Sugawara (WMT 2025)** — *Specification-Aware Machine Translation and Evaluation for Purpose Alignment* (arXiv:2509.17559).
- **Wang et al. (ICLR 2025)** — *DelTA: An Online Document-Level Translation Agent Based on Multi-Level Memory* (arXiv:2410.08143).
- **Kocmi & Federmann (WMT 2023)** — *GEMBA-MQM: Detecting Translation Quality Error Spans with GPT-4* (arXiv:2310.13988).
- **Freitag et al. (TACL 2021)** — *Experts, Errors, and Context: A Large-Scale Study of Human Evaluation for MT* (arXiv:2104.14478).
- **Wu et al. (TACL 2025)** — *(Perhaps) Beyond Human Translation: Harnessing Multi-Agent Collaboration for Translating Ultra-Long Literary Texts* (arXiv:2405.11804).

## License

TBD.

## Status

Research prototype. Not production-ready. Public deployment should require user-supplied API keys (default behavior when `.env` is absent).
