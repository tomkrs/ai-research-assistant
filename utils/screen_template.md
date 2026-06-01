---
# ── Screening settings ────────────────────────────────────────────────────────
model: gemma4:e4b          # Ollama model used for screening decisions
ollama_url: http://localhost:11434

input_csv:                 # path to the results.csv to screen (required)
                           # example: results/embedding-outliers/001/results.csv
output_csv:                # output path (leave blank: auto-named <input>_screened.csv)

save_every: 10             # save progress every N papers
# ─────────────────────────────────────────────────────────────────────────────
---

# Screening Criteria

<!-- Fill in the sections below. The LLM reads all three sections together
     when deciding whether to include or exclude each paper.
     Leave a section blank if not needed. -->

## Topic context

<!-- Optional: briefly re-state what the review is about.
     Helps the model understand the intent behind the criteria.
     Example: "This review investigates embedding-based outlier detection
     methods for structured biomedical datasets with multiple subcohorts." -->


## Inclusion criteria

<!-- List what a paper must have or be about to be included.
     Use plain bullet points — the LLM reads these directly.
     Example:
     - Uses embeddings or learned latent representations
     - Addresses outlier or anomaly detection
     - Evaluated on a real dataset with empirical results
     - Published in a peer-reviewed venue or as a preprint with substantial content -->


## Exclusion criteria

<!-- List reasons to exclude a paper.
     Example:
     - Purely theoretical with no empirical evaluation
     - Focuses only on text or NLP without applicability to structured data
     - Animal or in-vitro studies only
     - Editorial, letter, or commentary without original research
     - Duplicate or extended version of an already-included paper -->


## Additional instructions

<!-- Any extra guidance for the model that doesn't fit neatly into
     inclusion or exclusion criteria.
     Example:
     - When in doubt between include and uncertain, prefer uncertain
     - Systematic reviews and survey papers are especially valuable — include them
     - Papers that only mention embeddings in passing without making them central
       to the method should be excluded -->
