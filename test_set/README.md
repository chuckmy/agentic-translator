# Test set for the Agentic Translator

A small but representative bilingual test set covering three genres in each direction. All texts are original and multi-paragraph, with recurring proper nouns so that R3 (DelTA-lite document memory) can be observed in action.

## Files

```
test_set/
├── glossary_ja_en.tsv          ← JA→EN glossary
├── glossary_en_ja.tsv          ← EN→JA glossary
├── paired_examples_ja_en.tsv   ← JA→EN paired examples
├── paired_examples_en_ja.tsv   ← EN→JA paired examples
├── style_guide_news.md         ← style guide for news/reportage genre
├── style_guide_literary.md     ← style guide for literary genre
├── ja/
│   ├── 01_sports_news.txt      ← motorsport preview, ~400 chars × 4 paragraphs
│   ├── 02_literary_kyoto.txt   ← atmospheric Kyoto night scene, ~350 chars × 4 paragraphs
│   └── 03_academic_tpr.txt     ← TS abstract on MTPE/cognitive load, ~600 chars × 5 paragraphs
└── en/
    ├── 01_tech_news.txt        ← fictional AI product launch, ~250 words × 4 paragraphs
    ├── 02_literary_october.txt ← short literary piece set in Brattleboro, ~280 words × 4 paragraphs
    └── 03_academic_linguistics.txt ← linguistics abstract on DM transfer, ~300 words × 4 paragraphs
```

## How to use with the prototype

1. Start the app: `streamlit run app.py`
2. **① Reference materials** — upload as needed:
   - Glossary: `glossary_ja_en.tsv` for JA→EN, `glossary_en_ja.tsv` for EN→JA
   - Paired examples: corresponding `paired_examples_*.tsv`
   - Style guide: `style_guide_news.md` for genre 01 / 03; `style_guide_literary.md` for genre 02
3. **② Source text** — paste the entire content of one test file (multi-paragraph)
4. **③** Propose spec → refine via chat → ✅ Use this spec
5. **④** Translate → watch the **📚 Memory after chunk N** panels populate

## Suggested experiments

### A. Glossary effect
Run `ja/01_sports_news.txt` once with `glossary_ja_en.tsv`, once without. Compare:
- Is "鈴鹿" rendered consistently as "Suzuka Circuit"?
- Is "三連覇" rendered as "third consecutive title" (glossary) vs. "three-peat" or "third-straight title" (no glossary)?

### B. Paired-examples effect (style transfer)
Run `en/02_literary_october.txt` once with `paired_examples_en_ja.tsv` + `style_guide_literary.md`, once with neither. Compare:
- Sentence rhythm — does the target preserve clipped sentences?
- Cultural items — is "the Common" handled idiomatically?

### C. Spec refinement effect
For `ja/03_academic_tpr.txt`:
- Spec A: "audience is undergraduate students of linguistics, no domain expertise"
- Spec B: "audience is peer reviewers in *Target* journal"
Compare register, sentence complexity, and how technical terms are introduced.

### D. Document memory effect
Run `ja/01_sports_news.txt` (4 paragraphs, multiple proper nouns spanning paragraphs) and observe whether:
- "ファルコン・モータースポーツ" is translated identically across all 4 chunks
- "佐久間涼", "ロベルト・ガリアーニ", "李子龍" are added to the proper-noun ledger
- The running summary in chunks 3–4 references content from chunks 1–2

### E. Genre crossover (negative test)
Apply `style_guide_literary.md` to `en/03_academic_linguistics.txt`. The Stage 4 verifier should flag the register mismatch in its feedback.

## Notes

- All proper nouns (people, companies, products) are fictional. Place names (鈴鹿, 祇園, Brattleboro, Shibuya) are real.
- Texts are designed to span genres that exercise different parts of the spec: register (academic), voice (literary), terminology (sports), proper-noun handling (news).
- Chunk count under default `max_chars=1500` settings: each test text yields 1 chunk in single-paragraph mode but **4 chunks** when paragraph-splitting is on (the default), which is what triggers DelTA-lite memory.
