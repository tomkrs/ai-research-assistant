#!/usr/bin/env python3
"""Screen and filter papers from a search CSV using an Ollama LLM.

Reads title + abstract for each paper, applies inclusion/exclusion criteria
via an LLM, and appends decision columns to the CSV.

Usage:
    # From a criteria file (recommended):
    python screen.py --criteria utils/my-screen.md

    # Quick one-liner:
    python screen.py --input results/topic/001/results.csv \
                     --include "uses embeddings" "empirical evaluation" \
                     --exclude "animal studies" "no abstract available"

    # Criteria file + CLI override (CLI wins):
    python screen.py --criteria utils/my-screen.md --model gemma3:12b

Options:
    --criteria      Path to a filled-in screen_template.md
    --input         Path to results.csv to screen (overrides template)
    --output        Path for screened output CSV (default: <input>_screened.csv)
    --model         Ollama model (default: gemma4:e4b)
    --ollama-url    Ollama base URL (default: http://localhost:11434)
    --include       One or more inclusion criteria strings
    --exclude       One or more exclusion criteria strings
    --instructions  Free-text screening instructions
    --save-every    Save progress every N papers (default: 10)
    --resume        Skip papers that already have a screen_decision (default: true)

Output columns added to CSV:
    screen_decision         include / exclude / uncertain
    screen_inclusion_reason why the paper meets inclusion criteria
    screen_exclusion_reason why the paper should be excluded
    screen_confidence       high / medium / low
    screen_model            model used for this decision
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "model": "gemma4:e4b",
    "ollama_url": "http://localhost:11434",
    "save_every": 10,
    "resume": True,
}

_SCREEN_COLS = [
    "screen_decision",
    "screen_inclusion_reason",
    "screen_exclusion_reason",
    "screen_confidence",
    "screen_model",
]


# ---------------------------------------------------------------------------
# Template / criteria parsing
# ---------------------------------------------------------------------------

def parse_template(path: Path) -> tuple[dict, dict[str, str]]:
    """Parse YAML frontmatter and named prose sections from a screen template.

    Returns (params_dict, sections_dict) where sections_dict maps
    lowercased heading text to the content beneath it.
    """
    text = path.read_text(encoding="utf-8")
    params: dict = {}
    body = text

    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            params = yaml.safe_load(text[3:end]) or {}
            body = text[end + 4:].strip()

    # Normalise YAML keys
    params = {k.replace("-", "_"): v for k, v in params.items()}

    # Split body into sections by ## headings, stripping HTML comments
    import re
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []

    for line in body.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip().lower()
            buf = []
        else:
            buf.append(line)

    if current is not None:
        sections[current] = "\n".join(buf).strip()

    return params, sections


def _resolve(cli_val, params: dict, key: str):
    if cli_val is not None:
        return cli_val
    if key in params and params[key] not in (None, ""):
        return params[key]
    return _DEFAULTS.get(key)


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return fieldnames, rows


def save_csv(fieldnames: list[str], rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Screening via Ollama
# ---------------------------------------------------------------------------

def _build_prompt(title: str, abstract: str, inclusion: str, exclusion: str,
                  instructions: str, topic_context: str) -> str:
    abstract_text = abstract.strip() if abstract.strip() else "(no abstract available — decide based on title only)"

    parts = ["You are screening academic papers for a systematic literature review."]

    if topic_context:
        parts += ["", "Topic context:", topic_context.strip()]

    parts += [
        "",
        "Paper to screen:",
        f"Title: {title}",
        f"Abstract: {abstract_text}",
    ]

    if inclusion:
        parts += ["", "Inclusion criteria (paper should meet these to be included):", inclusion.strip()]

    if exclusion:
        parts += ["", "Exclusion criteria (paper should be excluded if it meets any of these):", exclusion.strip()]

    if instructions:
        parts += ["", "Additional instructions:", instructions.strip()]

    parts += [
        "",
        'Respond with a single JSON object only — no explanation, no markdown:',
        '{"decision": "include" or "exclude" or "uncertain", '
        '"inclusion_reason": "brief reason this paper meets inclusion criteria, or empty string if excluded", '
        '"exclusion_reason": "brief reason this paper should be excluded, or empty string if included", '
        '"confidence": "high" or "medium" or "low"}',
    ]

    return "\n".join(parts)


def screen_paper(
    title: str,
    abstract: str,
    inclusion: str,
    exclusion: str,
    instructions: str,
    topic_context: str,
    model: str,
    ollama_url: str,
) -> dict:
    prompt = _build_prompt(title, abstract, inclusion, exclusion, instructions, topic_context)

    try:
        resp = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(f"[error] Cannot connect to Ollama at {ollama_url}. Is Ollama running?")
    except requests.exceptions.Timeout:
        return {
            "screen_decision": "uncertain",
            "screen_inclusion_reason": "",
            "screen_exclusion_reason": "timeout — could not get LLM response",
            "screen_confidence": "low",
        }

    raw = resp.json()["response"].strip()
    start, end = raw.find("{"), raw.rfind("}") + 1

    if start == -1 or end == 0:
        return {
            "screen_decision": "uncertain",
            "screen_inclusion_reason": "",
            "screen_exclusion_reason": f"could not parse LLM response: {raw[:120]}",
            "screen_confidence": "low",
        }

    try:
        data = json.loads(raw[start:end])
        decision = data.get("decision", "uncertain").lower()
        if decision not in ("include", "exclude", "uncertain"):
            decision = "uncertain"
        return {
            "screen_decision": decision,
            "screen_inclusion_reason": data.get("inclusion_reason", ""),
            "screen_exclusion_reason": data.get("exclusion_reason", ""),
            "screen_confidence": data.get("confidence", "medium").lower(),
        }
    except json.JSONDecodeError:
        return {
            "screen_decision": "uncertain",
            "screen_inclusion_reason": "",
            "screen_exclusion_reason": f"JSON parse error: {raw[:120]}",
            "screen_confidence": "low",
        }


# ---------------------------------------------------------------------------
# Summary markdown
# ---------------------------------------------------------------------------

def save_screen_info(
    path: Path,
    cfg: dict,
    inclusion: str,
    exclusion: str,
    instructions: str,
    topic_context: str,
    n_total: int,
    counts: dict[str, int],
    timestamp: datetime,
    input_csv: Path,
) -> None:
    lines = [
        "# Screening info",
        "",
        f"**Timestamp:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Input CSV:** {input_csv}",
        f"**Model:** {cfg['model']}",
        "",
        "## Criteria",
        "",
    ]

    if topic_context:
        lines += ["### Topic context", "", topic_context.strip(), ""]
    if inclusion:
        lines += ["### Inclusion criteria", "", inclusion.strip(), ""]
    if exclusion:
        lines += ["### Exclusion criteria", "", exclusion.strip(), ""]
    if instructions:
        lines += ["### Additional instructions", "", instructions.strip(), ""]

    lines += [
        "## Results",
        "",
        "| Decision | Count | % |",
        "|---|---|---|",
        f"| Include | {counts.get('include', 0)} | "
        f"{counts.get('include', 0) / n_total * 100:.1f}% |",
        f"| Exclude | {counts.get('exclude', 0)} | "
        f"{counts.get('exclude', 0) / n_total * 100:.1f}% |",
        f"| Uncertain | {counts.get('uncertain', 0)} | "
        f"{counts.get('uncertain', 0) / n_total * 100:.1f}% |",
        f"| Skipped (already screened) | {counts.get('skipped', 0)} | — |",
        f"| **Total** | **{n_total}** | |",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Screen papers from a search CSV using inclusion/exclusion criteria",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--criteria", default=None,
                        help="Path to a filled-in screen_template.md")
    parser.add_argument("--input", default=None, dest="input_csv",
                        help="Path to results.csv (overrides template)")
    parser.add_argument("--output", default=None, dest="output_csv",
                        help="Output CSV path (default: <input>_screened.csv)")
    parser.add_argument("--model", default=None)
    parser.add_argument("--ollama-url", default=None, dest="ollama_url")
    parser.add_argument("--include", nargs="+", default=None,
                        help="Inclusion criteria strings")
    parser.add_argument("--exclude", nargs="+", default=None,
                        help="Exclusion criteria strings")
    parser.add_argument("--instructions", default=None,
                        help="Free-text screening instructions")
    parser.add_argument("--save-every", type=int, default=None, dest="save_every",
                        help="Save progress every N papers (default: 10)")
    parser.add_argument("--no-resume", action="store_true",
                        help="Re-screen all papers, even those already screened")
    args = parser.parse_args()

    # --- Load template ---
    template_params: dict = {}
    sections: dict[str, str] = {}
    if args.criteria:
        template_params, sections = parse_template(Path(args.criteria))

    # --- Resolve config ---
    model = _resolve(args.model, template_params, "model")
    ollama_url = _resolve(args.ollama_url, template_params, "ollama_url")
    save_every = _resolve(args.save_every, template_params, "save_every")
    resume = not args.no_resume

    # Resolve input CSV
    input_csv_str = args.input_csv or template_params.get("input_csv")
    if not input_csv_str:
        parser.error("Provide --input or set input_csv in the criteria template.")
    input_path = Path(input_csv_str)
    if not input_path.exists():
        sys.exit(f"[error] Input CSV not found: {input_path}")

    # Resolve output CSV
    output_csv_str = args.output_csv or template_params.get("output_csv")
    output_path = (
        Path(output_csv_str) if output_csv_str
        else input_path.parent / (input_path.stem + "_screened.csv")
    )

    # Resolve criteria text
    inclusion = (
        "\n".join(f"- {c}" for c in args.include) if args.include
        else sections.get("inclusion criteria", "")
    )
    exclusion = (
        "\n".join(f"- {c}" for c in args.exclude) if args.exclude
        else sections.get("exclusion criteria", "")
    )
    instructions = args.instructions or sections.get("additional instructions", "")
    topic_context = sections.get("topic context", "")

    cfg = {"model": model, "ollama_url": ollama_url}

    print(f"Model      : {model}")
    print(f"Input      : {input_path}")
    print(f"Output     : {output_path}")
    print(f"Resume     : {resume}")
    print()

    # --- Load CSV ---
    fieldnames, rows = load_csv(input_path)

    # Add screening columns if not present
    for col in _SCREEN_COLS:
        if col not in fieldnames:
            fieldnames.append(col)
        for row in rows:
            row.setdefault(col, "")

    # --- Screen papers ---
    timestamp = datetime.now()
    counts: dict[str, int] = {"include": 0, "exclude": 0, "uncertain": 0, "skipped": 0}
    n_total = len(rows)

    print(f"Screening {n_total} papers...\n")

    for i, row in enumerate(rows, 1):
        title = row.get("title", "").strip()
        abstract = row.get("abstract", "").strip()

        # Resume: skip already-screened rows
        if resume and row.get("screen_decision", "").strip():
            counts["skipped"] += 1
            decision = row["screen_decision"]
            if decision in counts:
                counts[decision] += 1
            print(f"  [{i:>4}/{n_total}] skip  — {title[:60]}")
            continue

        result = screen_paper(
            title, abstract, inclusion, exclusion,
            instructions, topic_context, model, ollama_url,
        )

        decision = result["screen_decision"]
        counts[decision] = counts.get(decision, 0) + 1

        row["screen_decision"] = decision
        row["screen_inclusion_reason"] = result["screen_inclusion_reason"]
        row["screen_exclusion_reason"] = result["screen_exclusion_reason"]
        row["screen_confidence"] = result["screen_confidence"]
        row["screen_model"] = model

        symbol = {"include": "+", "exclude": "-", "uncertain": "?"}.get(decision, "?")
        conf = result["screen_confidence"][0].upper()  # H/M/L
        print(f"  [{i:>4}/{n_total}] [{symbol}][{conf}] {title[:60]}")

        # Save progress periodically
        if i % save_every == 0:
            save_csv(fieldnames, rows, output_path)

    # Final save
    save_csv(fieldnames, rows, output_path)

    # Save screen_info.md
    info_path = output_path.parent / "screen_info.md"
    save_screen_info(
        info_path, cfg, inclusion, exclusion, instructions, topic_context,
        n_total, counts, timestamp, input_path,
    )

    # Summary
    screened = n_total - counts["skipped"]
    print(f"\n{'─' * 50}")
    print(f"Total papers   : {n_total}")
    print(f"Newly screened : {screened}")
    print(f"  Include      : {counts['include']}")
    print(f"  Exclude      : {counts['exclude']}")
    print(f"  Uncertain    : {counts['uncertain']}")
    if counts["skipped"]:
        print(f"  Skipped      : {counts['skipped']}")
    print(f"\nOutput CSV   -> {output_path}")
    print(f"Screen info  -> {info_path}")


if __name__ == "__main__":
    main()
