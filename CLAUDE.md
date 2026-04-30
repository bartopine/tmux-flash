# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

tmux-flash is a tmux plugin that gives copy-mode the same fast jump-to-location experience as flash.nvim gives Neovim. It is a fork of `Kristijan/flash-copy.tmux`. The fork keeps the live-search engine (multi-char query, labels updating per keystroke inside a tmux popup) and replaces the terminal action: instead of copying matched text to the clipboard, it positions the tmux copy-mode cursor at the matched `(line, col)`.

## Development Commands

```bash
uv venv
source .venv/bin/activate
uv sync --locked --all-extras --dev
```

Tests, lint, type-check (matches CI):

```bash
uv run ty check
uv run ruff check
uv run ruff format --check
uv run pytest --cov=src --cov-report=term-missing
```

## Architecture

### Entry points

- `tmux-flash.tmux` — TPM bash entry. Registers the keybinding (`@flash-bind-key`, default `s`) and points it at the launcher.
- `bin/tmux-flash.py` — Launcher: gets the active pane id, captures the visible viewport, opens the popup, and on result calls `cursor_jump.jump_to(pane_id, line, col)`.
- `bin/tmux-flash-interactive.py` — Runs inside the tmux `display-popup`. Live search loop: reads keystrokes, runs `SearchInterface.search` per keystroke, renders labels, waits for label press, writes `f"{match.line}:{match.col}"` to a tmux paste-buffer, exits.

### Core modules (`src/`)

- `search_interface.py` — Search and label assignment. Smart-case logic.
- `config.py` — `FlashConfig` dataclass and `ConfigLoader` reader. All options live under `@flash-*`.
- `pane_capture.py` — `tmux capture-pane -p` (visible viewport only).
- `popup_ui.py` — Popup launcher (parent side); reads `"line:col"` from result buffer, returns `Optional[tuple[int, int]]`.
- `cursor_jump.py` — Single function `jump_to(pane_id, line, col)` that issues `tmux copy-mode` + `send-keys -X top-line/start-of-line/cursor-down/cursor-right` to position the cursor.
- `ansi_utils.py`, `debug_logger.py`, `utils.py` — unchanged from upstream.

### IPC contract between popup parent and child

Child writes the chosen target as the ASCII string `"<line>:<col>"` to the tmux paste buffer named `__tmux_flash_result_<pane_id>__`. Parent reads, deletes the buffer, parses two ints, calls `cursor_jump.jump_to`. Empty/missing buffer = cancelled.

### Configuration system

- All options use `@flash-*` prefix.
- Boolean accepts `on/off/true/false/1/0/yes/no` (see `ConfigLoader.parse_bool`).
- `@flash-smart-case` is a 3-state choice: `"on"` (default), `"case-sensitive"`, `"case-insensitive"`.

## Testing philosophy

- Mock `subprocess.run` for tmux interactions; assert exact argv lists.
- `tests/test_cursor_jump.py` is the contract for the cursor-positioning command sequence — keep it strict.
- CI runs against Python 3.9, 3.10, 3.11, 3.12, 3.13, 3.14.

## Lineage

This is a fork of [Kristijan/flash-copy.tmux](https://github.com/Kristijan/flash-copy.tmux). Sync upstream improvements to the search/popup engine when they land; the cursor-jump action and `@flash-*` config naming are local.
