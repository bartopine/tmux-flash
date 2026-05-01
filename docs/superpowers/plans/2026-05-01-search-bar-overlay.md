# Search Bar Overlay Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the 1-line viewport shift when the tmux-flash search bar appears by rendering all content lines and overlaying the search bar with absolute cursor positioning.

**Architecture:** Remove scrolling regions entirely. Render all N lines of pane content (filling the popup identically to the underlying pane), then use `\033[{row};1H` to position the cursor on the target line and overwrite it with the search bar.

**Tech Stack:** Python 3.9+, ANSI escape sequences, tmux display-popup

---

### Task 1: Remove scrolling regions and render all N lines with overlay

**Files:**
- Modify: `bin/tmux-flash-interactive.py:182-186` (delete `_reset_terminal`)
- Modify: `bin/tmux-flash-interactive.py:419-502` (rewrite `_display_content`)
- Modify: `bin/tmux-flash-interactive.py:626-630` (remove `_reset_terminal()` call in `finally` block)

- [ ] **Step 1: Delete the `_reset_terminal` method (lines 182-186)**

Remove this method entirely:

```python
    def _reset_terminal(self):
        """Reset terminal state (scrolling region, etc.)."""
        # Reset scrolling region to full screen (ANSI: \033[r)
        sys.stderr.write("\033[r")
        sys.stderr.flush()
```

- [ ] **Step 2: Remove the `_reset_terminal()` call in the `finally` block of `run()` (line 628)**

Change:

```python
        finally:
            # Reset terminal state (scrolling region)
            self._reset_terminal()
            # Clean up terminal
            self._clear_screen()
```

To:

```python
        finally:
            self._clear_screen()
```

- [ ] **Step 3: Rewrite `_display_content` to use absolute positioning instead of scrolling regions**

Replace the entire `_display_content` method with:

```python
    def _display_content(self):
        """Display the pane content with visual distinction for matches."""
        self._clear_screen()

        # Strip trailing newline to avoid empty line at end (tmux capture-pane adds one)
        lines = self.pane_content.rstrip("\n").split("\n")
        lines_plain = self.pane_content_plain.rstrip("\n").split("\n")

        # Get popup dimensions
        try:
            popup_height = shutil.get_terminal_size().lines
        except OSError:
            popup_height = 40

        # Render all lines up to popup_height (fills the popup identically to the pane)
        available_height = popup_height

        # Trim lines to fit popup
        if len(lines) > available_height:
            lines = lines[:available_height]
            lines_plain = lines_plain[:available_height]

        # Display all pane content lines
        self._display_pane_content(lines, lines_plain, available_height)

        # Build the search bar
        search_output = self._build_search_bar_output()

        if self.config.prompt_position == "top":
            # Overwrite line 1 with search bar
            sys.stderr.write("\033[1;1H")
            sys.stderr.write(search_output)
            # Position cursor after prompt + query
            cursor_col = len(self.config.prompt_indicator) + 2
            if self.search_query:
                cursor_col += len(self.search_query)
            sys.stderr.write(f"\033[1;{cursor_col}H")
        else:
            # Overwrite last line with search bar
            sys.stderr.write(f"\033[{popup_height};1H")
            sys.stderr.write(search_output)
            # Position cursor after prompt + query on that line
            cursor_col = len(self.config.prompt_indicator) + 2
            if self.search_query:
                cursor_col += len(self.search_query)
            sys.stderr.write(f"\033[{popup_height};{cursor_col}H")

        sys.stderr.flush()
```

- [ ] **Step 4: Run existing tests to verify nothing is broken**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS (no tests directly depend on scrolling region behavior)

- [ ] **Step 5: Run linting and type-check**

Run: `uv run ruff check && uv run ruff format --check`
Expected: PASS (no lint or format errors)

- [ ] **Step 6: Manual verification**

1. Open tmux with status bar ON (`tmux set -g status on`)
2. Press `prefix + s` to trigger flash
3. Verify: content lines are perfectly aligned with the pane beneath (no shift)
4. Verify: search bar overlays the last line
5. Verify: tmux status bar remains visible
6. Type a query, verify highlights appear and labels work
7. Press Escape, verify clean exit
8. Repeat with status bar OFF

- [ ] **Step 7: Commit**

```bash
git add bin/tmux-flash-interactive.py
git commit -m "fix: render all content lines and overlay search bar with absolute positioning

Remove scrolling regions that caused a 1-line viewport shift. Now all N
lines are rendered to fill the popup, and the search bar overwrites the
target line (last for bottom prompt, first for top prompt) using absolute
cursor positioning."
```
