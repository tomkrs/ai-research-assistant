---
# ── Search settings ───────────────────────────────────────────────────────────
# All fields are optional — leave blank to use the script defaults.

model: gemma3:12b          # Ollama model used for query generation
databases:                 # databases to search (remove any you don't want)
  - pubmed
  - semantic_scholar
  - arxiv
n_queries: 1               # number of search queries to generate
max_results: 20            # max results per query per database

date_from: 2015            # earliest publication year  (leave blank: no limit)
date_to:                   # latest  publication year  (leave blank: no limit)
min_citations: 0           # minimum citation count; applies only where citation
                           # data is available (Semantic Scholar). Papers from
                           # PubMed/arXiv without citation data are kept.

topic_name:                # 1-2 word directory slug  (leave blank: auto-generate)
output_dir: results        # root folder for all search outputs
email: your@email.com      # required by NCBI Entrez (PubMed)
# ─────────────────────────────────────────────────────────────────────────────
---

# Research Topic

<!-- Fill in the sections below. The more detail and specificity you provide,
     the better the generated search queries will be.
     Sections you don't need can be left blank or deleted. -->

## Main research question

<!-- What is the central question your thesis or review tries to answer?
     Be as precise as possible — include the intervention/exposure AND the outcome.
     Example: "Does intermittent fasting improve insulin sensitivity in adults with
     pre-diabetes compared to continuous caloric restriction?" -->


## Background and context

<!-- What is the broader field or clinical/scientific context?
     Why is this topic relevant or timely? What gap does your work address?
     Example: "Despite growing interest in dietary interventions for metabolic
     syndrome, head-to-head comparisons between fasting protocols remain scarce." -->


## Population / system / domain

<!-- Who or what is being studied?
     Be specific about age, condition, species, setting, or technical domain.
     Examples:
       - "Adult ICU patients with sepsis-induced immunosuppression"
       - "Pre-trained transformer models in low-resource NLP tasks"
       - "Alpine wetlands under climate-change-driven drought stress" -->


## Intervention, exposure, or phenomenon

<!-- What is the key factor, treatment, technology, or event being examined?
     Include dosage, duration, or technical variant if relevant.
     Example: "Intermittent fasting (16:8 protocol), minimum 8-week duration" -->


## Outcomes or endpoints of interest

<!-- What results, measurements, or effects are you looking for?
     List primary and secondary outcomes separately if you have both.
     Example:
       Primary:   "insulin sensitivity (HOMA-IR, glucose clamp)"
       Secondary: "body weight, HbA1c, lipid profile, quality of life" -->


## Key terms, synonyms, and abbreviations

<!-- List the most important keywords including synonyms and abbreviations.
     The LLM uses these to build varied Boolean queries.
     Example: "sepsis, septicaemia, septic shock, bloodstream infection,
               bacteraemia, SIRS, organ failure, ICU, intensive care" -->


## Exclusion hints

<!-- What should NOT be in scope? Helps the LLM avoid irrelevant queries.
     Example: "exclude animal studies, pediatric populations, case reports,
               studies without a control group, publications before 2010" -->


## Preferred study designs or methods

<!-- Steer toward specific evidence types if relevant.
     Example: "prefer systematic reviews, meta-analyses, and RCTs;
               include observational cohort studies; exclude editorials and letters" -->


## Additional notes

<!-- Anything else the search algorithm should know: funding sources to exclude,
     geographic scope, language restrictions, known landmark papers to cross-check,
     or related MeSH terms you already know are useful. -->
