# tmux-flash Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert this Python tmux plugin (forked from flash-copy.tmux) from copy-to-clipboard semantics to copy-mode-cursor-jump semantics, replacing the user's `roy2220/easyjump.tmux` with a flash.nvim-style live-search jump.

**Architecture:** The fork keeps the existing live-search engine (search_interface, popup_ui, pane_capture) and replaces the terminal action. The clipboard module is deleted; a new `cursor_jump` module enters copy-mode and walks the cursor to `(line, col)` via `tmux send-keys -X`. The popup IPC payload changes from a matched-word string to a `"line:col"` string. All `@flash-copy-*` tmux options are renamed to `@flash-*`.

**Tech Stack:** Python 3.9+ (project uses `uv`), pytest + coverage, ruff, ty type checker, tmux 3.0+ (`capture-pane`, `display-popup`, `copy-mode`, `send-keys -X`). Repo lives at `~/.config/tmux/plugins/tmux-flash/`. Spec: `docs/superpowers/specs/2026-04-30-tmux-flash-design.md`.

---

## Conventions for every task

- All shell commands assume cwd is `~/.config/tmux/plugins/tmux-flash/`.
- Run tests via `uv run pytest …`. Run type-check via `uv run ty check`. Run lint via `uv run ruff check`.
- After each task's final step, commit with a conventional-commit-style message. **Do NOT** include `Co-Authored-By: Claude`, `Generated with Claude Code`, or any AI/Anthropic mention in commit messages — see `~/.claude/CLAUDE.md`. Commits should look like the user authored them.
- Author identity for commits: `bartopine <bartopine@gmail.com>`. The repo's git config may not be set globally; use `git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit …` if needed.
- Do not push to `origin/main` until the user explicitly asks. All work stays local until then.

---

## Phase 0 — Environment setup

### Task 0: Create dev branch and verify toolchain

**Files:** none (git operations only)

- [ ] **Step 1: Create a feature branch off main**

```bash
git checkout -b feat/jump-cursor
git status
```

Expected: `On branch feat/jump-cursor`, working tree clean.

- [ ] **Step 2: Verify uv is available and sync deps**

```bash
uv --version
uv sync --locked --all-extras --dev
```

Expected: dependencies installed, no errors.

- [ ] **Step 3: Run the existing test suite to establish a green baseline**

```bash
uv run pytest 2>&1 | tail -20
```

