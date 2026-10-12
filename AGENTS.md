# Mini Claude: notes for coding agents

A floating desktop pet for Windows, written as one Python file with Tkinter. It talks with Claude through the Claude Code CLI.

## Setup

- Windows 10 or 11.
- Python 3.11+ with Tkinter (tested on 3.12). No other packages: keep it that way.
- Claude Code installed and signed in (`claude` on PATH, or `~\.local\bin\claude.exe`).
- Run: `pythonw pet.pyw` (no console) or `python pet.pyw` (shows errors).
- Start at sign-in: see [START-AT-SIGN-IN.md](START-AT-SIGN-IN.md).

## File structure

| Path | What it is |
|---|---|
| `pet.pyw` | The whole program |
| `README.md` | For users: setup, commands, privacy, behavior |
| `ACTIONS.md` | Every action, activity, mood and reaction, with pictures |
| `docs/actions/*.png` | Those pictures, rendered from the pet's own drawing code |
| `pet-memory.example.md` | Template of the memory file format |
| `START-AT-SIGN-IN.md` | How to launch it when Windows starts |
| `LICENSE` | MIT |
| `state.json` | Made at run time: chat history, settings, counters. Personal, git-ignored |
| `pet-memory.md`, `pet-memory.previous.md` | Made at run time: what the pet knows about its person. Personal, git-ignored |
| `exports/` | Chats saved with `/export`. Personal, git-ignored |

## Inside `pet.pyw` (top to bottom)

1. Constants: colors, sizes, models, commands, states, action weights, lines, pixel glyphs, angle tables, prompts.
2. Helpers: screen and window scanning (ctypes), line detection (`LineEye` thread), memory file parsing, `state.json` loading, Claude CLI calls (`ask_claude`, `ask_big_claude_to_update`).
3. `class Pet`: chat and slash commands, menu, size, play on edges and game mode physics, states and circles, `random_action`, `update_view` (angles), `tick` (30 fps loop), drawing (`draw`, `draw_body`, `draw_prop`, `draw_lake`, `eye`, `draw_bubble`).

## Rules

- **No personal data in code or docs.** Anything about a person belongs in `pet-memory.md`, which is never committed.
- **Talking:** `claude -p` with `--safe-mode`, no tools, no MCP, no session saved. `/update` may use only Read, Glob and Grep.
- **Nothing leaves the computer** except what is sent to Claude. Screen pixels, window titles and idle time stay in memory.
- **Draw with rectangles, not fonts,** for anything on the transparent background; font edges show a dark rim against the transparent color key.
- **Window size changes** hide the window for a moment (`-alpha 0`), because a grown layered window is black until it is repainted.
- **Keep `README.md` and `ACTIONS.md` in sync** with behavior changes. Re-render the pictures if poses change.

## Testing

There is no test suite. Only one pet can run at a time (a named mutex, `already_running()`), so a test that runs while a pet is open must replace `if already_running():` with `if False:`. Tests load `pet.pyw` with `root.mainloop()` replaced by test code and `STATE_FILE` pointed at a throwaway file, then drive the pet directly (`pet.tick()`, `pet.update_view()`, `pet.draw()`). For pictures, swap `pet.c` for a fake canvas that records rectangles and lines, and rasterize them; this works even when the screen is locked. Never write test files into the real `state.json`.
