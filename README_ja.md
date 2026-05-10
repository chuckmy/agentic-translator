# Agentic Translator

> 翻訳を「テキスト→テキストの変換」ではなく「**コミュニケーション設計（design）**」として捉え直す研究プロトタイプ。翻訳学のメタ言語を機械への指示コードとして用いる、エージェンティック翻訳の4ステージサイクル（Identify → Prompt → Generate → Verify）の実装です。

🌐 **公開デモ:** https://agentic-translator-chuckmy.streamlit.app
📄 **English version:** [README.md](README.md)

---

## このプロジェクトの位置づけ

DeepL や Google Translate のような汎用機械翻訳は、翻訳を **変換問題**として扱います。原文を入力すれば訳文が出力され、最適化対象は正確性（accuracy）です。しかし山田 (forthcoming) が *The Routledge Handbook of Translation and Technology*（第2版）所収の章 *Metalanguage and GenAI: Empowering Language Learners and Translators in Training* で論じるように、生成 AI の時代において、翻訳の「価値」はもはやそこにはありません：

> "The easier it becomes to generate text, the harder it becomes to ensure that text fulfils a specific communicative purpose."
>
> （テキスト生成が容易になればなるほど、特定のコミュニケーション目的を達成させるのは難しくなる）

良い翻訳とそうでない翻訳を分けるもの——レジスター、対象読者への適合、声、文化的な枠組み——は、これまでも常に **設計上の判断**であり、語彙レベルの正確性ではありませんでした。生成 AI は、これら従来は職人芸として暗黙化されていた判断を、**明示的で機械可読な指示**として扱うことを可能にしました。

このプロトタイプは、その考えを実装に落とし込んだものです。原文を投げる前に、ユーザは（モデルの助けを借りて）**翻訳仕様書**を作成し、それを踏まえてエージェンティックな4段階パイプラインが翻訳を実行します。

## 4ステージの循環

```
        ┌─────────────────────────────────────────────────────────┐
        │  ① Identification    Skopos · Audience · Register ·     │
        │     状況解析         Genre · Stance  →  JSON            │
        ├─────────────────────────────────────────────────────────┤
        │  ② Prompting         spec ＋参考資料＋状況解析を         │
        │     仕様化           決定論的にプロンプト合成             │
        ├─────────────────────────────────────────────────────────┤
        │  ③ Generation        LLM 呼出し → 翻訳ドラフト          │
        │     翻訳生成                                            │
        ├─────────────────────────────────────────────────────────┤
        │  ④ Verification      MQM エラースパン抽出（Freitag 2021）│
        │     検証             Accuracy / Fluency / Terminology / │
        │                      Style / Locale → スコア → 判定      │
        │                      （revise なら ② に戻り再生成）      │
        └─────────────────────────────────────────────────────────┘
```

このコアの周りに、3つの拡張層：

- **対話的 spec 作成。** 翻訳実行前に、モデルが markdown 形式で仕様書を提案します（skopos / 対象読者 / レジスター / ジャンル / 用語ガイダンス / スタイル決定 / 保持すべきもの・現地化すべきもの・避けるべきもの / 未決事項）。ユーザは直接編集するか、チャットで指示して詰めます（「対象を 15-25歳の K-pop ファンに」「正式な場面なので だ・である調 で」など）。**ユーザが明示的に spec をロックするまで翻訳は実行されません**。
- **参考資料の取り込み。** 用語集、対訳例、目標言語のパラレルテクスト、自由記述のスタイルガイドの 4 種類をアップロードでき、それらは spec 提案・翻訳プロンプト・検証の各ステージに自動的に注入されます。
- **文書レベルメモリ（DelTA-lite）。** 複数段落の入力では、文書を段落単位でチャンク化し、**固有名詞台帳**と**走行用の二言語要約**がチャンクをまたいで持続します。これにより章単位の翻訳でも用語と声の一貫性が保たれます。

## 既存の翻訳ツールとの違い

| 一般的な MT | このプロトタイプ |
|---|---|
| 単一機能：テキスト → テキスト | spec 作成 + 翻訳 + 検証 |
| スタイル・対象読者は暗黙 | スタイル・対象読者は **ユーザが明示的に記述するフィールド** |
| 評価軸は固定（正確性のみ） | MQM の類型化されたエラー＋重み付きスコア |
| チャンク間で状態を持たない | 文書全体で用語・要約を持続 |
| 評価はブラックボックス | エラースパンを原文・訳文から逐語的に引用、判定はスコアから決定論的に算出 |
| ユーザは戦略を指示できない | ユーザがチャットで spec を共同設計 |

## 理論的背景

このアーキテクチャは下記の枠組みに準拠します：

