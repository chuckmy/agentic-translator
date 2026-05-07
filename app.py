"""Streamlit UI for the agentic translation pipeline.

Run:
    source .venv/bin/activate
    streamlit run app.py
"""
from __future__ import annotations

import json

import streamlit as st

import api
from chunker import split_into_chunks
from i18n import LANGS, t as _t
from pipeline import run_document_pipeline
from references import References, parse_pair_table
from spec_chat import propose_spec, refine_spec

st.set_page_config(page_title="Agentic Translator", layout="wide")

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
    ss.setdefault("user_api_key", "")
    ss.setdefault("references", References())
    ss.setdefault("spec_md", "")
    ss.setdefault("spec_rev", 0)  # increments when spec_md changes externally (chat)
    ss.setdefault("spec_locked", False)
    ss.setdefault("spec_chat", [])
    ss.setdefault("source_text", "")
    ss.setdefault("source_language", "Japanese")
    ss.setdefault("target_language", "English")
    ss.setdefault("max_iterations", 2)
    ss.setdefault("chunk_max_chars", 1500)
    ss.setdefault("accept_threshold", -2)
    ss.setdefault("translation_result", None)


_init_state()

# Apply runtime API key override on every script run
api.set_api_key(st.session_state.user_api_key or None)


def t(key: str, **kwargs) -> str:
    return _t(key, st.session_state.ui_lang, **kwargs)


_UI_LANG_TO_SPEC = {"en": "English", "ja": "Japanese"}


def _spec_language() -> str:
    return _UI_LANG_TO_SPEC.get(st.session_state.ui_lang, "English")


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

    # API key
    st.header(t("sb_api_section"))
    typed_key = st.text_input(
        t("sb_api_label"),
        value=st.session_state.user_api_key,
        type="password",
        placeholder=t("sb_api_placeholder"),
        help=t("sb_api_help"),
    )
    if typed_key != st.session_state.user_api_key:
        st.session_state.user_api_key = typed_key
        api.set_api_key(typed_key or None)

    if st.session_state.user_api_key.strip():
        st.success(t("sb_api_set_runtime"))
        if st.button(t("sb_api_clear"), use_container_width=True):
            st.session_state.user_api_key = ""
            api.set_api_key(None)
            st.rerun()
    elif api.env_has_real_key():
        st.info(t("sb_api_set_env"))
    else:
        st.warning(t("sb_api_unset"))

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
        t("sb_max_iter"), 1, 4, st.session_state.max_iterations,
    )
    st.session_state.chunk_max_chars = st.slider(
        t("sb_chunk_max"), 500, 3000, st.session_state.chunk_max_chars, step=100,
    )
    st.session_state.accept_threshold = st.slider(
        t("sb_threshold"), -25, 0, st.session_state.accept_threshold,
        help=t("sb_threshold_help"),
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
    n_chunks = len(split_into_chunks(
        st.session_state.source_text, max_chars=st.session_state.chunk_max_chars,
    ))
    if n_chunks > 1:
        st.caption(t("sec2_chunks_doc", n=n_chunks))
    else:
        st.caption(t("sec2_chunks_single", n=n_chunks))

# ---------------------------------------------------------------------------
# Section 3: Spec proposal + refinement chat
# ---------------------------------------------------------------------------

st.subheader(t("sec3_header"))

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

# ---------------------------------------------------------------------------
# Section 4: Translate
# ---------------------------------------------------------------------------

st.subheader(t("sec4_header"))

translate_clicked = st.button(
    t("sec4_button"),
    type="primary",
    disabled=not (
        st.session_state.spec_locked
        and st.session_state.source_text.strip()
        and api.has_api_key()
    ),
)

if not st.session_state.spec_locked:
    st.caption(t("sec4_lock_first"))

if translate_clicked:
    status = st.status(t("run_status"), expanded=True)
    chunk_containers: dict[int, "st.delta_generator.DeltaGenerator"] = {}
    memory_box = st.empty()
    state = {"current_chunk": 0}

    def _chunk_container(idx: int):
        if idx not in chunk_containers:
            chunk_containers[idx] = st.container()
        return chunk_containers[idx]

    def on_event(name, payload):
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
                score = payload.get("score", 0)
                counts = payload.get("counts", {})
                errors = payload.get("errors", [])
                emoji = "✅" if verdict == "accept" else "🔁"
                with st.expander(
                    t("stage4_title",
                      i=state["current_chunk"], iter=payload["iteration"],
                      emoji=emoji, verdict=verdict, score=score,
                      th=payload.get("accept_threshold", -2)),
                    expanded=bool(errors),
                ):
                    cols = st.columns(4)
                    cols[0].metric(t("stage4_metric_score"), score)
                    cols[1].metric(t("stage4_metric_critical"), counts.get("critical", 0))
                    cols[2].metric(t("stage4_metric_major"), counts.get("major", 0))
                    cols[3].metric(t("stage4_metric_minor"), counts.get("minor", 0))
                    if errors:
                        rows = [
                            {
                                "severity": e.get("severity", ""),
                                "category": e.get("category", ""),
                                "span": e.get("span", ""),
                                "explanation": e.get("explanation", ""),
                            }
                            for e in errors
                        ]
                        st.dataframe(rows, use_container_width=True, hide_index=True)
                    if payload.get("summary"):
                        st.caption(payload["summary"])
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
            spec_text=st.session_state.spec_md,
            references=st.session_state.references,
            max_iterations=st.session_state.max_iterations,
            accept_threshold=st.session_state.accept_threshold,
            chunk_max_chars=st.session_state.chunk_max_chars,
            on_event=on_event,
        )
        st.session_state.translation_result = result
    except Exception as e:
        status.update(label=f"Error: {e}", state="error")
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
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            language="json",
        )
