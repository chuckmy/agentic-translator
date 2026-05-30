# Agentic AI Translate：コミュニケーション設計としての翻訳を実装するエージェンティック翻訳プロトタイプ

**山田 優**（立教大学；株式会社翻訳ラボ）

> **ステータス:** システム論文ドラフトの確認用日本語版。アーキテクチャ上・概念上の貢献を中心に記述し、実証評価は今後の課題として位置づける。

---

## 要旨

本稿では、山田（forthcoming）が提示する「翻訳学のメタ言語は生成 AI への指示コードになった」という主張を実装として具体化するエージェンティック翻訳プロトタイプ **Agentic AI Translate** を提示する。本システムは、従来の機械翻訳における支配的な「テキスト入力／テキスト出力」パラダイムを、**Identify → Prompt → Generate → Verify** からなる4段階のエージェンティックな循環へと置き換える。その前段には、ユーザがモデル支援の対話を通じて、スコポス理論、レジスター、対象読者、ジャンル規範に基づく構造化された翻訳仕様書を作成する **対話的仕様化フェーズ** を置く。検証段階では、エビデンスに基づく採点のために GEMBA-MQM エラースパン抽出プロトコル（Kocmi & Federmann, 2023）を採用し、文書レベルの一貫性は、固有名詞台帳と走行要約からなる *DelTA-lite* メモリ（Wang et al., 2025）によって保持する。本稿では、システムの哲学的動機、アーキテクチャ上のコミットメント、取り込む4種類の参考資料、そしてこの構成が明示化する主要な設計上の緊張関係を述べる。実証的検証は今後の課題とし、本稿の貢献は概念的・アーキテクチャ的なものである。すなわち、*GenAI 時代の翻訳はテキスト変換ではなくコミュニケーション設計である* という立場を、実行可能なシステムとして具現化することである。

**キーワード:** エージェンティック翻訳、翻訳学のメタ言語、スコポス、MQM、文書レベル翻訳、大規模言語モデル、翻訳仕様書。

---

## 1. はじめに

過去40年にわたり、機械翻訳研究は単一の最適化目標を中心に展開してきた。すなわち、原文文字列と訳文文字列のあいだの語彙的・文法的忠実性である。統計的機械翻訳およびニューラル機械翻訳は、高リソース言語対において専門的な人間翻訳との精度差を徐々に縮めてきた。そして大規模言語モデル（LLM）は現在、セグメント単位における流暢性、慣用性、基本的なレジスター適合をほぼ無償のものにしつつある（Kocmi et al., 2024; Karpinska & Iyyer, 2023）。Kano モデル（Kano, 1984）の観点からいえば、**正確性は Must-Be 品質として飽和した**。正確性があることはもはや差別化要因ではなく、欠けている場合にのみ気づかれる。

したがって、翻訳価値のフロンティアは、Tannen（1986）がいう *what* ではなく *how* へ、すなわちレジスター、対象読者設計、声、スタンス、文化的枠組み、ジャンル規範へと移った。これらは専門翻訳者にとって常に重要であったにもかかわらず、計算機的研究では歴史的に暗黙化されてきた次元である。山田（forthcoming）は、*Metalanguage and GenAI: Empowering Language Learners and Translators in Training*（*Routledge Handbook of Technology and Translation* 第2版所収予定）において、これは単なる評価基準の変化ではなく、翻訳者の役割の根本的な **再構成** であると論じる。翻訳者は、訳文を手作業で作成する者から、生成システムがテキストを生み出す **条件を設計する者**、そしてそのテキストがコミュニケーション目的を満たしているかを **検証する者** へと移行する。山田は次のように述べる。

> “The easier it becomes to generate text, the harder it becomes to ensure that text fulfils a specific communicative purpose.”

この「自動化のパラドックス」は、翻訳学（Translation Studies: TS）の語彙、すなわち *skopos, register, audience, equivalence, foreignization, domestication, genre, stance, loyalty* などが、LLM に指示を与えるために必要な記述精度をまさに提供していると理解すれば解消される。**理論は操作可能なものになる。** かつて実践について考えるために学ばれていたものが、いまや機械に指示するために語られる。

