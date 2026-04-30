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
