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