本稿では、その議論を実行可能な形で具現化する。**Agentic AI Translate** は、翻訳リクエストを受け取り、生成の前にユーザを構造化された翻訳仕様書の作成へと導く、公開済みの研究プロトタイプであり、エージェンティック翻訳システムである。その後、仕様書を一貫して用いるエージェンティックな4段階パイプライン（Identification → Prompting → Generation → Verification）を実行し、長い入力における用語一貫性を保つために文書レベルの状態を保持する。本稿の貢献は実証的なものではない。非構造化プロンプトとの比較 MQM 研究はまだ実施していない。むしろ本稿の貢献は、上記の立場をコードとして実現するならば **そのシステムは何を含まなければならないか** を、実行可能な記述として提示する点にある。

以下では、第2節で哲学的動機を述べ、第3節でアーキテクチャを定義する。第4節では実装を説明し、第5節ではエージェンティック LLM 翻訳、文書レベル MT、翻訳評価に関する近年の研究との関係を整理する。第6節では限界と主要な設計上の緊張関係を論じ、第7節では検証計画と、今後の中心的研究課題である構造化 spec 拡張を示す。

---

## 2. 哲学的動機：コミュニケーション設計としての翻訳

### 2.1 GenAI 時代における二つの層

翻訳は常に二つの層で成り立ってきた。命題内容、すなわち *what* と、その内容が目標言語においてどのように実現されるか、すなわち *how* である。後者には、レジスター、文のリズム、社会方言的標識、脚注慣習、文化固有項目の処理、想定読者を位置づける呼びかけ性などが含まれる。House（2015）の overt/covert 区別、Reiss（1971/2000）のテキスト類型論、Nord（1997）の機能主義的枠組み、Vermeer（1978）のスコポス理論はいずれも、表層的等価性よりコミュニケーション目的を優先することを前景化している。これは新しい観察ではなく、翻訳学における広範な合意である（Munday, 2016）。

新しいのは、近年までそのような制約を翻訳システムに符号化するには、領域特化モデルを学習するか、汎用システムの出力をポストエディットするしかなかったという点である。いずれの方法も、コミュニケーション設計を翻訳に **後から適用されるもの** として扱っていた。生成 LLM はこの状況を変える。LLM は長く構造化された自然言語指示を推論時に受け取り、その指示に基づいて生成を条件づける能力を持つ（Vilar et al., 2023; Karpinska & Iyyer, 2023）。**コミュニケーション設計は第一級の入力になる。**

### 2.2 翻訳単位としての「声」

村上春樹による Salinger の *The Catcher in the Rye* の日本語訳を考えてみる。冒頭の “If you really want to hear about it...” は複数の日本語訳で異なる忠実性をもって訳されてきたが、村上訳が意図的に保存しているのは、Salinger の表層語彙ではなく、Holden Caulfield の **声** である。すなわち、特定のリズム、特定の読者との関係である。現在の LLM に短い村上訳の例を与え、few-shot プロンプトとして隣接箇所を翻訳させると、その声をかなり忠実に再現できる。これは LLM が Salinger や村上を読んでいるからではなく、その声がモデルの従うべき **制約として指定された** からである。

ここに「翻訳＝設計」論の操作上の核心がある。文学翻訳において最も職人的に見える「声」は **指定可能** であり、指定されれば大規模に再現可能である。翻訳者の貢献は、すべての文を手で起草することではなく、**制約としての声を設計すること** へと移る。

### 2.3 翻訳者の再構成

山田（forthcoming）は、これからの翻訳者の役割を **designer + verifier** として捉える。

- **Designer**: スコポス、対象読者、レジスター、ジャンルなどの状況分析と、用語集、対訳例、パラレルテクストなどの操作的 artefact を、メタ言語的精度をもって構成する。
- **Verifier**: 出力を単なるポストエディット対象としてではなく、機能的・認識論的判断の対象として評価する。つまり、その訳文は読者に届くか、事実構造を保持しているか、spec と合っているかを判断する。

教育上の重要な含意は、翻訳学の **語彙**、すなわち Gambier（2009）が discipline の *meta-language* と呼んだものが、もはや実践について **考えるため** だけでなく、機械に **指示するため** に学ばれるという点にある。翻訳学の理論装置は、操作可能なインフラになる。本システムはこの認識に基づいて構築されている。

---