Expected: all tests pass (or note any pre-existing failures so we know they aren't ours).

- [ ] **Step 4: Verify type-check and lint baseline**

```bash
uv run ty check 2>&1 | tail -10
uv run ruff check 2>&1 | tail -10
```

Expected: clean, or note pre-existing issues.

- [ ] **Step 5: No commit needed for this task — just confirm baseline is green.**

---

## Phase 1 — Build cursor_jump module (TDD, no behavior change yet)

### Task 1: Write failing tests for cursor_jump.jump_to

**Files:**
- Create: `tests/test_cursor_jump.py`

This task writes the test file before the module exists. The module API: `cursor_jump.jump_to(pane_id: str, line: int, col: int) -> None` issues a sequence of `subprocess.run(["tmux", ...])` calls.

- [ ] **Step 1: Create the test file with all unit tests**

Write `tests/test_cursor_jump.py`:

```python
"""Tests for src.cursor_jump."""

from unittest.mock import MagicMock, patch

import pytest

from src import cursor_jump


def _argv(call):
    """Extract positional args[0] (the command list) from a mock call."""
    return list(call.args[0])


class TestJumpTo:
    """Tests for cursor_jump.jump_to."""

    @patch("src.cursor_jump.subprocess.run")
    def test_jump_to_origin_emits_copy_mode_and_anchor(self, mock_run: MagicMock):
        """At (0, 0) we enter copy-mode and anchor to top-line/start-of-line, no walking."""
        cursor_jump.jump_to("%5", 0, 0)

        argvs = [_argv(c) for c in mock_run.call_args_list]
        # Must contain: copy-mode -t %5
        assert ["tmux", "copy-mode", "-t", "%5"] in argvs
        # Must contain: send-keys -X -t %5 top-line
        assert ["tmux", "send-keys", "-X", "-t", "%5", "top-line"] in argvs
        assert ["tmux", "send-keys", "-X", "-t", "%5", "start-of-line"] in argvs
        # No cursor-down or cursor-right at origin
        for argv in argvs:
            assert "cursor-down" not in argv
            assert "cursor-right" not in argv

    @patch("src.cursor_jump.subprocess.run")
    def test_jump_to_nonzero_emits_walk(self, mock_run: MagicMock):
        """At (3, 7) we walk down 3 and right 7."""
        cursor_jump.jump_to("%2", 3, 7)

        argvs = [_argv(c) for c in mock_run.call_args_list]
        assert ["tmux", "send-keys", "-X", "-t", "%2", "top-line"] in argvs
        # Walk down 3 rows in a single send-keys -N invocation:
        assert [
            "tmux", "send-keys", "-X", "-N", "3", "-t", "%2", "cursor-down",
        ] in argvs
        # Walk right 7 cols:
        assert [
            "tmux", "send-keys", "-X", "-N", "7", "-t", "%2", "cursor-right",
        ] in argvs

    @patch("src.cursor_jump.subprocess.run")
    def test_jump_skips_walk_when_zero(self, mock_run: MagicMock):
        """At (0, 5) we walk right but not down. At (5, 0) the inverse."""
        cursor_jump.jump_to("%1", 0, 5)
        argvs = [_argv(c) for c in mock_run.call_args_list]
        assert not any("cursor-down" in argv for argv in argvs)
        assert ["tmux", "send-keys", "-X", "-N", "5", "-t", "%1", "cursor-right"] in argvs

        mock_run.reset_mock()
        cursor_jump.jump_to("%1", 5, 0)
        argvs = [_argv(c) for c in mock_run.call_args_list]
        assert ["tmux", "send-keys", "-X", "-N", "5", "-t", "%1", "cursor-down"] in argvs
        assert not any("cursor-right" in argv for argv in argvs)

    @patch("src.cursor_jump.subprocess.run")
    def test_jump_rejects_negative(self, mock_run: MagicMock):
        with pytest.raises(ValueError):
            cursor_jump.jump_to("%1", -1, 0)
        with pytest.raises(ValueError):
            cursor_jump.jump_to("%1", 0, -1)
        mock_run.assert_not_called()

    @patch("src.cursor_jump.subprocess.run")
    def test_jump_call_order_is_anchor_then_walk(self, mock_run: MagicMock):
        """Order matters: copy-mode first, then top-line/start-of-line, then walk."""
        cursor_jump.jump_to("%9", 2, 3)
        argvs = [_argv(c) for c in mock_run.call_args_list]

        def index_of(argv_match):
            for i, a in enumerate(argvs):
                if a == argv_match:
                    return i
            raise AssertionError(f"Not found: {argv_match} in {argvs}")

        i_copy = index_of(["tmux", "copy-mode", "-t", "%9"])
        i_top = index_of(["tmux", "send-keys", "-X", "-t", "%9", "top-line"])
        i_sol = index_of(["tmux", "send-keys", "-X", "-t", "%9", "start-of-line"])
        i_down = index_of(
            ["tmux", "send-keys", "-X", "-N", "2", "-t", "%9", "cursor-down"]
        )
        i_right = index_of(
            ["tmux", "send-keys", "-X", "-N", "3", "-t", "%9", "cursor-right"]
        )
        assert i_copy < i_top < i_sol < i_down < i_right
```

- [ ] **Step 2: Run the test to confirm it fails (module does not exist yet)**

```bash
uv run pytest tests/test_cursor_jump.py -v 2>&1 | tail -10
```

Expected: collection or import error — `ModuleNotFoundError: No module named 'src.cursor_jump'`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_cursor_jump.py
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "test: add failing tests for cursor_jump.jump_to"
```

---

### Task 2: Implement src/cursor_jump.py

**Files:**
- Create: `src/cursor_jump.py`

- [ ] **Step 1: Write the module**

Write `src/cursor_jump.py`:

```python
"""Move tmux copy-mode cursor to a (line, col) coordinate within the visible viewport.

Coordinates are 0-indexed: top-left of the visible pane is (0, 0).
"""

import subprocess


def jump_to(pane_id: str, line: int, col: int) -> None:
    """Enter copy-mode in `pane_id` and position the cursor at (line, col).

    Raises:
        ValueError: if line or col is negative.
    """
    if line < 0 or col < 0:
        raise ValueError(f"line and col must be non-negative; got line={line}, col={col}")

    # Enter copy-mode (no-op if already in copy-mode).
    subprocess.run(["tmux", "copy-mode", "-t", pane_id], check=False)

    # Anchor: move cursor to top-left of the visible viewport.
    subprocess.run(
        ["tmux", "send-keys", "-X", "-t", pane_id, "top-line"],
        check=False,
    )
    subprocess.run(
        ["tmux", "send-keys", "-X", "-t", pane_id, "start-of-line"],
        check=False,
    )

    # Walk down `line` physical viewport rows, then right `col` columns.
    if line > 0:
        subprocess.run(
            ["tmux", "send-keys", "-X", "-N", str(line), "-t", pane_id, "cursor-down"],
            check=False,
        )
    if col > 0:
        subprocess.run(
            ["tmux", "send-keys", "-X", "-N", str(col), "-t", pane_id, "cursor-right"],
            check=False,
        )
```

- [ ] **Step 2: Run the cursor_jump tests, expect pass**

```bash
uv run pytest tests/test_cursor_jump.py -v 2>&1 | tail -15
```

Expected: 5 passed.

- [ ] **Step 3: Run the full suite to confirm no regressions**

```bash
uv run pytest 2>&1 | tail -10
```

Expected: same as baseline (Task 0 Step 3) plus 5 new passing tests.

- [ ] **Step 4: Type-check and lint the new module**

```bash
uv run ty check src/cursor_jump.py
uv run ruff check src/cursor_jump.py tests/test_cursor_jump.py
uv run ruff format --check src/cursor_jump.py tests/test_cursor_jump.py
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/cursor_jump.py
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "feat: add cursor_jump module for copy-mode cursor positioning"
```

---

## Phase 2 — Switch IPC payload from matched-text to "line:col"

The popup writes a result to a tmux paste-buffer; the parent reads and acts. Today the buffer holds the matched word. We change it to hold `"<line>:<col>"`.

### Task 3: Find and rename internal "save result" sites in popup_ui.py

**Files:**
- Modify: `src/popup_ui.py` (locate `_save_result` and the call sites that pass `match.copy_text`)

This task introduces a new shape without yet changing all callers. We'll add a `_save_match_position(match)` method that writes `f"{match.line}:{match.col}"` and have the existing `_save_result` delegate to it. We leave the existing `_save_result(text, …)` API intact for now (Phase 3 will remove it).

- [ ] **Step 1: Read the existing `_save_result` implementation**

```bash
grep -n "_save_result\|def _save_result\|set-buffer.*result_buffer" src/popup_ui.py
```

Note the line range of `_save_result` and where it's called.

- [ ] **Step 2: Add a new method `_save_match_position` next to `_save_result`**

Edit `src/popup_ui.py` and add (right after the existing `_save_result`):

```python
    def _save_match_position(self, match) -> None:
        """Write 'line:col' for the chosen match into the tmux result buffer.

        This is the IPC payload consumed by the parent launcher to position
        the copy-mode cursor.
        """
        payload = f"{match.line}:{match.col}"
        result_buffer = f"__tmux_flash_copy_result_{self.pane_id}__"
        subprocess.run(
            ["tmux", "set-buffer", "-b", result_buffer, payload],
            check=False,
        )
```

(If `subprocess` is not already imported at the top of `popup_ui.py`, add the import. Run `grep -n "^import subprocess" src/popup_ui.py` to check.)

- [ ] **Step 3: Run tests, expect green (we haven't changed behavior)**

```bash
uv run pytest 2>&1 | tail -10
```

Expected: same as baseline.

- [ ] **Step 4: Commit**

```bash
git add src/popup_ui.py
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "refactor(popup_ui): add _save_match_position helper for line:col IPC"
```

---

### Task 4: Switch popup_ui call sites to use match-position payload

**Files:**
- Modify: `src/popup_ui.py` (call sites around lines 640-665 — `_save_result(match.copy_text, ...)` → `_save_match_position(match)`)
- Modify: `src/popup_ui.py` (`run()` return: from `(text, should_paste)` to `Optional[tuple[int, int]]`)
- Modify: `tests/test_popup_ui.py` (any tests asserting the old `(text, should_paste)` shape)

- [ ] **Step 1: Find every call to `_save_result` and every assertion on `run()`'s return**

```bash
grep -n "_save_result\|should_paste\|copy_text" src/popup_ui.py
grep -n "\.run()\|copy_text\|should_paste" tests/test_popup_ui.py | head -30
```

Read enough surrounding context to plan the edit.

- [ ] **Step 2: Replace each `self._save_result(match.copy_text, …)` with `self._save_match_position(match)`**

For each call site like:
```python
self._save_result(self.current_matches[0].copy_text, should_paste=should_paste)
return self.current_matches[0].copy_text
```
change to:
```python
self._save_match_position(self.current_matches[0])
return (self.current_matches[0].line, self.current_matches[0].col)
```

(Same transformation for the other call site that uses `match.copy_text`.)

- [ ] **Step 3: Update the `run()` parser in popup_ui.py to parse `"line:col"` and return `Optional[tuple[int, int]]`**

Locate the block (around lines 187-238) that reads from `result_buffer` and returns `(result_text, should_paste)`. Replace the return shape:

```python
            # Empty string means cancelled (ESC/Ctrl+C); None means buffer not found.
            if result_text is not None and result_text != "":
                try:
                    line_str, col_str = result_text.split(":", 1)
                    line, col = int(line_str), int(col_str)
                except (ValueError, AttributeError):
                    if logger.enabled:
                        logger.log(
                            f"Malformed result buffer payload: {result_text!r}; treating as cancel"
                        )
                    return None
                if logger.enabled:
                    logger.log(f"Returning jump target line={line} col={col}")
                return (line, col)

            if logger.enabled:
                logger.log("No result to return (cancelled or empty)")
            return None
```

Update the docstring of `run()` accordingly: returns `Optional[tuple[int, int]]` (`None` on cancel).

- [ ] **Step 4: Update `tests/test_popup_ui.py` to assert the new return shape**

For each test that asserts something like `assert result == ("matched_text", False)` or unpacks `text, should_paste = ui.run()`, change the expectation. Tests that mock the result buffer to contain a word like `"hello"` should now mock it to contain `"3:7"` and assert `result == (3, 7)`. Tests asserting cancel-returns-`(None, False)` should assert `result is None`.

After editing, list the changed tests:

```bash
grep -n "should_paste\|copy_text" tests/test_popup_ui.py
```

Expected: zero matches for either symbol (both gone).

- [ ] **Step 5: Run popup_ui tests**

```bash
uv run pytest tests/test_popup_ui.py -v 2>&1 | tail -20
```

Expected: all pass. If a test fails, read the failure, adjust expectation to match the new shape, re-run.

- [ ] **Step 6: Run the full suite**

```bash
uv run pytest 2>&1 | tail -15
```

At this point clipboard.py and the launcher still reference the old API; expect failures only in `bin/tmux-flash-copy.py` integration paths if tested, but the unit suite should be green except for any test that exercised the now-changed return signature in another file.

- [ ] **Step 7: Commit**

```bash
git add src/popup_ui.py tests/test_popup_ui.py
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "refactor(popup_ui): switch IPC payload to line:col, run() returns Optional[(line,col)]"
```

---

### Task 5: Switch the launcher (bin/tmux-flash-copy.py) to call cursor_jump

**Files:**
- Modify: `bin/tmux-flash-copy.py`

- [ ] **Step 1: Replace the import and the action call**

In `bin/tmux-flash-copy.py`, remove the `from src.clipboard import Clipboard` import and replace it with:

```python
from src.cursor_jump import jump_to  # noqa: E402
```

Remove the line `clipboard = Clipboard()` and the `clipboard=clipboard` argument when constructing `PopupUI`. (Then update PopupUI's constructor to no longer require `clipboard` — see Task 6.)

Replace the post-popup block:

```python
        # Run the interactive search interface
        result, should_paste = ui.run()

        if result:
            # Copy to clipboard and optionally paste
            logger = DebugLogger.get_instance() if config.debug_enabled else None
            clipboard.copy_and_paste(
                result, pane_id=pane_id, auto_paste=should_paste, logger=logger
            )
```

with:

```python
        # Run the interactive search interface
        target = ui.run()

        if target is not None:
            line, col = target
            jump_to(pane_id, line, col)
```

- [ ] **Step 2: Run the launcher manually as a smoke test (optional, requires tmux)**

If running inside a tmux session, this is a real end-to-end check:

```bash
tmux new-session -d -s flashtest "for i in $(seq 1 200); do echo line $i with word foo$i; done; sleep 60"
tmux send-keys -t flashtest "" "C-l"
# In another shell:
uv run python bin/tmux-flash-copy.py
# Type 'foo50' in the popup; press the assigned label.
# Verify the cursor is on 'f' of 'foo50' in the flashtest pane.
tmux kill-session -t flashtest
```

If end-to-end testing is not possible right now, skip; unit tests cover the call wiring.

- [ ] **Step 3: Run the full unit suite**

```bash
uv run pytest 2>&1 | tail -15
```

Expected: still green (clipboard module is no longer called by the launcher; PopupUI may still import it — that's fixed in Task 6).

- [ ] **Step 4: Commit**

```bash
git add bin/tmux-flash-copy.py
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "feat(launcher): call cursor_jump.jump_to instead of clipboard.copy_and_paste"
```

---

### Task 6: Drop the `clipboard` parameter from PopupUI

**Files:**
- Modify: `src/popup_ui.py` (constructor signature, attribute, any internal use of `self.clipboard`)
- Modify: `tests/test_popup_ui.py` (constructor calls in test fixtures)

The launcher no longer passes `clipboard`; PopupUI doesn't need it. Auto-paste logic is also gone.

- [ ] **Step 1: Find references to `clipboard` and `auto_paste` inside popup_ui.py**

```bash
grep -n "clipboard\|auto_paste\|should_paste" src/popup_ui.py
```

Read each line in context.

- [ ] **Step 2: Remove the parameter from `__init__`**

Locate `class PopupUI`'s `__init__` and remove `clipboard` from the signature, the docstring, and `self.clipboard = clipboard`. Remove any branch that checks `self.clipboard` or `self.config.auto_paste_enable`.

If the popup currently passes `--auto-paste true/false` to the interactive child (around line 159 of the unedited `popup_ui.py`), remove that argument since auto-paste no longer exists. The interactive child will be cleaned up in Task 11.

- [ ] **Step 3: Update test fixtures in `tests/test_popup_ui.py` that construct PopupUI**

Remove `clipboard=…` from every PopupUI(...) call in the test file. The test file may import a `Clipboard` mock — those lines can be removed.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_popup_ui.py -v 2>&1 | tail -15
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/popup_ui.py tests/test_popup_ui.py
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "refactor(popup_ui): drop clipboard/auto_paste parameters"
```

---

### Task 7: Delete src/clipboard.py and its tests

**Files:**
- Delete: `src/clipboard.py`
- Delete: `tests/test_clipboard.py`
- Delete: `tests/test_auto_paste.py`
- Delete: `CLIPBOARD.md`

- [ ] **Step 1: Confirm no imports of `src.clipboard` remain**

```bash
grep -rn "from src.clipboard\|src.clipboard\|clipboard\.Clipboard\|copy_and_paste" src/ bin/ tests/
```

Expected: zero hits (or only hits inside the files we're about to delete).

- [ ] **Step 2: Delete the files**

```bash
git rm src/clipboard.py tests/test_clipboard.py tests/test_auto_paste.py CLIPBOARD.md
```

- [ ] **Step 3: Run the full suite**

```bash
uv run pytest 2>&1 | tail -15
```

Expected: green.

- [ ] **Step 4: Run type-check and lint**

```bash
uv run ty check 2>&1 | tail -10
uv run ruff check 2>&1 | tail -10
```

Expected: clean. If `ty` complains about missing imports anywhere, fix before committing.

- [ ] **Step 5: Commit**

```bash
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "chore: remove clipboard module and copy-related tests/docs"
```

---

## Phase 3 — Update the interactive child script (write line:col, drop auto-paste)

### Task 8: Audit `bin/tmux-flash-copy-interactive.py` for clipboard / auto-paste references

**Files:**
- Modify: `bin/tmux-flash-copy-interactive.py` (no edits in this task — read only)

- [ ] **Step 1: Find every reference**

```bash
grep -n "set-buffer\|copy_text\|auto[-_]paste\|--auto-paste\|argparse\|argv" bin/tmux-flash-copy-interactive.py | head -40
```

Note: where the matched word is written to the result buffer, where `--auto-paste` is parsed, and where the exit code is set (recall popup_ui used exit code 10 to signal paste).

- [ ] **Step 2: No commit — this is a reading task. Record findings in the next task's edits.**

---

### Task 9: Change interactive child to write `"line:col"` to the result buffer

**Files:**
- Modify: `bin/tmux-flash-copy-interactive.py`

- [ ] **Step 1: Replace the result-write call**

Find the line that writes the matched word, e.g.:

```python
subprocess.run(
    ["tmux", "set-buffer", "-b", result_buffer, match.copy_text],
    ...
)
```

Replace with:

```python
subprocess.run(
    ["tmux", "set-buffer", "-b", result_buffer, f"{match.line}:{match.col}"],
    check=False,
)
```

Apply to every site that writes the result buffer (there may be one for unique-match auto-jump and one for explicit label selection).

- [ ] **Step 2: Remove `--auto-paste` argument parsing and the exit-code-10 paste signal**

Find the argparse section that defines `--auto-paste`. Remove the argument and any code that sets exit code 10. Always exit `0` on success, non-zero only on error/cancel.

- [ ] **Step 3: Run any tests that exercise the interactive script (if integration tests exist)**

```bash
grep -rn "tmux-flash-copy-interactive" tests/
```

If no tests reference the script directly, that's fine — popup_ui tests cover the IPC contract.

- [ ] **Step 4: Run the full suite**

```bash
uv run pytest 2>&1 | tail -15
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add bin/tmux-flash-copy-interactive.py
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "feat(interactive): write line:col IPC payload, drop auto-paste exit signal"
```

---

## Phase 4 — Rebrand: rename files and tmux options

### Task 10: Rename binaries and entry tmux script

**Files:**
- Rename: `bin/tmux-flash-copy.py` → `bin/tmux-flash.py`
- Rename: `bin/tmux-flash-copy-interactive.py` → `bin/tmux-flash-interactive.py`
- Rename: `tmux-flash-copy.tmux` → `tmux-flash.tmux`
- Modify: contents of the renamed `tmux-flash.tmux` (default key, binding script path, option name)
- Modify: `bin/tmux-flash.py` to point at the renamed interactive script
- Modify: `src/popup_ui.py` to spawn the renamed interactive script

- [ ] **Step 1: Rename the files via git**

```bash
git mv bin/tmux-flash-copy.py bin/tmux-flash.py
git mv bin/tmux-flash-copy-interactive.py bin/tmux-flash-interactive.py
git mv tmux-flash-copy.tmux tmux-flash.tmux
```

- [ ] **Step 2: Update `tmux-flash.tmux` to use new key, option, and script name**

Replace its contents with:

```bash
#!/usr/bin/env bash
# tmux-flash plugin file for TPM
# Entry point: registers the keybinding and points it at the launcher.

PLUGIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

get_tmux_option() {
    local option="${1}"
    local default_value="${2}"
    local option_override
    option_override="$(tmux show-option -gqv "${option}")"
    if [ -z "${option_override}" ]; then
        echo "${default_value}"
    else
        echo "${option_override}"
    fi
}

bind_key=$(get_tmux_option "@flash-bind-key" "s")

tmux bind-key "${bind_key}" run-shell "${PLUGIN_DIR}/bin/tmux-flash.py"
```

Make sure it stays executable:

```bash
chmod +x tmux-flash.tmux
```

- [ ] **Step 3: Update `bin/tmux-flash.py` to spawn the renamed interactive script**

Find any reference to `"tmux-flash-copy-interactive.py"` in the launcher and change it to `"tmux-flash-interactive.py"`.

```bash
grep -n "tmux-flash-copy-interactive\|tmux-flash-copy" bin/tmux-flash.py
```

Replace each hit.

- [ ] **Step 4: Update `src/popup_ui.py` to spawn the renamed interactive script**

```bash
grep -n "tmux-flash-copy-interactive\|tmux-flash-copy" src/popup_ui.py
```

The popup launcher path is built around line 101 of popup_ui.py: `interactive_script = plugin_dir / "bin" / "tmux-flash-copy-interactive.py"`. Change `"tmux-flash-copy-interactive.py"` to `"tmux-flash-interactive.py"`.

Also update any internal buffer name like `__tmux_flash_copy_result_{pane_id}__` → `__tmux_flash_result_{pane_id}__` (and `__tmux_flash_copy_pane_content_…__` similarly). Search and replace via:

```bash
grep -rn "__tmux_flash_copy_" src/ bin/ tests/
```

Replace each occurrence with the new prefix `__tmux_flash_`.

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest 2>&1 | tail -15
```

Expected: green. If any test hard-codes the old buffer name, update the test.

- [ ] **Step 6: Commit**

```bash
git add -A
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "refactor: rename binaries and tmux entry script to tmux-flash"
```

---

### Task 11: Rename all `@flash-copy-*` tmux options to `@flash-*`

**Files:**
- Modify: `src/config.py` (all occurrences of `@flash-copy-` → `@flash-`)
- Modify: `tests/test_config.py` (test fixtures and assertions)
- Modify: `src/debug_logger.py` (any reference to `@flash-copy-debug` if present)

- [ ] **Step 1: Find all hits**

```bash
grep -rn "@flash-copy-" src/ bin/ tests/ docs/ *.tmux *.toml 2>/dev/null
```

Make a list. Should include keys: `@flash-copy-reverse-search`, `@flash-copy-case-sensitive`, `@flash-copy-word-separators`, `@flash-copy-prompt-placeholder-text`, `@flash-copy-highlight-colour`, `@flash-copy-label-colour`, `@flash-copy-prompt-position`, `@flash-copy-prompt-indicator`, `@flash-copy-prompt-colour`, `@flash-copy-debug`, `@flash-copy-auto-paste`, `@flash-copy-label-characters`, `@flash-copy-idle-timeout`, `@flash-copy-idle-warning`, `@flash-copy-bind-key`.

- [ ] **Step 2: Replace `@flash-copy-` with `@flash-` repo-wide**

Use a single `sed` invocation to make the renames atomic across files (verify with grep first):

```bash
grep -rl "@flash-copy-" src/ bin/ tests/ | xargs sed -i 's/@flash-copy-/@flash-/g'
grep -rn "@flash-copy-" src/ bin/ tests/
```

Expected: second grep returns nothing.

- [ ] **Step 3: Also drop `auto_paste_enable` from `FlashCopyConfig`**

In `src/config.py`, in the dataclass `FlashCopyConfig`, remove the `auto_paste_enable: bool = True` field. In `load_all_flash_copy_config()`, remove the `auto_paste_enable=ConfigLoader.get_bool("@flash-auto-paste", default=True)` line.

Update `tests/test_config.py` to drop assertions about `auto_paste_enable`.

- [ ] **Step 4: Rename `FlashCopyConfig` → `FlashConfig` and `load_all_flash_copy_config` → `load_all_flash_config`**

```bash
grep -rl "FlashCopyConfig\|load_all_flash_copy_config" src/ bin/ tests/ | \
  xargs sed -i -e 's/FlashCopyConfig/FlashConfig/g' -e 's/load_all_flash_copy_config/load_all_flash_config/g'
grep -rn "FlashCopyConfig\|load_all_flash_copy_config" src/ bin/ tests/
```

Expected: no remaining matches.

- [ ] **Step 5: Run tests, type-check, lint**

```bash
uv run pytest 2>&1 | tail -15
uv run ty check 2>&1 | tail -10
uv run ruff check 2>&1 | tail -10
```

Expected: green/clean.

- [ ] **Step 6: Commit**

```bash
git add -A
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "refactor(config): rename @flash-copy-* options to @flash-*; drop auto-paste config"
```

---

## Phase 5 — Smart-case search and Colemak-DH default labels

### Task 12: Add smart-case logic to search_interface

**Files:**
- Modify: `src/search_interface.py` (`SearchInterface.search` and/or `__init__`)
- Modify: `src/config.py` (replace `case_sensitive: bool` with `smart_case: str` 3-state)
- Modify: `tests/test_search_interface.py`
- Modify: `tests/test_config.py`

The 3-state is `"on"` (smart-case, default), `"case-sensitive"`, `"case-insensitive"`. When `"on"`: case-insensitive iff query is all-lowercase.

- [ ] **Step 1: Update `FlashConfig` to have `smart_case: str = "on"` instead of `case_sensitive: bool`**

Edit `src/config.py`:

In the dataclass:
```python
    smart_case: str = "on"  # "on" (smart) | "case-sensitive" | "case-insensitive"
```
(Remove `case_sensitive: bool = False`.)

In `load_all_flash_config()`, replace:
```python
            case_sensitive=ConfigLoader.get_bool("@flash-case-sensitive", default=False),
```
with:
```python
            smart_case=ConfigLoader.get_choice(
                "@flash-smart-case",
                choices=["on", "case-sensitive", "case-insensitive"],
                default="on",
            ),
```

- [ ] **Step 2: Update `SearchInterface` to accept `smart_case` and resolve case-sensitivity per query**

In `src/search_interface.py`, replace the `case_sensitive: bool` constructor parameter with `smart_case: str = "on"`. Store on `self.smart_case`. In `search(self, query: str)`, resolve effective case-sensitivity:

```python
def _resolve_case_sensitive(self, query: str) -> bool:
    if self.smart_case == "case-sensitive":
        return True
    if self.smart_case == "case-insensitive":
        return False
    # "on" — smart-case
    return any(c.isupper() for c in query)
```

Replace existing references to `self.case_sensitive` in `search()` with `self._resolve_case_sensitive(query)`.

- [ ] **Step 3: Update launcher (`bin/tmux-flash.py`) construction of `SearchInterface`**

Change `case_sensitive=config.case_sensitive` to `smart_case=config.smart_case`.

- [ ] **Step 4: Update tests**

In `tests/test_search_interface.py`, find tests that pass `case_sensitive=…` to `SearchInterface(...)`. Replace with `smart_case=…` semantics:
- `case_sensitive=True` → `smart_case="case-sensitive"`
- `case_sensitive=False` → `smart_case="case-insensitive"` (preserves old behavior for unrelated tests)

Add three new tests:

```python
def test_smart_case_lowercase_query_is_case_insensitive():
    si = SearchInterface("Hello hello HELLO", smart_case="on")
    matches = si.search("hello")
    assert len(matches) == 3

def test_smart_case_mixed_query_is_case_sensitive():
    si = SearchInterface("Hello hello HELLO", smart_case="on")
    matches = si.search("Hello")
    assert len(matches) == 1

def test_smart_case_force_options_override():
    si = SearchInterface("Hello hello", smart_case="case-sensitive")
    assert len(si.search("hello")) == 1
    si2 = SearchInterface("Hello hello", smart_case="case-insensitive")
    assert len(si2.search("Hello")) == 2
```

In `tests/test_config.py`, replace assertions on `config.case_sensitive` with assertions on `config.smart_case`. Add a test that `@flash-smart-case` defaults to `"on"`.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_search_interface.py tests/test_config.py -v 2>&1 | tail -25
uv run pytest 2>&1 | tail -10
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/search_interface.py src/config.py bin/tmux-flash.py tests/test_search_interface.py tests/test_config.py
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "feat(search): add smart-case mode (default on); replace case_sensitive bool"
```

---

### Task 13: Set Colemak-DH-optimized default label characters

**Files:**
- Modify: `src/search_interface.py` (DEFAULT_LABELS constant)
- Modify: `tests/test_search_interface.py` if any test asserts the old default

- [ ] **Step 1: Locate the existing default label constant**

```bash
grep -n "DEFAULT_LABELS\|asdfghjkl\|label_characters" src/search_interface.py
```

The existing default is `"asdfghjklqwertyuiopzxcvbnmASDFGHJKLQWERTYUIOPZXCVBNM"`.

- [ ] **Step 2: Replace with the Colemak-DH-optimized order**

```python
DEFAULT_LABELS = "srtnaeoigmwfpluycdvkhxzbjq"
```

Drop the uppercase suffix — flash.nvim and most modern label-jump plugins use single-case labels and rely on smart-case for query matching. (If we ever need more than 26 labels we can extend later; YAGNI.)

- [ ] **Step 3: Update or add tests for the default**

In `tests/test_search_interface.py`, replace any assertion like `assert SearchInterface.DEFAULT_LABELS.startswith("asdf")` with `assert SearchInterface.DEFAULT_LABELS.startswith("srtn")`.

- [ ] **Step 4: Run tests**

```bash
uv run pytest 2>&1 | tail -10
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/search_interface.py tests/test_search_interface.py
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "feat(search): default labels to Colemak-DH-optimized alphabet"
```

---

## Phase 6 — Project metadata, README, in-repo CLAUDE.md

### Task 14: Update pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit name, version, description**

In `pyproject.toml`, change:

```toml
name = "tmux-flash-copy"
version = "1.3.1"
description = "A tmux plugin for searching and copying visible words to clipboard"
```

to:

```toml
name = "tmux-flash"
version = "0.1.0"
description = "A tmux plugin for flash.nvim-style live-search jump in copy-mode"
```

- [ ] **Step 2: Run lint and tests**

```bash
uv run ruff check 2>&1 | tail -5
uv run pytest 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "chore: rename project to tmux-flash, reset version to 0.1.0"
```

---

### Task 15: Rewrite README.md

**Files:**
- Modify: `README.md` (full rewrite)

- [ ] **Step 1: Replace README content**

Replace the entire file with:

```markdown
# tmux-flash

A tmux plugin for [flash.nvim](https://github.com/folke/flash.nvim)-style live-search jump in copy-mode.

Type a multi-character query, watch labels appear over each match in real time, then press a label to position the copy-mode cursor there. From there, tmux's built-in copy-mode keys (`v`, `V`, `y`, `Space`, …) take over.

This plugin is a fork of [Kristijan/flash-copy.tmux](https://github.com/Kristijan/flash-copy.tmux), which solved the live-search-with-labels rendering problem inside a tmux popup. tmux-flash replaces that plugin's clipboard action with a copy-mode cursor jump.

## Why fork?

flash-copy.tmux is excellent for grabbing visible text into the clipboard. It is not designed to position the copy-mode cursor — it always copies, never moves the cursor. Existing "jump" plugins for tmux (`schasse/tmux-jump`, `roy2220/easyjump.tmux`, `IngoMeyer441/tmux-easy-motion`, `ddzero2c/tmux-easymotion`) all cap their query at one or two characters. tmux-flash takes flash-copy.tmux's live-growing-query engine and uses it to drive a cursor jump.

## Install

Via [TPM](https://github.com/tmux-plugins/tpm):

```tmux
set -g @plugin 'bartopine/tmux-flash'
set -g @flash-bind-key 's'
```

Then prefix-`I` to install.

## Usage

1. Press `<prefix> + s` (default; configurable).
2. Type a search query. Labels appear on each match and update as you type.
3. Press the label of the desired target — or, if your query is unique, the cursor jumps automatically.
4. The pane is now in copy-mode at the chosen location. Continue with tmux's normal copy-mode keys.

`Esc` or `Ctrl-C` cancels with no cursor movement. Backspace removes the last query character and reflows the labels.

## Configuration

| tmux option | Default | Notes |
|---|---|---|
| `@flash-bind-key` | `s` | Bound under the prefix |
| `@flash-smart-case` | `on` | `on` / `case-sensitive` / `case-insensitive` |
| `@flash-auto-jump` | `on` | Jump automatically when query is unique |
| `@flash-label-characters` | `srtnaeoigmwfpluycdvkhxzbjq` | Colemak-DH ordered |
| `@flash-prompt-indicator` | `>` | Prompt prefix in popup |
| `@flash-highlight-colour` | ANSI | Match highlight |
| `@flash-label-colour` | ANSI | Label rendering |
| `@flash-prompt-colour` | ANSI | Prompt rendering |
| `@flash-debug` | `off` | Enable debug log |

## Scope (v0.1)

- Search runs against the **current pane**, **current viewport** only — no scrollback, no cross-pane.
- The only action is "move copy-mode cursor to the target." No clipboard, no remote operations, no treesitter.
- Future: cross-pane jump may land in v0.2 if the single-pane experience proves insufficient.

## Credits

- [folke/flash.nvim](https://github.com/folke/flash.nvim) — the original idea.
- [Kristijan/flash-copy.tmux](https://github.com/Kristijan/flash-copy.tmux) — the upstream that solved tmux popup live-search rendering. tmux-flash inherits its core search and rendering pipeline.

## License

MIT (inherited from flash-copy.tmux).
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "docs: rewrite README for tmux-flash jump semantics"
```

---

### Task 16: Update repo CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (in repo root)

- [ ] **Step 1: Replace content**

Replace `CLAUDE.md` with:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git -c user.name="bartopine" -c user.email="bartopine@gmail.com" commit -m "docs: rewrite repo CLAUDE.md for jump semantics"
```

---

## Phase 7 — Final verification

### Task 17: Full CI parity run

**Files:** none

- [ ] **Step 1: Type-check**

```bash
uv run ty check 2>&1 | tail -10
```

Expected: clean.

- [ ] **Step 2: Lint**

```bash
uv run ruff check 2>&1 | tail -10
uv run ruff format --check 2>&1 | tail -10
```

Expected: clean. If `ruff format --check` reports diffs, run `uv run ruff format` and commit as `style: ruff format`.

- [ ] **Step 3: Tests with coverage**

```bash
uv run pytest --cov=src --cov-report=term-missing 2>&1 | tail -30
```

Expected: green. Coverage on `cursor_jump.py` should be 100% (all paths covered by tests).

- [ ] **Step 4: Manual end-to-end smoke test in tmux**

In a real tmux session:

```bash
# In an unrelated pane, generate scrolling content:
for i in $(seq 1 200); do echo "line $i widget alpha bravo charlie"; done

# Reload tmux config so the binding is registered (after first run, just install via TPM):
tmux source-file ~/.config/tmux/tmux.conf
# Or, for dev: directly bind once in the current session:
tmux bind-key s run-shell "$HOME/.config/tmux/plugins/tmux-flash/bin/tmux-flash.py"

# Press <prefix>+s, type "alpha", press the label on a chosen line.
# Verify the pane enters copy-mode with the cursor on the 'a' of "alpha" on that line.
# Repeat with: a unique query (auto-jump), an Esc cancel, and a wrapped-line case.
```

Record observed behavior for each case.

- [ ] **Step 5: If smoke tests pass, no commit needed.**

---

### Task 18: Tag v0.1.0 (local only — do not push)

**Files:** none

- [ ] **Step 1: Tag**

```bash
git tag -a v0.1.0 -m "tmux-flash 0.1.0 — initial cursor-jump release"
git tag --list | head
```

- [ ] **Step 2: Stop here.** Do not push or merge. Report completion to the user. The user will decide when to push `feat/jump-cursor` and `v0.1.0` to `origin`, when to merge to `main`, and when to switch their `tmux.conf` to install via TPM.

---

## Self-review notes

- All spec requirements covered: cursor-jump action (Tasks 1–2), copy IPC switch (Tasks 3–9), file/option rename (Tasks 10–11), smart-case (Task 12), Colemak-DH labels (Task 13), metadata + docs (Tasks 14–16), verification (Task 17).
- No placeholders: every code change shows the exact code; every command shows expected output direction.
- Type/name consistency: `FlashConfig` (renamed from `FlashCopyConfig`), `load_all_flash_config`, `cursor_jump.jump_to(pane_id, line, col)`, IPC payload format `"line:col"`, buffer name `__tmux_flash_result_<pane_id>__`, default labels `"srtnaeoigmwfpluycdvkhxzbjq"`, smart-case states `"on"`/`"case-sensitive"`/`"case-insensitive"`.
- Out-of-scope deferred per spec: cross-pane, scrollback, action-plugin system. None of those have tasks here.
