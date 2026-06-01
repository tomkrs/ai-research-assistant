# Research Project — Claude Instructions

## Python environment

Always use the project venv for every Python command:

```
.venv\Scripts\python.exe   # relative to the project root
```

Never use the system `python` or `pip` directly. Install new packages with:

```powershell
& ".venv\Scripts\python.exe" -m pip install <package>
```

Update `requirements.txt` (project root) whenever a new package is added.

## Project structure

```
ai-research-assistant/
├── code/           # source code
│   └── search.py   # main script
├── dev/            # project docs (CLAUDE.md, HISTORY.md)
├── utils/          # templates and helper files
│   └── topic_template.md
├── .venv/          # Python virtual environment
└── requirements.txt
```

## README maintenance

`README.md` lives at the project root. Keep it in sync whenever any of the following change:

- Project structure (directories, key files added or moved)
- CLI options or their defaults in `code/search.py`
- New features added or status of planned features
- Setup or usage instructions
- Dependencies in `requirements.txt`

Update the relevant section(s) of `README.md` as part of the same task — do not wait for a separate request.

## Session history

At the end of every session — or whenever significant work is completed — append a summary entry to `dev/HISTORY.md`. Use this format:

```markdown
## YYYY-MM-DD — <short title>

**What was done:**
- bullet points of concrete changes made

**Key decisions:**
- any choices made and why (e.g. library chosen, design tradeoff)

**Next steps / open items:**
- anything left to do or follow up on
```

Never overwrite previous entries. Always append.

## Project context

Master thesis literature search tool. Main script: `code/search.py`.
Databases: PubMed, Semantic Scholar, arXiv.
Planned features: auto-summarization, PRISMA-style filtering.