## 3. アーキテクチャ

本システムは三つの同心円的な層から成る。パイプラインとしての **4段階サイクル**、すべての段階を条件づける **対話的仕様書**、そして文書レベルの一貫性を保つ **持続状態** である。

### 3.1 4段階サイクル

```
        ┌─────────────────────────────────────────────────────────┐
        │  ① Identification                                       │
        │     LLM が原文から {skopos, audience, register,         │
        │     genre, stance, notes} を JSON として抽出する。      │
        ├─────────────────────────────────────────────────────────┤
        │  ② Prompting                                            │
        │     Python が spec + references + identification +      │
        │     memory から決定論的に翻訳プロンプトを合成する。      │
        ├─────────────────────────────────────────────────────────┤
        │  ③ Generation                                           │
        │     単一の LLM 呼び出しがドラフト訳を生成する           │
        │     （T = 0.3）。                                      │
        ├─────────────────────────────────────────────────────────┤
        │  ④ Verification                                         │
        │     LLM-as-judge が MQM エラースパン                    │
        │     {span, category, severity, explanation} を返す。    │
        │     Score = -25·crit -5·major -1·minor。                │
        │     閾値に対して判定を決定論的に算出する。              │
        │     revise の場合は、エラーを Stage 2 に戻し、          │
        │     最大2回まで再生成する。                            │
        └─────────────────────────────────────────────────────────┘
```

**なぜ一段階ではなく四段階なのか。** 単一の end-to-end プロンプトでは、モデルは状況分析、プロンプト組み立て、生成、自己評価を一つの forward pass の中で行うことになる。その結果、出力は流暢でも、ほとんど分析不能になる。分解により、それぞれのコミットメントが検査可能な artefact として表面化する。Identification JSON、組み立てられた Stage 2 プロンプト、Verification のエラースパンは、すべてログとして残され、UI 上で可視化される。これは意図的な設計である。システムの教育的・研究的価値は、各段階が読めることに依存しているからである。

**なぜ Stage 1 を独立した LLM 呼び出しにするのか。** 状況分析は、原理的には単一の生成プロンプトに折り込むこともできる。ここで分離する理由は二つある。第一に、その JSON（`{skopos, audience, register, genre, stance, notes}`）は、メタ言語論の最も直接的な具現化である。翻訳学のカテゴリーが散文ではなく構造化フィールドとして現れる。第二に、分離することで、モデルが行った状況分析をユーザが見ることができ、生成前に異議を唱える余地が生まれる。現行実装ではこれは読み取り専用 artefact であるが、ユーザ編集可能にすることは計画中の拡張である。

### 3.2 対話的仕様書

本システムの最も特徴的な要素は、パイプラインの前に置かれた層である。原文入力後、ユーザが **Propose spec** をクリックすると、モデルは原文とアップロード済みの参考資料に基づき、十の標準セクションを持つ構造化 markdown 文書を返す。セクションは *Skopos, Audience, Register & Voice, Genre, Terminology guidance, Style decisions, Things to preserve, Things to localise, Things to avoid, Open questions* である。ユーザは次の操作を行える。

1. markdown を UI 上で直接編集する。
2. チャットで改訂する（例：「audience is academic peer reviewers」「use だ・である調 throughout」「preserve emoji and source-language fan vocabulary」）。
3. 満足するまで反復し、最後に **Use this spec** をクリックして spec をロックする。

ロック段階は意図的である。これは、明示的でユーザが承認した仕様書なしに翻訳を生成できないという **アーキテクチャ上のコミットメント** を強制する。したがって、このシステムは汎用 MT ツールとしては使えない。spec 駆動の翻訳ツールとしてのみ使える。この制約こそが、哲学的立場を操作可能にしている。

仕様書は Stage 2（Prompting）と Stage 4（Verification）の双方で同一に消費される。検証器は、生成器が条件づけられたのと同じ spec に照らして訳文を判断する。これにより、生成器と検証器が暗黙に異なる「良い翻訳」像を持つという評価上の抜け穴を閉じる。

### 3.3 参考資料層

アップロードできる参考資料は四種類である。

