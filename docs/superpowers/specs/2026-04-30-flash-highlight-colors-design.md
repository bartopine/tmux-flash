# tmux-flash highlight & label colors

Make matched-character highlights and jump-letter labels render as colored backgrounds behind the original text, so syntax-highlighted pane content shows through tinted bands instead of being overwritten with default foreground.

## Motivation

Current defaults set foreground color only (`\033[1;33m` for highlight, `\033[1;32m` for labels), which makes highlights blend into surrounding text. flash.nvim-style backgrounds make targets instantly scannable. The user wants a "transparent orange" band behind currently-typed match characters and a "transparent green" band behind the jump-letter labels.

## Design

### Defaults (`src/config.py`)

- `highlight_colour = "\033[48;5;208m\033[1m"` — 256-color orange bg + bold, no foreground
- `label_colour = "\033[48;5;142m\033[1m"` — 256-color olive-green bg + bold, no foreground

256-color codes (208, 142) adapt to the terminal's palette so the colors stay theme-consistent under Gruvbox.

### Rendering (`bin/tmux-flash-interactive.py`)

The dim-non-matches mode replaces every `RESET` in matched lines with `RESET + DIM`, so any text segment we splice in inherits the dim attribute. To paint only a background while preserving the text's original foreground:

- **Highlight (line 367):** replace
  ```python
  f"{AnsiStyles.RESET}{self.config.highlight_colour}{plain_matched_part}{AnsiStyles.RESET}"
  ```
  with
  ```python
  f"\033[22m{self.config.highlight_colour}{plain_matched_part}{AnsiStyles.RESET}"
  ```
  `\033[22m` clears `bold`/`dim` without touching foreground color.

- **Label (lines 338, 347):** prepend `\033[22m` to the existing `f"{self.config.label_colour}{match.label}{AnsiStyles.RESET}"`, becoming `f"\033[22m{self.config.label_colour}{match.label}{AnsiStyles.RESET}"`. Labels are spliced into the same dimmed line as highlights, so they inherit dim too.

### Why bg-only escapes work

Setting only `\033[48;5;Nm` (background) leaves the foreground unchanged. Combined with `\033[22m` to clear dim/bold from the surrounding dimmed context, the matched/labeled text renders in its original syntax-highlighted color on top of a colored background band — the closest ANSI equivalent of "transparent overlay."

## Out of scope

- Truecolor (`\033[48;2;R;G;Bm`) variants — 256-color is sufficient and more portable
- Per-mode color schemes (e.g., different colors when reverse-search is on)
- Configurable bg-only vs full-replacement modes — users who want the old behavior can override `@flash-highlight-colour` / `@flash-label-colour` directly

## Tests

No assertions in the existing test suite check the default values of `highlight_colour` / `label_colour` or the exact format of the rendered highlight string, so no test changes are required. Manual verification in a live tmux session confirms the visual.
