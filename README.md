# Mini Claude

A tiny pixel Claude that lives on your desktop. It floats, climbs your windows, plays piano, goes fishing, and really talks with Claude through Claude Code.

<p>
<img src="docs/actions/laptop-45.png" width="150"> <img src="docs/actions/piano-45.png" width="150"> <img src="docs/actions/fishing.png" width="150"> <img src="docs/actions/read-side.png" width="150"> <img src="docs/actions/mood-love.png" width="150">
</p>

An unofficial fan project, not made or endorsed by Anthropic. "Claude" is a trademark of Anthropic.

- **Everything it does,** with pictures: [ACTIONS.md](ACTIONS.md).

## What you need

- Windows 10 or 11.
- Python 3.11 or newer, with Tkinter (the standard python.org installer includes it). Tested on Python 3.12.
- Claude Code (the `claude` command) installed and signed in. Run `claude` once in a terminal to sign in.
- No other packages.

## Start

1. Download this folder.
2. Double-click `pet.pyw`, or run `pythonw pet.pyw`.
3. It appears at the bottom right of your screen and says hello.

- **Start when you sign in (optional):** see [START-AT-SIGN-IN.md](START-AT-SIGN-IN.md).
- **Close it:** right-click → "Bye", or type `/exit`.

## Use it

- **Talk:** double-click the pet. A cursor floats under it. Type and press Enter. Click elsewhere or press Esc to close it. A reply takes 1–3 seconds on Haiku: Claude Code starts in the background when you open the chat, so it is ready when you press Enter. Opus and Sonnet take a little longer.
- **Long replies:** click the bubble to see the next part.
- **Pet it:** click it. It reacts only now and then, as a little surprise.
- **Move it:** drag it.
- **Menu:** right-click it. You can change the size, state, float or play on edges, start game mode, and more.
- **Commands:** type `/` to see floating suggestions. Tab or Enter picks one, the arrow keys move. Start a message with `#` to make it remember something.

| Command | What it does |
|---|---|
| `/model` | Switch brain: opus (default), sonnet, haiku, fable |
| `/effort` | auto, low, medium, high, xhigh, max |
| `/fast` | Fast mode on/off, Opus only (needs extra usage on your account) |
| `/clear` (`/new`) | New chat; the old one is kept for `/resume` |
| `/resume` | Pick one of the last 10 chats |
| `/rewind` (`/undo`) | Take back the last exchange |
| `/compact` | Squeeze the chat into a short summary |
| `/btw` | Side question, not saved in the chat |
| `/copy` | Copy the last reply |
| `/export` | Save the chat as a .md file in `exports/` |
| `/memory` | Show notes; `/memory clear` forgets them; `# text` adds one |
| `/workspace` | Choose the notes folder big Claude reads for `/update` |
| `/update` | Ask big Claude to refresh what the pet knows about you |
| `/context` | What it carries with each message |
| `/usage` (`/cost`) | Replies, average wait, list-price value |
| `/status` | Model, effort, fast mode, energy, pets |
| `/doctor` | Check the Claude Code connection |
| `/state` | Preview Lively, Calm or Sleepy for about 5 minutes |
| `/play`, `/float` | Play on window edges, or float freely |
| `/lines` | Climb lines inside apps on or off |
| `/game` | Game mode: control it with the keyboard |
| `/still`, `/wander` | Stay in one place, or move around |
| `/say`, `/pet`, `/hum`, `/dance`, `/sleep`, `/wake` | Pet things |
| `/help`, `/exit` (`/bye`) | Help; close the pet |

## Teach it about you

The program itself holds no personal details. What the pet knows about you lives in `pet-memory.md` next to `pet.pyw`: your name, a few notes, dates to count down to, things to say, thoughts, and reactions to apps you use. There are two ways to make that file.

- **Let big Claude write it (recommended).**
  1. Type `/workspace` and choose a folder with notes about you, for example a folder you already use with Claude Code.
  2. Type `/update`. Claude Code runs in that folder with read-only tools (Read, Glob, Grep), reads your notes, and writes the memory file. The old version is kept as `pet-memory.previous.md`.
  - It refreshes itself once a day when the file is over 2 days old.
- **Write it yourself.** Copy `pet-memory.example.md` to `pet-memory.md` and edit it.

The pet rereads the file whenever it changes. Text after `<!--` on a line is a hidden note that the pet never shows.

## Privacy: what leaves your computer

- **Sent to Claude (through Claude Code) when you talk:** your message, the last 12 chat lines, the chat summary, your `#` notes, and the notes and dates from `pet-memory.md`.
- **Sent when you use `/update`:** big Claude reads files in the folder you chose with `/workspace`, so what it reads goes to Claude.
- **Never sent anywhere:**
  - Screen pixels. Twice a second it looks at the screen around itself to find lines to climb. The pixels stay in memory only and are never saved.
  - Window titles. It checks the title of the active window to react to apps it knows.
  - How long the computer has been idle. It uses this to know when no one is there.
  - Keys. In game mode it reads the keyboard only while its own window has focus.
- **Stored on your computer:** `state.json` (chat history, settings, counters), `pet-memory.md`, and chat exports in `exports/`.

## Cost and models

