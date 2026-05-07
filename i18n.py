"""UI strings for English and Japanese."""
from __future__ import annotations

LANGS = {"en": "English", "ja": "日本語"}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # App header
        "app_title": "Agentic Translator",
        "app_caption": "References → Spec (interactive) → Identify → Prompt → Generate → Verify",
        # Sidebar — API key
        "sb_api_section": "API key",
        "sb_api_label": "Anthropic API key",
        "sb_api_help": "Your key is kept only in this browser session. Get one at console.anthropic.com.",
        "sb_api_placeholder": "sk-ant-api03-...",
        "sb_api_set_runtime": "✓ key configured (this session)",
        "sb_api_set_env": "✓ key configured (from .env)",
        "sb_api_unset": "⚠️ no API key — translation will fail",
        "sb_api_clear": "Clear key",
        # Sidebar — language
        "sb_ui_lang": "Interface language",
        # Sidebar — settings
        "sb_languages": "Languages",
        "sb_source_lang": "Source language",
        "sb_target_lang": "Target language",
        "sb_pipeline": "Pipeline",
        "sb_max_iter": "Max verification iterations",
        "sb_chunk_max": "Max chars per chunk",
        "sb_threshold": "MQM accept threshold (≥ accept)",
        "sb_threshold_help": "MQM score = -25·critical -5·major -1·minor. -2 ≈ allow up to 2 minors; 0 = strict.",
        "sb_reset": "Reset session",
        # Section 1 — references
        "sec1_header": "① Reference materials — {summary}",
        "sec1_glossary_md": "**Glossary** (TSV/CSV: `source<TAB>target` per line)",
        "sec1_glossary_label": "Glossary file",
        "sec1_glossary_loaded": "Loaded {n} glossary entries",
        "sec1_paired_md": "**Paired examples** (TSV/CSV: `source<TAB>target` per line)",
        "sec1_paired_label": "Paired examples file",
        "sec1_paired_loaded": "Loaded {n} paired examples",
        "sec1_parallel_md": "**Parallel target-language texts** (one or more `.txt` / `.md`)",
        "sec1_parallel_label": "Parallel texts",
        "sec1_parallel_loaded": "Loaded {n} parallel texts",
        "sec1_styleguide_md": "**Style guide** (`.md` / `.txt`)",
        "sec1_styleguide_label": "Style guide",
        "sec1_styleguide_loaded": "Style guide loaded",
        "sec1_preview": "Preview combined reference block (as sent to the model)",
        # Section 2 — source
        "sec2_header": "② Source text",
        "sec2_placeholder": "Paste the text to translate (use blank lines to separate paragraphs)...",
        "sec2_chunks_doc": "Will be processed as **{n} chunk(s)** — document-level memory active",
        "sec2_chunks_single": "Will be processed as **{n} chunk(s)** — single-chunk mode",
        # Section 3 — spec
        "sec3_header": "③ Translation specification",
        "sec3_propose": "Propose spec",
        "sec3_lock": "✅ Use this spec",
        "sec3_unlock": "🔓 Unlock to edit",
        "sec3_proposing": "Proposing spec from source + references...",
        "sec3_propose_failed": "Spec proposal failed: {err}",
        "sec3_locked_msg": "Spec locked. You can now translate.",
        "sec3_spec_label": "Current spec (markdown — edit directly or refine via chat below)",
        "sec3_chat_md": "**Refine via chat** — describe what to change",
        "sec3_chat_placeholder": "e.g., 'audience is K-pop fans aged 15-25', 'keep emoji and source-language fan vocabulary', etc.",
        "sec3_refining": "Refining...",
        # Section 4 — translate
        "sec4_header": "④ Translate",
        "sec4_button": "Translate",
        "sec4_lock_first": "Lock the spec above first to enable translation.",
        # Run-time event labels
        "run_status": "Running document pipeline...",
        "run_doc_start": "**Document start** — {chunks} chunk(s) → {target}",
        "run_chunk_start": "**Chunk {i}/{n}** — {chars} chars",
        "run_iter_prompt": "  Chunk {i} · iteration {iter} — prompt {chars:,} chars",
        "run_chunk_done_ok": "✅ Chunk {i} done (iters: {iters})",
        "run_chunk_done_warn": "⚠️ Chunk {i} done (iters: {iters})",
        "run_doc_done": "Document done — {chunks} chunks, {chars:,} chars",
        "run_memory_title": "📚 Memory after chunk {i} (+{n} new terms)",
        "run_memory_new_terms": "**Newly established terms:**",
        "run_memory_notes": "Notes: {text}",
        "run_memory_summary": "**Running summary:**",
        "run_memory_error": "⚠️ memory update failed at chunk {i}: {err}",
        # Stage panels
        "stage1_title": "Chunk {i} · Stage 1 — Identification",
        "stage3_title": "Chunk {i} · iter {iter} — Stage 3 Generation",
        "stage4_title": "Chunk {i} · iter {iter} — Stage 4 Verification {emoji} (verdict: {verdict}, score: {score}, threshold: {th})",
        "stage4_metric_score": "Score",
        "stage4_metric_critical": "Critical",
        "stage4_metric_major": "Major",
        "stage4_metric_minor": "Minor",
        # Final results
        "fin_header": "Final translation",
        "fin_terminology": "📚 Established terminology ({n} terms)",
        "fin_summary": "📖 Document summary (running, target-language)",
        "fin_run_details": "Run details (tokens, timings)",
        "fin_token_summary": "Pipeline: input {tin:,} · output {tout:,} tokens. Memory updates: input {mu_in:,} · output {mu_out:,} tokens.",
        "fin_raw_json": "Raw result JSON",
    },
    "ja": {
        # App header
        "app_title": "エージェンティック翻訳",
        "app_caption": "参考資料 → spec（対話） → Identify → Prompt → Generate → Verify",
        # Sidebar — API key
        "sb_api_section": "APIキー",
        "sb_api_label": "Anthropic APIキー",
        "sb_api_help": "キーはこのブラウザセッションのみに保持されます。console.anthropic.com で取得してください。",
        "sb_api_placeholder": "sk-ant-api03-...",
        "sb_api_set_runtime": "✓ キー設定済（このセッション）",
        "sb_api_set_env": "✓ キー設定済（.env から）",
        "sb_api_unset": "⚠️ APIキー未設定 — 翻訳できません",
        "sb_api_clear": "キーをクリア",
        # Sidebar — language
        "sb_ui_lang": "UI言語",
        # Sidebar — settings
        "sb_languages": "言語",
        "sb_source_lang": "原言語",
        "sb_target_lang": "目標言語",
        "sb_pipeline": "パイプライン",
        "sb_max_iter": "verification の最大反復回数",
        "sb_chunk_max": "1チャンク最大文字数",
        "sb_threshold": "MQM受理閾値（≥ で受理）",
        "sb_threshold_help": "MQM スコア = -25·critical -5·major -1·minor。-2 で minor を最大2件許容、0 で厳格。",
        "sb_reset": "セッションをリセット",
        # Section 1 — references
        "sec1_header": "① 参考資料 — {summary}",
        "sec1_glossary_md": "**用語集** (TSV/CSV：`source<TAB>target` 形式、1行1ペア)",
        "sec1_glossary_label": "用語集ファイル",
        "sec1_glossary_loaded": "用語集 {n} 件を読み込みました",
        "sec1_paired_md": "**対訳例** (TSV/CSV：`source<TAB>target` 形式、1行1ペア)",
        "sec1_paired_label": "対訳例ファイル",
        "sec1_paired_loaded": "対訳例 {n} 件を読み込みました",
        "sec1_parallel_md": "**パラレルテクスト**（目標言語のみ、`.txt` / `.md` 複数可）",
        "sec1_parallel_label": "パラレルテクスト",
        "sec1_parallel_loaded": "パラレルテクスト {n} 件を読み込みました",
        "sec1_styleguide_md": "**スタイルガイド** (`.md` / `.txt`)",
        "sec1_styleguide_label": "スタイルガイド",
        "sec1_styleguide_loaded": "スタイルガイドを読み込みました",
        "sec1_preview": "モデルへ送られる参考資料ブロックをプレビュー",
        # Section 2 — source
        "sec2_header": "② 原文",
        "sec2_placeholder": "翻訳する原文を貼り付けてください（段落は空行で区切ります）...",
        "sec2_chunks_doc": "**{n} チャンク** として処理されます — 文書レベルメモリ有効",
        "sec2_chunks_single": "**{n} チャンク** として処理されます — 単一チャンクモード",
        # Section 3 — spec
        "sec3_header": "③ 翻訳仕様（spec）",
        "sec3_propose": "spec を提案",
        "sec3_lock": "✅ この spec を確定",
        "sec3_unlock": "🔓 編集可能に戻す",
        "sec3_proposing": "原文と参考資料から spec を提案中...",
        "sec3_propose_failed": "spec 提案に失敗: {err}",
        "sec3_locked_msg": "spec が確定しました。翻訳を実行できます。",
        "sec3_spec_label": "現在の spec（markdown — 直接編集 もしくは下のチャットで指示）",
        "sec3_chat_md": "**チャットで spec を改訂** — 変更したい点を指示",
        "sec3_chat_placeholder": "例：「audience を20代の K-pop ファンに」「絵文字とソース言語の語をそのまま残して」 など",
        "sec3_refining": "改訂中...",
        # Section 4 — translate
        "sec4_header": "④ 翻訳実行",
        "sec4_button": "翻訳する",
        "sec4_lock_first": "上の spec を確定すると翻訳を実行できます。",
        # Run-time event labels
        "run_status": "文書パイプライン実行中...",
        "run_doc_start": "**文書開始** — {chunks} チャンク → {target}",
        "run_chunk_start": "**チャンク {i}/{n}** — {chars} 文字",
        "run_iter_prompt": "  チャンク {i}・反復 {iter} — プロンプト {chars:,} 文字",
        "run_chunk_done_ok": "✅ チャンク {i} 完了（反復: {iters}）",
        "run_chunk_done_warn": "⚠️ チャンク {i} 完了（反復: {iters}）",
        "run_doc_done": "文書翻訳完了 — {chunks} チャンク、{chars:,} 文字",
        "run_memory_title": "📚 チャンク {i} 後のメモリ（新規 {n} 項目）",
        "run_memory_new_terms": "**新規確立した用語：**",
        "run_memory_notes": "ノート: {text}",
        "run_memory_summary": "**走行要約：**",
        "run_memory_error": "⚠️ チャンク {i} のメモリ更新失敗: {err}",
        # Stage panels
        "stage1_title": "チャンク {i}・Stage 1 — Identification（状況解析）",
        "stage3_title": "チャンク {i}・反復 {iter} — Stage 3 Generation（翻訳生成）",
        "stage4_title": "チャンク {i}・反復 {iter} — Stage 4 Verification（検証）{emoji}（判定: {verdict}、スコア: {score}、閾値: {th}）",
        "stage4_metric_score": "スコア",
        "stage4_metric_critical": "Critical",
        "stage4_metric_major": "Major",
        "stage4_metric_minor": "Minor",
        # Final results
        "fin_header": "最終訳",
        "fin_terminology": "📚 確立された用語（{n} 項目）",
        "fin_summary": "📖 文書要約（走行・目標言語）",
        "fin_run_details": "実行詳細（トークン・所要時間）",
        "fin_token_summary": "パイプライン: 入力 {tin:,} ・出力 {tout:,} トークン。メモリ更新: 入力 {mu_in:,} ・出力 {mu_out:,} トークン。",
        "fin_raw_json": "結果 JSON（Raw）",
    },
}


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Look up a UI string. Falls back to English if key is missing in the requested language."""
    s = STRINGS.get(lang, {}).get(key)
    if s is None:
        s = STRINGS["en"].get(key, key)
    if kwargs:
        try:
            return s.format(**kwargs)
        except (KeyError, IndexError):
            return s
    return s