| 種類 | 形式 | 機能 |
|---|---|---|
| 用語集 | TSV/CSV（source ↔ target） | 必須用語 |
| 対訳例 | TSV/CSV（source ↔ target） | 翻訳判断の few-shot 例 |
| 目標言語のパラレルテクスト | TXT/MD | ジャンル・声の例示 |
| スタイルガイド | MD/TXT | 自由記述の制約 |

これらの分類は、専門的な CAT/TMS ワークフローで用いられる実務的分類に従うものであり、翻訳仕様に関する ASTM F2575 標準とも部分的に対応している。システムは四種類すべてを、spec 提案、生成プロンプト、検証器に注入する。各消費者は、それらをどのように重みづけるかを判断する。現行実装ではすべての対訳例を注入するが、選択的検索（Agrawal et al., 2023 に基づく R-BM25 や embedding similarity）は今後の改良点である。

### 3.4 文書レベルメモリ（DelTA-lite）

複数段落の入力では、chunker が空行による段落境界で文書を分割する。長すぎる段落については文境界で補助的に分割する。各チャンクは独立に翻訳されるが、チャンク間では補助的な LLM 呼び出しによって **持続メモリ** が更新される。これは Wang et al.（2025）の DelTA に基づく。

- **固有名詞台帳**: 安定して訳されるべき語（人物、地名、組織、製品、専門用語）について、source-to-target の辞書を走行的に保持する。
- **二言語走行要約**: 文書の進行を把握し、文体的連続性を支えるための、目標言語による50〜150語程度の要約。
- **直前ウィンドウ文脈**: 直前チャンクの原文と訳文。

これら三つの artefact は、次チャンクの Stage 2 プロンプトに、明示的見出し（*Established terminology*, *Document summary so far*, *Immediately preceding chunk*）のもとで注入され、モデルにはそれらを遵守するよう指示される。複数段落の文学・ジャーナリズム系テスト入力に対する非公式観察では、台帳はチャンクをまたいで再出する固有表現（例：*夏目漱石 → Natsume Soseki*, *苦沙弥先生 → Kushami*）を追加介入なしに正しく捕捉しており、Wang et al.（2025）が大規模に報告した一貫性向上と対応している。

### 3.5 MQM に基づく検証

Stage 4 は Kocmi & Federmann（2023）の **GEMBA-MQM** プロトコルに従う。検証プロンプトは言語非依存であり、モデルにエラースパンを特定し、それぞれに MQM カテゴリーと深刻度を割り当て、構造化 JSON リストとして返すよう指示する。カテゴリー集合は Freitag et al.（2021）の標準的な分類に従う。すなわち、*Accuracy*（誤訳、追加、脱落、未翻訳、訳さない指定違反）、*Fluency*（文法、句読点、綴り、レジスター、不一致、文字コード）、*Terminology, Style, Locale convention, Other* である。深刻度は *critical, major, minor* のいずれかである。エラーリストから決定論的に以下のスコアを算出する。

$$
\text{score} = -25 \cdot n_{\text{critical}} - 5 \cdot n_{\text{major}} - 1 \cdot n_{\text{minor}}
$$

判定は、スコアが設定可能な閾値（デフォルト −2、すなわち minor 2件まで許容、major または critical があれば再生成）を満たせば *accept*、そうでなければ *revise* となる。revise の場合、型づけされたエラーリストが実行可能な指示として Stage 2 プロンプトにそのまま追加され、Stage 3 が再実行される。ループは2回に制限される。Huang et al.（2024）および Stechly et al.（2024）は、LLM の内在的自己修正が急速に逓減し、出力を悪化させることさえあることを示しているためである。

本システムでは Fernandes et al.（2023）および Wang et al.（2024）に従い、検証器に **スコアの前にエビデンス（エラースパン）を出力させる**。これは、LLM-as-judge 構成における冗長性や自己選好バイアスを経験的に減らす。

---

## 4. 実装

システムは、プロンプトとテストを除き、およそ1200行の Python で実装されている。ランタイムスタックは以下である。

- **Anthropic SDK**（デフォルトモデルは Claude Sonnet 4.6、設定可能）および **OpenAI SDK**（Responses API、設定可能）。
- **Streamlit** による UI。
- ローカル開発用の **python-dotenv**。デプロイ時には、API キーはサイドバーからユーザがセッションごとに入力する（共有キーは持たない）。
- ベクトルデータベース、GPU、ファインチューニングは使用しない。