> Yamada, M. (forthcoming). Metalanguage and GenAI: Empowering language learners and translators in training. In *The Routledge Handbook of Translation and Technology* (2nd ed.).

同章の中心的な主張——**翻訳学の語彙は、いまや機械への指示コードである**（skopos / register / audience / equivalence / foreignization / domestication / genre 等）——が、本アプリの中核に据えた「明示的・構造化された spec」の動機になっています。

加えて以下の研究を参照しています：

- Kocmi, T. & Federmann, C. (2023). [GEMBA-MQM: Detecting Translation Quality Error Spans with GPT-4](https://arxiv.org/abs/2310.13988). *WMT 2023.* — MQM 形式の verifier の根拠。
- Freitag, M., Foster, G., Grangier, D., Ratnakar, V., Tan, Q., & Macherey, W. (2021). [Experts, Errors, and Context: A Large-Scale Study of Human Evaluation for Machine Translation](https://arxiv.org/abs/2104.14478). *TACL.* — エラーカテゴリと重み付けの根拠。
- Wang, Y. et al. (2024). [DelTA: An Online Document-Level Translation Agent Based on Multi-Level Memory](https://arxiv.org/abs/2410.08143). *ICLR 2025.* — 固有名詞台帳と走行要約の根拠。
- Kayano, S. & Sugawara, Y. (2025). [Specification-Aware Machine Translation and Evaluation for Purpose Alignment](https://arxiv.org/abs/2509.17559). *WMT 2025.* — spec 駆動 LLM 翻訳の最も近い先行研究。
- Wu, M. et al. (2024/2025). [(Perhaps) Beyond Human Translation: Harnessing Multi-Agent Collaboration for Translating Ultra-Long Literary Texts](https://arxiv.org/abs/2405.11804). *TACL.* — 役割分割型のエージェント翻訳。

## 構成

```
agentic_translator/
├── app.py                    Streamlit UI（英語／日本語切替）
├── pipeline.py               4ステージサイクル + run_document_pipeline
├── spec_chat.py              propose_spec + 対話改訂
├── memory.py                 DocumentMemory + update_memory（DelTA-lite）
├── chunker.py                段落分割
├── references.py             参考資料 4 種類の取り込み
├── api.py                    APIキーの集中管理
├── i18n.py                   UI 翻訳辞書（en / ja）
├── prompts/
│   ├── identify.txt          Stage 1 — 状況解析
│   ├── translate.txt         Stage 3 テンプレート
│   ├── verify.txt            Stage 4 — MQM エラースパン抽出
│   ├── propose_spec.txt      初期 spec 生成
│   ├── refine_spec.txt       チャットによる spec 改訂
│   └── update_memory.txt     固有名詞・要約の更新
├── specs/                    サンプル スタイル仕様
├── test_set/                 バイリンガル テストセット（3ジャンル×2方向）
└── requirements.txt
```

## クイックスタート

### 公開デモを試す

https://agentic-translator-chuckmy.streamlit.app を開き、サイドバーで自分の Anthropic APIキーを入力してください（**キーはあなたのブラウザセッション内にのみ保持され、サーバーには保存されません**）。APIキーは https://console.anthropic.com で取得できます。

### ローカルで実行

```bash
git clone https://github.com/chuckmy/agentic-translator.git
cd agentic-translator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# .env にキーを設定するか（.env.example 参照）、UI から入力
streamlit run app.py
```

ブラウザで http://localhost:8501 を開きます。

### 操作の流れ

1. （任意）**① 参考資料**で用語集・対訳例・パラレルテクスト・スタイルガイドをアップロード
2. **② 原文** に翻訳したい文章を貼付（複数段落で文書レベルメモリ有効）
3. **③ 翻訳仕様** で **spec を提案** → markdownを直接編集 or チャットで改訂 → **この spec を確定**でロック
4. **④ 翻訳実行** をクリック。各ステージがリアルタイムで展開、チャンク間で固有名詞台帳と要約が育っていきます

## テストセット

`test_set/` には、ジャンル（スポーツニュース／文学／学術）× 方向（日→英・英→日）の **6 つの複数段落テキスト**、用語集、対訳例、スタイルガイドが含まれています。複数チャンクにまたがるよう設計されているので、文書レベルメモリの動作を観察できます。詳細は [`test_set/README.md`](test_set/README.md) を参照。

## ステータス

これは **研究プロトタイプ**であり、商用品ではありません。山田 (forthcoming) の議論を補完し、同僚・学生・研究者が spec 駆動エージェンティック翻訳を試行できるようにすることを目的に公開しています。フィードバック・プルリクエスト歓迎。

## ライセンス

MIT License — © 2026 株式会社翻訳ラボ Translation Lab Inc. 詳細は [LICENSE](LICENSE) を参照。
