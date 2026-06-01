#!/usr/bin/env python3
"""Automated literature search with LLM-generated queries.

Usage:
    # From a filled-in template (recommended):
    python search.py --template my_topic.md

    # Quick one-liner:
    python search.py --topic "your research description" [options]

    # Template + CLI override (CLI wins):
    python search.py --template my_topic.md --model gemma3:4b --max-results 50

Options:
    --template      Path to a filled-in topic_template.md
    --topic         Research topic description (overrides template prose)
    --model         Ollama model (default: gemma3:12b)
    --ollama-url    Ollama base URL (default: http://localhost:11434)
    --n-queries     Number of search queries to generate (default: 5)
    --max-results   Max results per query per database (default: 20)
    --date-from     Earliest publication year, e.g. 2015 (default: no limit)
    --date-to       Latest  publication year, e.g. 2024 (default: no limit)
    --min-citations Min citation count — only filters where data is available
                    (Semantic Scholar); PubMed/arXiv papers without citation
                    data are always kept (default: 0 = no filter)
    --output-dir    Root directory for results (default: results)
    --topic-name    Short 1-2 word slug (auto-generated if omitted)
    --search-id     Numeric run ID (auto-incremented if omitted)
    --email         Email for PubMed Entrez API (required by NCBI)
    --databases     Space-separated subset: pubmed semantic_scholar arxiv

Output structure:
    <output-dir>/<topic-name>/<search-id>/results.csv
    <output-dir>/<topic-name>/<search-id>/search_info.md
"""

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import requests
import yaml


# ---------------------------------------------------------------------------
# Hardcoded defaults (lowest priority — overridden by template then by CLI)
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "model": "gemma3:12b",
    "ollama_url": "http://localhost:11434",
    "n_queries": 5,
    "max_results": 20,
    "date_from": "",
    "date_to": "",
    "min_citations": 0,
    "output_dir": "results",
    "topic_name": None,
    "search_id": None,
    "email": "search@example.com",
    "databases": ["pubmed", "semantic_scholar", "arxiv"],
}


# ---------------------------------------------------------------------------
# Template parsing
# ---------------------------------------------------------------------------