最小構成であることは意図的である。システム内のすべてのコミットメントは、学習済み重みではなく、*プロンプト* と *Python のフロー制御* に置かれている。これにより、システムは完全に検査可能かつ再現可能になり、代替 spec 構造や検証プロンプトを試すコストはテキストファイルを編集する程度に抑えられる。

リポジトリは MIT ライセンス（© Translation Lab Inc.）のもと GitHub（https://github.com/chuckmy/agentic-translator）で公開されており、bring-your-own API key 方式のライブデモが Streamlit Community Cloud（https://agentic-translator-chuckmy.streamlit.app）上にデプロイされている。再現的な探索を支援するため、3ジャンル（モータースポーツニュース、文学描写、学術抄録）×双方向翻訳のバイリンガルテストセットも含めている。

---

## 5. 関連研究

**Spec-aware MT.** 最も近い先行研究は Kayano & Sugawara（2025）である。彼らは、目的、対象読者、レジスターを含む明示的な翻訳仕様を用いたプロンプトが、意図が豊かなテキストにおける選好スコアを有意に改善し、ときに人間参照訳を上回ることを示した。彼らの仕様は平坦な自由記述テキストとして提示される。本研究は、仕様を安定した構造テンプレートを持つ、対話的に **作成される** artefact とし、生成だけでなく検証にも通す点で拡張している。

**マルチエージェント翻訳.** Wu et al.（2024/2025）の **TransAgents** は、CEO、編集者、翻訳者、ローカライザー、校正者、QA からなる六エージェント・シミュレーションを用いて、超長編文学テキストを翻訳する。専門家およびクラウド評価者は、書籍長入力において、GPT-4 の単一呼び出し出力や人間参照訳よりもこのシステムを好んだ。ただし d-BLEU は低かった。これは、第2節で述べた *attractive quality* の次元に対して、パイプライン分解が質的に有益であることを示す最も強い証拠である。Briakou et al.（2024）の **Translating Step-by-Step** も、単一モデル内で pre-translation research → drafting → refining → proofreading という同様の原理を示し、WMT24 SOTA を達成している。本プロトタイプの形は TransAgents より後者に近いが、計画中の拡張（R5, §7）は役割分解へ向かう。

**文書レベル翻訳.** Karpinska & Iyyer（2023）は、特に文学的レジスターにおいて、文単位より段落単位の LLM 翻訳が人間評価で強く好まれることを示した。**DelTA**（Wang et al., 2025）は、固有名詞、二言語要約、長期、短期からなる明示的な四層メモリを導入し、一貫性の測定可能な向上を示した。本システムの DelTA-lite は、そのうち最初の二層を実装している。

**翻訳評価における LLM-as-judge.** Kocmi & Federmann（2023）は、固定された three-shot MQM プロンプトを用いた GPT-4 が、専門家 MQM と十分に相関するスコアを生成し、WMT23 metrics task で優勝する水準に達することを示した。xCOMET（Guerreiro et al., 2024）や MetricX-25 は、WMT24/25 のセグメントレベルでは *学習済み* メトリクスがなお LLM-judge プロンプトを上回ることを示している。本研究はこれを受け入れ、LLM-judge をシステムの第一評価線として用いつつ、外部信号として xCOMET を追加する計画を第6節で述べる。

**MT における自己修正.** Madaan et al.（2023）は Self-Refine を提案し、Feng et al.（2024）の **TEaR** は MQM 型フィードバックがリファイン品質を改善することを示した。一方、Huang et al.（2024）および Stechly et al.（2024）は、内在的自己修正の限界を示し、見かけの改善が真の自己批判ではなくサンプリング多様性の artefact である場合が多いことを指摘している。本システムはこのため revise ループを制限している。

**操作化された翻訳学フレームワーク.** Singh et al.（2024）および *Honorific Effect* 論文（2024）は、LLM による文化的・レジスター固有の適応を検討している。Reiss、Nord、House などの翻訳学フレームワークを機械可読スキーマとして体系的に符号化することは、なお未開拓領域であり、第7節で本研究の主要な方向として位置づける。

---

## 6. 議論と限界

### 6.1 このプロトタイプが主張すること、しないこと

