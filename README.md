# Agentic AI Translate

> A research prototype that treats translation as **communication design**, not text-to-text conversion — implementing the four-stage agentic translation cycle (Identify → Prompt → Generate → Verify) grounded in Translation Studies metalanguage.

🌐 **Live demo:** https://agentic-translator-chuckmy.streamlit.app
📄 **日本語版:** [README_ja.md](README_ja.md)
🚀 **Current version:** [v0.10.1](https://github.com/chuckmy/agentic-translator/releases/latest) — TranslationModel + Engine (lock & compile) · Company-shared deployment mode
🏢 **Self-host for a team:** see [docs/deploy-tailscale.md](docs/deploy-tailscale.md) for a Tailscale-fronted localhost deployment (recommended for small LSP teams up to ~20 translators)

---

## What this is

Generic machine translation tools (DeepL, Google Translate, etc.) treat translation as **a conversion problem**: source text in, target text out, optimized for accuracy. But as Yamada (forthcoming) argues in his chapter *Metalanguage and GenAI: Empowering Language Learners and Translators in Training* (in *The Routledge Handbook of Translation and Technology*, 2nd ed.), accuracy is no longer where the value of translation lives:

> "The easier it becomes to generate text, the harder it becomes to ensure that text fulfils a specific communicative purpose."

What separates a good translation from a serviceable one — register, audience fit, voice, cultural framing — has always been a matter of **design decisions**, not lexical accuracy. Generative AI now lets us treat those decisions as **explicit, machine-readable instructions** rather than tacit artisanal knowledge.

This prototype is an attempt to operationalize that idea: it asks the user to author a translation specification (with the model's help) **before** any translation is produced, then runs an agentic four-stage pipeline that uses that specification end-to-end.

## The four-stage cycle

```
        ┌─────────────────────────────────────────────────────────┐
        │  ① Identification    Skopos · Audience · Register ·     │
        │                      Genre · Stance  →  JSON            │
        ├─────────────────────────────────────────────────────────┤
        │  ② Prompting         Spec + References + Identification │
        │                      → deterministic prompt assembly    │
        ├─────────────────────────────────────────────────────────┤
        │  ③ Generation        LLM call → draft translation       │
        ├─────────────────────────────────────────────────────────┤
        │  ④ Verification      MQM error spans (Freitag 2021):    │
        │                      Accuracy / Fluency / Terminology / │
        │                      Style / Locale → score → verdict   │
        │                      (revise → ② if score below thresh) │
        └─────────────────────────────────────────────────────────┘
```

Around this core, three additional layers:

- **Interactive specification.** Before any translation runs, the model proposes a markdown specification (skopos, audience, register, genre, terminology guidance, style decisions, things to preserve / localize / avoid, open questions). The user edits it directly or refines it through chat ("audience is K-pop fans aged 15–25", "use だ・である調 for formal register"). Translation is gated until the user explicitly locks the spec.
- **Reference materials.** Glossaries, paired translation examples, parallel target-language texts, and free-form style guides can be uploaded; they are injected into the spec proposal, the translation prompt, and the verifier.
- **Document-level memory (DelTA-lite).** For multi-paragraph inputs, the document is chunked at paragraph boundaries, and a proper-noun ledger plus a running bilingual summary persist across chunks so that terminology and voice stay consistent.

## What makes this different

| Conventional MT | This prototype |
|---|---|
| Single function: text → text | Spec-authoring + translation + verification |
| Style and audience are implicit | Style and audience are **explicit fields** the user composes |
| Fixed quality dimension (accuracy) | MQM-typed errors with severity-weighted score |
| Stateless across chunks | Persistent terminology + summary across the document |
| Black-box evaluation | Error spans cited verbatim; verdict computed deterministically |
| User cannot direct strategy | User chats with the planner to compose the spec |

## Theoretical grounding

The architecture reflects the framework developed in:

> Yamada, M. (forthcoming). Metalanguage and GenAI: Empowering language learners and translators in training. In *The Routledge Handbook of Translation and Technology* (2nd ed.).

Specifically, the chapter's argument that **the vocabulary of Translation Studies is now the instruction code for the machine** — skopos, register, audience, equivalence, foreignization, domestication, genre — is what motivates the explicit, structured specification at the centre of this app.

The prototype also draws on:

- Kocmi, T. & Federmann, C. (2023). [GEMBA-MQM: Detecting Translation Quality Error Spans with GPT-4](https://arxiv.org/abs/2310.13988). *WMT 2023.* — for the MQM-typed verifier.
- Freitag, M., Foster, G., Grangier, D., Ratnakar, V., Tan, Q., & Macherey, W. (2021). [Experts, Errors, and Context: A Large-Scale Study of Human Evaluation for Machine Translation](https://arxiv.org/abs/2104.14478). *TACL.* — for the error category set and severity weights.
- Wang, Y. et al. (2024). [DelTA: An Online Document-Level Translation Agent Based on Multi-Level Memory](https://arxiv.org/abs/2410.08143). *ICLR 2025.* — for the persistent proper-noun ledger and running summary.
- Kayano, S. & Sugawara, Y. (2025). [Specification-Aware Machine Translation and Evaluation for Purpose Alignment](https://arxiv.org/abs/2509.17559). *WMT 2025.* — the closest precedent for spec-driven LLM translation.
- Wu, M. et al. (2024/2025). [(Perhaps) Beyond Human Translation: Harnessing Multi-Agent Collaboration for Translating Ultra-Long Literary Texts](https://arxiv.org/abs/2405.11804). *TACL.* — for role-decomposed agentic translation.

## Architecture

```
agentic_translator/
├── app.py                    Streamlit UI (English / Japanese toggle)
├── pipeline.py               4-stage cycle + run_document_pipeline
├── spec_chat.py              propose_spec + interactive refinement
├── memory.py                 DocumentMemory + update_memory (DelTA-lite)
├── chunker.py                paragraph splitting
├── references.py             4-category reference handling
├── api.py                    provider selection + API key management
├── i18n.py                   UI translations (en / ja)
├── prompts/
│   ├── identify.txt          Stage 1 — situational analysis
│   ├── translate.txt         Stage 3 template
│   ├── verify.txt            Stage 4 — MQM error span extraction
│   ├── propose_spec.txt      initial spec generation
│   ├── refine_spec.txt       chat-based spec refinement
│   └── update_memory.txt     proper-noun + summary update
├── specs/                    sample style specifications
├── test_set/                 bilingual test set (3 genres × 2 directions)
└── requirements.txt
```

## Quick start

### Try the live demo

Open https://agentic-translator-chuckmy.streamlit.app, choose Anthropic or OpenAI in the sidebar, and supply your own API key (kept only in your browser session). You will need an API key from the selected provider.

### Run locally

```bash
git clone https://github.com/chuckmy/agentic-translator.git
cd agentic-translator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Choose a provider and either set its key in .env (see .env.example)
# or enter it in the UI sidebar.
streamlit run app.py
```

Open http://localhost:8501.

### Recommended API models

As of **2026-05-16**, the default recommended models are:

| Provider | Recommended default | Higher-quality option | Notes |
|---|---|---|---|
| Anthropic Claude API | `claude-sonnet-4-6` | `claude-opus-4-7` | Sonnet is the practical default for quality, speed, and cost. Use Opus for the most difficult literary or long-form work. |
| OpenAI API | `gpt-5.4-mini` | `gpt-5.4` | Mini is the practical default because this app makes multiple calls per run. Use GPT-5.4 when quality matters more than cost/latency. |

Set these in `.env` if you do not want to enter keys in the sidebar:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-sonnet-4-6

# or

LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
```

Model availability changes over time. Check the official docs if a model name stops working: [OpenAI models](https://developers.openai.com/api/docs/models) and [Claude model IDs](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions).

### Workflow

1. (Optional) Upload reference materials in **① Reference materials**.
2. In the sidebar, choose **Model provider** (`Anthropic` or `OpenAI`) and enter the corresponding API key, unless it is already set in `.env`.
3. Paste source text into **② Source text**. Multi-paragraph input activates document-level memory.
4. Click **Propose spec** in **③ Translation specification**. The app generates a markdown translation specification from the source text and any references.
5. Review the proposed spec. Edit it directly or refine it through the chat box until the translation brief is ready.
6. Once a spec exists, **Use this spec** becomes clickable. Click it to lock the spec.
7. After the spec is locked, **Translate** in **④ Translate** becomes clickable. Click it to run the pipeline.
8. Stage panels populate live; the final translation, run data, and run log can be downloaded at the end. If the run fails midway, the partial run log can still be downloaded.

## Test set

`test_set/` contains six original multi-paragraph texts (three Japanese, three English) covering sports news, literary, and academic genres, plus glossaries, paired examples, and style guides for both directions. Each text is designed to span multiple chunks so the document-level memory can be observed. See [`test_set/README.md`](test_set/README.md) for suggested experiments.

## Status

This is a **research prototype**, not a production system. It is shared here to support the discussion in Yamada (forthcoming) and to enable colleagues, students, and researchers to experiment with spec-driven agentic translation. Feedback and pull requests are welcome.

## License

MIT License — © 2026 株式会社翻訳ラボ Translation Lab Inc. See [LICENSE](LICENSE).