def parse_template(path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter and cleaned prose body from a topic_template.md."""
    text = path.read_text(encoding="utf-8")

    params: dict = {}
    body = text

    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            params = yaml.safe_load(text[3:end]) or {}
            body = text[end + 4:].strip()

    # Remove HTML comments and markdown headings, then collapse whitespace
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    body = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # Normalise YAML keys to underscore form
    normalised = {}
    for k, v in params.items():
        normalised[k.replace("-", "_")] = v
    return normalised, body


def _resolve(cli_val, template_params: dict, key: str):
    """Return cli_val if not None, else template value, else _DEFAULTS value."""
    if cli_val is not None:
        return cli_val
    if key in template_params and template_params[key] not in (None, ""):
        return template_params[key]
    return _DEFAULTS[key]


# ---------------------------------------------------------------------------
# Query + slug generation via Ollama (single round-trip)
# ---------------------------------------------------------------------------

def generate_queries_and_slug(topic: str, model: str, ollama_url: str, n: int) -> tuple[str, list[str]]:
    """Returns (topic_slug, queries)."""
    prompt = f"""You are a research librarian helping to find academic papers.

Given this research topic description:
"{topic}"

Do two things and return the result as a single JSON object:
1. "slug": a short 1-2 word label for the topic, lowercase, hyphens only \
(e.g. "sleep-deprivation", "nlp-transformers")
2. "queries": an array of exactly {n} different academic database search queries. \
Use different keywords, synonyms, and perspectives per query. \
Use Boolean operators (AND, OR) where useful.

Return ONLY the JSON object, no explanation, no markdown. Example:
{{"slug": "cancer-immunotherapy", "queries": ["query one AND topic", "query two OR synonym"]}}"""

    try:
        resp = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(f"[error] Cannot connect to Ollama at {ollama_url}. Is Ollama running?")

    raw = resp.json()["response"].strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start == -1 or end == 0:
        sys.exit(f"[error] Could not parse JSON from LLM response:\n{raw}")

    data = json.loads(raw[start:end])
    slug = re.sub(r"[^a-z0-9-]", "", data.get("slug", "search").lower().replace(" ", "-"))[:30]
    queries = [q.strip() for q in data.get("queries", []) if isinstance(q, str) and q.strip()]
    return slug, queries


# ---------------------------------------------------------------------------
# Search directory helpers
# ---------------------------------------------------------------------------

def next_search_id(topic_dir: Path) -> str:
    if not topic_dir.exists():
        return "001"
    existing = [int(d.name) for d in topic_dir.iterdir() if d.is_dir() and d.name.isdigit()]
    return str(max(existing) + 1 if existing else 1).zfill(3)


def save_search_info(
    path: Path,
    topic: str,
    topic_slug: str,
    search_id: str,
    cfg: dict,
    queries: list[str],
    n_raw: int,
    n_unique: int,
    timestamp: datetime,
) -> None:
    lines = [
        f"# Search info — {topic_slug}/{search_id}",
        "",
        f"**Timestamp:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Search ID:** {search_id}",
        f"**Topic slug:** {topic_slug}",
        "",
        "## Topic description",
        "",
        topic.strip(),
        "",
        "## Settings",
        "",
        "| Setting | Value |",
        "|---------|-------|",
        f"| Model | {cfg['model']} |",
        f"| Databases | {', '.join(cfg['databases'])} |",
        f"| Queries generated | {len(queries)} |",
        f"| Max results per query/DB | {cfg['max_results']} |",
        f"| Date from | {cfg['date_from'] or '—'} |",
        f"| Date to | {cfg['date_to'] or '—'} |",
        f"| Min citations | {cfg['min_citations'] if cfg['min_citations'] else '—'} |",
        f"| PubMed email | {cfg['email']} |",
        "",
        "## Generated queries",
        "",
    ]
    for i, q in enumerate(queries, 1):
        lines.append(f"{i}. {q}")
    lines += [
        "",
        "## Results",
        "",
        "| | Count |",
        "|---|---|",
        f"| Raw results collected | {n_raw} |",
        f"| After deduplication | {n_unique} |",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Paper data model
# ---------------------------------------------------------------------------

@dataclass
class Paper:
    source: str = ""
    title: str = ""
    authors: str = ""
    year: str = ""
    abstract: str = ""
    doi: str = ""
    url: str = ""
    journal: str = ""
    keywords: str = ""
    citation_count: str = ""
    reference_count: str = ""
    # PubMed
    pubmed_id: str = ""
    mesh_terms: str = ""
    publication_types: str = ""
    issn: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    # arXiv
    arxiv_id: str = ""
    categories: str = ""
    # Semantic Scholar
    semantic_scholar_id: str = ""
    is_open_access: str = ""
    open_access_url: str = ""
    fields_of_study: str = ""
    # Provenance
    found_by_query: str = ""


# ---------------------------------------------------------------------------
# PubMed via Biopython Entrez
# ---------------------------------------------------------------------------

def search_pubmed(
    query: str, max_results: int, email: str,
    date_from: str = "", date_to: str = "",
) -> list[Paper]:
    try:
        from Bio import Entrez, Medline
    except ImportError:
        print("  [skip] biopython not installed — skipping PubMed", file=sys.stderr)
        return []

    Entrez.email = email
    papers = []

    try:
        term = query
        if date_from or date_to:
            df = date_from or "1900"
            dt = date_to or "2100"
            term = f"({query}) AND {df}:{dt}[dp]"

        handle = Entrez.esearch(db="pubmed", term=term, retmax=max_results, usehistory="y")
        record = Entrez.read(handle)
        handle.close()

        ids = record.get("IdList", [])
        if not ids:
            return papers

        handle = Entrez.efetch(db="pubmed", id=ids, rettype="medline", retmode="text")
        records = list(Medline.parse(handle))
        handle.close()

        for rec in records:
            p = Paper(source="PubMed")
            p.title = rec.get("TI", "")
            p.authors = "; ".join(rec.get("AU", []))
            dp = rec.get("DP", "")
            p.year = dp[:4] if dp else ""
            p.abstract = rec.get("AB", "")
            for aid in rec.get("AID", []):
                if "[doi]" in aid:
                    p.doi = aid.replace(" [doi]", "").strip()
                    break
            p.journal = rec.get("TA", "")
            p.keywords = "; ".join(rec.get("OT", []))
            p.pubmed_id = rec.get("PMID", "")
            p.mesh_terms = "; ".join(rec.get("MH", []))
            p.publication_types = "; ".join(rec.get("PT", []))
            p.issn = rec.get("IS", "")
            p.volume = rec.get("VI", "")
            p.issue = rec.get("IP", "")
            p.pages = rec.get("PG", "")
            p.url = f"https://pubmed.ncbi.nlm.nih.gov/{p.pubmed_id}/" if p.pubmed_id else ""
            p.found_by_query = query
            papers.append(p)

        time.sleep(0.4)  # NCBI rate limit: max 3 req/s without API key
    except Exception as e:
        print(f"  [PubMed error] {e}", file=sys.stderr)

    return papers


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------

_SS_FIELDS = (
    "title,authors,year,abstract,externalIds,venue,citationCount,referenceCount,"
    "isOpenAccess,openAccessPdf,publicationTypes,journal,fieldsOfStudy"
)


def search_semantic_scholar(
    query: str, max_results: int,
    date_from: str = "", date_to: str = "",
) -> list[Paper]:
    papers = []
    try:
        params: dict = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": _SS_FIELDS,
        }
        if date_from or date_to:
            params["year"] = f"{date_from or ''}-{date_to or ''}"

        resp = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("data", []):
            p = Paper(source="Semantic Scholar")
            p.title = item.get("title", "")
            p.authors = "; ".join(a.get("name", "") for a in (item.get("authors") or []))
            p.year = str(item.get("year", ""))
            p.abstract = item.get("abstract", "") or ""
            ext = item.get("externalIds") or {}
            p.doi = ext.get("DOI", "")
            p.arxiv_id = ext.get("ArXiv", "")
            p.pubmed_id = ext.get("PubMed", "")
            journal = item.get("journal") or {}
            p.journal = journal.get("name", "") or item.get("venue", "")
            p.volume = journal.get("volume", "")
            p.pages = journal.get("pages", "")
            p.citation_count = str(item.get("citationCount", ""))
            p.reference_count = str(item.get("referenceCount", ""))
            p.is_open_access = str(item.get("isOpenAccess", ""))
            oa_pdf = item.get("openAccessPdf")
            p.open_access_url = oa_pdf.get("url", "") if oa_pdf else ""
            p.publication_types = "; ".join(item.get("publicationTypes") or [])
            p.fields_of_study = "; ".join(item.get("fieldsOfStudy") or [])
            p.semantic_scholar_id = item.get("paperId", "")
            p.url = (
                f"https://www.semanticscholar.org/paper/{p.semantic_scholar_id}"
                if p.semantic_scholar_id else ""
            )
            p.found_by_query = query
            papers.append(p)

        time.sleep(1)  # S2 public API: be polite
    except Exception as e:
        print(f"  [Semantic Scholar error] {e}", file=sys.stderr)

    return papers


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

def search_arxiv(
    query: str, max_results: int,
    date_from: str = "", date_to: str = "",
) -> list[Paper]:
    try:
        import arxiv
    except ImportError:
        print("  [skip] arxiv package not installed — skipping arXiv", file=sys.stderr)
        return []

    year_from = int(date_from) if date_from else None
    year_to = int(date_to) if date_to else None

    papers = []
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results * 3 if (year_from or year_to) else max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        count = 0
        for result in client.results(search):
            if result.published:
                year = result.published.year
                if year_from and year < year_from:
                    continue
                if year_to and year > year_to:
                    continue
            if count >= max_results:
                break
            p = Paper(source="arXiv")
            p.title = result.title
            p.authors = "; ".join(str(a) for a in result.authors)
            p.year = str(result.published.year) if result.published else ""
            p.abstract = result.summary.replace("\n", " ")
            p.doi = result.doi or ""
            p.arxiv_id = result.get_short_id()
            p.url = result.entry_id
            p.journal = result.journal_ref or ""
            p.categories = "; ".join(result.categories)
            p.keywords = "; ".join(result.categories)
            p.found_by_query = query
            papers.append(p)
            count += 1
    except Exception as e:
        print(f"  [arXiv error] {e}", file=sys.stderr)

    return papers


# ---------------------------------------------------------------------------
# Deduplication and filtering
# ---------------------------------------------------------------------------

def deduplicate(papers: list[Paper]) -> list[Paper]:
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[Paper] = []

    for p in papers:
        if p.doi and p.doi in seen_dois:
            continue
        title_key = p.title.lower().strip()[:120]
        if title_key and title_key in seen_titles:
            continue
        if p.doi:
            seen_dois.add(p.doi)
        if title_key:
            seen_titles.add(title_key)
        unique.append(p)

    return unique


def filter_min_citations(papers: list[Paper], min_citations: int) -> list[Paper]:
    """Drop papers that have citation data AND are below the threshold."""
    if min_citations <= 0:
        return papers
    result = []
    for p in papers:
        if p.citation_count and p.citation_count.isdigit():
            if int(p.citation_count) >= min_citations:
                result.append(p)
        else:
            result.append(p)  # keep papers without citation data
    return result


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def save_csv(papers: list[Paper], path: Path) -> None:
    if not papers:
        print("No papers found.")
        return
    fieldnames = list(asdict(papers[0]).keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for p in papers:
            writer.writerow(asdict(p))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automated literature search with LLM-generated queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # All defaults are None so we can detect what was explicitly set
    parser.add_argument("--template", default=None,
                        help="Path to a filled-in topic_template.md")
    parser.add_argument("--topic", default=None,
                        help="Research topic description (overrides template prose)")
    parser.add_argument("--model", default=None)
    parser.add_argument("--ollama-url", default=None, dest="ollama_url")
    parser.add_argument("--n-queries", type=int, default=None, dest="n_queries")
    parser.add_argument("--max-results", type=int, default=None, dest="max_results")
    parser.add_argument("--date-from", default=None, dest="date_from",
                        help="Earliest publication year, e.g. 2015")
    parser.add_argument("--date-to", default=None, dest="date_to",
                        help="Latest publication year, e.g. 2024")
    parser.add_argument("--min-citations", type=int, default=None, dest="min_citations",
                        help="Minimum citation count (filters only where data is available)")
    parser.add_argument("--output-dir", default=None, dest="output_dir")
    parser.add_argument("--topic-name", default=None, dest="topic_name")
    parser.add_argument("--search-id", default=None, dest="search_id")
    parser.add_argument("--email", default=None)
    parser.add_argument("--databases", nargs="+", default=None,
                        choices=["pubmed", "semantic_scholar", "arxiv"])
    args = parser.parse_args()

    # --- Load template ---
    template_params: dict = {}
    template_topic: str = ""
    if args.template:
        template_params, template_topic = parse_template(Path(args.template))

    # --- Resolve final config (CLI > template > hardcoded defaults) ---
    cfg = {k: _resolve(getattr(args, k, None), template_params, k) for k in _DEFAULTS}

    # Resolve topic: CLI --topic > template prose
    topic = args.topic or template_topic
    if not topic or not topic.strip():
        parser.error("Provide a topic via --topic or fill in a --template file.")

    # --- Generate queries ---
    timestamp = datetime.now()
    print(f"Model : {cfg['model']}")
    print(f"DBs   : {', '.join(cfg['databases'])}")
    if cfg["date_from"] or cfg["date_to"]:
        print(f"Dates : {cfg['date_from'] or '*'} → {cfg['date_to'] or '*'}")
    if cfg["min_citations"]:
        print(f"Min citations: {cfg['min_citations']}")
    print()

    print(f"Generating {cfg['n_queries']} search queries via Ollama...")
    topic_slug, queries = generate_queries_and_slug(
        topic, cfg["model"], cfg["ollama_url"], cfg["n_queries"]
    )
    if cfg["topic_name"]:
        topic_slug = re.sub(r"[^a-z0-9-]", "",
                            cfg["topic_name"].lower().replace(" ", "-"))[:30]

    print(f"Topic slug : {topic_slug}")
    print("Queries:")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}")

    # --- Resolve output directory ---
    output_root = Path(cfg["output_dir"])
    topic_dir = output_root / topic_slug
    search_id = cfg["search_id"] or next_search_id(topic_dir)
    search_dir = topic_dir / str(search_id)
    search_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nOutput dir : {search_dir}")
    print(f"Search ID  : {search_id}\n")

    # --- Search databases ---
    all_papers: list[Paper] = []
    date_from, date_to = str(cfg["date_from"]), str(cfg["date_to"])

    for i, query in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] {query[:70]}")

        if "pubmed" in cfg["databases"]:
            print("  PubMed ...", end=" ", flush=True)
            r = search_pubmed(query, cfg["max_results"], cfg["email"], date_from, date_to)
            print(len(r))
            all_papers.extend(r)

        if "semantic_scholar" in cfg["databases"]:
            print("  Semantic Scholar ...", end=" ", flush=True)
            r = search_semantic_scholar(query, cfg["max_results"], date_from, date_to)
            print(len(r))
            all_papers.extend(r)

        if "arxiv" in cfg["databases"]:
            print("  arXiv ...", end=" ", flush=True)
            r = search_arxiv(query, cfg["max_results"], date_from, date_to)
            print(len(r))
            all_papers.extend(r)

    print(f"\nTotal raw        : {len(all_papers)}")
    unique = deduplicate(all_papers)
    print(f"After dedup      : {len(unique)}")
    filtered = filter_min_citations(unique, cfg["min_citations"])
    if cfg["min_citations"]:
        print(f"After min-cit={cfg['min_citations']} : {len(filtered)}")

    # --- Save outputs ---
    csv_path = search_dir / "results.csv"
    info_path = search_dir / "search_info.md"

    save_csv(filtered, csv_path)
    save_search_info(info_path, topic, topic_slug, str(search_id), cfg, queries,
                     len(all_papers), len(filtered), timestamp)

    print(f"\nresults.csv  -> {csv_path}")
    print(f"search_info  -> {info_path}")


if __name__ == "__main__":
    main()
