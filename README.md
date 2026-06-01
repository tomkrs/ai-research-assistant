# AI Research Assistant

A local, LLM-powered literature search and screening tool for academic research. Describe your topic in plain language, and the tool generates targeted search queries, fetches papers from multiple databases, deduplicates the results, and saves everything to a structured CSV. A second script then screens each paper against your inclusion/exclusion criteria using an LLM, appending a decision and reasoning to each row.

Built as a supporting tool for my own master thesis literature review, but designed to be reusable for any systematic literature search.

> **Disclaimer:** This is a personal project, written by me (Tom Kraus). It is not a product of, affiliated with, or endorsed by my employer Vector Informatik GmbH, and it contains no Vector code, data or confidential information. All searched sources are public literature databases (PubMed, Semantic Scholar, arXiv).

---

## Status

> **In development** — search and screening pipelines are working. Auto-summarization is planned next.

| Feature | Status |
|---|---|
| LLM query generation (Ollama) | Working |
| PubMed search | Working |
| Semantic Scholar search | Working |
| arXiv search | Working |
| Deduplication | Working |
| CSV export (`;` delimiter, Excel-ready) | Working |
| Topic template with structured parameters | Working |
| Structured output directories with search IDs | Working |
| Date range and min-citation filtering | Working |
| LLM-based paper screening (include/exclude) | Working |
| Screening criteria template | Working |
| Abstract auto-summarization | Planned |
| PRISMA flow export | Planned |

---

## How it works

### Step 1 — Search

1. **Fill in a topic template** (`utils/topic_template.md`) — describe your research question and set search parameters in the YAML frontmatter.
2. **Run `search.py`** — the script asks a local Ollama LLM to generate N Boolean search queries from your description.
3. **Papers are fetched** from the configured databases, deduplicated, and filtered by date / citation count.
4. **Output is saved** to `results/<topic>/<id>/results.csv` alongside a `search_info.md` documenting every setting and query.

### Step 2 — Screen

1. **Fill in a screening criteria template** (`utils/screen_template.md`) — set your inclusion/exclusion criteria and point it at the results CSV.
2. **Run `screen.py`** — for each paper the LLM reads the title and abstract, applies your criteria, and returns a decision with reasoning.
3. **New columns are appended** to the CSV: `screen_decision`, `screen_inclusion_reason`, `screen_exclusion_reason`, `screen_confidence`.
4. Progress is saved every N papers, and interrupted runs can be resumed.

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally with the relevant models pulled
  - Search: `gemma3:12b` (default)
  - Screening: `gemma4:e4b` (default — fast, efficient for batch decisions)
- Dependencies listed in `requirements.txt`

---

## Setup

```powershell
# Create and activate the virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

---

## Usage

### Step 1 — Search

```powershell
# Copy and fill in the topic template
copy utils\topic_template.md utils\my-topic.md

# Run the search
& .\.venv\Scripts\python.exe code\search.py --template utils\my-topic.md
```

**`search.py` CLI options**

| Option | Default | Description |
|---|---|---|
| `--template` | — | Path to a filled-in topic template |
| `--topic` | — | Topic description (overrides template prose) |
| `--model` | `gemma3:12b` | Ollama model for query generation |
| `--ollama-url` | `http://localhost:11434` | Ollama base URL |
| `--n-queries` | `5` | Number of search queries to generate |
| `--max-results` | `20` | Max results per query per database |
| `--date-from` | — | Earliest publication year |
| `--date-to` | — | Latest publication year |
| `--min-citations` | `0` | Min citation count (Semantic Scholar only) |
| `--databases` | all three | Space-separated: `pubmed semantic_scholar arxiv` |
| `--output-dir` | `results` | Root folder for output |
| `--topic-name` | auto | Override auto-generated topic slug |
| `--search-id` | auto | Override auto-incremented run ID |
| `--email` | — | Required for PubMed (NCBI Entrez ToS) |

### Step 2 — Screen

```powershell
# Copy and fill in the screening criteria template
copy utils\screen_template.md utils\my-screen.md
# Set input_csv in the YAML to point at your results.csv, fill in criteria

# Run the screener
& .\.venv\Scripts\python.exe code\screen.py --criteria utils\my-screen.md
```

**`screen.py` CLI options**

| Option | Default | Description |
|---|---|---|
| `--criteria` | — | Path to a filled-in screen template |
| `--input` | — | Path to `results.csv` (overrides template) |
| `--output` | auto | Output path (default: `<input>_screened.csv`) |
| `--model` | `gemma4:e4b` | Ollama model for screening |
| `--ollama-url` | `http://localhost:11434` | Ollama base URL |
| `--include` | — | Inclusion criteria strings (space-separated) |
| `--exclude` | — | Exclusion criteria strings (space-separated) |
| `--instructions` | — | Free-text screening instructions |
| `--save-every` | `10` | Save progress every N papers |
| `--no-resume` | — | Re-screen papers that already have a decision |

---

## Output structure

```
results/
└── <topic-slug>/
    └── 001/
        ├── results.csv           # raw search results, semicolon-delimited
        ├── results_screened.csv  # after screening — includes decision columns
        ├── search_info.md        # search settings, queries, result counts
        └── screen_info.md        # screening criteria and decision summary
```

**Screening columns added to CSV:**

| Column | Values |
|---|---|
| `screen_decision` | `include` / `exclude` / `uncertain` |
| `screen_inclusion_reason` | why the paper meets inclusion criteria |
| `screen_exclusion_reason` | why the paper should be excluded |
| `screen_confidence` | `high` / `medium` / `low` |
| `screen_model` | which Ollama model made the decision |

The `found_by_query` column records which query found each paper — useful for PRISMA flow tracing.

---

## Project structure

```
ai-research-assistant/
├── code/
│   ├── search.py             # Step 1 — fetch papers from databases
│   └── screen.py             # Step 2 — screen papers by inclusion/exclusion criteria
├── dev/
│   ├── CLAUDE.md             # instructions for the AI assistant
│   └── HISTORY.md            # session-by-session change log
├── utils/
│   ├── topic_template.md     # blank search template — copy for each topic
│   ├── screen_template.md    # blank screening template — copy for each review
│   └── <your filled-in files>
├── results/                  # generated — search and screening outputs
├── .venv/                    # generated — Python virtual environment
└── requirements.txt
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP calls to Ollama and Semantic Scholar APIs |
| `biopython` | PubMed access via NCBI Entrez |
| `arxiv` | arXiv search |
| `pyyaml` | Parsing YAML frontmatter in topic and screening templates |