Every message is one Claude Code call, so it counts toward your Claude plan's usage, like any other Claude Code use. `/model haiku` or `/effort low` make replies lighter. Fast mode needs extra usage enabled on your account, and some models (such as Fable) may need usage credits.

## Play on edges and float

- **They take turns by themselves:** about 4 minutes of each, an 8-minute circle. It switches only at a free moment: not mid-air, climbing, asleep, busy, being dragged or talking.
- **Pick one now:** right-click → "Float freely" / "Play on edges", or `/float` and `/play`. Your pick lasts about 4 minutes, then the circle carries on.
- **Float:** it drifts anywhere on the screen.
- **Play on edges:**
  - It stands on the taskbar and on the visible top edges of windows, walks along them and jumps between them.
  - It climbs the screen sides, window sides that reach down to it, and long vertical lines inside apps. It hangs on a wall, then climbs down or jumps off.
  - It rides a window when you move it, and falls when its edge is covered, closed or maximized.
  - It also stands on long horizontal lines inside apps: table rules, borders, dividers, the edges of images. It falls when a line disappears, for example when you scroll. Turn this off with right-click → "Ignore lines in apps", or `/lines`.
  - If you drop it, it falls. A fall of more than 300 px (at Normal size) makes it dizzy.

## Game mode

Start it with right-click → "Game mode" or `/game`. Stop it with Esc.

| Key | What it does |
|---|---|
| A / D (or ← →) | Walk; walking off an edge makes it fall |
| Double-tap A / D, then hold | Run, twice as fast |
| W / S (or ↑ ↓) | Climb up or down when next to a wall or vertical line; at the top it steps onto the ledge |
| A / D away from the wall while climbing | Let go: drop and move that way |
| Double-tap W, then hold | Climb up twice as fast |
| Space | Jump; when climbing, jump off the wall |
| W + Space | High jump, about twice as high |
| Hold Space | Float down slowly for up to 2.5 seconds |
| S + Space | Drop through the line it's standing on |

- It only listens while its own window has the keyboard, so typing in other apps never moves it.
- Clicking elsewhere pauses the game. Click the pet to go on.
- When you stop, it keeps its final pose, still looking the way it last moved.
- After 5 seconds without a key, the game ends and it plays by itself again.

## States: Lively, Calm, Sleepy

It always runs on a 15-minute circle: Lively, Calm and Sleepy, 5 minutes each, in a random order, never the same state twice in a row. The time left is never shown. Its first state depends on the time of day, with chance mixed in.

| State | Pace | Time between actions | Favorite things | Sleeps? |
|---|---|---|---|---|
| Lively | 1.35× | 3–8 s | wandering, leaping, climbing, dancing, workouts, piano, selfies | no |
| Calm | 1× | 5–11 s | laptop work, reading, humming, thinking, fishing, tea, meditating | no |
| Sleepy | 0.8× | 8–18 s | yawning, tea, stargazing, sitting, meditating | yes, after 90 s left alone; often half-wakes |

- **Preview a state:** right-click → "State: …", or `/state`. It switches now for about 5 minutes, then the circle carries on.
- `/sleep` is a short nap of 2 to 4 minutes in any state.

## Angles

- **Five views:** front, 45°, side (90°), back three-quarter and back. Facing left is a mirror image. It turns one step at a time.
- **Moving, climbing, falling and being dragged** always use the front view.
- **Whole scenes turn:** laptop work, reading and piano are drawn as a whole scene from the front, at 45° (the laptop on a little desk beside it, the piano beside it with its keys running off to the back) or from the side.
- **No side view while it's still or floating:** then it turns 45° at most. The side view only shows inside an activity scene or a dance spin.
- **Small signs of life:** it breathes, sometimes blinks twice, glances around, and looks toward your cursor.
- More details per activity are in [ACTIONS.md](ACTIONS.md).

## When no one is there

After 2 minutes without keyboard or mouse input, it switches between staying still and wandering by itself every few minutes. When you're back, your own choice ("Stay still" or "Wander") returns.

## Files

| File | What it is |
|---|---|
| `pet.pyw` | The whole program |
| `ACTIONS.md`, `docs/actions/` | Overview of everything it does, with pictures |
| `pet-memory.example.md` | A template for what the pet knows about you |
| `START-AT-SIGN-IN.md` | How to start it when you sign in to Windows |
| `AGENTS.md` | Setup and structure notes for coding agents |
| `state.json` | Made on first run: chat history, settings, counters. Stays on your computer |
| `pet-memory.md`, `pet-memory.previous.md` | What it knows about you, and the version before the last update |
| `exports/` | Chats you saved with `/export` |

## Troubleshooting

- **It doesn't answer:** type `/doctor`. Check that `claude` works in a terminal and that you're signed in.
- **"I can't find Claude Code":** install Claude Code, or make sure `claude` is on your PATH (it also looks in `~\.local\bin`).
- **Something covers it:** it puts itself back on top of other always-on-top apps every second. Only the Start menu, Windows pop-ups and full-screen games can still cover it.
- **Fast mode turns itself off:** your account needs extra usage enabled for fast mode.
- **It sits on something that isn't a real line:** with "lines in apps" on, it can mistake the edge of an image or video for a line. That's part of the fun; turn it off with `/lines` if you prefer.

## License

MIT. See [LICENSE](LICENSE).
