# arXiv Submission Plan

Working title:

> Agentic AI Translate: A Spec-Driven Implementation of Translation as Communication Design

## Target

- Primary arXiv category: `cs.CL`
- Possible secondary categories: `cs.HC`, `cs.AI`
- Software version to cite: `v0.8.0`
- Repository: `https://github.com/chuckmy/agentic-translator`

## Core Claim

The system operationalizes the idea that translation in the GenAI era is not only text conversion but communication design. Translation Studies metalanguage, such as skopos, audience, register, genre, and stance, becomes machine-readable instruction that controls generation and verification.

## Suggested Paper Structure

1. **Introduction**
   - Problem: generic machine translation optimizes text conversion, not communicative purpose.
   - Claim: GenAI shifts translator work toward specification design and verification.
   - Contribution: an executable prototype implementing this architecture.

2. **Theoretical Motivation**
   - Translation as communication design.
   - Translation Studies metalanguage as instruction language.
   - Relationship to skopos theory, register, audience design, and genre.

3. **System Architecture**
   - Interactive specification phase.
   - Four-stage cycle: Identify -> Prompt -> Generate -> Verify.
   - Reference materials: glossary, paired examples, parallel texts, style guide.
   - Document-level memory: proper-noun ledger and running summary.

4. **Implementation**
   - Streamlit UI.
   - Provider abstraction for Anthropic Claude API and OpenAI API.
   - Prompt templates and deterministic prompt assembly.
   - Downloadable run logs for research inspection.

5. **Evaluation Plan**
   - Compare generic prompting vs. spec-driven prompting.
   - Use MQM-style human or LLM-assisted evaluation.
   - Measure purpose alignment, register consistency, terminology consistency, and document-level coherence.

6. **Limitations**
   - LLM-as-judge reliability.
   - Provider/model variability.
   - API cost and reproducibility.
   - Privacy and handling of source/reference materials.

7. **Conclusion**
   - Summary of architecture.
   - Implications for translator training and research.

## Before Submission

- Convert the current Markdown draft into LaTeX.
- Ensure all claims about external models are time-stamped.
- Cite the `v0.8.0` GitHub release.
- Optionally archive the release on Zenodo and cite the DOI.
- Add screenshots only if they improve architectural clarity.
- Avoid claiming empirical superiority until a formal evaluation is completed.