本研究は **アーキテクチャ上の貢献** である。本稿が主張するのは、このアーキテクチャが「翻訳＝設計」という立場を整合的に具現化しているという点であり、代替手法より測定可能に良い翻訳を生成すると主張するものではない。同じ原文、同じ目標言語、同じモデルを用い、spec あり／なしを複数ジャンル・複数言語対で比較し、専門翻訳者が完全な MQM で評価する統制実験が次の必要な段階である。

### 6.2 単一モデル検証は最も弱いリンクである

現在の検証器は生成器と同じモデルファミリ上で動作する。このため、**自己選好バイアス**（Zheng et al., 2023; Wang et al., 2024）および内在的自己修正の一般的限界（Huang et al., 2024; Stechly et al., 2024）にさらされる。二回に制限されたループと、エラーをスコアより先に出力させる evidence-first プロンプト構造は、これを緩和するが解決はしない。計画中の拡張（R2, §7）では、クロスモデル judge と外部の学習済み QE 信号（xCOMET-XL または MetricX-25）を導入する。

### 6.3 現在の spec は自由記述 markdown である

対話的仕様書は十の標準見出しを持つ markdown 文書であるが、それ以外の内容は制約されない。これは表現の豊かさを許す一方で、機械可読性を制限し、個別フィールドに対する体系的 A/B 実験（例：*loyalty target* を指定すると測定可能な行動変化が起きるか）を困難にする。計画中の拡張（R6, §7）では、markdown を Reiss のテキスト類型論、Nord の loyalty、House の overt/covert mode、domestication–foreignization 連続体を操作化する JSON スキーマに置き換え、markdown 表示はスキーマから派生させる。これが本プロジェクトの主要な研究方向である。

### 6.4 参考資料は選択なしに注入される

現在はすべての対訳例がすべてのプロンプトに注入される。Agrawal et al.（2023）は、ミスマッチな in-context example が一つでもあると、例がない場合より翻訳品質を悪化させ得ることを示した。Vilar et al.（2023）は、大規模モデルでは例の *品質* が類似性より支配的であることを示している。これらはいずれも、品質タグ付き TU ストアに対する R-BM25 と embedding similarity による検索選択を動機づけるが、現行実装にはまだ存在しない。

### 6.5 実証評価がまだない

最も重要な限界である。検証計画は §7.1 に示す。

---

## 7. 今後の課題

### 7.1 実証的検証

（a）汎用プロンプト翻訳、（b）自由記述 spec、（c）構造化スキーマ spec を比較する factorial study が必要である。ジャンルは（i）文学、（ii）ジャーナリズム、（iii）学術、言語方向は（α）JA→EN、（β）EN→JA とし、Freitag-2021 MQM と ESA severity protocol を用いて専門翻訳者が評価する。この研究により、spec 駆動アーキテクチャがどこで測定可能な改善をもたらすかを確認できる。評価者間一致と、accuracy / style / terminology ごとの分解により、どの *attractive quality* 次元が spec に敏感かを同定できる。

### 7.2 構造化仕様スキーマ（R6）

markdown spec を次のような JSON スキーマに置き換える。

```json
{
  "skopos": "...",
  "text_type": "informative | expressive | operative | audiomedial",
  "house_mode": "overt | covert",
  "loyalty": { "author_intention": 0.7,
               "ST_culture_fidelity": 0.5,
               "TT_reader_orientation": 0.9,
               "commissioner_brief": 0.6 },
  "domestication_axis": 0.7,
  "audience": { ... },
  "register": { ... },
  "preserve": [...], "localize": [...], "avoid": [...]
}
```

Reiss のテキスト類型論、Nord の loyalty 原則、House の overt/covert 区別、Schleiermacher–Venuti の domestication–foreignization 軸は、ユーザが入力する **フィールド** になる。同じスキーマが生成プロンプト、検証プロンプト、そして重要なことに実験設計を支える。フィールドを ablate したり、入れ替えたり、一定に保ったりできるため、自由記述 spec では構造的に不可能な A/B 研究が可能になる。

### 7.3 マルチエージェント分解

TransAgents および Briakou et al. に従い、Stage 3 を **research → draft → localise → proofread** に分割する。各 pass は同じロック済み仕様書によって統制される。特に *localise* pass（文化的レンダリング、慣用句処理）に価値が期待される。TransAgents はこれを専門家選好に最も寄与する要素として同定している。

