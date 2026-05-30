"""Streamlit UI for the agentic translation pipeline.

Run:
    source .venv/bin/activate
    streamlit run app.py
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import streamlit as st

# Company-shared deployment mode (set AT_COMPANY_MODE=1 in the server's env).
# When on, the BYOK sidebar is hidden — translators use the server's API key
# via env vars (ANTHROPIC_API_KEY / OPENAI_API_KEY) and never see it.
_COMPANY_MODE = os.environ.get("AT_COMPANY_MODE", "").strip().lower() in {"1", "true", "yes", "on"}

import api
from chunker import split_into_chunks
from i18n import LANGS, t as _t
from model import (
    Engine, TranslationModel, engines_dir, list_engines, list_models, models_dir,
)
from pipeline import SCORING_CRITERIA, run_document_pipeline
from references import References, parse_pair_table
from spec_chat import propose_spec, refine_spec
from tracelog import (
    bilingual_to_csv, bilingual_to_excel, build_bilingual_rows,
    build_trace_data, to_excel, to_markdown,
)

st.set_page_config(page_title="Agentic AI Translate", layout="wide")

LANGS_SUPPORTED = [
    "Japanese", "English", "Traditional Chinese", "Simplified Chinese",
    "Korean", "Spanish", "Portuguese", "French", "German",
]

# ---------------------------------------------------------------------------
# session state init
# ---------------------------------------------------------------------------

def _init_state():
    ss = st.session_state
    ss.setdefault("ui_lang", "en")
    ss.setdefault("llm_provider", api.get_provider())
    if ss.llm_provider not in api.provider_names():
        ss.llm_provider = api.get_provider()
    ss.setdefault("user_api_keys", {})
    for provider_name in api.provider_names():
        ss.user_api_keys.setdefault(provider_name, "")
    if "user_api_key" in ss:
        ss.user_api_keys.setdefault(ss.llm_provider, ss.user_api_key)
        del ss["user_api_key"]
    ss.setdefault("references", References())
    ss.setdefault("spec_md", "")
    ss.setdefault("spec_rev", 0)  # increments when spec_md changes externally (chat)
    ss.setdefault("spec_locked", False)
    ss.setdefault("spec_chat", [])
    ss.setdefault("source_text", "")
    ss.setdefault("source_language", "Japanese")
    ss.setdefault("target_language", "English")
    ss.setdefault("max_iterations", 3)
    ss.setdefault("dual_verifier", False)
    ss.setdefault("chunk_max_chars", 1500)
    ss.setdefault("chunk_max_segments", 6)
    # MQM 0–100 scale. Migrate any legacy negative threshold from earlier versions.
    if not isinstance(ss.get("accept_threshold"), (int, float)) or ss.get("accept_threshold", 95) <= 0:
        ss["accept_threshold"] = 95.0
    ss.setdefault("accept_threshold", 95.0)
    ss.setdefault("translation_result", None)
    ss.setdefault("run_events", [])
    ss.setdefault("align_cache", {})
    # Model / Engine state (v0.10.0)
    ss.setdefault("at_mode", "session")          # session | model_dev | engine
    ss.setdefault("active_model_id", "")          # current model in dev mode
    ss.setdefault("active_engine_ref", "")        # "<id>@<version>" in engine mode


_init_state()

# Apply runtime provider/key overrides on every script run
api.set_provider(st.session_state.llm_provider)
for _provider_name, _key in st.session_state.user_api_keys.items():
    api.set_api_key(_key or None, provider=_provider_name)


def t(key: str, **kwargs) -> str:
    return _t(key, st.session_state.ui_lang, **kwargs)


_UI_LANG_TO_SPEC = {"en": "English", "ja": "Japanese"}


def _spec_language() -> str:
    return _UI_LANG_TO_SPEC.get(st.session_state.ui_lang, "English")


def _active_engine() -> Engine | None:
    if st.session_state.at_mode == "engine" and st.session_state.active_engine_ref:
        try:
            return Engine.load(st.session_state.active_engine_ref)
        except Exception:
            return None
    return None


def _active_model() -> TranslationModel | None:
    if st.session_state.at_mode == "model_dev" and st.session_state.active_model_id:
        try:
            return TranslationModel.load(st.session_state.active_model_id)
        except Exception:
            return None
    return None


def _jsonable(value):
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return str(value)


def _record_run_event(name: str, payload: object) -> None:
    st.session_state.run_events.append({
        "time": datetime.now(timezone.utc).isoformat(),
        "event": name,
        "payload": _jsonable(payload),
    })


def _run_events_json() -> str:
    return json.dumps(st.session_state.run_events, ensure_ascii=False, indent=2)


def _format_md_value(value, indent: int = 0) -> list[str]:
    prefix = "  " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}- **{key}:**")
                lines.extend(_format_md_value(item, indent + 1))
            else:
                lines.append(f"{prefix}- **{key}:** {item}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_format_md_value(item, indent + 1))
            else:
                lines.append(f"{prefix}- {item}")
        return lines
    return [f"{prefix}{value}"]


def _run_events_markdown() -> str:
    lines = ["# Agentic AI Translate Run Log", ""]
    for ev in st.session_state.run_events:
        lines.append(f"## {ev['event']}")
        lines.append("")
        lines.append(f"- Time: `{ev['time']}`")
        payload = ev.get("payload")
        if payload not in (None, "", {}, []):
            lines.append("")
            lines.extend(_format_md_value(payload))
        lines.append("")
    return "\n".join(lines)


def _show_run_log_downloads() -> None:
    if not st.session_state.run_events:
        return
    st.caption(t("run_log_privacy"))
    cols = st.columns(2)
    with cols[0]:
        st.download_button(
            t("run_log_download_json"),
            data=_run_events_json(),
            file_name="agentic_translation_run_log.json",
            mime="application/json",
            use_container_width=True,
        )
    with cols[1]:
        st.download_button(
            t("run_log_download_md"),
            data=_run_events_markdown(),
            file_name="agentic_translation_run_log.md",
            mime="text/markdown",
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# header
# ---------------------------------------------------------------------------

st.title(t("app_title"))
st.caption(t("app_caption"))

# ---------------------------------------------------------------------------
# sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    # UI language
    ui_lang_keys = list(LANGS.keys())
    ui_lang_choice = st.radio(
        t("sb_ui_lang"),
        options=ui_lang_keys,
        format_func=lambda k: LANGS[k],
        index=ui_lang_keys.index(st.session_state.ui_lang),
        horizontal=True,
    )
    if ui_lang_choice != st.session_state.ui_lang:
        st.session_state.ui_lang = ui_lang_choice
        st.rerun()

    st.divider()

    # API key — hidden in company-shared deployment mode
    if _COMPANY_MODE:
        provider = st.session_state.llm_provider
        if api.env_has_real_key(provider):
            st.caption(f"🔒 Using company API key ({api.provider_label(provider)} · {api.get_model(provider)})")
        else:
            st.error(
                "AT_COMPANY_MODE=1 but no API key is set in the server env. "
                f"Set {provider.upper()}_API_KEY on the server and restart."
            )
    else:
        st.header(t("sb_api_section"))
        provider_keys = api.provider_names()
        provider_choice = st.selectbox(
            t("sb_provider_label"),
            provider_keys,
            index=provider_keys.index(st.session_state.llm_provider),
            format_func=api.provider_label,
        )
        if provider_choice != st.session_state.llm_provider:
            st.session_state.llm_provider = provider_choice
            api.set_provider(provider_choice)
            st.rerun()

        provider = st.session_state.llm_provider
        st.caption(t("sb_model_caption", model=api.get_model(provider)))

        typed_key = st.text_input(
            t("sb_api_label", provider=api.provider_label(provider)),
            value=st.session_state.user_api_keys.get(provider, ""),
            type="password",
            placeholder=api.provider_placeholder(provider),
            help=t("sb_api_help", provider=api.provider_label(provider)),
        )
        if typed_key != st.session_state.user_api_keys.get(provider, ""):
            st.session_state.user_api_keys[provider] = typed_key
            api.set_api_key(typed_key or None, provider=provider)

        if st.session_state.user_api_keys.get(provider, "").strip():
            st.success(t("sb_api_set_runtime"))
            if st.button(t("sb_api_clear"), use_container_width=True):
                st.session_state.user_api_keys[provider] = ""
                api.set_api_key(None, provider=provider)
                st.rerun()
        elif api.env_has_real_key(provider):
            st.info(t("sb_api_set_env"))
        else:
            st.warning(t("sb_api_unset"))

    st.divider()

    # Model / Engine
    st.header("Model / Engine")
    mode = st.radio(
        "Mode",
        options=["session", "model_dev", "engine"],
        index=["session", "model_dev", "engine"].index(st.session_state.at_mode),
        format_func=lambda m: {
            "session": "Session only (legacy)",
            "model_dev": "Model dev (author a Model)",
            "engine": "Engine (use a compiled Engine)",
        }[m],
        help=(
            "Session only: legacy behaviour, no persistence. "
            "Model dev: author a versioned Model with spec/refs/decisions on disk. "
            "Engine: run a frozen Engine snapshot (production use)."
        ),
    )
    if mode != st.session_state.at_mode:
        st.session_state.at_mode = mode
        st.rerun()

    if mode == "engine":
        engines = list_engines()
        if not engines:
            st.info(
                f"No engines yet at {engines_dir()}. "
                "Compile one from a locked Model first."
            )
            st.session_state.active_engine_ref = ""
        else:
            refs = [e.display_id for e in engines]
            cur = st.session_state.active_engine_ref
            idx = refs.index(cur) if cur in refs else 0
            chosen = st.selectbox("Engine", refs, index=idx)
            if chosen != st.session_state.active_engine_ref:
                st.session_state.active_engine_ref = chosen
                st.rerun()
            e = next(eng for eng in engines if eng.display_id == chosen)
            ok, drifted = e.verify()
            ll = e.llm_settings()
            pl = e.pipeline_kwargs()
            st.caption(
                f"compiled: {e.seal.get('compiled_at','')}  ·  "
                f"system v{e.seal.get('system_version','')}  ·  "
                f"{'✅ verified' if ok else f'⚠️ drift ({len(drifted)})'}\n\n"
                f"LLM: {ll.get('provider')} / {ll.get('model')}  ·  "
                f"threshold: {pl.get('mqm_threshold')}"
            )

    elif mode == "model_dev":
        models = list_models()
        labels = ["(create new)"] + [f"{m.id} ({m.version}, {'locked' if m.is_locked else 'draft'})" for m in models]
        cur_id = st.session_state.active_model_id
        idx = 0
        if cur_id:
            for i, m in enumerate(models):
                if m.id == cur_id:
                    idx = i + 1
                    break
        chosen_label = st.selectbox("Model", labels, index=idx)
        if chosen_label == "(create new)":
            with st.form("new_model_form"):
                new_id = st.text_input("New model id (kebab-case)", placeholder="corporate-tech-ja-en")
                new_display = st.text_input("Display name", placeholder="Corporate Tech JA→EN")
                new_desc = st.text_area("Description", placeholder="One-line description", height=70)
                new_locale = st.text_input("Target locale (optional)", placeholder="en-US")
                created = st.form_submit_button("Create", type="primary")
                if created and new_id.strip():
                    try:
                        m = TranslationModel.new(
                            id=new_id.strip(),
                            display_name=new_display.strip() or new_id.strip(),
                            description=new_desc.strip(),
                            source_language=st.session_state.source_language,
                            target_language=st.session_state.target_language,
                            locale=new_locale.strip(),
                            created_by="",
                        )
                        st.session_state.active_model_id = m.id
                        st.success(f"Created model {m.id} at {m.model_dir}")
                        st.rerun()
                    except FileExistsError as exc:
                        st.error(str(exc))
        else:
            sel = models[labels.index(chosen_label) - 1]
            if sel.id != st.session_state.active_model_id:
                st.session_state.active_model_id = sel.id
                st.rerun()
            drift, files = sel.has_drift()
            drift_note = f"  ·  ⚠️ drift ({len(files)})" if drift else ""
            st.caption(
                f"path: `{sel.model_dir.relative_to(models_dir().parent) if models_dir() in sel.model_dir.parents or sel.model_dir.parent == models_dir() else sel.model_dir}`\n\n"
                f"version: **{sel.version}**  ·  "
                f"state: **{'locked' if sel.is_locked else 'draft'}**{drift_note}"
            )

    st.divider()

    # Languages
    st.header(t("sb_languages"))
    st.session_state.source_language = st.selectbox(
        t("sb_source_lang"), LANGS_SUPPORTED,
        index=LANGS_SUPPORTED.index(st.session_state.source_language),
    )
    st.session_state.target_language = st.selectbox(
        t("sb_target_lang"), LANGS_SUPPORTED,
        index=LANGS_SUPPORTED.index(st.session_state.target_language),
    )

    # Pipeline
    st.header(t("sb_pipeline"))
    st.session_state.max_iterations = st.slider(
        t("sb_max_iter"), 1, 5, st.session_state.max_iterations,
    )
    st.session_state.dual_verifier = st.checkbox(
        "Dual verifier (experimental)",
        value=st.session_state.dual_verifier,
        help="Run a second Spec-grounded verifier and merge findings. Doubles verification cost.",
    )
    st.session_state.chunk_max_chars = st.slider(
        t("sb_chunk_max"), 500, 3000, st.session_state.chunk_max_chars, step=100,
    )
    st.session_state.accept_threshold = st.slider(
        "MQM accept threshold (0–100)",
        min_value=80.0, max_value=100.0,
        value=float(st.session_state.accept_threshold),
        step=0.5,
        help=(
            "MQM score ≥ threshold ⇒ accept; otherwise revise. "
            "Burchardt et al. benchmark: 95+ = publication, 90–94 = business, <85 = needs major revision."
        ),
    )

    st.divider()
    if st.button(t("sb_reset"), use_container_width=True):
        keep_lang = st.session_state.ui_lang
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.session_state.ui_lang = keep_lang
        st.rerun()

# ---------------------------------------------------------------------------
# Section 1: References upload
# ---------------------------------------------------------------------------

_engine_active = _active_engine()
_model_active = _active_model()

if _engine_active is not None:
    st.info(
        f"**Engine mode** — using **{_engine_active.display_id}** "
        f"(compiled {_engine_active.seal.get('compiled_at','')}). "
        f"Spec and references come from the engine; sections 1 and 3 are hidden."
    )

# Section 1 is hidden in engine mode (engine bundles refs).
if _engine_active is None:
  with st.expander(
    t("sec1_header", summary=st.session_state.references.summary()),
    expanded=st.session_state.references.is_empty(),
  ):
    refs: References = st.session_state.references
    cols = st.columns(2)

    with cols[0]:
        st.markdown(t("sec1_glossary_md"))
        gf = st.file_uploader(
            t("sec1_glossary_label"), type=["tsv", "csv", "txt"],
            key="upl_glossary", label_visibility="collapsed",
        )
        if gf is not None:
            text = gf.read().decode("utf-8", errors="replace")
            refs.glossary = parse_pair_table(text)
            st.success(t("sec1_glossary_loaded", n=len(refs.glossary)))

        st.markdown(t("sec1_paired_md"))
        pf = st.file_uploader(
            t("sec1_paired_label"), type=["tsv", "csv", "txt"],
            key="upl_paired", label_visibility="collapsed",
        )
        if pf is not None:
            text = pf.read().decode("utf-8", errors="replace")
            refs.paired = parse_pair_table(text)
            st.success(t("sec1_paired_loaded", n=len(refs.paired)))

    with cols[1]:
        st.markdown(t("sec1_parallel_md"))
        para_files = st.file_uploader(
            t("sec1_parallel_label"), type=["txt", "md"],
            key="upl_parallel", label_visibility="collapsed",
            accept_multiple_files=True,
        )
        if para_files:
            refs.parallel = [
                (f.name, f.read().decode("utf-8", errors="replace"))
                for f in para_files
            ]
            st.success(t("sec1_parallel_loaded", n=len(refs.parallel)))

        st.markdown(t("sec1_styleguide_md"))
        sg = st.file_uploader(
            t("sec1_styleguide_label"), type=["md", "txt"],
            key="upl_style", label_visibility="collapsed",
        )
        if sg is not None:
            refs.style_guide = sg.read().decode("utf-8", errors="replace")
            st.success(t("sec1_styleguide_loaded"))

    if not refs.is_empty():
        with st.expander(t("sec1_preview")):
            st.code(refs.to_context_block(), language="markdown")

# ---------------------------------------------------------------------------
# Section 2: Source text
# ---------------------------------------------------------------------------

st.subheader(t("sec2_header"))

DEFAULT_SAMPLE = (
    "8月の鈴鹿は気温・路面温度ともに非常に高く、マシンの耐久性、"
    "ライダーのテクニックや体力、そして戦略を含めたチームワークが試されます。"
)

st.session_state.source_text = st.text_area(
    "source_text",
    value=st.session_state.source_text or DEFAULT_SAMPLE,
    height=200,
    label_visibility="collapsed",
    placeholder=t("sec2_placeholder"),
)
if st.session_state.source_text.strip():
    _chunks = split_into_chunks(
        st.session_state.source_text,
        max_chars=st.session_state.chunk_max_chars,
        max_segments=st.session_state.chunk_max_segments,
    )
    n_chunks = len(_chunks)
    n_segments = sum(len(c.segments) for c in _chunks)
    if n_chunks > 1:
        st.caption(t("sec2_chunks_doc", n=n_chunks) + f" · {n_segments} segments")
    else:
        st.caption(t("sec2_chunks_single", n=n_chunks) + f" · {n_segments} segments")

# ---------------------------------------------------------------------------
# Section 3: Spec proposal + refinement chat
# ---------------------------------------------------------------------------

if _engine_active is not None:
    # Engine mode: spec is baked in. Show a compact summary instead of authoring UI.
    with st.expander(f"Spec (from engine {_engine_active.display_id}, read-only)", expanded=False):
        st.code(_engine_active.spec_narrative, language="markdown")

# Section 3 is shown in session and model_dev modes.
if _engine_active is None:
  st.subheader(t("sec3_header"))

  # Model dev: load spec from model on first activation (only if session spec is empty).
  if _model_active is not None and not st.session_state.spec_md:
      model_spec = _model_active.spec_narrative
      if model_spec.strip():
          st.session_state.spec_md = model_spec
          st.session_state.spec_locked = _model_active.is_locked
          st.session_state.spec_rev += 1

  c1, c2, c3 = st.columns([1, 1, 1])
  with c1:
    propose_clicked = st.button(
        t("sec3_propose"),
        type="primary" if not st.session_state.spec_md else "secondary",
        disabled=not st.session_state.source_text.strip() or not api.has_api_key(),
        use_container_width=True,
    )
  with c2:
    lock_clicked = st.button(
        t("sec3_lock"),
        disabled=not st.session_state.spec_md or st.session_state.spec_locked,
        use_container_width=True,
    )
  with c3:
    unlock_clicked = st.button(
        t("sec3_unlock"),
        disabled=not st.session_state.spec_locked,
        use_container_width=True,
    )

  if propose_clicked:
    with st.spinner(t("sec3_proposing")):
        try:
            spec_md, _ = propose_spec(
                source_text=st.session_state.source_text,
                source_language=st.session_state.source_language,
                target_language=st.session_state.target_language,
                references=st.session_state.references,
                spec_language=_spec_language(),
            )
            st.session_state.spec_md = spec_md
            st.session_state.spec_chat = []
            st.session_state.spec_locked = False
            st.session_state.spec_rev += 1
        except Exception as e:
            st.error(t("sec3_propose_failed", err=str(e)))

  if lock_clicked:
    st.session_state.spec_locked = True
    st.success(t("sec3_locked_msg"))

  if unlock_clicked:
    st.session_state.spec_locked = False

  if st.session_state.spec_md:
    # Use a versioned key so external updates (Propose / chat refine) force the
    # widget to rebuild and pick up the new value. Direct edits keep the same
    # version and are tracked via the return value.
    edited = st.text_area(
        t("sec3_spec_label"),
        value=st.session_state.spec_md,
        height=400,
        disabled=st.session_state.spec_locked,
        key=f"spec_editor_v{st.session_state.spec_rev}",
    )
    if not st.session_state.spec_locked and edited != st.session_state.spec_md:
        st.session_state.spec_md = edited

    if not st.session_state.spec_locked:
        st.markdown(t("sec3_chat_md"))
        for msg in st.session_state.spec_chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_msg = st.chat_input(t("sec3_chat_placeholder"))
        if user_msg:
            st.session_state.spec_chat.append({"role": "user", "content": user_msg})
            with st.spinner(t("sec3_refining")):
                try:
                    new_spec, comment, _ = refine_spec(
                        source_text=st.session_state.source_text,
                        source_language=st.session_state.source_language,
                        target_language=st.session_state.target_language,
                        references=st.session_state.references,
                        current_spec=st.session_state.spec_md,
                        conversation=st.session_state.spec_chat[:-1],
                        user_message=user_msg,
                        spec_language=_spec_language(),
                    )
                    st.session_state.spec_md = new_spec
                    st.session_state.spec_rev += 1
                    st.session_state.spec_chat.append(
                        {"role": "assistant", "content": comment}
                    )
                except Exception as e:
                    st.session_state.spec_chat.append(
                        {"role": "assistant", "content": f"Error: {e}"}
                    )
            st.rerun()

  # ---- Model dev: Save / Lock & Compile -----------------------------------
  if _model_active is not None:
    st.markdown("---")
    st.markdown(f"**Model dev controls — `{_model_active.id}` ({_model_active.version}, "
                f"{'locked' if _model_active.is_locked else 'draft'})**")

    mc1, mc2, mc3 = st.columns([1, 1, 1])

    with mc1:
        save_clicked = st.button(
            "💾 Save Spec → Model",
            disabled=_model_active.is_locked or not st.session_state.spec_md.strip(),
            help="Write the current spec narrative to models/<id>/spec/narrative.md",
            use_container_width=True,
        )
        if save_clicked:
            try:
                _model_active.write_spec(st.session_state.spec_md)
                st.success(f"Saved spec to {_model_active.spec_narrative_path}")
            except Exception as exc:
                st.error(str(exc))

    with mc2:
        if _model_active.is_locked:
            unlock_model_clicked = st.button(
                "🔓 Unlock Model",
                help="Return the Model to draft state. Existing Engines are unaffected.",
                use_container_width=True,
            )
            if unlock_model_clicked:
                _model_active.unlock()
                st.success(f"Unlocked {_model_active.id}.")
                st.rerun()
        else:
            bump = st.selectbox(
                "Bump",
                ["patch", "minor", "major"],
                index=1,
                key="model_bump_select",
                help="Version bump for the lock.",
            )

    with mc3:
        if _model_active.is_locked:
            drift, files = _model_active.has_drift()
            if drift:
                st.warning(f"⚠️ Drift in {len(files)} file(s) since lock. Unlock + re-lock.")
            existing_engine_dir = engines_dir() / f"{_model_active.id}@{_model_active.version}"
            if existing_engine_dir.exists():
                st.info(f"Engine `{_model_active.id}@{_model_active.version}` already compiled.")
            else:
                compile_clicked = st.button(
                    "📦 Compile Engine",
                    type="primary",
                    use_container_width=True,
                )
                if compile_clicked:
                    try:
                        e = Engine.compile_from(_model_active)
                        st.success(f"Compiled engine {e.display_id} at {e.engine_dir}")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
        else:
            lock_compile_clicked = st.button(
                "🔒 Lock & Compile",
                type="primary",
                disabled=not st.session_state.spec_md.strip(),
                help="Lock the model with a version bump, then compile to an Engine.",
                use_container_width=True,
            )
            if lock_compile_clicked:
                try:
                    # Persist current spec_md to model first (in case user forgot Save)
                    _model_active.write_spec(st.session_state.spec_md)
                    _model_active.lock(bump=st.session_state.get("model_bump_select", "minor"))
                    e = Engine.compile_from(_model_active)
                    st.success(
                        f"Locked {_model_active.id} at {_model_active.version} and "
                        f"compiled engine {e.display_id}"
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

# ---------------------------------------------------------------------------
# Section 4: Translate
# ---------------------------------------------------------------------------

st.subheader(t("sec4_header"))

st.caption(
    f"Scoring: **MQM 0–100** (higher is better) · "
    f"Accept threshold: **{float(st.session_state.accept_threshold):.1f}** · "
    f"Weights: critical=25, major=5, minor=1 per 100 source chars · "
    f"Standard: {SCORING_CRITERIA['standard']}"
)

# In engine mode, the spec comes from the engine — no need to lock a session spec.
_ready_for_translate = (
    bool(st.session_state.source_text.strip()) and api.has_api_key()
    and (_engine_active is not None or st.session_state.spec_locked)
)

translate_clicked = st.button(
    t("sec4_button"),
    type="primary",
    disabled=not _ready_for_translate,
)

if _engine_active is None and not st.session_state.spec_locked:
    st.caption(t("sec4_lock_first"))
elif _engine_active is not None:
    st.caption(f"Using engine **{_engine_active.display_id}** — spec, references, "
               f"and pipeline knobs come from the engine.")

if translate_clicked:
    st.session_state.run_events = []
    status = st.status(t("run_status"), expanded=True)
    chunk_containers: dict[int, "st.delta_generator.DeltaGenerator"] = {}
    memory_box = st.empty()
    state = {"current_chunk": 0}

    def _chunk_container(idx: int):
        if idx not in chunk_containers:
            chunk_containers[idx] = st.container()
        return chunk_containers[idx]

    def on_event(name, payload):
        _record_run_event(name, payload)
        if name == "doc_start":
            status.write(t(
                "run_doc_start",
                chunks=payload["chunks"],
                target=payload["target_language"],
            ))
        elif name == "chunk_start":
            state["current_chunk"] = payload["index"]
            status.write(t(
                "run_chunk_start",
                i=payload["index"], n=payload["total"],
                chars=len(payload["source"]),
            ))
        elif name == "identification":
            with _chunk_container(state["current_chunk"]):
                with st.expander(t("stage1_title", i=state["current_chunk"]),
                                 expanded=False):
                    st.json(payload)
        elif name == "prompting":
            status.write(t(
                "run_iter_prompt",
                i=state["current_chunk"], iter=payload["iteration"],
                chars=payload["prompt_chars"],
            ))
        elif name == "generation":
            with _chunk_container(state["current_chunk"]):
                with st.expander(
                    t("stage3_title", i=state["current_chunk"], iter=payload["iteration"]),
                    expanded=True,
                ):
                    st.write(payload["translation"])
        elif name == "verification":
            with _chunk_container(state["current_chunk"]):
                verdict = payload.get("verdict", "?")
                score = payload.get("score", 0.0)              # MQM 0–100
                penalty = payload.get("penalty", 0)
                src_len = payload.get("source_length", 0)
                threshold = payload.get("accept_threshold", 95.0)
                band = payload.get("quality_band", "")
                counts = payload.get("counts", {})
                errors = payload.get("errors", [])
                criteria = payload.get("scoring_criteria", {})

                light = "🟢" if score >= 95 else ("🟡" if score >= 90 else "🔴")
                verdict_word = "ACCEPT" if verdict == "accept" else "REVISE"

                with st.expander(
                    f"{light} verify (chunk {state['current_chunk']} · iter {payload['iteration']}) "
                    f"— MQM {score:.1f}/100 · {verdict_word} (threshold {threshold:.1f})",
                    expanded=bool(errors),
                ):
                    cols = st.columns(4)
                    cols[0].metric("MQM score", f"{score:.1f}/100",
                                   delta=f"{score - threshold:+.1f} vs threshold")
                    cols[1].metric("Critical", counts.get("critical", 0))
                    cols[2].metric("Major", counts.get("major", 0))
                    cols[3].metric("Minor", counts.get("minor", 0))
                    st.caption(
                        f"Penalty: {penalty} pts over {src_len} source chars · "
                        f"Quality band: **{band.replace('_',' ')}**"
                    )
                    if errors:
                        rows = [
                            {
                                "severity": e.get("severity", ""),
                                "category": e.get("category", ""),
                                "spec_section": e.get("spec_section", ""),
                                "span": e.get("span", ""),
                                "explanation": e.get("explanation", ""),
                            }
                            for e in errors
                        ]
                        st.dataframe(rows, use_container_width=True, hide_index=True)
                    if payload.get("summary"):
                        st.caption(payload["summary"])
                    # Scoring criteria (transparency)
                    if criteria:
                        with st.expander("ⓘ Scoring criteria used", expanded=False):
                            w = criteria.get("weights", {})
                            bands = criteria.get("bands", {})
                            refs = criteria.get("references", [])
                            st.markdown(
                                f"- **Standard**: {criteria.get('standard','')}\n"
                                f"- **Normalization**: {criteria.get('normalize_unit','')}\n"
                                f"- **Severity weights**: critical={w.get('critical')}, "
                                f"major={w.get('major')}, minor={w.get('minor')}\n"
                                f"- **Formula**: score = max(0, 100 − penalty × 100 ÷ source_chars)\n"
                                f"- **Threshold (this run)**: {threshold:.1f}\n"
                                f"- **Quality bands**: publication ≥ {bands.get('publication_quality','95')}, "
                                f"business {bands.get('business_quality','90–94')}, "
                                f"needs revision {bands.get('needs_major_revision','<85')}"
                            )
                            if refs:
                                st.caption("References: " + "; ".join(refs))
        elif name == "chunk_done":
            with _chunk_container(payload["index"]):
                if payload["accepted"]:
                    st.success(t("run_chunk_done_ok",
                                 i=payload["index"], iters=payload["iterations"]))
                else:
                    st.warning(t("run_chunk_done_warn",
                                 i=payload["index"], iters=payload["iterations"]))
        elif name == "memory_updated":
            with memory_box.container():
                with st.expander(
                    t("run_memory_title",
                      i=payload["index"], n=len(payload["new_terms"])),
                    expanded=False,
                ):
                    if payload["new_terms"]:
                        st.markdown(t("run_memory_new_terms"))
                        st.json(payload["new_terms"])
                    if payload.get("notes"):
                        st.caption(t("run_memory_notes", text=payload["notes"]))
                    st.markdown(t("run_memory_summary"))
                    st.write(payload["summary"])
        elif name == "memory_error":
            status.write(t(
                "run_memory_error", i=payload["index"], err=payload["error"],
            ))
        elif name == "doc_done":
            status.update(
                label=t("run_doc_done",
                        chunks=payload["chunks"], chars=payload["final_chars"]),
                state="complete", expanded=False,
            )

    try:
        result = run_document_pipeline(
            source_text=st.session_state.source_text,
            source_language=st.session_state.source_language,
            target_language=st.session_state.target_language,
            engine=_engine_active,
            spec_text=None if _engine_active is not None else st.session_state.spec_md,
            references=None if _engine_active is not None else st.session_state.references,
            max_iterations=st.session_state.max_iterations,
            accept_threshold=st.session_state.accept_threshold,
            chunk_max_chars=st.session_state.chunk_max_chars,
            chunk_max_segments=st.session_state.chunk_max_segments,
            dual_verifier=st.session_state.dual_verifier,
            on_event=on_event,
        )
        st.session_state.translation_result = result
        st.session_state.align_cache = {}  # reset on new run
    except Exception as e:
        _record_run_event("error", {"message": str(e)})
        status.update(label=f"Error: {e}", state="error")
        _show_run_log_downloads()
        st.exception(e)
        st.stop()

# ---------------------------------------------------------------------------
# Section 5: Results
# ---------------------------------------------------------------------------

result = st.session_state.translation_result
if result is not None:
    st.divider()
    st.subheader(t("fin_header"))
    st.text_area(
        "final_output",
        value=result.final_translation,
        height=300,
        label_visibility="collapsed",
    )

    with st.expander("📥 Downloads", expanded=False):
        # --- Translation only ---
        st.markdown("**Translation**")
        st.download_button(
            t("fin_download_txt"),
            data=result.final_translation,
            file_name="agentic_translation.txt",
            mime="text/plain",
            use_container_width=True,
        )

        st.markdown("---")

        # --- Bilingual for human review ---
        st.markdown("**Bilingual (for human review)**")
        st.caption(
            "Sentence-level uses regex when the translation's sentence count matches the source's; "
            "otherwise an LLM aligner is invoked (cached after first use)."
        )
        bi_sent_rows = build_bilingual_rows(
            result,
            granularity="sentence",
            target_language=st.session_state.target_language,
            use_llm_for_misaligned=True,
            align_cache=st.session_state.align_cache,
        )
        _q_counts = {}
        for r in bi_sent_rows:
            _q_counts[r["alignment_quality"]] = _q_counts.get(r["alignment_quality"], 0) + 1
        st.caption(f"Sentence-level rows: {len(bi_sent_rows)} — " +
                   ", ".join(f"{k}={v}" for k, v in _q_counts.items()))

        bi_chunk_rows = build_bilingual_rows(result, granularity="chunk")

        sent_cols = st.columns(2)
        with sent_cols[0]:
            st.download_button(
                "Sentence-level (CSV)",
                data=bilingual_to_csv(bi_sent_rows),
                file_name="agentic_bilingual_sentence.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with sent_cols[1]:
            st.download_button(
                "Sentence-level (Excel)",
                data=bilingual_to_excel(bi_sent_rows),
                file_name="agentic_bilingual_sentence.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        chunk_cols = st.columns(2)
        with chunk_cols[0]:
            st.download_button(
                "Chunk-level (CSV)",
                data=bilingual_to_csv(bi_chunk_rows),
                file_name="agentic_bilingual_chunk.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with chunk_cols[1]:
            st.download_button(
                "Chunk-level (Excel)",
                data=bilingual_to_excel(bi_chunk_rows),
                file_name="agentic_bilingual_chunk.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        st.markdown("---")

        # --- Process trace ---
        st.markdown("**Process trace (full pipeline log)**")
        _run_meta = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_language": st.session_state.source_language,
            "target_language": st.session_state.target_language,
            "provider": st.session_state.llm_provider,
            "max_iterations": st.session_state.max_iterations,
            "accept_threshold": st.session_state.accept_threshold,
            "chunk_max_chars": st.session_state.chunk_max_chars,
            "chunk_max_segments": st.session_state.chunk_max_segments,
            "dual_verifier": st.session_state.dual_verifier,
            "n_chunks": len(result.chunk_results),
            "spec_text": st.session_state.spec_md,
            "scoring_criteria": SCORING_CRITERIA,
        }
        _trace = build_trace_data(result, _run_meta)
        result_json = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

        trace_cols = st.columns(3)
        with trace_cols[0]:
            st.download_button(
                "Trace (Markdown)",
                data=to_markdown(_trace),
                file_name="agentic_trace.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with trace_cols[1]:
            st.download_button(
                "Trace (Excel)",
                data=to_excel(_trace),
                file_name="agentic_trace.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with trace_cols[2]:
            st.download_button(
                t("fin_download_json"),
                data=result_json,
                file_name="agentic_translation_run.json",
                mime="application/json",
                use_container_width=True,
            )

        _show_run_log_downloads()

    if result.memory.proper_nouns:
        with st.expander(t("fin_terminology", n=len(result.memory.proper_nouns)),
                         expanded=False):
            st.json(result.memory.proper_nouns)

    if result.memory.summary:
        with st.expander(t("fin_summary")):
            st.write(result.memory.summary)

    with st.expander(t("fin_run_details")):
        rows = []
        for ci, r in enumerate(result.chunk_results, 1):
            for s in r.stages:
                rows.append({
                    "chunk": ci,
                    "stage": s.name,
                    "duration_s": round(s.duration_s, 2),
                    "input_tokens": s.usage["input_tokens"],
                    "output_tokens": s.usage["output_tokens"],
                })
        st.table(rows)
        total_in = sum(s.usage["input_tokens"] for r in result.chunk_results for s in r.stages)
        total_out = sum(s.usage["output_tokens"] for r in result.chunk_results for s in r.stages)
        mu_in = sum(u["input_tokens"] for u in result.memory_update_usage)
        mu_out = sum(u["output_tokens"] for u in result.memory_update_usage)
        st.caption(t(
            "fin_token_summary",
            tin=total_in, tout=total_out, mu_in=mu_in, mu_out=mu_out,
        ))

    with st.expander(t("fin_raw_json")):
        st.code(
            result_json,
            language="json",
        )
