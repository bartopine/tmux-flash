# tmux-flash highlight & label colors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render matched-character highlights and jump-letter labels as bg-only colored bands (orange for highlights, green for labels) so the original syntax-highlighted pane text shows through.

**Architecture:** Three small edits — change two `FlashConfig` defaults to bg-only ANSI escapes, then update three rendering sites in the popup script to clear `dim`/`bold` (`\033[22m`) without touching foreground color before applying the bg escape. Test assertions on the old defaults get updated.

**Tech Stack:** Python 3.9+, ANSI escape codes (256-color SGR `\033[48;5;Nm`, attribute reset `\033[22m`), pytest.

**Spec:** `docs/superpowers/specs/2026-04-30-flash-highlight-colors-design.md`

---

### Task 1: Update default colors

**Files:**
- Modify: `src/config.py:22-23`
- Modify: `tests/test_config.py:18-19`
- Modify: `tests/test_config.py:598-599`

- [ ] **Step 1: Update defaults in `src/config.py`**

Replace lines 22-23:

```python
    highlight_colour: str = "\033[1;33m"
    label_colour: str = "\033[1;32m"
```

with:

```python
    highlight_colour: str = "\033[48;5;208m\033[1m"
    label_colour: str = "\033[48;5;142m\033[1m"
```

- [ ] **Step 2: Update default-value assertions in `tests/test_config.py`**

Replace lines 18-19:

```python
        assert config.highlight_colour == "\033[1;33m"
        assert config.label_colour == "\033[1;32m"
```

with:

```python
        assert config.highlight_colour == "\033[48;5;208m\033[1m"
        assert config.label_colour == "\033[48;5;142m\033[1m"
```

Replace lines 598-599 with the same pair (the file has two near-identical default-value assertions — one in `test_default_values`, one in `test_load_all_flash_config_defaults`).

- [ ] **Step 3: Run config tests**

Run: `uv run pytest tests/test_config.py -v`

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "default to bg-only orange/green for flash highlight & labels"
```

---

### Task 2: Highlight rendering preserves original fg

**Files:**
- Modify: `bin/tmux-flash-interactive.py:367`

- [ ] **Step 1: Update the highlight wrapping**

At line 367, replace:

```python
            highlighted = f"{AnsiStyles.RESET}{self.config.highlight_colour}{plain_matched_part}{AnsiStyles.RESET}"
```

with:

```python
            highlighted = f"\033[22m{self.config.highlight_colour}{plain_matched_part}{AnsiStyles.RESET}"
```

`\033[22m` clears `dim`/`bold` from the surrounding dimmed-line context without touching foreground color, so the original syntax-highlighted fg shows through the bg-only `highlight_colour` band.

- [ ] **Step 2: Run the label-placement tests**

Run: `uv run pytest tests/test_label_placement.py -v`

Expected: PASS. (These tests strip ANSI codes before asserting visible characters, so the `\033[22m` change is invisible to them — they verify the structural placement is unchanged.)

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest`

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add bin/tmux-flash-interactive.py
git commit -m "preserve original fg color under flash highlight bg"
```

---

### Task 3: Label rendering preserves original fg

**Files:**
- Modify: `bin/tmux-flash-interactive.py:338`
- Modify: `bin/tmux-flash-interactive.py:347`

- [ ] **Step 1: Update both label-rendering sites**

At line 338 (and the duplicate at line 347), replace:

```python
                coloured_label = f"{self.config.label_colour}{match.label}{AnsiStyles.RESET}"
```

with:

```python
                coloured_label = f"\033[22m{self.config.label_colour}{match.label}{AnsiStyles.RESET}"
```

The label is spliced into the dimmed line in the same way as the highlight, so it inherits dim too — same `\033[22m` fix applies.

- [ ] **Step 2: Run the label-placement tests**

Run: `uv run pytest tests/test_label_placement.py -v`

Expected: PASS.

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest`

Expected: all tests pass.

- [ ] **Step 4: Manual visual verification in tmux**

In tmux, press `prefix-s` and type a character. Confirm:
- Matched chars render with an orange band behind them (text remains in its original syntax-highlighted color, not white).
- The jump-letter label renders with a green band behind it.
- Non-matching content remains dimmed.

If any of those don't visually match, recheck that `\033[22m` precedes both the highlight and label escapes and that `RESET` follows.

- [ ] **Step 5: Commit**

```bash
git add bin/tmux-flash-interactive.py
git commit -m "preserve original fg color under flash label bg"
```
