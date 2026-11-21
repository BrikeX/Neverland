# AGENTS.md

## What this repo is

Neverland is a personal Linux playground: standalone Python 3.12 utilities for media renaming and ffmpeg stream edits, plus Bash helpers for environment, APT/Docker, GPG, and file-sharing tasks. There is no library API, automated test suite, or packaged CLI; each utility is run directly.

## Layout

- `pytools/` - Python CLI utilities:
  - `rename_bangumi.py` renames anime episodes and optionally copies subtitles; supports `--dry-run`, `--subs`, `--lang`, and `--start`.
  - `rename_films.py` renames photos/videos from ExifTool metadata dates; renames in place and has no dry-run.
  - `rename_subs.py` copies subtitles to match film filenames; supports `--dry-run`, `--offset`, and `--exclude`.
  - `video_util.py` inspects or edits ffmpeg tracks (remove, keep, shift, add subtitles); writes a new file and refuses to overwrite.
- `scripts/` - Bash helpers. `neverland` and `cursor` define shell functions and are meant to be sourced; `proxy` must be sourced or eval'd. `archive_directories` and `extract_directories` are not executable; run them with `bash <script>`.
- `skills/<name>/SKILL.md` - canonical project skills. `.qoder/skills` is a relative symlink to `../skills`, and `.qoder/` is gitignored so other tools can link the same directory.
- `pyproject.toml`, `uv.lock`, `.python-version` - uv-managed Python >=3.12 environment with `pyexiftool` and `yt-dlp`. `.venv/` is local and ignored.
- `README.md` - intentionally minimal.

## Setup and checks

- Sync the environment with `uv sync`.
- Run utilities with `uv run python pytools/<tool>.py --help`.
- Syntax checks: `uv run python -m compileall -q pytools` and `bash -n scripts/*`.
- There are no automated tests. Test file operations in a scratch directory or on copies before touching real media.
- External binaries are required by some tools: ExifTool for `rename_films.py`; `ffmpeg` and `ffprobe` for `video_util.py` and `merge_va`; Docker, GPG, aria2, UFW, or systemd for the relevant helpers.

## Formatting

- Python: format with Black. Use `uvx black pytools` when Black is not installed, or `black pytools` otherwise. Black has no project-specific configuration; use its defaults.
- Bash: format with shfmt at two-space indentation: `shfmt -w -i 2 scripts`. The existing scripts already match this setting.
- Markdown: lint and auto-fix with `markdownlint-cli2 --fix AGENTS.md README.md "skills/**/*.md"`. The repo config `.markdownlint-cli2.yaml` disables MD013 because command examples and skill descriptions are intentionally long.
- Run the relevant formatter on files you change. Keep formatting-only changes separate from behavioral changes when practical.
- Black, shfmt, and markdownlint-cli2 are developer tools, not project dependencies.

## Conventions

- Keep utilities standalone and directly runnable. Do not introduce packages, entry points, or shared abstractions unless requested.
- Python: use 3.12+, `argparse`, and the standard library unless an existing dependency is appropriate. Match the surrounding formatting and human-readable output style.
- Bash: use `#!/usr/bin/env bash`; preserve existing option parsing and help text. Several scripts use `set -euo pipefail`; do not add or remove it without testing the script's behavior.
- Add dependencies with `uv add` and refresh `uv.lock`; do not use pip directly.
- Prefer a script's `--help` and this file for documentation. Do not create extra guides unless asked.

## Safety

- These tools mutate real files. Use `--dry-run` where available; otherwise test on copies or a temp directory and inspect output first.
- Destructive defaults to check before running: `archive_directories` removes source directories unless `-k`; `merge_va` deletes inputs unless `-k`; `gpg_encrypt` and `gpg_decrypt` remove originals unless `-k`. `rename_films.py` renames in place with no dry-run.
- `share_files` serves a directory over HTTP and temporarily opens a UFW port; `apt_proxy` edits `/etc/apt/apt.conf.d/`; `apt_aria2` runs APT through sudo; Docker helpers pull and remove images. Read the help/source and get explicit confirmation before running anything system-wide, network-exposing, or destructive.
- Never read, print, or commit secrets such as `.cookie`, passphrase files, keys, or environment files. Keep `.cookie`, `.qoder/`, `.venv/`, and `__pycache__/` ignored.
- The GPG helpers accept passphrase files; never create or store one inside this repo.

## Git

- Use short imperative commit subjects in sentence case, e.g. "Add yt-dlp into uv env" or "Rename as video_util".
- Only commit when explicitly asked; never push unless asked. Stage specific paths instead of using `git add .`.
- Do not commit `.venv/`, `__pycache__/`, `.cookie`, `.qoder/`, generated media, or secrets.

## Skills

- Add new skills under `skills/<skill-name>/SKILL.md`; the folder name must match the hyphen-case `name` field.
- Keep the `description` a single line (<=1024 characters) with clear trigger scenarios, and keep the body under 500 lines.
- Validate that frontmatter is present, no unresolved task markers remain, and `.qoder/skills/<skill-name>/SKILL.md` resolves through the symlink. Keep the symlink relative (`../skills`) so other tool directories can link the same canonical skills folder.