### 7.4 外部品質信号

LLM judge と並行して **xCOMET-XL** または **MetricX-25** を追加し、そのスコアも acceptance gate に組み込む。Sonnet generator + Gemini または GPT-5 judge のようなクロスモデル judging により、自己選好バイアスに対処する。

### 7.5 ハルシネーション検出

Stage 4 に entity-preservation check を追加する。すなわち、原文中の固有名詞と数値は訳文中に現れるか、明示的対応物を持たなければならない（Guerreiro et al., 2023）。山田の *factual* 軸は、現在、流暢だが捏造を含む出力に対して最も弱い検出器である。

---

## 8. 結論

本稿では、GenAI 時代の翻訳は *コミュニケーション設計* であるという立場を、実行可能な形で具現化する研究プロトタイプを記述した。対話的仕様書、4段階サイクル、文書レベルメモリ、MQM に基づく evidence-first 検証という中核的コミットメントは、恣意的な工学的選択ではなく、山田（forthcoming）が提示するメタ言語論を直接操作化したものである。本システムは公開されており、同僚、学生、研究者がこの立場を検討し、拡張し、批判できるようにしている。

残されているのは、本稿が意図的にまだ行っていない実証的作業である。すなわち、*仕様を明示すること* が、MQM 上測定可能な形で、lecture-platform argument が予測する *attractive quality* の質的変化をもたらすかどうかを示す統制研究である。その研究と、それに必要な構造化スキーマ拡張が、本プロジェクトの次段階である。

---

## 参考文献

Agrawal, S., Zhou, C., Lewis, M., Zettlemoyer, L., & Ghazvininejad, M. (2023). In-context examples selection for machine translation. In *Findings of ACL 2023* (pp. 8857–8873).

Briakou, E., Luo, J., Cherry, C., & Freitag, M. (2024). Translating step-by-step: Decomposing the translation process for improved translation quality of long-form texts. In *Proceedings of WMT 2024*. arXiv:2409.06790.

Buffon, G.-L. L. (1753). *Discours sur le style.* Paris: Académie française.

Feng, Z., Zhang, Y., Li, H., Liu, W., Lang, J., Feng, Y., Wu, J., & Liu, Z. (2025). TEaR: Improving LLM-based machine translation with systematic self-refinement. In *Proceedings of NAACL 2025*. arXiv:2402.16379.

Fernandes, P., Yin, K., Liu, E., Martins, A. F. T., & Neubig, G. (2023). The devil is in the errors: Leveraging large language models for fine-grained machine translation evaluation. arXiv:2308.07286.

Freitag, M., Foster, G., Grangier, D., Ratnakar, V., Tan, Q., & Macherey, W. (2021). Experts, errors, and context: A large-scale study of human evaluation for machine translation. *Transactions of the Association for Computational Linguistics, 9*, 1460–1474.

Freitag, M., et al. (2024). Are LLMs breaking MT metrics? Results of the WMT24 metrics shared task. In *Proceedings of WMT 2024*.

Gambier, Y. (2009). *Stratégies et tactiques en traduction et interprétation.* In Gambier, Y., & Doorslaer, L. van (Eds.), *Handbook of Translation Studies* (Vol. 1). Amsterdam: John Benjamins.

Guerreiro, N. M., Voita, E., & Martins, A. F. T. (2023). Looking for a needle in a haystack: A comprehensive study of hallucinations in neural machine translation. In *Proceedings of EACL 2023* (pp. 1059–1075).

Guerreiro, N. M., Rei, R., van Stigt, D., Coheur, L., Colombo, P., & Martins, A. F. T. (2024). xCOMET: Transparent machine translation evaluation through fine-grained error detection. *Transactions of the Association for Computational Linguistics, 12*, 979–995.

House, J. (2015). *Translation Quality Assessment: Past and Present.* London: Routledge.

Huang, J., Chen, X., Mishra, S., Zheng, H. S., Yu, A. W., Song, X., & Zhou, D. (2024). Large language models cannot self-correct reasoning yet. In *Proceedings of ICLR 2024.* arXiv:2310.01798.

