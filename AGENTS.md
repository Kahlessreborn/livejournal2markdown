# AI Agent Instructions

## Purpose
This repository contains a small Python utility that fetches public LiveJournal posts and converts them into Markdown files saved under `Scraped Journals/`.

## Key files
- `main.py` — single-script implementation, entrypoint for the tool.
- `requirements.txt` — Python dependencies.
- `README.md` — usage and setup instructions.

## How to run
- Install dependencies: `pip install -r requirements.txt`
- Execute the script: `python main.py`

## Behavior to preserve
- The tool fetches posts by subdomain and paginates using `?skip=`.
- It discovers post links by scanning `.html` permalinks on LiveJournal archive pages and ignores `www.` links.
- It converts LiveJournal HTML content to Markdown using `BeautifulSoup`.
- It writes output files into `Scraped Journals/`.
- It updates file creation/modification timestamps on Windows via `pywin32` so markdown files reflect the original post date.
- Filenames are generated from the post date and a sanitized title.

## Important conventions
- Keep CLI interaction simple: `main.py` currently prompts for the LiveJournal subdomain rather than using CLI arguments.
- Do not assume private or locked posts are supported; this is designed for public blogs.
- Maintain the warning about responsible request rates to avoid LiveJournal restrictions.

## When editing
- Prefer preserving the existing markdown file structure and timestamp behavior.
- Use `README.md` for dependency and usage details rather than duplicating large sections.
- If adding new features, update `AGENTS.md` or `README.md` with the new user-facing behavior.

## Notes for agents
- There is no existing test suite in this repository.
- The code is Windows-focused because of `pywin32` timestamp handling.
- The `Scraped Journals/` directory is created automatically by `main.py`.
