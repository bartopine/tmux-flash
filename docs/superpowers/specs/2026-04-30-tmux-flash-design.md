# tmux-flash — Design

**Date:** 2026-04-30
**Author:** bartopine
**Fork base:** [Kristijan/flash-copy.tmux](https://github.com/Kristijan/flash-copy.tmux)
**Fork:** [bartopine/tmux-flash](https://github.com/bartopine/tmux-flash)

## Goal

Create `tmux-flash`, a tmux plugin that gives copy-mode the same fast jump-to-location experience as [flash.nvim](https://github.com/folke/flash.nvim) gives Neovim. Replaces the user's current jump plugin (`roy2220/easyjump.tmux`), removing its 2-character query limit by adopting flash-style live-growing search with continuously updating labels.

The plugin is a fork of `flash-copy.tmux` because that plugin already solved the hard problem — live multi-character search with labels that update per keystroke inside a tmux popup — but it currently only copies text to the clipboard. This fork swaps the terminal action so that selecting a label instead positions the tmux copy-mode cursor at the matched location.

## Non-goals (v1)

- No treesitter / syntax-aware selection. (tmux has no syntax tree; not portable.)
- No "remote operations" (e.g., yank-without-moving-cursor). The user does not need them.
- No multi-pane search. Current pane only.
- No scrollback search. Current viewport only — `tmux capture-pane -p` without `-S`/`-E` flags.
- No new actions besides cursor jump. Once the cursor lands on a target, the user uses tmux's existing copy-mode keys (`v`, `V`, `y`, `Space`, etc.) for selection and yank.

## User-facing behavior

1. User presses `prefix + s` (default; configurable via `@flash-bind-key`) from normal tmux mode.
2. A `display-popup` overlay opens with a query prompt. The plugin enters copy-mode in the underlying pane (or prepares to).
3. User types a search query. As each character is typed, the plugin re-runs the search across the visible viewport, places single-character labels on each match using a Colemak-DH-optimized alphabet, and re-renders the popup.
4. When exactly one match remains (auto-jump on unique match — configurable via `@flash-auto-jump`, default on), the cursor moves immediately. Otherwise, the user presses the label of the desired match.
5. The popup closes. The pane is in copy-mode with the cursor positioned at the first character of the chosen match.
6. `Esc` or `Ctrl-C` cancels with no cursor movement. Backspace removes the last query character and reflows the labels.

### Search semantics

- **Smart-case** (default, `@flash-smart-case=on`): query is case-insensitive if it contains no uppercase letters; case-sensitive if it contains any. Matches flash.nvim and vim's `smartcase` convention.
- Zero-match state: popup stays open, no labels visible. No error popup. Cancel returns the user to where they were.

### Label alphabet (Colemak-DH optimized)

Default order, easiest fingers first: `srtnaeoigmwfpluycdvkhxzbjq`

Rationale:
- `srtnaeoi` — Colemak-DH home row, strongest fingers (index/middle), no inward stretch
- `gm` — home row, slight inward index stretch
- `wfpluy` — top row, comfortable
- `cdvkh` — bottom row, comfortable
- `xzbjq` — fallback, harder reaches

Configurable via `@flash-label-characters`.

## Architecture

### Process model (inherited from flash-copy.tmux)

```
prefix + s
   │
   ▼
tmux-flash.tmux  (bash; TPM entry — registers binding, launches Python)
   │
   ▼
bin/tmux-flash.py  (launcher: gets pane_id, captures pane, opens popup)
   │
   ▼
tmux display-popup  ──────► bin/tmux-flash-interactive.py
                              (live-search loop inside the popup;
                               reads keystrokes, updates labels, exits
                               with chosen SearchMatch.line:col)
   │
   ▼
src/cursor_jump.py  (NEW: enters copy-mode, walks cursor to (line, col)
                     via `tmux send-keys -X`)
```

Result data flow: child popup process writes the string `"<line>:<col>"` (decimal, ASCII) to the tmux paste-buffer that upstream already uses for the matched word. Parent reads the buffer, deletes it, parses the two integers, and calls `cursor_jump.jump_to(pane_id, line, col)`. We pick this string format over a pickled `SearchMatch` because cursor-jump needs only the two integers and the buffer-as-string mechanism is already in place upstream — no new IPC.

### Module map

| File | Status | Purpose |
|---|---|---|
| `tmux-flash.tmux` | RENAMED from `tmux-flash-copy.tmux` | TPM entry, key binding registration |
| `pyproject.toml` | MODIFIED | Project name → `tmux-flash`, version reset to `0.1.0` |
| `bin/tmux-flash.py` | RENAMED + MODIFIED | Launcher; calls `cursor_jump.jump_to` instead of `clipboard.copy_and_paste` |
| `bin/tmux-flash-interactive.py` | RENAMED + MODIFIED | Popup loop; result is `(line, col)` not text |
| `src/cursor_jump.py` | NEW | `jump_to(pane_id, line, col)` — emits `tmux copy-mode` + `send-keys -X` sequence |
| `src/clipboard.py` | DELETED | Not needed for jump |
| `src/search_interface.py` | MINOR EDIT | Smart-case helper; default label alphabet |
| `src/config.py` | MODIFIED | All `@flash-copy-*` keys renamed to `@flash-*`; smart-case 3-state knob; new defaults |
| `src/pane_capture.py` | UNCHANGED | Already correct (viewport-only via `capture-pane -p`) |
| `src/popup_ui.py` | MINOR EDIT | `run()` returns `(line, col)` tuple or `None`, instead of `(text, should_paste)` |
| `src/ansi_utils.py` | UNCHANGED | |
| `src/debug_logger.py` | UNCHANGED | |
| `tests/test_cursor_jump.py` | NEW | Mocked-subprocess tests of jump command sequence |
| `tests/test_clipboard.py` | DELETED | |
| `tests/test_auto_paste.py` | DELETED | |
| Other tests | KEPT (config keys updated) | |
| `README.md` | REWRITTEN | Jump-focused; credits flash-copy.tmux upstream |
| `CLIPBOARD.md` | DELETED | |
| `CLAUDE.md` (in repo) | REWRITTEN | Reflects jump semantics |

### Cursor-jump command sequence

`cursor_jump.jump_to(pane_id, line, col)` where `(line, col)` are 0-indexed coordinates within the visible viewport (top-left = `(0, 0)`):

```
tmux copy-mode -t <pane_id>
tmux send-keys -X -t <pane_id> top-line
tmux send-keys -X -t <pane_id> start-of-line
tmux send-keys -X -N <line>  -t <pane_id> cursor-down     # if line > 0
tmux send-keys -X -N <col>   -t <pane_id> cursor-right    # if col  > 0
```

Edge cases handled:
- `line == 0` and/or `col == 0`: skip the `-N` send-keys to avoid `-N 0` ambiguity.
- Wrapped lines: `top-line` plus `cursor-down` count physical viewport rows, which is what we want — `SearchMatch.line` is already in viewport-row coordinates because `pane_capture` reads via `capture-pane -p` which expands wraps to visible rows.
- Tmux version: tested against the user's installed `tmux -V`. Implementation will note known-good versions in the README.

### Configuration options

| tmux option | Default | Notes |
|---|---|---|
| `@flash-bind-key` | `s` | Bound under the prefix |
| `@flash-smart-case` | `on` | `on` / `case-sensitive` / `case-insensitive` |
| `@flash-auto-jump` | `on` | Auto-jump when query is unique |
| `@flash-label-characters` | `srtnaeoigmwfpluycdvkhxzbjq` | Colemak-DH ordered |
| `@flash-prompt-indicator` | `flash> ` | Prompt prefix in popup |
| `@flash-highlight-colour` | (inherit) | Match highlight |
| `@flash-label-colour` | (inherit) | Label rendering |
| `@flash-prompt-colour` | (inherit) | Prompt rendering |
| `@flash-debug` | `off` | Enables `debug_logger` |

`@flash-copy-*` keys from upstream are removed entirely — they would not migrate, since this is a new plugin name and a new install path (no users on the upstream plugin name).

## Testing

- **Unit (pytest):** Keep upstream's `pytest` + `ruff` + `ty` discipline. New `test_cursor_jump.py` mocks `subprocess.run` and asserts the exact `tmux send-keys -X ...` argv sequence emitted for sample `(line, col)` inputs (including `line=0, col=0` and end-of-viewport boundaries). Keep the rest of the test suite (search, popup, pane capture, config) with renamed config keys.
- **Manual smoke test plan for v0.1:**
  1. Open a fresh tmux pane with miscellaneous text. Press `prefix + s`. Type a query. Verify labels appear, pressing one positions the cursor on the matched word.
  2. Repeat in a wide pane (>120 cols), narrow pane, tall pane.
  3. Test wrapped lines: `seq 1 1000`, narrow pane to force wrap, jump to a number near the bottom.
  4. Test unicode: jump to non-ASCII characters.
  5. Test smart-case: `foo` matches `Foo`, `FOO`. `Foo` matches only `Foo`.
  6. Test cancel: press `Esc` mid-query, confirm cursor did not move.
  7. Test auto-jump: type a unique query, confirm immediate jump (no label needed).
  8. Test viewport-only scope: scroll back into history (in copy-mode), exit copy-mode, jump — verify only currently-visible content is searched.

## Installation

After v0.1 tag is cut and pushed:

```tmux
# in tmux.conf (chezmoi-tracked)
set -g @plugin 'bartopine/tmux-flash'
set -g @flash-bind-key 's'
```

Replace the existing `set -g @plugin 'roy2220/easyjump.tmux'` line. Run `prefix + I` to install via TPM.

During development the user has the fork cloned manually at `~/.config/tmux/plugins/tmux-flash/`. TPM ignores manually-cloned plugin dirs not listed in `tmux.conf`.

## Out of scope / deferred

- Cross-pane jump (focus + cursor jump to a label in any pane in the current window). Possible v0.2 if the v1 single-pane experience proves insufficient.
- Scrollback search.
- Action plugin system (e.g., select-from-here-to-there). User explicitly does not want this.
- Migration shims from `@flash-copy-*` keys.
