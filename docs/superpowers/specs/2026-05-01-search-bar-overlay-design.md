# Search Bar Overlay Fix

## Problem

When tmux-flash triggers, the search bar at the bottom of the popup causes the viewport content to shift up by 1 line. The user sees a visible jump — lines that were at specific positions in the pane appear 1 row higher in the popup. Additionally, the popup can cover the tmux status bar.

Root cause: the current implementation uses terminal scrolling regions (`\033[1;{N}r`) to "protect" the search bar line, and renders N-1 content lines in the remaining space. The scrolling region interacts poorly with clear-screen and causes the 1-line shift.

## Solution

Render all N content lines (matching the pane exactly), then overwrite the search bar's target line using absolute cursor positioning. No scrolling regions.

## Changes to `bin/tmux-flash-interactive.py`

### `_display_content()` method

1. Set `available_height = popup_height` (full popup height, no reservation).
2. Print all N content lines — the popup is now pixel-identical to the underlying pane.
3. Use absolute cursor positioning to place the search bar:
   - **Bottom prompt:** `\033[{popup_height};1H` then write search bar (overwrites last content line).
   - **Top prompt:** `\033[1;1H` then write search bar (overwrites first content line).
4. Position the text cursor after the prompt indicator + query text for visual feedback.
5. Remove all scrolling region escape sequences (`\033[{start};{end}r`).

### `_reset_terminal()` method

Remove entirely — no scrolling region means nothing to reset.

### `_display_pane_content()` method

No changes to internal logic. It receives the full line count and renders all lines.

### Refresh cycle

On each keystroke:
1. `_clear_screen()` (unchanged: `\033[2J\033[H`)
2. Print all N lines via `_display_pane_content()`
3. Absolute-position to prompt line
4. Write search bar

### Top prompt variant

Same approach but overwrite line 1 instead of line N. Content lines 2..N remain aligned with pane lines 2..N; pane line 1 is hidden behind the search bar.

## Popup positioning (status bar fix)

The `_get_status_top_offset()` helper in `src/utils.py` (already implemented) offsets the popup y-coordinate by 1 when the tmux status bar is active and at the top. This prevents the popup from covering the status bar. No further changes needed here.

## Testing

- Existing unit tests for `_build_search_bar_output`, `_display_line_with_matches`, and popup positioning remain valid.
- Manual verification: trigger flash with status bar on/off, confirm no content shift and status bar visibility.

## Scope

- Only `bin/tmux-flash-interactive.py` changes (rendering logic).
- `src/utils.py` popup positioning already fixed in prior commit.
- No config changes, no new options.