Kano, N., Seraku, N., Takahashi, F., & Tsuji, S. (1984). Attractive quality and must-be quality. *Journal of the Japanese Society for Quality Control, 14*(2), 39–48.

Karpinska, M., & Iyyer, M. (2023). Large language models effectively leverage document-level context for literary translation, but critical errors persist. In *Proceedings of WMT 2023* (pp. 419–451).

Kayano, S., & Sugawara, Y. (2025). Specification-aware machine translation and evaluation for purpose alignment. In *Proceedings of WMT 2025*. arXiv:2509.17559.

Kocmi, T., & Federmann, C. (2023). Large language models are state-of-the-art evaluators of translation quality. In *Proceedings of EAMT 2023.* arXiv:2302.14520.

Kocmi, T., & Federmann, C. (2023). GEMBA-MQM: Detecting translation quality error spans with GPT-4. In *Proceedings of WMT 2023.* arXiv:2310.13988.

Kocmi, T., et al. (2024). Findings of the 2024 Conference on Machine Translation (WMT24). In *Proceedings of WMT 2024*.

Madaan, A., et al. (2023). Self-Refine: Iterative refinement with self-feedback. In *Advances in Neural Information Processing Systems 36* (NeurIPS 2023). arXiv:2303.17651.

Munday, J. (2016). *Introducing Translation Studies: Theories and Applications* (4th ed.). London: Routledge.

Nord, C. (1997). *Translating as a Purposeful Activity: Functionalist Approaches Explained.* Manchester: St. Jerome.

O'Brien, S. (2024). Human-centred augmented translation: Against antagonism between human and machine. *Translation Spaces, 13*(1).

Reiss, K. (1971/2000). *Translation Criticism: The Potentials and Limitations* (E. Rhodes, Trans.). Manchester: St. Jerome.

Singh, P., Jangra, A., et al. (2024). Translating across cultures: LLMs for intralingual cultural adaptation. In *Proceedings of CoNLL 2024*.

Stechly, K., Valmeekam, K., & Kambhampati, S. (2024). On the self-verification limitations of large language models on reasoning and planning tasks. In *Proceedings of ICML 2024.* arXiv:2402.08115.

Tannen, D. (1986). *That's Not What I Meant! How Conversational Style Makes or Breaks Relationships.* New York: William Morrow.

Vermeer, H. J. (1978). Ein Rahmen für eine allgemeine Translationstheorie. *Lebende Sprachen, 23*, 99–102.

Vilar, D., Freitag, M., Cherry, C., Luo, J., Ratnakar, V., & Foster, G. (2023). Prompting PaLM for translation: Assessing strategies and performance. In *Proceedings of ACL 2023* (pp. 15406–15427).

Wang, P., Li, L., Chen, L., Cai, Z., Zhu, D., Lin, B., Cao, Y., Liu, Q., Liu, T., & Sui, Z. (2024). Large language models are not fair evaluators. In *Proceedings of ACL 2024.* arXiv:2305.17926.

Wang, Y., Zeng, J., Liu, X., Wong, D. F., Meng, F., Zhou, J., & Zhang, M. (2025). DelTA: An online document-level translation agent based on multi-level memory. In *Proceedings of ICLR 2025.* arXiv:2410.08143.

Wu, M., Yuan, Y., Haffari, G., & Wang, L. (2024). (Perhaps) Beyond human translation: Harnessing multi-agent collaboration for translating ultra-long literary texts. *Transactions of the Association for Computational Linguistics* (2025). arXiv:2405.11804.

Yamada, M. (forthcoming). Metalanguage and GenAI: Empowering language learners and translators in training. In M. A. Jiménez-Crespo & V. Enríquez-Raido (Eds.), *Routledge Handbook of Technology and Translation* (2nd ed.). London: Routledge.

Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin, Z., Li, Z., Li, D., Xing, E. P., Zhang, H., Gonzalez, J. E., & Stoica, I. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. In *Advances in Neural Information Processing Systems 36* (NeurIPS 2023). arXiv:2306.05685.

---

*確認用日本語版作成: 2026-05-16。Repository: https://github.com/chuckmy/agentic-translator. Live demo: https://agentic-translator-chuckmy.streamlit.app. Licence: MIT, © Translation Lab Inc.*
