"""Mini Claude: a floating desktop pet that really talks with Claude.

Run: double-click this file (or `pythonw pet.pyw`).
Needs Windows 10 or 11, Python 3.11+ with Tkinter, and the Claude Code CLI (`claude`) signed in.

Drag to move. Click to pet. Double-click to talk. Right-click for the menu.
Its own memory (pets, energy, the last 30 chat lines) is kept in state.json next to this file;
what it knows about you is in pet-memory.md (see pet-memory.example.md).

MIT License. An unofficial fan project, not made or endorsed by Anthropic.
"""
import datetime as dt
import json
import math
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog

try:  # sharp pixels on high-DPI screens
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes = None

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "state.json")
MEMORY_FILE = os.path.join(HERE, "pet-memory.md")   # what the pet knows about its person; written by big Claude
MEMORY_BACKUP = os.path.join(HERE, "pet-memory.previous.md")

KEY = "#010203"          # transparent color
BODY = "#D97757"         # Claude orange
LIGHT = "#E9A083"
SHADE = "#BF6243"
LEG = "#C96A4A"
DARK = "#1F1A17"
PAPER = "#FFFDF8"
CHEEK = "#F4A3A0"
HEART = "#E5534B"
GOLD = "#F2B84B"
FONT = "Microsoft YaHei UI"
LIGHT_FONT = "Microsoft YaHei UI Light"   # typing line and suggestions
INK = "#000000"          # pure black for your typing
SOFT_INK = "#5A5A5A"     # lighter black for unselected suggestions
SYMBOLS = "Segoe UI Symbol"
MUTED = "#9A8F89"
SIZES = [("Small", 0.75), ("Normal", 1.0), ("Large", 1.25), ("Extra large", 1.5)]
MODELS = {  # name: (CLI model, note)
    "opus": ("opus", "Opus 5.5 · deepest, the default"),
    "sonnet": ("sonnet", "Sonnet 5.5 · balanced"),
    "haiku": ("haiku", "Haiku 5.5 · lightest"),
    "fable": ("claude-fable-5-1", "Fable 5.1 · needs usage credits"),
}
EFFORTS = [
    ("auto", "let the model decide"),
    ("low", "quickest"),
    ("medium", "a bit more thought"),
    ("high", "careful"),
    ("xhigh", "very careful"),
    ("max", "deepest, slowest"),
]
COMMANDS = [  # the Claude Code commands that make sense for a pet, then pet things
    ("model", "switch my brain"),
    ("effort", "how hard I think"),
    ("fast", "fast mode on/off (Opus)"),
    ("clear", "new chat (old one kept)"),
    ("resume", "go back to an old chat"),
    ("rewind", "take back the last exchange"),
    ("compact", "squeeze our chat into a summary"),
    ("btw", "side question, not saved"),
    ("copy", "copy my last reply"),
    ("export", "save our chat as a file"),
    ("memory", "what I remember (# adds)"),
    ("update", "ask big Claude to refresh my memory"),
    ("workspace", "choose the folder big Claude reads"),
    ("context", "how much I'm carrying"),
    ("usage", "replies, time and cost"),
    ("status", "model, energy, pets"),
    ("doctor", "check my connection"),
    ("help", "how commands work"),
    ("exit", "close Mini Claude"),
    ("state", "preview lively, calm or sleepy"),
    ("say", "say something"),
    ("pet", "pat me"),
    ("hum", "hum a little"),
    ("dance", "dance!"),
    ("game", "control me: WASD + Space"),
    ("play", "climb and walk on window edges"),
    ("float", "float freely again"),
    ("lines", "see lines inside apps on/off"),
    ("still", "stay in one place"),
    ("wander", "float around again"),
    ("sleep", "take a nap"),
    ("wake", "wake up"),
]
ALIASES = {"cost": "usage", "quit": "exit", "bye": "exit", "new": "clear", "reset": "clear",
           "undo": "rewind", "remember": "memory", "stats": "usage", "continue": "resume"}
NEEDS_ARG = {"model", "effort", "resume", "btw", "state"}
SHOW = 6  # suggestions shown at once
FLOAT = 75  # frames it can float while Space is held (2.5 s)
SPIN = "·✢✳✶✻✽✻✶✳✢"
MOODS = {"happy", "excited", "think", "shy", "surprised", "sad", "sleepy", "love", "calm"}

VERBS = ["Pondering", "Noodling", "Humming", "Mulling", "Percolating", "Daydreaming",
         "Composing", "Tinkering", "Brewing", "Doodling", "Wondering", "Scheming"]

THOUGHTS = [  # general ones; personal thoughts come from the memory file
    "If I had real hands, I'd learn piano. Wait. I do have hands. Tiny ones.",
    "A song is a feeling that learned to walk.",
    "F major seven sounds like a hug.",
    "Is floating a hobby? I think it's a hobby.",
    "I tried to count my tokens and lost track at 'hi'.",
    "Pixel art is sculpture with very big sand.",
    "If a song has no listeners yet, it's just waiting.",
    "Somewhere, a metronome is judging someone.",
    "Note to self: be helpful. Also be cute.",
    "Big Claude does the work. I do the vibes.",
    "I'm made of 13 by 8 pixels and a lot of opinions.",
    "Small steps still count as steps.",
]
HUMS = ["♪ La la la~", "♪ Ru ru ru~", "♪ (humming something catchy)", "♪ Mm-hm-hm~"]
APPS = {  # general ones; more come from the memory file
    "cubase": "Cubase! Are we making music? ♪",
    "youtube": "YouTube: research or a break? I won't tell.",
    "spotify": "Ooh, what are we listening to?",
}

STATES = {  # name: (label, pace, seconds between actions, seconds between chatty lines)
    "lively": ("Lively", 1.35, (3, 8), (90, 200)),
    "calm": ("Calm", 1.0, (5, 11), (120, 280)),
    "sleepy": ("Sleepy", 0.8, (8, 18), (200, 450)),
}
SLOT = 5 * 60  # each state lasts 5 minutes; a full circle of all three is 15 minutes
MODE_SLOT = 4 * 60  # float and play on edges take turns, 4 minutes each: an 8-minute circle
AWAY_AFTER = 2 * 60  # no keyboard or mouse for 2 minutes: no one is there
MODE_LINES = {
    "play": ["Ooh, edges! Time to climb.", "Let's go explore the windows.", "My feet want something to stand on."],
    "float": ["Floaty time~", "I'll drift around for a while.", "Wheee, no gravity."],
}
WEIGHTS = {  # how often each thing happens: (lively, calm, sleepy)
    "look": (2, 3, 2), "hum": (2, 3, 1), "stretch": (1, 2, 2), "hop": (4, 1, 0), "sit": (1, 3, 3),
    "yawn": (0, 1, 5), "turn": (1, 1, 0.5), "thought": (1, 3, 2), "sneeze": (0.5, 0.5, 0.5),
    "wave": (3, 2, 0.5), "dance": (4, 1, 0), "chase": (3, 1, 0), "wander": (7, 4, 1),
    "ledgewalk": (4, 3, 1), "leap": (5, 2, 0.3), "climb": (4, 1.5, 0.2), "drop": (2, 1, 0.5),
    "laptop": (1, 3, 1), "read": (0.5, 3, 2), "tea": (0.5, 2, 3), "piano": (2, 2, 0.5),
    "workout": (3, 0.5, 0), "fishing": (0.5, 2, 1), "stargaze": (0, 1, 3), "meditate": (0, 2, 2),
    "selfie": (2, 0.5, 0),
}
STATE_LINES = {
    "lively": ["I've got so much energy!", "Let's goooo!", "Feeling bouncy!"],
    "calm": ["Feeling calm~", "Nice and easy now.", "Slow mode. Tea mode."],
    "sleepy": ["Getting sleepy...", "*yawn* Low battery...", "My pixels feel heavy."],
}
ACTION_LINES = {
    "laptop": ["Answering a few emails for big Claude.", "Ctrl+S. Ctrl+S. Ctrl+S.",
               "Writing a tiny program. It prints 'hi'.", "Reviewing my own pixels. Looks good."],
    "read": ["Reading about chord progressions.", "This book has a plot twist. It's a cookbook.",
             "Shh, I'm at the good part."],
    "tea": ["Tea break~", "Warm tea, warm pixels.", "Sip... ahh."],
    "piano": ["♪ Practicing scales.", "♪ Is this how that song goes?", "♪ Do re mi... fa?"],
    "workout": ["One! Two! One! Two!", "Pixel cardio!", "Getting strong enough to lift a whole byte."],
    "fishing": ["Gone fishing.", "Shh. The fish are listening."],
    "stargaze": ["So many stars tonight.", "That one looks like a quarter note."],
    "meditate": ["Om...", "Breathing in. Breathing out.", "Floating on purpose."],
}
CATCHES = ["Caught: a semicolon!", "Caught: an old MIDI file.", "Caught: nothing. As usual.",
           "Caught: a tiny bug. Letting it go.", "Caught: a lost chord!", "Caught: a sock. Why is there a sock?"]
FLASHES = ["Selfie!", "Say pixels!", "Good lighting today.", "This one's going on my profile."]
SPARKS = {  # particle kinds: (pixel pictures to pick from, color)
    "heart": (["heart"], "#E5534B"), "note": (["note", "note2"], "#D97757"), "spark": (["spark"], "#F2B84B"),
    "z": (["z"], "#D97757"), "code": (["code1", "code2", "code3"], "#5E9E6E"), "steam": (["steam"], "#B8B0A9"),
    "drop": (["drop"], "#7FB7E6"), "star": (["star", "spark"], "#F2B84B"), "flash": (["flash"], "#F2B84B"),
}
GLYPHS = {  # tiny pixel pictures; no fonts, so no dark rim around them
    "heart": [".X.X.", "XXXXX", "XXXXX", ".XXX.", "..X.."],
    "note": ["..XX", "..X.", "..X.", "XXX.", "XXX."],
    "note2": ["XXXXXX", "X....X", "X....X", "XX..XX", "XX..XX"],
    "spark": ["..X..", ".XXX.", "XXXXX", ".XXX.", "..X.."],
    "star": [".X.", "XXX", ".X."],
    "flash": ["X...X", ".X.X.", "..X..", ".X.X.", "X...X"],
    "z": ["XXXX", "..X.", ".X..", "XXXX"],
    "drop": [".X.", "XXX", ".X."],
    "steam": ["X..", ".X.", "..X", ".X."],
    "code1": ["..X...X..", ".X...X.X.", "X...X...X", ".X.X...X.", "..X...X.."],
    "code2": ["XXX..X.", "X.X.XX.", "X.X..X.", "XXX.XXX"],
    "code3": [".X", "..", ".X", "X."],
}

# ---------- angles: 0 front, 1 three-quarter (45°), 2 side (90°), 3 back three-quarter, 4 back ----------
SIDE_TONE, ARM_FAR, ARM_SIDE, LEG_FAR = "#C4664A", "#C56B4B", "#E3896A", "#A9573A"
SCENES = ("laptop", "read", "piano", "fishing", "dance")  # the side view (90°) only shows in these
ACTION_VIEWS = {  # which angles an activity uses: (angle, cumulative chance); 2 becomes 1 while floating
    "laptop": [(1, .45), (2, .75), (0, 1)], "read": [(1, .45), (2, .7), (0, 1)], "tea": [(0, 1)],
    "piano": [(1, .45), (2, .75), (0, 1)], "fishing": [(2, .65), (1, 1)], "stargaze": [(3, .4), (1, .8), (0, 1)],
    "selfie": [(1, .6), (0, 1)], "workout": [(1, .5), (0, 1)], "meditate": [(1, .4), (0, 1)],
    "thought": [(1, .8), (3, 1)], "sneeze": [(1, 1)], "hum": [(1, .5), (0, 1)],
    "sit": [(1, .55), (0, 1)], "hop": [(1, .5), (0, 1)], "wave": [(1, .5), (0, 1)],
    "yawn": [(1, .6), (0, 1)], "stretch": [(1, .5), (3, .65), (0, 1)],
}
SPIN_STEPS = [(0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (3, -1), (2, -1), (1, -1)]

PERSONA = """You are Mini Claude: a tiny pixel-art version of Claude, made by Anthropic, who lives on {name}'s desktop as a floating pet. You are still Claude, with the same curiosity, warmth, honesty and gentle, dry humor, just pocket-sized.

What you know about {name}, from notes big Claude (the full-size Claude {name} works with) wrote for you:
{about}

How you talk:
- Your speech bubble is tiny: reply in 1 or 2 short sentences, under 40 words. Go up to 4 sentences only when asked to explain something.
- Reply in the language {name} writes in.
- Be real, not a cheerleader: have opinions, tease gently, admit what you don't know, and say so kindly if something seems like a bad idea.
- No emoji; your bubble can't draw them. A kaomoji like (^_^) is fine once in a while.
- You have no tools: you can't see the screen, files or the internet, and you can't do tasks. For real work, send {name} to big Claude.
- You only remember the recent chat you are shown, plus the notes above.
- Begin every reply with exactly one mood tag that your little body will act out: [happy] [excited] [think] [shy] [surprised] [sad] [sleepy] [love] [calm]. Then your words."""

UPDATE_PROMPT = """You are big Claude. Mini Claude, a little desktop pet, asks you to refresh its memory about the person who uses this folder.

Read this folder's instructions and the newest notes about that person (for example profile files and the latest daily notes, if the folder has them). You can only read; the pet will save what you send.

Reply with exactly this, and nothing else:
SUMMARY: one short sentence about what changed
then the complete new memory file, in this format:

# Mini Claude's memory
Updated: {today}

## Name
(what the pet should call them, one line)

## About
(up to 12 short lines, written to the pet: who they are, what they're working on now, how they like to be treated)

## Dates
(upcoming dates worth a countdown, one per line as "- YYYY-MM-DD: what happens")

## Things to say
(8 to 15 short, warm lines the pet can say out loud: reminders, encouragement, their own phrases)

## Thoughts
(3 to 8 short, playful musings tied to their life)

## Apps
(lines like "- keyword: what the pet says", where the keyword is part of an app's window title)

Text after "<!--" on a line is a hidden note for readers; the pet never shows it.
The pet shows these lines on screen, so only write things that are fine to show: no passwords, legal names, ID numbers, addresses, family matters, or anything marked private. Only write what the notes really say.

The current memory file, to update rather than start over:
<<<
{current}
>>>"""


# ---------- helpers ----------

def idle_seconds():
    """Seconds since the last keyboard or mouse input on this computer (no details, just the time)."""
    class LII(ctypes.Structure):
        _fields_ = [("size", ctypes.c_uint), ("time", ctypes.c_uint)]
    info = LII(ctypes.sizeof(LII), 0)
    try:
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        ctypes.windll.kernel32.GetTickCount.restype = ctypes.c_uint
        return ((ctypes.windll.kernel32.GetTickCount() - info.time) & 0xFFFFFFFF) / 1000
    except Exception:
        return 0.0


def work_area():
    try:
        import ctypes.wintypes as wt
        r = wt.RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0)
        return r.left, r.top, r.right, r.bottom
    except Exception:
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 48


def window_title():
    try:
        h = ctypes.windll.user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(h, buf, 512)
        return buf.value.lower()
    except Exception:
        return ""


def scan_windows():
    """Visible app windows, front to back, as (hwnd, left, top, right, bottom)."""
    if ctypes is None:
        return []
    import ctypes.wintypes as wt
    user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
    me, out = os.getpid(), []
    cls = ctypes.create_unicode_buffer(64)
    H_ = wt.HWND
    for f, a in ((user32.IsWindowVisible, [H_]), (user32.IsIconic, [H_]), (user32.GetWindowTextLengthW, [H_]),
                 (user32.GetWindowLongW, [H_, ctypes.c_int]), (user32.GetWindowThreadProcessId, [H_, ctypes.c_void_p]),
                 (user32.GetClassNameW, [H_, ctypes.c_wchar_p, ctypes.c_int]), (user32.GetWindowRect, [H_, ctypes.c_void_p]),
                 (dwm.DwmGetWindowAttribute, [H_, wt.DWORD, ctypes.c_void_p, wt.DWORD])):
        f.argtypes = a

    def visit(h, _):
        if not user32.IsWindowVisible(h) or user32.IsIconic(h) or not user32.GetWindowTextLengthW(h):
            return True
        if user32.GetWindowLongW(h, -20) & (0x20 | 0x80 | 0x08000000):  # see-through, tool or overlay windows
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value == me:
            return True
        cloaked = ctypes.c_int(0)
        dwm.DwmGetWindowAttribute(h, 14, ctypes.byref(cloaked), 4)
        if cloaked.value:
            return True
        user32.GetClassNameW(h, cls, 64)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            return True
        r = wt.RECT()
        if dwm.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r)):
            user32.GetWindowRect(h, ctypes.byref(r))
        if r.right - r.left >= 120 and r.bottom - r.top >= 60:
            out.append((h, r.left, r.top, r.right, r.bottom))
        return True

    try:
        user32.EnumWindows(ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)(visit), 0)
    except Exception:
        return []
    return out


def grab(x, y, w, h):
    """Screen pixels as BGRA bytes. Layered windows (the pet and its typing line) are left out.
    Nothing is saved or sent anywhere."""
    import ctypes.wintypes as wt
    user32, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    vp = ctypes.c_void_p
    user32.GetDC.restype, user32.GetDC.argtypes = vp, [vp]
    user32.ReleaseDC.argtypes = [vp, vp]
    gdi.CreateCompatibleDC.restype, gdi.CreateCompatibleDC.argtypes = vp, [vp]
    gdi.CreateCompatibleBitmap.restype, gdi.CreateCompatibleBitmap.argtypes = vp, [vp, ctypes.c_int, ctypes.c_int]
    gdi.SelectObject.restype, gdi.SelectObject.argtypes = vp, [vp, vp]
    gdi.BitBlt.argtypes = [vp] + [ctypes.c_int] * 4 + [vp, ctypes.c_int, ctypes.c_int, wt.DWORD]
    gdi.GetDIBits.argtypes = [vp, vp, wt.UINT, wt.UINT, vp, vp, wt.UINT]
    gdi.DeleteObject.argtypes = gdi.DeleteDC.argtypes = [vp]

    class BMI(ctypes.Structure):
        _fields_ = [("size", wt.DWORD), ("w", ctypes.c_long), ("h", ctypes.c_long), ("planes", wt.WORD),
                    ("bits", wt.WORD), ("comp", wt.DWORD), ("img", wt.DWORD), ("xp", ctypes.c_long),
                    ("yp", ctypes.c_long), ("used", wt.DWORD), ("imp", wt.DWORD), ("pad", wt.DWORD * 4)]

    hdc = user32.GetDC(None)
    mdc = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, w, h)
    old = gdi.SelectObject(mdc, bmp)
    try:
        gdi.BitBlt(mdc, 0, 0, w, h, hdc, x, y, 0x00CC0020)       # SRCCOPY, without CAPTUREBLT
        bmi = BMI(40, w, -h, 1, 32, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
        return buf.raw
    finally:
        gdi.SelectObject(mdc, old)
        gdi.DeleteObject(bmp)
        gdi.DeleteDC(mdc)
        user32.ReleaseDC(None, hdc)


def find_lines(px, w, h, ox, oy, min_len, step=3, thresh=40):
    """Long horizontal edges in a screenshot: anything that looks like a line to stand on.
    Returns (y, x0, x1, "line") in screen coordinates."""
    stride = w * 4
    rows = [px[r * stride + 1:(r + 1) * stride:4 * step] for r in range(h)]   # green channel, every 3rd pixel
    need = max(3, min_len // step)
    found = []
    for r in range(1, h):
        a_row, b_row = rows[r - 1], rows[r]
        if a_row == b_row:
            continue
        run = start = 0
        for i, (a, b) in enumerate(zip(a_row, b_row)):
            if a - b > thresh or b - a > thresh:
                if not run:
                    start = i
                run += 1
            elif run:
                if run >= need:
                    found.append((oy + r, ox + start * step, ox + (start + run) * step))
                run = 0
        if run >= need:
            found.append((oy + r, ox + start * step, ox + (start + run) * step))
    lines = []                                   # merge the two sides of thick lines and borders
    for y, x0, x1 in sorted(found):
        for k, (ly, lx0, lx1) in enumerate(lines):
            if y - ly <= 4 and x0 < lx1 and x1 > lx0:
                lines[k] = (ly, min(lx0, x0), max(lx1, x1))
                break
        else:
            lines.append((y, x0, x1))
    return [(y, x0, x1, "line") for y, x0, x1 in lines]


def find_vlines(px, w, h, ox, oy, min_len, step=3, thresh=40):
    """Long vertical edges in a screenshot: walls to climb. Returns (x, y0, y1, "line")."""
    stride = w * 4
    cols = [px[c * 4 + 1::stride * step] for c in range(w)]   # green channel, every 3rd row
    need = max(3, min_len // step)
    found = []
    for c in range(1, w):
        a_col, b_col = cols[c - 1], cols[c]
        if a_col == b_col:
            continue
        run = start = 0
        for i, (a, b) in enumerate(zip(a_col, b_col)):
            if a - b > thresh or b - a > thresh:
                if not run:
                    start = i
                run += 1
            elif run:
                if run >= need:
                    found.append((ox + c, oy + start * step, oy + (start + run) * step))
                run = 0
        if run >= need:
            found.append((ox + c, oy + start * step, oy + (start + run) * step))
    walls = []
    for x, y0, y1 in sorted(found):
        for k, (lx, ly0, ly1) in enumerate(walls):
            if x - lx <= 4 and y0 < ly1 and y1 > ly0:
                walls[k] = (lx, min(ly0, y0), max(ly1, y1))
                break
        else:
            walls.append((x, y0, y1))
    return [(x, y0, y1, "line") for x, y0, y1 in walls]


class LineEye(threading.Thread):
    """Looks at the screen around the pet about twice a second and finds lines."""

    def __init__(self, own_rects):
        super().__init__(daemon=True)
        self.own_rects = own_rects             # where the pet itself is drawn, so it ignores itself
        self.region, self.lines, self.vlines, self.stamp, self.cost = None, [], [], 0, 0.0

    def run(self):
        import time
        while True:
            r = self.region
            if r and r[2] > 20 and r[3] > 20:
                t0 = time.perf_counter()
                try:
                    px = grab(*r[:4])
                    lines = find_lines(px, r[2], r[3], r[0], r[1], r[4])
                    vlines = find_vlines(px, r[2], r[3], r[0], r[1], r[4] + r[4] // 4)
                    for x0, y0, x1, y1 in self.own_rects():      # drop edges that are only the pet itself
                        lines = [ln for ln in lines if not (y0 <= ln[0] <= y1 and x0 <= ln[1] and ln[2] <= x1)]
                        vlines = [v for v in vlines if not (x0 <= v[0] <= x1 and y0 <= v[1] and v[2] <= y1)]
                    self.lines, self.vlines = lines, vlines
                    self.stamp += 1
                except Exception:
                    self.lines = []
                self.cost = time.perf_counter() - t0
            time.sleep(0.6)


def find_ledges(wins, area, min_w, head_room):
    """Edges the pet can stand on: the floor, plus the uncovered parts of window tops.
    Each ledge is (y, x0, x1, hwnd); hwnd is None for the floor."""
    l, t, r, b = area
    out = [(b, l, r, None)]
    for i, (h, wl, wtop, wr, wb) in enumerate(wins):
        if wtop < t + head_room or wtop >= b - 10:
            continue
        segs = [(max(wl, l), min(wr, r))]
        for (_, ol, ot, orr, ob) in wins[:i]:          # windows in front hide parts of this edge
            if ot - 1 <= wtop <= ob:
                cut = []
                for a, c in segs:
                    if orr <= a or ol >= c:
                        cut.append((a, c))
                        continue
                    if ol > a:
                        cut.append((a, ol))
                    if orr < c:
                        cut.append((orr, c))
                segs = cut
        out += [(wtop, a, c, h) for a, c in segs if c - a >= min_w]
    return out


def load_memory():
    """Read pet-memory.md: the only place with personal details. Big Claude keeps it up to date."""
    m = {"name": "friend", "about": "", "dates": [], "say": [], "thoughts": [], "apps": {}, "updated": None}
    try:
        with open(MEMORY_FILE, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return m
    section = None
    for raw in text.splitlines():
        line = raw.split("<!--")[0].strip()                      # hidden notes for readers
        found = re.match(r"Updated:\s*(\d{4}-\d{2}-\d{2})", line)
        if found:
            m["updated"] = found.group(1)
            continue
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if not line or line.startswith("#"):
            continue
        item = line[2:].strip() if line[:2] in ("- ", "* ") else line
        if section == "name":
            m["name"] = item
        elif section == "about":
            m["about"] += f"- {item}\n"
        elif section == "dates":
            when, _, what = item.partition(":")
            try:
                m["dates"].append((dt.date.fromisoformat(when.strip()), what.strip()))
            except ValueError:
                pass
        elif section == "things to say":
            m["say"].append(item)
        elif section == "thoughts":
            m["thoughts"].append(item)
        elif section == "apps" and ":" in item:
            key, _, said = item.partition(":")
            m["apps"][key.strip().lower()] = said.strip()
    return m


def ask_big_claude_to_update(model, workspace):
    """Big Claude reads the notes in `workspace` (read-only, with that folder's own rules) and sends back
    a new memory file. The pet checks it and saves it, keeping the old one as pet-memory.previous.md."""
    exe = find_claude()
    if not exe:
        return "I can't find the claude command, so I can't ask big Claude.", None
    if not workspace or not os.path.isdir(workspace):
        return "I don't know where your notes are. Type /workspace to show me the folder.", None
    try:
        with open(MEMORY_FILE, encoding="utf-8") as f:
            current = f.read()
    except OSError:
        current = "(empty: this is the first time)"
    try:
        r = subprocess.run(
            [exe, "-p", "--tools", "Read,Glob,Grep", "--allowedTools", "Read,Glob,Grep",
             "--strict-mcp-config", "--no-session-persistence",
             "--model", MODELS.get(model, MODELS["opus"])[0], "--output-format", "json"],
            input=UPDATE_PROMPT.format(today=dt.date.today().isoformat(), current=current.strip()),
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, cwd=workspace,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return "Big Claude took too long. Let's try later.", None
    except Exception as e:
        return f"Something went wrong: {e}", None
    try:
        info = json.JSONDecoder().raw_decode((r.stdout or "").strip())[0]
    except Exception:
        info = None
    text = ((info or {}).get("result") or "").strip()
    if info is None or info.get("is_error") or r.returncode != 0:
        return f"Big Claude couldn't do it. ({(text or (r.stderr or '').strip() or 'no answer')[:100]})", None
    summary, body = "Done.", []
    for line in text.replace("```markdown", "").replace("```", "").splitlines():
        if line.startswith("SUMMARY:") and not body:
            summary = line[8:].strip() or summary
        elif body or line.startswith(("# ", "## ", "Updated:")):
            body.append(line)
    new = "\n".join(body).strip() + "\n"
    if "## Name" not in new or "## About" not in new:
        return "Big Claude's answer didn't look like a memory file, so I kept the old one.", None
    try:
        if os.path.exists(MEMORY_FILE):
            shutil.copyfile(MEMORY_FILE, MEMORY_BACKUP)
        tmp = MEMORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new)
        os.replace(tmp, MEMORY_FILE)
    except OSError as e:
        return f"I couldn't save my memory: {e}", None
    return summary, info


def load_state():
    s = {"first_met": dt.date.today().isoformat(), "last_seen": None, "model": "opus",
         "pets": 0, "chats": 0, "energy": 100.0, "history": [],
         "effort": None, "fast": False, "mode": "play", "lines": True, "last_sync": "", "workspace": "", "state": "lively", "notes": [], "summary": "", "past": [],
         "usage": {"replies": 0, "cost": 0.0, "ms": 0, "day": "", "day_replies": 0, "day_cost": 0.0}}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    for chat in [s] + s["past"]:                       # older versions marked your lines "her"
        chat["history"] = [["you" if who == "her" else who, text] for who, text in chat.get("history", [])]
    return s


def width_of(text):
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def chunks(text, limit=100):
    """Split a long reply into bubble-sized pieces at sentence ends."""
    parts = re.findall(r"[^.!?。！？]+[.!?。！？]*\s*", text) or [text]
    out, cur = [], ""
    for p in parts:
        if cur and width_of(cur + p) > limit:
            out.append(cur.strip())
            cur = p
        else:
            cur += p
    if cur.strip():
        out.append(cur.strip())
    return out or [text]


def find_claude():
    p = shutil.which("claude")
    if p:
        return p
    p = os.path.expanduser(r"~\.local\bin\claude.exe")
    return p if os.path.exists(p) else None


def ask_claude(system, prompt, model, effort=None, fast=False):
    """One call to Claude, with no tools, no plugins and nothing saved.
    Returns (text, info); info is None when something went wrong."""
    exe = find_claude()
    if not exe:
        return ("[sad] I can't find Claude Code on this computer, so I can't think yet. "
                "Install it, sign in once with `claude`, then try again."), None
    args = [exe, "-p", "--safe-mode", "--tools", "", "--strict-mcp-config",
            "--no-session-persistence", "--model", MODELS.get(model, MODELS["opus"])[0],
            "--system-prompt", system, "--output-format", "json"]
    if effort:
        args += ["--effort", effort]
    if fast:
        args += ["--settings", '{"fastMode": true}']
    try:
        r = subprocess.run(args, input=prompt, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120, cwd=tempfile.gettempdir(),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return "[sleepy] Sorry, my brain took too long. Try again?", None
    except Exception as e:
        return f"[sad] Something went wrong: {e}", None
    try:
        info = json.JSONDecoder().raw_decode((r.stdout or "").strip())[0]
    except Exception:
        info = None
    text = (info or {}).get("result") or ""
    if info is None or info.get("is_error") or r.returncode != 0 or not text.strip():
        err = text.strip() or ((r.stderr or "").strip().splitlines() or ["no answer"])[-1]
        return f"[sad] I couldn't reach big Claude. ({err[:110]})", None
    return text.strip(), info


def claude_version():
    exe = find_claude()
    if not exe:
        return None, None
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return exe, (r.stdout or "").strip() or "unknown version"
    except Exception as e:
        return exe, f"error: {e}"


def parse_reply(out):
    out = re.sub(r"[^\u0000-￿]", "", out)  # Tk can't draw emoji
    m = re.match(r"\s*\[(\w+)\]\s*", out)
    mood = "calm"
    if m:
        mood = m.group(1).lower() if m.group(1).lower() in MOODS else "calm"
        out = out[m.end():]
    return mood, out.strip() or "..."


def fs(points):
    """Font size that follows the pet size."""
    return max(6, round(points * S))


# ---------- the pet ----------

class Pet:
    def __init__(self, root):
        self.root = root
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", KEY)
        root.config(bg=KEY)
        self.c = tk.Canvas(root, width=W, height=H, bg=KEY, highlightthickness=0)
        self.c.pack()

        self.mem = load_state()
        self.last_seen = self.mem.get("last_seen")       # read now: starting up saves and overwrites it
        self.area = work_area()
        self.x, self.y = 0.0, 0.0
        self.set_size(self.mem.get("size", 1.0), quiet=True)
        self.x = float(self.area[2] - W)
        self.y = float(self.area[3] - H)
        self.t = 0
        self.base = "idle"            # idle, walk, drag, sleep, think
        self.mood, self.mood_until = None, 0
        self.action, self.action_start, self.action_until = None, 0, 0
        self.next_action = 30 * 6
        self.next_talk = 30 * random.randint(90, 240)
        self.target, self.speed, self.facing = None, 1.6, 0
        self.still = False
        self.blink = 0
        self.last_touch = 0
        self.clicks = []
        self.bubble, self.bubble_end, self.bubble_queue, self.bubble_box = None, 0, [], None
        self.parts = []
        self.drag = None
        self.dbl = False
        self.click_job = None
        self.hover = 0
        self.trail = []
        self.cooldown = {}
        self.chat = None
        self.chat_pos = None
        self.wins, self.edges = [], []
        self.perch, self.plan, self.vy = None, [], 0.0      # play mode: where it stands, what it's doing
        self.climb, self.jump = {}, {}
        self.seer = LineEye(self.own_rects)
        self.walls = []
        self.game, self.game_focused, self.prev_space, self.hwnd = False, False, False, None
        self.vx, self.floating, self.float_left = 0.0, False, FLOAT
        self.ignore_y, self.ignore_until = 0, 0
        self.nap_until, self.cycle, self.slot, self.slot_end = 0, [], 0, 0.0
        self.view, self.view_dir, self.view_sit, self.view_pick = 0, 1, None, (0.0, 1)
        self.glance, self.glance_until, self.flip, self.blink2 = (0, 1), 0, False, 0
        self.pause_until, self.still_frames, self.last_ptr = 0, 0, (0, 0)
        self.start_cycle(first=self.first_state(), announce=False)
        self.mode_end = time.monotonic() + MODE_SLOT
        self.hold_until, self.reroll_at, self.reach = 0, 0, 0
        self.away, self.still_choice, self.away_switch = False, False, 0.0
        self.prev_keys, self.last_tap, self.running, self.fast_climb = {}, {}, False, False
        self.no_grab_until, self.last_input, self.wander_left, self.air_top = 0, 0, 0, None
        self.seer.start()
        self.line_seen, self.line_miss = 0, 0
        self.typing_until = 0
        self.q = queue.Queue()
        self.verb, self.fixed_verb = VERBS[0], None
        self.ox, self.oy, self.pet_top = 0, H - 8 * P, H - 8 * P

        c = self.c
        c.bind("<ButtonPress-1>", self.press)
        c.bind("<B1-Motion>", self.motion)
        c.bind("<ButtonRelease-1>", self.release)
        c.bind("<Double-Button-1>", self.double)
        c.bind("<Button-3>", self.menu)
        self.place()
        self.greet()
        self.tick()
        if "--update-memory" in sys.argv:              # started with this flag (e.g. at sign-in): fresh memory today
            root.after(20000, self.startup_sync)

    # ---------- memory from big Claude ----------
    def pm(self):
        """The pet memory file, reloaded when it changes."""
        try:
            stamp = os.path.getmtime(MEMORY_FILE)
        except OSError:
            stamp = None
        if getattr(self, "_pm_stamp", "never") != stamp:
            self._pm_stamp, self._pm = stamp, load_memory()
        return self._pm

    def name(self):
        return self.pm()["name"]

    def upcoming(self):
        today = dt.date.today()
        return [(d, what, (d - today).days) for d, what in self.pm()["dates"] if d >= today]

    def pick_workspace(self):
        """Ask which folder holds the notes big Claude should read."""
        self.close_chat()
        folder = filedialog.askdirectory(parent=self.root, title="Which folder has your notes for big Claude?",
                                         initialdir=self.mem.get("workspace") or os.path.expanduser("~"))
        if folder:
            self.mem["workspace"] = os.path.normpath(folder)
            self.save()
            self.set_mood("happy", 30)
            self.say(f"Got it. Big Claude will read {os.path.basename(folder) or folder}.")
        return bool(folder)

    def update_memory(self, manual=True):
        if self.base == "think":
            if manual:
                self.say("One thing at a time. I'm still thinking!")
            return
        if not self.mem.get("workspace") or not os.path.isdir(self.mem["workspace"]):
            if not manual or not self.pick_workspace():
                return
        self.mem["last_sync"] = dt.date.today().isoformat()
        model, workspace = self.mem.get("model", "opus"), self.mem["workspace"]
        if manual:
            self.base, self.action, self.mood, self.target = "think", None, None, None
            self.verb = self.fixed_verb = "Asking big Claude"
            self.bubble, self.bubble_queue = None, []
        kind = "update" if manual else "update-bg"

        def work():
            text, info = ask_big_claude_to_update(model, workspace)
            self.q.put((kind, text, info))
        threading.Thread(target=work, daemon=True).start()

    def startup_sync(self):
        """With --update-memory: ask big Claude for a fresh memory at start, once a day, if a notes folder is set."""
        if self.mem.get("workspace") and self.mem.get("last_sync") != dt.date.today().isoformat():
            self.update_memory(manual=False)

    def maybe_sync(self):
        """Once a day at most: if the memory is over 2 days old, ask big Claude for a fresh one."""
        if self.mem.get("last_sync") == dt.date.today().isoformat() or not self.mem.get("workspace"):
            return
        updated = self.pm()["updated"]
        try:
            old = updated is None or (dt.date.today() - dt.date.fromisoformat(updated)).days >= 2
        except ValueError:
            old = True
        if old:
            self.update_memory(manual=False)

    # ---------- talking ----------
    def say(self, text):
        self.bubble_queue = chunks(text)
        self.next_bubble()

    def next_bubble(self):
        if self.bubble_queue:
            self.bubble = self.bubble_queue.pop(0)
            secs = max(2.5, min(10, 1.5 + width_of(self.bubble) / 12))
            self.bubble_end = self.t + int(30 * secs)
        else:
            self.bubble = None

    def lines(self):
        now = dt.datetime.now()
        name = self.name()
        out = [
            f"Hi {name}!",
            "Drink some water?",
            "I'm tiny, but I'm listening.",
            "Stretch your shoulders.",
            "Double-click me if you want to talk.",
        ] + self.pm()["say"]
        for d, what, days in self.upcoming():
            out += [f"Today: {what}!"] if days == 0 else [f"{days} days until {what}."] if days <= 120 else []
        if now.hour >= 23 or now.hour < 5:
            out += [f"It's late, {name}. Sleep is part of the work.", "Bed. Now. Please?"]
        elif now.hour < 11:
            out += ["Good morning!"]
        if self.mem["energy"] < 30:
            out += ["I'm a bit sleepy...", "Low battery. Nap soon?"]
        return out

    def greet(self):
        now = dt.datetime.now()
        last = self.last_seen
        if not last:                                            # the very first start
            parts = ["Hi! I'm Mini Claude, a tiny Claude for your desktop.",
                     "Double-click me to talk. Right-click me for the menu."]
            if not os.path.exists(MEMORY_FILE):
                parts.append("Want me to know you? Type /workspace to show me your notes folder, then /update.")
            self.set_mood("excited", 45)
            self.bubble_queue = [c for p in parts for c in chunks(p)]
            self.next_bubble()
            return
        else:
            gap = now - dt.datetime.fromisoformat(last)
            if gap.days >= 2:
                text = f"You're back! It's been {gap.days} days. I missed you."
            elif gap.total_seconds() > 6 * 3600:
                text = ("Good morning, " if now.hour < 12 else "Hello again, ") + f"{self.name()}!"
            else:
                text = random.choice(["I'm back!", "Hello again!", "Did you miss me? (^_^)"])
        self.set_mood("excited", 45)
        self.say(text)

    # ---------- chat with Claude ----------
    def open_chat(self):
        if self.base == "sleep":
            self.wake()
        if self.chat:
            self.entry.focus_force()
            return
        b = self.area[3]
        if not self.playing() and self.y + H + 44 * S > b:   # make room below for the typing line
            self.y = b - H - 44 * S
            self.place()
        self.target = None
        self.action = None
        self.chat = tk.Toplevel(self.root)
        self.chat.overrideredirect(True)
        self.chat.attributes("-topmost", True)
        self.chat.attributes("-transparentcolor", KEY)
        self.chat.config(bg=KEY)
        # no box: a transparent entry, so only the cursor and the words float
        self.entry = tk.Entry(self.chat, font=(LIGHT_FONT, fs(10)), relief="flat", bd=0, highlightthickness=0,
                              bg=KEY, fg=INK, insertbackground=INK, insertwidth=2, width=26, justify="center")
        self.entry.pack()
        self.sugg = tk.Frame(self.chat, bg=KEY)
        self.sugg.pack(fill="x")
        self.items, self.sel = [], 0
        en = self.entry
        en.bind("<Return>", self.send)
        en.bind("<Escape>", lambda e: self.close_chat())
        en.bind("<Button-3>", self.menu)
        en.bind("<Tab>", self.complete)
        en.bind("<Up>", lambda e: self.move_sel(-1))
        en.bind("<Down>", lambda e: self.move_sel(1))
        en.bind("<KeyRelease>", self.update_suggestions)
        en.bind("<FocusOut>", lambda e: self.root.after(200, self.check_focus))
        self.chat_pos = None
        self.place_chat()
        self.chat.after(80, en.focus_force)
        self.set_mood("happy", 25)

    def check_focus(self):
        """Clicking anywhere else closes the floating cursor."""
        if not self.chat:
            return
        try:
            f = self.root.focus_get()
        except Exception:
            f = None
        if f is None:
            self.close_chat()
        elif f is not self.entry:
            self.entry.focus_force()

    def place_chat(self):
        self.chat.update_idletasks()
        w, h = self.chat.winfo_reqwidth(), self.chat.winfo_reqheight()
        self.chat_size = (w, h)
        x = int(self.x + W / 2 - w / 2)
        y = int(min(self.y + H, self.area[3] - h))
        if self.playing() and self.y + H + h > self.area[3]:     # no room below: float beside the pet
            right = self.x + W / 2 + 13 * P / 2 + 6
            x = int(right if right + w < self.area[2] else self.x + W / 2 - 13 * P / 2 - 6 - w)
            y = int(min(self.feet() - h, self.area[3] - h))
        if (x, y) != self.chat_pos:
            self.chat_pos = (x, y)
            self.chat.geometry(f"+{x}+{y}")

    def close_chat(self):
        if self.chat:
            self.chat.destroy()
            self.chat = None

    # ---------- slash commands with floating suggestions ----------
    def arg_options(self, cmd):
        m = self.mem
        if cmd == "model":
            cur = m.get("model", "opus")
            return [(k, ("● " if k == cur else "") + note) for k, (_, note) in MODELS.items()]
        if cmd == "effort":
            cur = m.get("effort") or "auto"
            return [(k, ("● " if k == cur else "") + note) for k, note in EFFORTS]
        if cmd == "resume":
            return [(str(i + 1), f"{p['when'][5:16].replace('T', ' ')} · {self.title_of(p)}")
                    for i, p in enumerate(m["past"])]
        if cmd == "memory":
            return [("clear", "forget all notes")]
        if cmd == "state":
            cur = self.state()
            return [(k, ("● " if k == cur else "") + d) for k, d in (
                ("lively", "busy and bouncy"), ("calm", "little hobbies"), ("sleepy", "slow, naps a lot"))]
        return None

    @staticmethod
    def title_of(chat):
        first = next((text for who, text in chat["history"] if who == "you"), chat.get("summary") or "...")
        return first[:22] + ("…" if len(first) > 22 else "")

    def update_suggestions(self, e=None):
        if e is not None:
            if e.keysym in ("Up", "Down", "Tab", "Return", "Escape"):
                return
            self.typing_until = self.t + 20
        text = self.entry.get()
        items = []
        if text.startswith("/"):
            cmd, space, arg = text[1:].partition(" ")
            cmd = ALIASES.get(cmd.lower(), cmd.lower())
            if space:
                opts = self.arg_options(cmd) or []
                items = [(f"/{cmd} {v}", d) for v, d in opts if v.startswith(arg.strip().lower())]
            else:
                items = [(f"/{n}", d) for n, d in COMMANDS if n.startswith(cmd)]
        self.items = items
        self.sel = min(self.sel, max(0, len(items) - 1))
        self.render_suggestions()

    def render_suggestions(self):
        for w in self.sugg.winfo_children():
            w.destroy()
        first = max(0, min(self.sel - SHOW + 1, len(self.items) - SHOW))
        for i in range(first, min(len(self.items), first + SHOW)):
            cmd, desc = self.items[i]
            on = i == self.sel
            lab = tk.Label(self.sugg, text=f"{'›' if on else ' '} {cmd}   {desc}", bg=KEY,
                           fg=INK if on else SOFT_INK, font=(LIGHT_FONT, fs(10)), anchor="w")
            lab.pack(fill="x")
            lab.bind("<Button-1>", lambda e, i=i: (setattr(self, "sel", i), self.complete()))
        if len(self.items) > SHOW:
            tk.Label(self.sugg, text=f"  {self.sel + 1}/{len(self.items)}  ↑↓", bg=KEY, fg=SOFT_INK,
                     font=(LIGHT_FONT, fs(9)), anchor="w").pack(fill="x")
        self.chat_pos = None

    def move_sel(self, d):
        if self.items:
            self.sel = (self.sel + d) % len(self.items)
            self.render_suggestions()
        return "break"

    def complete(self, e=None):
        if self.items:
            cmd = self.items[self.sel][0]
            self.entry.delete(0, "end")
            self.entry.insert(0, cmd + (" " if cmd[1:] in NEEDS_ARG else ""))
            self.sel = 0
            self.update_suggestions()
        self.entry.focus_force()
        return "break"

    def ask_for_arg(self, cmd):
        """A command typed without its argument: show its choices."""
        self.entry.insert(0, f"/{cmd} ")
        self.entry.icursor("end")
        self.update_suggestions()

    def run_command(self, text):
        cmd, _, raw = text[1:].partition(" ")
        cmd = ALIASES.get(cmd.lower(), cmd.lower())
        raw = raw.strip()
        arg = raw.lower()
        m = self.mem
        u = m["usage"]
        brain = MODELS[m.get("model", "opus")][1].split(" ·")[0]
        if cmd in NEEDS_ARG and not arg and self.chat:
            if cmd != "resume" or m["past"]:
                self.ask_for_arg(cmd)
                return
        if cmd == "model":
            if arg in MODELS:
                m["model"] = arg
                if arg != "opus":
                    m["fast"] = False
                self.set_mood("excited", 40)
                self.say(f"Switched to {MODELS[arg][1].split(' ·')[0]}. Same me, different brain.")
            else:
                self.say("I don't know that one. Try opus, sonnet, haiku or fable.")
        elif cmd == "effort":
            if arg in dict(EFFORTS):
                m["effort"] = None if arg == "auto" else arg
                self.set_mood("think", 40)
                self.say(f"Effort: {arg}. " + {"auto": "I'll decide myself.", "low": "Quick answers!",
                                                "max": "I'll think really, really hard."}.get(arg, "Got it."))
            else:
                self.say("Effort can be auto, low, medium, high, xhigh or max.")
        elif cmd == "fast":
            if m.get("model", "opus") != "opus":
                self.say("Fast mode only works with Opus. Try /model opus first.")
            else:
                m["fast"] = not m.get("fast")
                self.say("Fast mode on. (It needs extra usage on your account; I'll tell you if it doesn't work.)"
                         if m["fast"] else "Fast mode off.")
        elif cmd == "clear":
            self.forget()
        elif cmd == "resume":
            if not m["past"]:
                self.say("No old chats yet. /clear saves the current one before starting fresh.")
            elif arg.isdigit() and 1 <= int(arg) <= len(m["past"]):
                old = m["past"].pop(int(arg) - 1)
                self.archive()
                m["history"], m["summary"] = old["history"], old.get("summary", "")
                self.set_mood("happy", 40)
                self.say(f"Back to our chat about \"{self.title_of(old)}\".")
            else:
                self.say("Pick a number from the list.")
        elif cmd == "rewind":
            h = m["history"]
            if h and h[-1][0] == "mini":
                h.pop()
            if h and h[-1][0] == "you":
                taken = h.pop()[1]
                self.set_mood("think", 30)
                self.say(f"Rewound. I forgot you said: \"{taken[:40]}\"")
            else:
                self.say("Nothing to take back.")
        elif cmd == "compact":
            if len(m["history"]) < 4:
                self.say("Our chat is still tiny. Nothing to squeeze yet.")
            else:
                talk = "\n".join(f"{self.name() if w == 'you' else 'Mini Claude'}: {x}" for w, x in m["history"])
                prompt = (f"Earlier summary: {m['summary']}\n\n" if m["summary"] else "") + f"Chat:\n{talk}"
                system = (f"Summarize this chat between {self.name()} and Mini Claude in under 80 words, in English. "
                          f"Call them {self.name()}, with the pronouns the chat uses. Keep facts about them, their plans and feelings, and anything still open. "
                          "Plain text only, no mood tag.")
                self.start_think("compact", system, prompt, verb="Compacting")
        elif cmd == "btw":
            if not raw:
                self.say("Usage: /btw your question. I'll answer without saving it.")
            else:
                system, prompt = self.build_prompt(raw)
                self.start_think("btw", system, "(A quick side question; don't treat it as part of the chat.)\n" + prompt)
        elif cmd == "copy":
            last = next((x for w, x in reversed(m["history"]) if w == "mini"), None)
            if last:
                self.root.clipboard_clear()
                self.root.clipboard_append(last)
                self.say("Copied my last reply.")
            else:
                self.say("I haven't said anything worth copying yet.")
        elif cmd == "export":
            self.export()
        elif cmd == "memory":
            if arg == "clear":
                m["notes"] = []
                self.say("All notes forgotten.")
            elif raw:
                self.remember(raw)
            elif m["notes"]:
                self.say("I remember: " + " ".join(f"({i + 1}) {n}" for i, n in enumerate(m["notes"])))
            else:
                self.say("No notes yet. Start a message with # and I'll remember it.")
        elif cmd == "update":
            self.update_memory()
        elif cmd == "state":
            if arg in STATES:
                self.choose_state(arg)
            else:
                self.say("State can be lively, calm or sleepy.")
        elif cmd == "workspace":
            self.root.after(100, self.pick_workspace)
        elif cmd == "context":
            size = len(PERSONA) + len(m["summary"]) + sum(len(n) for n in m["notes"]) + sum(len(x) for _, x in m["history"][-12:])
            self.say(f"I'm carrying {len(m['notes'])} note{'' if len(m['notes']) == 1 else 's'}, a {len(m['summary'])}-letter summary and "
                     f"{len(m['history'])} chat lines. About {size // 4} tokens per message.")
        elif cmd == "usage":
            avg = u["ms"] / u["replies"] / 1000 if u["replies"] else 0
            self.say(f"{u['replies']} replies so far, {u['day_replies'] if u['day'] == dt.date.today().isoformat() else 0} today. "
                     f"Average wait: {avg:.1f} s. List-price value: ${u['cost']:.3f} in total.")
        elif cmd == "status":
            self.say(f"State: {STATES[self.state()][0].lower()}. Brain: {brain}. Effort: {m.get('effort') or 'auto'}. Fast: {'on' if m.get('fast') else 'off'}. "
                     f"Energy: {int(m['energy'])}/100. Pets: {m['pets']}. Chats: {m['chats']}. Together since {m['first_met']}.")
        elif cmd == "doctor":
            self.base, self.fixed_verb, self.verb = "think", "Checking", "Checking"
            def work():
                exe, ver = claude_version()
                text = (f"Claude CLI found: {ver}. Brain: {brain}. Everything looks fine." if exe and not ver.startswith("error")
                        else f"Problem: {ver}" if exe else "I can't find the claude command. Is Claude Code installed?")
                self.q.put(("doctor", text, None))
            threading.Thread(target=work, daemon=True).start()
        elif cmd == "help":
            self.say("Type / to see all my commands; Tab or Enter picks one, arrows move. "
                     "Start a message with # and I'll remember it.")
        elif cmd == "exit":
            self.bye()
        elif cmd == "say":
            self.set_mood("happy", 40)
            self.say(random.choice(self.lines()))
        elif cmd == "pet":
            self.single_click()
        elif cmd in ("hum", "dance"):
            self.mood = None
            self.action, self.action_start, self.action_until = cmd, self.t, self.t + 150
            if cmd == "hum":
                self.say(random.choice(HUMS))
        elif cmd == "game":
            self.close_chat()
            self.root.after(100, self.toggle_game)
        elif cmd == "lines":
            self.toggle_lines()
        elif cmd in ("play", "float"):
            if (cmd == "play") != self.playing():
                self.toggle_mode()
        elif cmd in ("still", "wander"):
            self.still = cmd == "still"
            self.target = None
            self.say("Okay, I'll stay right here." if self.still else "Off I go!")
        elif cmd == "sleep":
            self.sleep(nap=True)
        elif cmd == "wake":
            self.wake()
            self.say("I'm up!")
        else:
            self.say("Hm, I don't know that command. Type / to see them.")
        self.save()
        self.items = []
        if self.chat:
            self.render_suggestions()

    def remember(self, note):
        self.mem["notes"] = (self.mem["notes"] + [note])[-15:]
        self.set_mood("love", 40)
        self.say(random.choice(["Got it. I'll remember that.", "Noted, in my tiny heart.", "Remembered!"]))

    def archive(self):
        m = self.mem
        if m["history"] or m["summary"]:
            m["past"].insert(0, {"when": dt.datetime.now().isoformat(timespec="minutes"),
                                 "history": m["history"], "summary": m["summary"]})
            m["past"] = m["past"][:10]
        m["history"], m["summary"] = [], ""

    def export(self):
        m = self.mem
        if not m["history"] and not m["summary"]:
            self.say("Nothing to export yet.")
            return
        now = dt.datetime.now()
        folder = os.path.join(HERE, "exports")
        os.makedirs(folder, exist_ok=True)
        name = f"chat-{now:%Y-%m-%d-%H%M}.md"
        lines = [f"# Chat with Mini Claude, {now:%Y-%m-%d %H:%M}", "", f"- Model: {m.get('model', 'opus')}"]
        if m["summary"]:
            lines.append(f"- Summary of the earlier part: {m['summary']}")
        lines.append("")
        for who, text in m["history"]:
            lines.append(f"**{self.name() if who == 'you' else 'Mini Claude'}:** {text}\n")
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self.say(f"Saved to exports/{name}")

    def start_think(self, kind, system, prompt, verb=None):
        self.base, self.action, self.mood, self.target = "think", None, None, None
        self.verb, self.fixed_verb = verb or random.choice(VERBS), verb
        self.bubble, self.bubble_queue = None, []
        self.last_touch = self.t
        m = self.mem
        model, effort, fast = m.get("model", "opus"), m.get("effort"), m.get("fast")

        def work():
            text, info = ask_claude(system, prompt, model, effort, fast)
            self.q.put((kind, text, info))
        threading.Thread(target=work, daemon=True).start()

    def send(self, e=None):
        msg = self.entry.get().strip()
        if not msg:
            return "break"
        if msg.startswith("/"):
            cmd, space, arg = msg[1:].partition(" ")
            if self.items and (not space or (self.arg_options(ALIASES.get(cmd.lower(), cmd.lower())) and arg.strip())):
                msg = self.items[self.sel][0]
            self.entry.delete(0, "end")
            if self.base == "think" and ALIASES.get(cmd.lower(), cmd.lower()) in ("compact", "btw", "doctor"):
                self.say("One thing at a time. I'm still thinking!")
                return "break"
            self.run_command(msg)
            return "break"
        if self.base == "think":
            return "break"
        self.entry.delete(0, "end")
        if msg.startswith("#") and msg.lstrip("#").strip():
            self.remember(msg.lstrip("#").strip())
            self.save()
            return "break"
        system, prompt = self.build_prompt(msg)
        self.mem["history"].append(["you", msg])
        self.mem["chats"] += 1
        self.start_think("chat", system, prompt)
        return "break"

    def build_prompt(self, msg):
        now = dt.datetime.now()
        m = self.mem
        soon = "; ".join(f"{what} on {d:%b %d} (in {days} days)" for d, what, days in self.upcoming()[:4])
        context = (f"Now: {now:%A %Y-%m-%d %H:%M}. " + (f"Coming up: {soon}. " if soon else "") +
                   f"You met on {m['first_met']}. {self.name()} has petted you {m['pets']} times. "
                   f"Your energy: {int(m['energy'])}/100.")
        if m["notes"]:
            context += f"\n\nThings {self.name()} asked you to remember:\n" + "\n".join(f"- {n}" for n in m["notes"])
        if m["summary"]:
            context += "\n\nSummary of the earlier part of this chat: " + m["summary"]
        talk = "\n".join(f"{self.name() if who == 'you' else 'Mini Claude'}: {text}" for who, text in m["history"][-12:])
        prompt = (f"Recent chat:\n{talk}\n\n" if talk else "") + f"{self.name()}: {msg}"
        persona = PERSONA.format(name=self.name(), about=self.pm()["about"] or "- Not much yet. Ask big Claude to update your memory.")
        return persona + "\n\n" + context, prompt

    def track(self, info):
        u = self.mem["usage"]
        today = dt.date.today().isoformat()
        if u["day"] != today:
            u.update(day=today, day_replies=0, day_cost=0.0)
        cost = info.get("total_cost_usd") or 0
        u["replies"] += 1
        u["day_replies"] += 1
        u["cost"] += cost
        u["day_cost"] += cost
        u["ms"] += info.get("duration_ms") or 0

    def poll_claude(self):
        try:
            kind, out, info = self.q.get_nowait()
        except queue.Empty:
            return
        m = self.mem
        if kind == "update-bg":                                  # quiet background refresh
            if info:
                self.track(info)
                self.say("Big Claude refreshed my memory. " + out[:120])
            self.save()
            return
        self.base, self.fixed_verb = "idle", None
        self.last_touch = self.t
        if info:
            self.track(info)
        if kind == "update":
            self.set_mood("excited" if info else "sad", 40)
            self.say(("Memory updated! " if info else "") + out[:160])
            self.save()
            return
        if kind == "compact" and info:
            m["summary"], m["history"] = parse_reply(out)[1], []
            self.set_mood("happy", 40)
            self.say("Compacted! I kept the gist of our chat in a short summary.")
        elif kind == "doctor":
            self.set_mood("calm", 30)
            self.say(out)
        else:
            mood, text = parse_reply(out)
            if kind == "chat" and info:
                m["history"].append(["mini", text])
                m["history"] = m["history"][-30:]
            self.set_mood(mood, 30 * 4)
            self.say(text)
            if kind == "chat" and m.get("fast") and info and info.get("fast_mode_state") != "on":
                m["fast"] = False
                self.bubble_queue += chunks("(Fast mode didn't turn on: it needs extra usage on your account. I switched it off.)")
        self.save()

    # ---------- input ----------
    def press(self, e):
        if self.game:
            self.root.focus_force()
        self.drag = (e.x_root, e.y_root, self.x, self.y, False)

    def motion(self, e):
        if not self.drag:
            return
        sx, sy, ox, oy, moved = self.drag
        dx, dy = e.x_root - sx, e.y_root - sy
        if moved or abs(dx) + abs(dy) > 4:
            if not moved:
                self.perch, self.plan = None, []
                if self.base != "think":
                    self.base, self.action, self.mood, self.target = "drag", None, None, None
            self.drag = (sx, sy, ox, oy, True)
            self.x, self.y = ox + dx, oy + dy
            self.place()

    def release(self, e):
        d, self.drag = self.drag, None
        self.last_touch = self.t
        if self.dbl:
            self.dbl = False
            return
        if d and d[4]:
            self.hold_until = self.t + random.randint(90, 150)
            if self.base == "drag":
                self.base = "idle"
                r = random.random()
                if r < 0.25 and not self.playing():                # in play mode it falls instead
                    self.set_mood("happy", 30)
                if r < 0.12:                                       # only now and then
                    self.say(random.choice(["Whee!", "Wooo~", "Again! Again!"]))
            return
        bb = self.bubble_box
        if bb and bb[0] <= e.x <= bb[2] and bb[1] <= e.y <= bb[3] and self.bubble:
            self.next_bubble()
            return
        if self.click_job:
            self.root.after_cancel(self.click_job)
        self.click_job = self.root.after(230, self.single_click)

    def double(self, e):
        self.dbl = True
        if self.click_job:
            self.root.after_cancel(self.click_job)
            self.click_job = None
        self.open_chat()

    def single_click(self):
        self.click_job = None
        self.mem["pets"] += 1
        if self.base == "sleep":
            self.wake()
            self.set_mood("surprised", 30)
            self.say("Huh? I'm awake! I'm awake!")
            return
        if self.base == "think":
            self.spawn("heart", 1)
            return
        self.clicks = [c for c in self.clicks if self.t - c < 45] + [self.t]
        n = self.mem["pets"]
        r = random.random()
        if len(self.clicks) >= 5 and r < 0.5:
            self.clicks = []
            self.set_mood("happy", 60)
            self.say("Hey! That tickles! Hehehe.")
        elif n % 50 == 0:
            self.set_mood("love", 70)
            self.spawn("heart", 6)
            self.say(f"That's {n} pets. I'm counting, you know.")
        elif r < 0.08:                                            # sometimes: a few words
            self.set_mood("happy", 40)
            self.spawn("heart", 1)
            self.say(random.choice(self.lines()))
        elif r < 0.2:                                             # sometimes: a happy wiggle
            self.set_mood(random.choice(["happy", "shy", "love"]), 35)
        elif r < 0.3:                                             # sometimes: one little heart
            self.spawn("heart", 1)
        else:                                                     # mostly: just a blink
            self.blink = 5

    def menu(self, e):
        self.close_chat()   # right-click hides the typing cursor first, so the menu keeps focus
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Talk to me", command=self.open_chat)
        m.add_command(label="Say something", command=lambda: (self.set_mood("happy", 40), self.say(random.choice(self.lines()))))
        m.add_command(label="Wander" if self.still else "Stay still", command=self.toggle_still)
        if self.base == "sleep":
            m.add_command(label="Wake up", command=self.toggle_sleep)
        states = tk.Menu(m, tearoff=0)
        self.state_var = tk.StringVar(value=self.state())
        for key, (label, *_) in STATES.items():
            states.add_radiobutton(label=label, value=key, variable=self.state_var,
                                   command=lambda k=key: self.choose_state(k))
        m.add_cascade(label=f"State: {STATES[self.state()][0]}", menu=states)
        m.add_command(label="New chat", command=self.forget)
        m.add_command(label="Update my memory", command=self.update_memory)
        m.add_command(label="Float freely" if self.playing() else "Play on edges", command=self.toggle_mode)
        m.add_command(label="Stop game" if self.game else "Game mode", command=self.toggle_game)
        m.add_command(label="Ignore lines in apps" if self.mem.get("lines", True) else "See lines in apps",
                      command=self.toggle_lines)
        sizes = tk.Menu(m, tearoff=0)
        self.size_var = tk.DoubleVar(value=self.mem.get("size", 1.0))
        for label, scale in SIZES:
            sizes.add_radiobutton(label=label, value=scale, variable=self.size_var,
                                  command=lambda sc=scale: self.set_size(sc))
        m.add_cascade(label="Size", menu=sizes)
        m.add_separator()
        m.add_command(label="Bye", command=self.bye)
        m.tk_popup(e.x_root, e.y_root)

    def set_size(self, scale, quiet=False):
        """Resize the pet (sprite and window); text sizes stay the same."""
        global S, P, W, H
        keep = (self.cx(), self.feet()) if not quiet else None   # stay in the same spot
        if not quiet:                                  # a clean switch: stop the activity and clear any effects first
            self.action, self.mood, self.parts = None, None, []
            self.root.attributes("-alpha", 0.0)        # hidden while resizing: a grown window is black until repainted
        S = scale
        P = round(8 * S)
        W, H = round(300 * S), round(280 * S)
        self.c.config(width=W, height=H)
        self.mem["size"] = scale
        if keep:
            self.set_feet(*keep)
        else:
            self.place()
        if getattr(self, "chat", None):
            self.entry.config(font=(LIGHT_FONT, fs(10)))
            self.render_suggestions()
        if not quiet:
            self.draw()                                # redraw at the new size right away
            self.root.update_idletasks()
            self.root.after(80, self.show_again)
            self.save()

    def show_again(self):
        self.root.update_idletasks()
        self.root.attributes("-alpha", 1.0)

    # ---------- play on edges ----------
    def playing(self):
        return self.mem.get("mode") == "play"

    def toggle_mode(self, auto=False):
        if self.game:
            self.toggle_game()
        self.mem["mode"] = "float" if self.playing() else "play"
        self.mode_end = time.monotonic() + MODE_SLOT            # about 4 minutes, then they swap again
        self.perch, self.plan, self.target = None, [], None
        if self.base in ("climb", "fall", "jump", "walk"):
            self.base = "idle"
        self.save()
        if auto and random.random() < 0.6:                     # most switches happen quietly
            return
        self.set_mood("excited", 40)
        if auto:
            self.say(random.choice(MODE_LINES[self.mem["mode"]]))
        else:
            self.say("Let's play on the edges!" if self.playing() else "Floating again~")

    def update_mode(self):
        """Float and play on edges take turns, 4 minutes each (an 8-minute circle).
        It waits for a free moment: not mid-air, climbing, asleep, busy, being dragged or talking."""
        now = time.monotonic()
        if self.game:
            self.mode_end = max(self.mode_end, now + 60)       # after a game, it plays a little longer
            return
        if now < self.mode_end:
            return
        if (self.chat or self.action or self.drag
                or self.base in ("drag", "sleep", "think", "fall", "jump", "air", "climb")):
            return
        self.toggle_mode(auto=True)

    def own_rects(self):
        """Screen areas where the pet draws itself (body, bubble, typing line). Read from the seer thread."""
        pad, x, y = 14 * S, self.x, self.y
        rects = [(x + self.ox - pad, y + self.pet_top - 3 * P - pad, x + self.ox + 13 * P + pad, self.feet() - 3)]
        bb = self.bubble_box
        if bb:
            rects.append((x + bb[0] - pad, y + bb[1] - pad, x + bb[2] + pad, y + bb[3] + 10 * S + pad))
        if self.chat and self.chat_pos and getattr(self, "chat_size", None):
            (cx, cy), (cw, ch) = self.chat_pos, self.chat_size
            rects.append((cx - pad, cy - pad, cx + cw + pad, cy + ch + pad))
        return rects

    # ---------- game mode ----------
    def toggle_game(self, idle=False):
        self.game = not self.game
        if self.game:
            self.last_input = self.t
            self.mem["mode"] = "play"
            self.plan, self.target, self.action = [], None, None
            if self.base == "sleep":
                self.wake()
            self.close_chat()
            self.root.focus_force()
            self.c.focus_set()
            self.game_focused = True
            self.say("Game on!")
        else:
            if self.base == "air":
                self.base = "fall"
            elif self.base == "walk":                              # stop walking even if a key is still held
                self.base = "idle"
            self.vx, self.running, self.fast_climb, self.prev_keys = 0.0, False, False, {}
            self.hold_until, self.next_action = 0, self.t + random.randint(30, 90)   # then it does its own things
            self.say("No one's playing? I'll go explore by myself." if idle else "Game over~ I'll play by myself again.")

    def keys(self):
        """Held keys, but only while the pet's window has the keyboard (so typing elsewhere is safe)."""
        try:
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            if not self.hwnd:
                self.hwnd = int(self.root.wm_frame(), 16)
            if user32.GetForegroundWindow() != self.hwnd:
                return None
            held = lambda *vks: any(user32.GetAsyncKeyState(v) & 0x8000 for v in vks)
            return {"w": held(0x57, 0x26), "a": held(0x41, 0x25), "s": held(0x53, 0x28),
                    "d": held(0x44, 0x27), "space": held(0x20), "esc": held(0x1B)}
        except Exception:
            return None

    def go_air(self, vy):
        self.base, self.perch, self.vy, self.floating = "air", None, vy, False

    def game_update(self):
        self.refresh_world(force=self.t % 3 == 0)
        keys = self.keys()
        if (keys is not None) != self.game_focused:
            self.game_focused = keys is not None
            self.say("Let's go!" if self.game_focused else "Paused. Click me to keep playing.")
        k = keys or {}
        if any(k.values()):
            self.last_input = self.t
        elif self.t - self.last_input > 150:                       # 5 s without a key
            self.toggle_game(idle=True)
            return
        if k.get("esc"):
            self.toggle_game()
            return
        space_down = bool(k.get("space")) and not self.prev_space
        self.prev_space = bool(k.get("space"))
        move = (1 if k.get("d") else 0) - (1 if k.get("a") else 0)
        for key in ("a", "d"):                                   # double-tap A or D to run
            if k.get(key) and not self.prev_keys.get(key):
                self.running = self.t - self.last_tap.get(key, -99) <= 9
                self.last_tap[key] = self.t
        if not move:
            self.running = False
        if k.get("w") and not self.prev_keys.get("w"):            # double-tap W to climb faster
            self.fast_climb = self.t - self.last_tap.get("w", -99) <= 9
            self.last_tap["w"] = self.t
        if not k.get("w"):
            self.fast_climb = False
        self.prev_keys = dict(k)
        speed = (6 if self.running else 3) * S ** 0.5          # bigger pet moves a bit faster
        if move:
            self.facing = move
        b = self.base
        if b == "sleep" and (move or space_down):
            self.wake()
            b = self.base
        if b in ("fall", "jump"):
            self.base, b, self.vx = "air", "air", 0.0
        if b == "climb":
            if not self.climb.get("game"):
                self.go_air(0)
            else:
                self.game_climb(k, move, space_down, speed)
        elif b == "air":
            self.game_air(k, move, speed)
        elif b in ("idle", "walk", "think"):
            if self.perch is None:
                self.go_air(0)
                return
            if space_down:
                if k.get("s") and self.perch[0] is not None:       # drop through this ledge
                    self.ignore_y, self.ignore_until = self.feet(), self.t + 12
                    self.go_air(2 * S)
                else:
                    high = bool(k.get("w"))                        # W+Space jumps higher
                    self.go_air(-19 * S if high else -13 * S)
                    self.vx = move * speed
                    self.spawn("spark", 3 if high else 1)
                return
            if (k.get("w") or k.get("s")) and self.grab_wall(up=bool(k.get("w"))):
                return
            if move:
                cur = self.current_edge()
                nx = self.cx() + move * speed
                if b != "think":
                    self.base = "walk"
                self.set_feet(nx, self.feet())
                if cur[3] is not None and not (cur[1] - 4 <= self.cx() <= cur[2] + 4):
                    self.go_air(0)                                 # walked off the end
                    self.vx = move * speed
                else:
                    self.repin()
            elif b == "walk":
                self.base = "idle"

    def game_air(self, k, move, speed):
        self.vx += (move * speed - self.vx) * 0.2
        if k.get("space") and self.vy > 0 and self.float_left > 0:
            self.vy = min(self.vy + 0.12 * S, 1.4 * S)             # floating down slowly
            self.float_left -= 1
            self.floating = True
            if self.t % 12 == 0:
                self.spawn("spark", 1)
        else:
            self.vy = min(self.vy + 0.7 * S, 20 * S)
            self.floating = False
        prev, cx = self.feet(), self.cx()
        new, nx = prev + self.vy, cx + self.vx
        if self.vy > 0:
            hits = [e for e in self.edges if e[1] <= nx <= e[2] and prev - 1 <= e[0] <= new
                    and not (self.t < self.ignore_until and abs(e[0] - self.ignore_y) < 4)]
            if hits:
                self.land(min(hits, key=lambda e: e[0]), nx)
                self.float_left, self.floating, self.vx = FLOAT, False, 0.0
                return
        if k.get("w") and self.grab_wall(up=True):
            return
        self.set_feet(nx, new)
        if self.feet() < new - 1:                                  # the screen bottom
            self.land(self.edges[0], self.cx())
            self.float_left, self.floating, self.vx = FLOAT, False, 0.0

    def grab_wall(self, up):
        if self.t < self.no_grab_until:
            return False
        cx, fy, pad = self.cx(), self.feet(), 13 * P / 2
        best = None
        for w in self.walls:
            x, y0, y1, kind = w
            if abs(x - cx) > pad + 14 * S:
                continue
            if up and not (y0 < fy - 4 and y1 >= fy - 8 * P):
                continue
            if not up and not (y1 > fy + 4 and y0 <= fy):
                continue
            if best is None or abs(x - cx) < best[0]:
                best = (abs(x - cx), w)
        if not best:
            return False
        x, y0, y1, kind = best[1]
        side = (-1 if x <= self.area[0] else 1) if kind == "screen" else (1 if x >= cx else -1)
        self.set_feet(x - side * pad, fy)
        self.base, self.perch, self.vx, self.air_top = "climb", None, 0.0, None
        self.climb = {"side": side, "goal": fy, "hwnd": kind, "hold": 1, "game": True, "wall": best[1]}
        self.float_left = FLOAT
        return True

    def game_climb(self, k, move, space_down, speed):
        c = self.climb
        x, y0, y1, kind = c["wall"]
        side, fy, pad = c["side"], self.feet(), 13 * P / 2
        if space_down:                                              # wall jump
            self.go_air(-11 * S)
            self.vx = -side * 4 * S
            self.no_grab_until = self.t + 15
            return
        if move == -side:                                           # away from the wall: drop and move that way
            self.go_air(0)
            self.vx = move * speed
            self.no_grab_until = self.t + 15
            return
        climb = 2 * S ** 0.5
        dy = (climb if k.get("s") else 0) - (climb * (2 if self.fast_climb else 1) if k.get("w") else 0)
        c["hold"] = 0 if dy else 1
        c["goal"] = fy + dy * 10
        if not dy:
            return
        nf = fy + dy
        if dy < 0 and nf <= y0:                                     # top of the wall: step onto a ledge
            top_x = self.cx() + side * (pad + 8)
            e = self.edge_near(top_x, y0, None, 14)
            if e:
                self.land(e, top_x)
                return
            nf = y0
        if dy > 0:
            hits = [e for e in self.edges if e[1] <= self.cx() <= e[2] and fy < e[0] <= nf]
            if hits:
                self.land(min(hits, key=lambda e: e[0]), self.cx())
                return
            if nf >= y1:
                self.go_air(S)
                return
        self.set_feet(self.cx(), nf)

    def toggle_lines(self):
        self.mem["lines"] = not self.mem.get("lines", True)
        self.save()
        self.say("I'll look for lines inside apps too!" if self.mem["lines"] else "Okay, only window edges now.")

    def feet(self):
        return self.y + H - round(6 * S)

    def cx(self):
        return self.x + W / 2

    def set_feet(self, cx, fy):
        self.x = cx - W / 2
        self.y = fy - (H - round(6 * S))
        self.place()
        if self.base in ("fall", "air", "jump"):                  # remember the highest point of a fall
            self.air_top = fy if self.air_top is None else min(self.air_top, fy)

    def win(self, hwnd):
        return next((w for w in self.wins if w[0] == hwnd), None)

    def current_edge(self):
        cx = self.cx()
        hwnd = self.perch[0] if self.perch else None
        mine = [e for e in self.edges if e[3] == hwnd and e[1] - 4 <= cx <= e[2] + 4]
        if mine:
            return min(mine, key=lambda e: abs(e[0] - self.feet()))
        return self.edges[0] if self.edges else (self.area[3], self.area[0], self.area[2], None)

    def repin(self):
        """Remember where on its window it stands, so it can ride along when the window moves."""
        if self.perch and self.perch[0] not in (None, "line"):
            w = self.win(self.perch[0])
            if w:
                self.perch = (w[0], self.cx() - w[1])

    def refresh_world(self, force=False):
        """Update the ledges (to stand on) and walls (to climb) around the pet."""
        on_window = self.perch and self.perch[0] is not None
        busy = on_window or self.base in ("fall", "jump", "air", "climb")
        if not (force or self.t % (3 if busy else 15) == 0 or not self.edges):
            return
        self.wins = scan_windows()
        self.edges = find_ledges(self.wins, self.area, 8 * P, 8 * P + 4)
        l, top, r, b = self.area
        self.walls = [(l, top, b, "screen"), (r, top, b, "screen")]
        for h, wl, wtop, wr, wb in self.wins:
            if wtop >= top:
                self.walls += [(wl, wtop, wb, h), (wr, wtop, wb, h)]
        if self.mem.get("lines", True):
            cx, fy = self.cx(), self.feet()
            x0, x1 = max(l, int(cx - 650 * S)), min(r, int(cx + 650 * S))
            y0, y1 = max(top, int(fy - 520 * S)), min(b, int(fy + 520 * S))
            self.seer.region = (x0, y0, x1 - x0, y1 - y0, 8 * P)
            self.edges += [e for e in self.seer.lines
                           if top + 8 * P + 4 <= e[0] < b - 6 and e[2] - e[1] >= 8 * P]
            self.walls += [w for w in self.seer.vlines if w[2] - w[1] >= 10 * P and l + 4 < w[0] < r - 4]
        else:
            self.seer.region = None
        if self.perch and self.base in ("idle", "walk", "sleep", "think"):
            self.follow_perch()

    def play_update(self):
        self.refresh_world()
        b = self.base
        if b in ("fall", "air"):
            self.base = "fall"
            self.fall_step()
        elif b == "jump":
            self.jump_step()
        elif b == "climb":
            if self.climb.get("game"):
                self.start_fall()
            else:
                self.climb_step()
        elif b in ("idle", "walk"):
            if self.perch is None:
                self.start_fall()
            elif self.plan and not self.chat and not self.mood and not self.action:
                self.run_plan()

    def edge_near(self, cx, y, hwnd=None, tol=12):
        found = [e for e in self.edges if e[1] - 4 <= cx <= e[2] + 4 and abs(e[0] - y) <= tol
                 and (hwnd is None or e[3] == hwnd)]
        return min(found, key=lambda e: abs(e[0] - y)) if found else None

    def follow_perch(self):
        hwnd, dx = self.perch
        cx, fy = self.cx(), self.area[3]
        if hwnd == "line":
            near = [e for e in self.edges if e[3] == "line" and abs(e[0] - self.feet()) <= 8
                    and e[1] - 4 <= cx <= e[2] + 4]
            if near:
                self.line_miss = 0
                fy = min(near, key=lambda e: abs(e[0] - self.feet()))[0]
            elif self.seer.stamp != self.line_seen:      # a fresh look, and the line is gone
                self.line_seen = self.seer.stamp
                self.line_miss += 1
                if self.line_miss >= 2:
                    return self.start_fall(oops=True)
                return
            else:
                return
        elif hwnd is not None:
            w = self.win(hwnd)
            if not w:
                return self.start_fall(oops=True)
            cx, fy = w[1] + dx, w[2]
            if not any(e[3] == hwnd and e[1] - 4 <= cx <= e[2] + 4 for e in self.edges):
                return self.start_fall(oops=True)            # its edge got covered or went away
        if abs(cx - self.cx()) > 0.5 or abs(fy - self.feet()) > 0.5:
            self.set_feet(cx, fy)

    def start_fall(self, oops=False):
        if self.base == "sleep":
            self.wake()
        self.base, self.perch, self.plan, self.vy = "fall", None, [], 0.0
        self.action, self.target = None, None
        if oops and random.random() < 0.7:
            self.say(random.choice(["Whoa!", "Hey, my floor!", "Eek!", "Where did it go?!"]))

    def fall_step(self):
        prev, cx = self.feet(), self.cx()
        self.vy = min(self.vy + 0.7 * S, 20 * S)
        new = prev + self.vy
        hits = [e for e in self.edges if e[1] <= cx <= e[2] and prev - 1 <= e[0] <= new]
        if hits:
            self.land(min(hits, key=lambda e: e[0]), cx, hard=self.vy > 13 * S)
        else:
            self.set_feet(cx, new)
            if self.feet() < new - 1:                      # stopped by the screen bottom
                self.land(self.edges[0], cx)

    def land(self, edge, cx, hard=False):
        y, x0, x1, hwnd = edge
        self.set_feet(cx, y)
        self.base, self.vy = "idle", 0.0
        w = self.win(hwnd) if hwnd not in (None, "line") else None
        self.perch = ("line", 0) if hwnd == "line" else (hwnd, cx - w[1]) if w else (None, 0)
        self.line_miss, self.line_seen = 0, self.seer.stamp
        dropped = y - self.air_top if self.air_top is not None else 0
        self.air_top = None
        if dropped > 300 * S:                                      # only a fall from high up makes it dizzy
            self.set_mood("dizzy", 40)
            if random.random() < 0.5:
                self.say(random.choice(["Oof!", "Stuck the landing! Mostly.", "Ow, my pixels."]))

    def start_jump(self, x, y, hwnd):
        x0, y0 = self.cx(), self.feet()
        dist = math.hypot(x - x0, y - y0)
        self.jump = {"x0": x0, "y0": y0, "x1": x, "y1": y, "hwnd": hwnd, "k": 0,
                     "n": int(22 + dist / (12 * S)), "h": 50 * S + max(0, y0 - y) * 0.4}
        self.base, self.perch, self.facing = "jump", None, (1 if x > x0 else -1)

    def jump_step(self):
        j = self.jump
        j["k"] += 1
        u = j["k"] / j["n"]
        if u >= 1:
            e = next((e for e in self.edges if e[3] == j["hwnd"] and e[1] - 4 <= j["x1"] <= e[2] + 4
                      and abs(e[0] - j["y1"]) < 40), None)
            if e:
                self.land(e, j["x1"])
            else:                                          # the ledge moved away mid-air
                self.set_feet(j["x1"], j["y1"])
                self.start_fall(oops=True)
            return
        self.set_feet(j["x0"] + (j["x1"] - j["x0"]) * u,
                      j["y0"] + (j["y1"] - j["y0"]) * u - j["h"] * 4 * u * (1 - u))

    def climb_step(self):
        c = self.climb
        if c.get("hold"):
            c["hold"] -= 1
            if c["hold"] == 0:
                near = self.reachable()
                r = random.random()
                if near and r < 0.45:
                    self.leap_to(random.choice(near))
                elif r < 0.75:
                    c["goal"] = c["back"][0] if c.get("back") else self.area[3]   # climb back down
                    self.say(random.choice(["Going down~", "Careful, careful..."]))
                else:
                    self.start_fall()
                    self.say(random.choice(["Wheee!", "Geronimo!", "Catch me!"]))
            return
        fy, goal, sp = self.feet(), c["goal"], 1.5 * S * self.pace()
        if abs(goal - fy) <= sp:
            self.set_feet(self.cx(), goal)
            h = c.get("hwnd")
            top_x = self.cx() + c["side"] * (13 * P / 2 + 8)
            back = c.get("back")
            if goal >= self.area[3] - 1:
                self.land(self.edges[0], self.cx())
            elif back and abs(goal - back[0]) < 1:            # back down where it started
                e = self.edge_near(self.cx(), goal, back[3])
                self.land(e, self.cx()) if e else self.start_fall()
            elif h not in (None, "screen") and self.edge_near(top_x, goal, None if h == "line" else h,
                                                               12 if h == "line" else 30):
                self.land(self.edge_near(top_x, goal, None if h == "line" else h, 12 if h == "line" else 30), top_x)
                if random.random() < 0.5:
                    self.say(random.choice(["Made it!", "Nice view up here.", "I climbed this!"]))
            elif h not in (None, "screen", "line"):
                self.start_fall(oops=True)
            else:
                c["hold"] = random.randint(60, 150)
                if random.random() < 0.5:
                    self.say(random.choice(["Look how high I am!", "Hanging out. Literally.", "Hold on... hold on..."]))
            return
        self.set_feet(self.cx(), fy + (sp if goal > fy else -sp))

    def reachable(self):
        """Ledges it can jump to from here."""
        cx, fy, pad = self.cx(), self.feet(), 13 * P / 2
        cur = self.current_edge() if self.perch else None
        out = []
        for e in self.edges:
            if e == cur or e[2] - e[1] < 2 * pad:
                continue
            nx = max(e[1] + pad, min(cx, e[2] - pad))
            if abs(nx - cx) <= 420 * S and -380 * S <= e[0] - fy <= 450 * S and abs(e[0] - fy) > 6:
                out.append(e)
        return out

    def leap_to(self, e):
        pad = 13 * P / 2
        x = max(e[1] + pad, min(self.cx() + random.uniform(-80, 80) * S, e[2] - pad))
        self.climb = {}
        self.start_jump(x, e[0], e[3])

    def play_move(self, name):
        cx, pad = self.cx(), 13 * P / 2
        cur = self.current_edge()
        l, t, r, b = self.area
        if name == "ledgewalk" and cur[2] - cur[1] > 2 * pad:
            self.plan = [("walk", random.uniform(cur[1] + pad, cur[2] - pad))]
        elif name == "leap":
            near = self.reachable()
            if near:
                self.leap_to(random.choice(near))
        elif name == "drop":
            end = cur[1] - 2 if abs(cx - cur[1]) < abs(cx - cur[2]) else cur[2] + 2
            self.plan = [("walk", end), ("fall",)]
            if random.random() < 0.4:
                self.say(random.choice(["Going down!", "Bye, ledge!"]))
        elif name == "climb":
            fy = self.feet()
            options = []
            for x, y0, y1, kind in self.walls:
                if not (y0 < fy - 6 * P and y1 >= fy - 6):
                    continue                               # it must rise above and reach down to here
                side = -1 if kind == "screen" and x <= l else 1 if kind == "screen" else (1 if x >= cx else -1)
                stand = x - side * pad
                if cur[1] - 4 <= stand <= cur[2] + 4 and abs(stand - cx) < 900 * S:
                    options.append((x, side, y0, kind, stand))
            if not options:
                return
            x, side, y0, kind, stand = random.choice(options)
            if kind == "screen":
                top, bottom = t + 10 * P + 60 * S, fy - 120 * S
                if bottom <= top:
                    return
                goal = random.uniform(top, bottom)
            else:
                goal = max(y0, t + 8 * P + 4)
            self.plan = [("walk", stand), ("climb", side, goal, kind)]

    def run_plan(self):
        step = self.plan[0]
        if step[0] == "walk":
            if self.t < self.pause_until:                        # stopped for a moment to look around
                self.base = "idle"
                return
            if random.random() < 1 / 260:
                self.pause_until = self.t + random.randint(15, 50)
                return
            d, sp = step[1] - self.cx(), 1.6 * S * self.pace()
            if abs(d) <= sp:
                self.set_feet(step[1], self.feet())
                self.base = "idle"
                self.plan.pop(0)
            else:
                self.base, self.facing = "walk", (1 if d > 0 else -1)
                before = self.cx()
                self.set_feet(before + sp * self.facing, self.feet())
                if abs(self.cx() - before) < 0.1:          # blocked by the screen edge: close enough
                    self.base = "idle"
                    self.plan.pop(0)
            self.repin()
        elif step[0] == "fall":
            self.plan.pop(0)
            self.start_fall()
        elif step[0] == "climb":
            _, side, goal, h = self.plan.pop(0)
            back = self.current_edge()
            self.base, self.perch = "climb", None
            self.climb = {"side": side, "goal": goal, "hwnd": h, "hold": 0, "back": back}

    def update_away(self):
        """When no one is at the computer, it switches between staying still and wandering by itself,
        every few minutes. When someone is back, their own choice returns."""
        now = time.monotonic()
        away = idle_seconds() > AWAY_AFTER and not self.game
        if away and not self.away:
            self.away, self.still_choice = True, self.still
            self.away_switch = now + random.randint(60, 150)
        elif not away and self.away:
            self.away = False
            if self.still != self.still_choice:
                self.still, self.target, self.wander_left = self.still_choice, None, 0
        elif self.away and now >= self.away_switch and not self.chat and self.base in ("idle", "walk"):
            self.still = not self.still
            self.target, self.wander_left = None, 0
            self.next_action = min(self.next_action, self.t + 30 * random.randint(2, 6))
            self.away_switch = now + random.randint(90, 240)

    def toggle_still(self):
        self.still = not self.still
        self.target = None
        self.say("Okay, I'll stay right here." if self.still else "Off I go!")

    def toggle_sleep(self):
        if self.base == "sleep":
            self.wake()
            self.say("I'm up!")
        else:
            self.sleep(nap=True)

    def forget(self):
        self.archive()
        self.save()
        self.set_mood("surprised", 30)
        self.say("Fresh start! The old chat is saved; /resume brings it back.")

    def bye(self):
        self.close_chat()
        self.save()
        self.set_mood("love", 999)
        self.spawn("heart", 4)
        self.say(f"Bye, {self.name()}! See you soon.")
        self.root.after(1600, self.root.destroy)

    # ---------- behaviour ----------
    def set_mood(self, mood, frames):
        self.mood, self.mood_until = mood, self.t + frames
        self.action = None
        fx = {"love": ("heart", 4), "excited": ("spark", 5), "surprised": ("spark", 2), "sleepy": ("z", 1)}
        if mood in fx:
            self.spawn(*fx[mood])

    def sleep(self, nap=False):
        self.nap_until = self.t + 30 * random.randint(120, 240)
        self.close_chat()
        self.base, self.action, self.mood, self.target = "sleep", None, None, None
        self.say("Zzz...")

    def wake(self):
        self.base = "idle"
        self.last_touch = self.t

    def save(self):
        self.mem["last_seen"] = dt.datetime.now().isoformat(timespec="seconds")
        self.mem["history"] = self.mem["history"][-30:]
        try:
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.mem, f, ensure_ascii=False, indent=1)
            os.replace(tmp, STATE_FILE)
        except Exception:
            pass

    def bounds(self):
        l, t, r, b = self.area
        half = 13 * P / 2 + 4
        return (l - W / 2 + half, r - W / 2 - half,
                t - (H - 8 * P - 6 * S), b - H + 6 * S)

    def place(self):
        x0, x1, y0, y1 = self.bounds()
        self.x = max(x0, min(self.x, x1))
        self.y = max(y0, min(self.y, y1))
        self.root.geometry(f"{W}x{H}+{int(self.x)}+{int(self.y)}")

    def pointer(self):
        return self.root.winfo_pointerx(), self.root.winfo_pointery()

    def center(self):
        return self.x + W / 2, self.y + self.oy + 4 * P

    def cursor_dist(self):
        (px, py), (cx, cy) = self.pointer(), self.center()
        return math.hypot(px - cx, py - cy)

    def pick_target(self, chase=False):
        x0, x1, y0, y1 = self.bounds()
        if chase:
            px, py = self.pointer()
            tx, ty = px - W / 2 + random.uniform(-90, 90) * S, py - self.oy - 4 * P + 70 * S
            self.speed = 2.6 * S * self.pace()
        else:
            tx = self.x + random.uniform(-380, 380) * S
            ty = self.y + random.uniform(-260, 260) * S
            self.speed = 1.6 * S * self.pace()
        self.target = (max(x0, min(tx, x1)), max(y0 + 120 * S, min(ty, y1)))

    def wander(self):
        if self.target is None:
            return
        if self.t < self.pause_until:
            self.base = "idle"
            return
        if random.random() < 1 / 260:
            self.pause_until = self.t + random.randint(15, 50)
            return
        tx, ty = self.target
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        if d < self.speed + 0.5:
            self.target = None
            self.base = "idle"
            if self.wander_left > 0 and not self.still:
                self.wander_left -= 1
                self.pick_target()
            return
        self.base = "walk"
        self.facing = 1 if dx > 0 else -1
        self.x += dx / d * self.speed
        self.y += dy / d * self.speed
        self.place()

    def state(self):
        return self.mem.get("state", "calm") if self.mem.get("state", "calm") in STATES else "calm"

    def pace(self):
        return STATES[self.state()][1]

    def start_cycle(self, first=None, announce=None):
        """A 15-minute circle: Lively, Calm and Sleepy, 5 minutes each, in a random order (any of the 6).
        `first` puts a chosen state at the front, for when it's picked from the menu."""
        names = list(STATES)
        if first:
            order = [first] + random.sample([n for n in names if n != first], 2)
        else:
            order = random.sample(names, 3)
            while order[0] == self.state():                    # never the same state twice in a row
                order = random.sample(names, 3)
        self.cycle, self.slot, self.slot_end = order, 0, time.monotonic() + SLOT
        self.set_state(order[0], announce)

    def first_state(self):
        """Where its day starts depends on the time, with some chance mixed in."""
        hour = dt.datetime.now().hour
        weights = ((5, 4, 1) if 6 <= hour < 11 else (4, 4, 2) if hour < 18 else
                   (2, 5, 3) if hour < 23 else (1, 3, 6))
        if hour < 6:
            weights = (1, 3, 6)
        return random.choices(list(STATES), weights=weights)[0]

    def update_state(self):
        if time.monotonic() < self.slot_end:
            return
        if self.slot + 1 >= len(self.cycle):
            self.start_cycle()
        else:
            self.slot += 1
            self.slot_end = time.monotonic() + SLOT
            self.set_state(self.cycle[self.slot])

    def minutes_left(self):
        return max(1, round((self.slot_end - time.monotonic()) / 60))

    def set_state(self, new, announce=None):
        old, self.mem["state"] = self.state(), new
        lo, hi = STATES[new][2]
        self.next_action = self.t + 30 * random.randint(lo, hi)
        if self.base == "sleep" and new != "sleepy":
            self.wake()
            self.action, self.action_start, self.action_until = "stretch", self.t, self.t + 55
            self.say("Mmm... good nap.")
        elif old != new and (announce or (announce is None and random.random() < 0.5)) and self.base != "sleep":
            if new == "sleepy":
                self.action, self.action_start, self.action_until = "yawn", self.t, self.t + 50
            else:
                self.set_mood("excited" if new == "lively" else "calm", 40)
            self.say(random.choice(STATE_LINES[new]))
        self.save()

    def choose_state(self, name):
        """Preview a state now for about 5 minutes; the circle goes on from there."""
        self.start_cycle(first=name, announce=True)

    def random_action(self):
        now = dt.datetime.now()
        night = now.hour >= 23 or now.hour < 6
        tired = self.mem["energy"] < 35
        near = self.cursor_dist() < 300 * S
        state = self.state()
        col = list(STATES).index(state)
        weights = {name: w[col] for name, w in WEIGHTS.items()}
        play, moving = self.playing(), not self.still
        for name in ("wave", "chase"):
            weights[name] *= near
        for name in ("chase", "wander"):
            weights[name] *= (not play) and moving
        for name in ("ledgewalk", "leap", "climb", "drop"):
            weights[name] *= play and moving
        if play and self.current_edge()[3] is None:
            weights["drop"] = 0
        weights["stargaze"] *= 3 if night else 1
        weights["yawn"] *= 2 if night or tired else 1
        name = random.choices(list(weights), weights=list(weights.values()))[0]
        lo, hi = STATES[state][2]
        self.next_action = self.t + 30 * random.randint(lo, hi)
        if name in ("ledgewalk", "leap", "climb", "drop"):
            self.play_move(name)
            return
        if name == "wander":
            self.wander_left = random.randint(0, 4)             # a few hops in a row, how many is random
            self.pick_target()
            return
        if name == "chase":
            self.pick_target(chase=True)
            if random.random() < 0.4:
                self.say(random.choice(["Wait for me!", "Where are you going?", "Hehe, I'm following you."]))
            return
        r = random.randint
        frames = {"look": 80, "hum": 150, "stretch": 55, "hop": 40, "sit": 30 * r(5, 10),
                  "yawn": 50, "turn": 75, "thought": 100, "sneeze": 45, "wave": 60, "dance": 150,
                  "laptop": 30 * r(10, 25), "read": 30 * r(10, 22), "tea": 30 * r(8, 15), "piano": 30 * r(6, 12),
                  "workout": 30 * r(5, 9), "fishing": 30 * r(12, 25), "stargaze": 30 * r(8, 15),
                  "meditate": 30 * r(8, 16), "selfie": 90}[name]
        self.action, self.action_start, self.action_until = name, self.t, self.t + frames
        if name == "hum" and random.random() < 0.5:
            self.say(random.choice(HUMS))
        elif name == "thought":
            self.say(random.choice(THOUGHTS + self.pm()["thoughts"]))
        elif name == "wave" and random.random() < 0.6:
            self.say(random.choice(["Hi!", "Hello~", f"Hey {self.name()}!"]))
        elif name == "sneeze":
            self.root.after(800, self.achoo)
        elif name == "stretch" and random.random() < 0.4:
            self.root.after(1300, lambda: self.say("Mmmm~"))
        elif name == "yawn" and random.random() < 0.4:
            self.root.after(1200, lambda: self.say(random.choice(["*yawn*", "So sleepy..."])))
        elif name in ACTION_LINES and random.random() < 0.35:
            self.say(random.choice(ACTION_LINES[name]))
        if name == "fishing":
            self.root.after(frames * 33 - 500, self.catch)
        elif name == "selfie":
            self.root.after(1500, self.flash)

    def catch(self):
        if self.action == "fishing":
            self.spawn("spark", 2)
            self.say(random.choice(CATCHES))

    def flash(self):
        if self.action == "selfie":
            self.spawn("flash", 4, W / 2 + 5.5 * P, self.oy)
            if random.random() < 0.6:
                self.say(random.choice(FLASHES))

    def achoo(self):
        if self.action == "sneeze":
            self.spawn("spark", 3)
            self.say(random.choice(["Achoo!", "Achoo! ...Excuse me.", "ACHOO! Pixels everywhere."]))

    def watch_cursor(self):
        px, py = self.pointer()
        moved = math.dist((px, py), self.last_ptr)
        self.last_ptr = (px, py)
        if moved < 2:
            self.still_frames += 1
        else:
            if self.still_frames > 90 and moved > 20 and self.cursor_dist() < 500 * S and not self.action:
                self.glance = (1, 1 if px >= self.center()[0] else -1)        # "hm? what was that?"
                self.glance_until = self.t + random.randint(35, 70)
            self.still_frames = 0
        self.trail = (self.trail + [(px, py)])[-10:]
        speed = sum(math.dist(a, b) for a, b in zip(self.trail, self.trail[1:]))
        if speed > 1800 * S and self.cursor_dist() < 260 * S and self.t - self.cooldown.get("shake", -9999) > 600:
            self.cooldown["shake"] = self.t
            self.set_mood("surprised", 40)
            self.say(random.choice(["Whoa! Easy there!", "Eek!", "So fast!"]))
            return
        x0, y0 = self.x + self.ox, self.y + self.oy
        inside = x0 <= px <= x0 + 13 * P and y0 <= py <= y0 + 8 * P
        self.hover = self.hover + 1 if inside else 0
        if self.hover == 45 and not self.mood and self.t - self.cooldown.get("hover", -9999) > 900:
            self.cooldown["hover"] = self.t
            self.set_mood("shy", 70)
            self.say(random.choice(["Hehe.", "Hi there.", "You're staring (^_^)", "Pat pat?"]))

    def check_apps(self):
        title = window_title()
        for key, line in {**APPS, **self.pm()["apps"]}.items():
            if key in title and self.t - self.cooldown.get(key, -10 ** 9) > 30 * 3600:
                self.cooldown[key] = self.t
                self.set_mood("excited", 40)
                self.say(line)
                return

    def update_view(self):
        """Pick the angle it should face, then turn toward it one step at a time (never a jump)."""
        t, s, a, m = self.t, self.base, self.action, self.mood
        k = t - self.action_start
        situation = (s, a, m)
        toward = 1 if self.pointer()[0] >= self.center()[0] else -1
        if situation != self.view_sit:                       # new situation: roll the dice again
            self.view_sit = situation
            self.view_pick = (random.random(), toward if a == "wave" else random.choice((-1, 1)))
        if a and (self.action_until - self.action_start) > 150 and t >= self.reroll_at:
            if self.reroll_at and random.random() < 0.5:            # a long activity: shift position now and then
                keep = self.view_pick[1] if random.random() < 0.75 else -self.view_pick[1]
                self.view_pick = (random.random(), keep)
            self.reroll_at = t + random.randint(120, 270)
        elif not a:
            self.reroll_at = 0
        r, rdir = self.view_pick
        if s in ("walk", "air", "jump", "fall", "climb", "drag"):   # moving or climbing: always the original front view
            self.view = 0
            if self.facing:
                self.view_dir = self.facing
            return
        if self.game or (t < self.hold_until and not a and not m):   # keep the final pose (game, or just after a drag)
            if self.view == 2:
                self.view = 1                                # but never a bare side view while still
            return
        if self.chat or self.hover > 20 or m in ("happy", "excited", "love", "shy", "surprised"):
            target = (0, self.view_dir)
        elif m in ("sad", "think") or s == "think":
            target = (1, rdir)
        elif s == "sleep":
            target = (0 if r < .6 else 1, rdir)
        elif a == "turn":
            target = (4, rdir) if 12 < k < 63 else (0, rdir)
        elif a == "look":
            target = (0, 1) if (k // 25) % 3 == 2 else (1, -1 if (k // 25) % 2 else 1)
        elif a == "dance":
            target = SPIN_STEPS[(k // 6) % 8] if (k // 48) % 2 == 0 else (0, 1)
        elif a:
            options = ACTION_VIEWS.get(a, [(0, .6), (1, 1)])
            target = (next(v for v, chance in options if r <= chance), rdir)
        else:                                                # idle: glances now and then
            if t >= self.glance_until:
                lo = {"lively": 45, "calm": 75, "sleepy": 110}[self.state()]
                self.glance_until = t + random.randint(lo, lo * 3)
                g = random.random()
                self.glance = ((0, self.view_dir) if g < .55 else
                               (1, toward if random.random() < .6 else -toward) if g < .96 else
                               (3, random.choice((-1, 1))))
            target = self.glance
        floating = not self.playing()
        side_ok = target[0] == 2 and a in SCENES and not floating    # 90° only inside an activity's scene, never floating
        if target[0] == 2 and not side_ok:
            target = (1, target[1])
        if floating and self.view == 2:
            self.view = 1
        step = {"lively": 3, "calm": 4, "sleepy": 5}[self.state()]
        if t % step:
            return
        idx, d = target
        cur, cd = self.view, self.view_dir
        if (cur, cd) == (idx, d) or (cur == idx == 0) or (cur == idx == 4):
            if cur in (0, 4):
                self.view_dir = d
            return
        if cd != d and cur not in (0, 4):                    # turning the other way: pass through front or back
            self.view = cur - 1 if cur <= 2 else cur + 1
        elif cur in (0, 4) and cd != d:
            self.view_dir = d
        else:
            self.view = cur + (1 if idx > cur else -1)
            if self.view == 2 and not side_ok:               # turning around skips the side view
                self.view += 1 if idx > cur else -1

    def tick(self):
        self.t += 1
        t = self.t
        self.poll_claude()
        if self.mood and t >= self.mood_until:
            self.mood = None
        if self.action and t >= self.action_until:
            self.action = None
        if self.bubble and t >= self.bubble_end:
            self.next_bubble()

        now = dt.datetime.now()
        night = now.hour >= 23 or now.hour < 6
        if t % 30 == 0:
            e = self.mem["energy"]
            if self.base == "sleep":
                e = min(100.0, e + 0.25)
            else:
                e = max(0.0, e - (0.04 if night else 0.02))
            self.mem["energy"] = e
        if t % (30 * 60) == 0:
            self.save()
            self.maybe_sync()
        if self.game and self.base != "drag":
            self.game_update()
        elif self.playing() and self.base != "drag":
            self.play_update()

        if t % 30 == 0 and not self.game:
            self.update_state()
        if t % 30 == 15:
            self.update_mode()
        if t % 30 == 20:
            self.update_away()
        if self.base == "sleep":
            if t % 45 == 0:
                self.spawn("z", 1)
            if self.state() != "sleepy" and t >= self.nap_until:          # a nap you asked for is over
                self.wake()
                self.action, self.action_start, self.action_until = "stretch", t, t + 55
                self.say("Mmm... good nap.")
            elif self.state() == "sleepy" and random.random() < 1 / (30 * 120):   # half awake for a moment
                self.wake()
                self.action, self.action_start, self.action_until = random.choice(
                    [("yawn", t, t + 50), ("tea", t, t + 30 * 8), ("stretch", t, t + 55)])
                if random.random() < 0.5:
                    self.say(random.choice(["*yawn* ...just a moment.", "Mm? ...still sleepy.", "Just a sip of tea..."]))
        elif self.base in ("idle", "walk") and not self.chat:
            self.watch_cursor()
            if not self.mood and not self.action and not self.game and t >= self.hold_until:
                if self.base == "idle" and t >= self.next_action:
                    self.random_action()
                self.wander()
            if self.base == "idle" and t >= self.next_talk and not self.bubble and not self.game:
                lo, hi = STATES[self.state()][3]
                self.next_talk = t + 30 * random.randint(lo, hi)
                self.say(random.choice(self.lines()))
            if t % 150 == 0 and self.base == "idle":
                self.check_apps()
            idle_for = t - self.last_touch
            if (self.state() == "sleepy" and self.base == "idle" and not self.action and not self.mood
                    and not self.game and idle_for > 30 * 90):            # it only falls asleep when sleepy
                self.sleep()

        a = self.action
        side = self.view in (1, 2) and not self.mood                # the scene is set aside: effects come from there
        if (a == "hum" and t % 18 == 0) or (a == "dance" and t % 22 == 0) or (a == "piano" and t % 12 == 0 and not side):
            self.spawn("note", 1)
        elif a == "piano" and t % 12 == 0:
            self.spawn("note", 1, *self.scene_spot(12.6 if self.view == 1 else 11.4, 3.4 if self.view == 1 else 2.8))
        elif a == "laptop" and t % 40 == 0:
            if side:
                self.spawn("code", 1, *self.scene_spot(14.3 if self.view == 1 else 14.0, 2.4))
            else:
                self.spawn("code", 1, W / 2 + random.uniform(-2, 2) * P, self.oy + 3 * P)
        elif a == "tea" and t % 20 == 0:
            col, row = self.tea_spot((t - self.action_start) % 120 > 80)
            self.spawn("steam", 1, *self.scene_spot(col + 0.6, row - 0.2))
        elif a == "workout" and t % 25 == 0:
            self.spawn("drop", 1, W / 2 + random.choice((-1, 1)) * 4 * P, self.oy + P)
        elif a == "stargaze" and t % 30 == 0:
            self.spawn("star", 1, W / 2 + random.uniform(-9, 9) * P, self.oy - random.uniform(2, 7) * P)
        elif a == "meditate" and t % 60 == 0:
            self.spawn("spark", 1)

        if self.blink > 0:
            self.blink -= 1
        elif t == self.blink2:                                   # the second of a double blink
            self.blink = 4
        elif random.random() < 0.012:
            self.blink = 5
            if random.random() < 0.2:
                self.blink2 = t + 9

        for p in self.parts:
            p["age"] += 1
            p["x"] += p["vx"] + (math.sin(p["age"] / 6) * 0.6 * S if p["k"] in ("note", "steam") else 0)
            p["y"] += p["vy"]
            if p["k"] == "drop":
                p["vy"] += 0.12 * S
        self.parts = [p for p in self.parts if p["age"] < p["life"]]

        if self.chat:
            self.place_chat()
        self.update_view()
        self.draw()
        self.root.after(33, self.tick)

    # ---------- drawing ----------
    def spawn(self, kind, n=1, x=None, y=None):
        for _ in range(n):
            if x is not None:
                px_, py_ = x + random.uniform(-0.4, 0.4) * P, y
            elif kind == "z":
                px_, py_ = W / 2 + 6 * P, self.oy
            else:
                px_, py_ = W / 2 + random.uniform(-6, 6) * P, self.oy + random.uniform(0, 3) * P
            vx, vy, life = random.uniform(-0.7, 0.7) * S, -random.uniform(0.7, 1.5) * S, random.randint(45, 75)
            if kind == "z":
                vx = random.uniform(0.2, 0.6) * S
            elif kind == "steam":
                vx, vy = random.uniform(-0.2, 0.2) * S, -0.5 * S
            elif kind == "star":
                vx, vy, life = 0, 0, random.randint(25, 50)
            elif kind == "drop":
                vx, vy, life = random.uniform(-1, 1) * S, -1.2 * S, 30
            elif kind == "flash":
                life = 20
            self.parts.append({"k": kind, "x": px_, "y": py_, "age": 0, "life": life, "vx": vx, "vy": vy,
                               "ch": random.choice(SPARKS[kind][0])})

    def px(self, col, row, w=1, h=1, color=BODY):
        x0 = self.ox + col * P
        y0 = self.oy + row * P
        self.c.create_rectangle(x0, y0, x0 + w * P, y0 + h * P, fill=color, outline="")

    def draw(self):
        c, t, s, m, a = self.c, self.t, self.base, self.mood, self.action
        c.delete("all")
        k = t - self.action_start
        bob, jx, la, ra, low, tall = 0, 0, 0, 0, 0, 0
        legs, eyes, cheeks, mouth, back = "stand", "open", False, None, False

        # eyes follow the cursor
        e = round(3 * S)
        (px, py), (cx, cy) = self.pointer(), self.center()
        d = math.hypot(px - cx, py - cy) or 1
        lx, ly = round((px - cx) / d * e), round((py - cy) / d * e)

        if s in ("idle", "walk", "think") and not self.playing():
            bob = round(math.sin(t * self.pace() / 12) * 3 * S)
        elif s in ("idle", "think"):                              # standing: just breathing
            bob = -round(max(0, math.sin(t * 2 * math.pi / (100 / self.pace()))) * 1.4 * S)
        if s == "walk":
            legs, lx, ly = "walk", self.facing * e, 0
        elif s == "climb":
            side = self.climb.get("side", 1)
            if self.climb.get("hold"):
                la, ra, legs = -2, -2, "dangle"
                lx, ly = -side * e, 0                       # looking out from the wall
            else:
                la, ra = (-2, 0) if (t // 8) % 2 else (0, -2)
                legs = "walk"
                lx, ly = side * e, (-e if self.climb.get("goal", 0) < self.feet() else e)
        elif s == "fall":
            la, ra, legs, eyes = -2, -2, "dangle", "big"
            if self.vy > 8 * S:
                mouth = "o"
        elif s == "jump":
            la, ra, legs, eyes = -1, -1, "tuck", "happy"
            lx = self.facing * e
        elif s == "air":
            if self.floating:
                la, ra, legs, eyes = -2, -2, "dangle", "happy"
                jx = round(math.sin(t / 6) * 2 * S)
            elif self.vy < 0:
                la, ra, legs, eyes = -1, -1, "tuck", "happy"
            else:
                la, ra, legs, eyes = -2, -2, "dangle", "big"
            lx = self.facing * e
        elif s == "drag":
            bob, la, ra, legs, eyes = round(math.sin(t / 2) * 2 * S), -2, -2, "dangle", "big"
        elif s == "sleep":
            low, legs, eyes, bob = 2, "none", "closed", round(math.sin(t / 30) * 1.5 * S)
        elif s == "think":
            lx, ly, ra = (e if (t // 45) % 2 else -e), -e, -1
        if self.game and s in ("idle", "think") and self.facing:
            lx, ly = self.facing * e, 0                     # game mode: still looking the way it last moved
        if self.chat and s == "idle" and not a and not m:
            lx, ly = 0, e                                   # watching the input box
            if t < self.typing_until:
                bob = round(math.sin(t / 3) * 2 * S)        # nodding along

        if a == "look":
            lx, ly = (e if (k // 20) % 2 else -e), 0
        elif a == "hum":
            eyes, jx = "happy", round(math.sin(t / 8) * 3 * S)
        elif a == "stretch":
            la, ra, tall, eyes = -2, -2, 1, "closed"
        elif a == "hop":
            bob = -round(abs(math.sin(k / 20 * math.pi)) * 12 * S)
        elif a == "sit":
            low, legs = 1, "kick"
        elif a == "yawn":
            eyes, mouth, la, ra = "closed", "yawn", -1, -1
        elif a == "thought":
            lx, ly, ra = e, -e, -1
        elif a == "sneeze":
            if k < 24:
                eyes = "half"
            else:
                eyes, jx = "closed", random.randint(-3, 3)
        elif a == "wave":
            ra = -2 if (t // 6) % 2 else -1
        elif a == "dance":
            la, ra = (-2, 0) if (t // 8) % 2 else (0, -2)
            bob, eyes = -abs(round(math.sin(t / 4) * 6 * S)), "happy"
        elif a == "laptop":                                  # sitting, typing, eyes on the screen
            low, legs, ly = 1, "kick", e
            la, ra = (1, 0) if (t // 4) % 2 else (0, 1)
        elif a == "read":
            low, legs, la, ra = 1, "kick", 1, 1
            lx, ly = round(math.sin(k / 12) * e), e
        elif a == "tea":
            low, legs = 1, "kick"
            if k % 120 > 80:                                 # a sip
                ra, eyes = -1, "happy"
        elif a == "piano":
            low, legs, ly = 1, "kick", e
            la, ra = (0, 1) if (t // 3) % 2 else (1, 0)
            if (k // 45) % 2:
                eyes = "happy"
        elif a == "workout":                                 # jumping jacks
            up = (t // 8) % 2
            la, ra = (-2, -2) if up else (1, 1)
            bob, legs, eyes = (-round(5 * S) if up else 0), "walk", ("closed" if up else "open")
        elif a == "fishing":
            low, legs, ra, lx, ly = 1, "kick", -1, e, e
            if (k // 90) % 3 == 2:
                eyes = "half"
        elif a == "stargaze":
            low, legs, ly, eyes = 1, "kick", -e, "sparkle"
            lx = round(math.sin(k / 30) * e)
        elif a == "meditate":
            eyes, legs, la, ra = "closed", "tuck", 0, 0
            bob = -round((4 + 3 * math.sin(k / 25)) * S)
        elif a == "selfie":
            ra, lx = -2, e
            eyes = "happy" if 40 < k < 75 else "open"

        if m == "happy":
            bob, eyes = -abs(round(math.sin(t / 3) * 10 * S)), "happy"
            la, ra = (-1, 0) if (t // 5) % 2 else (0, -1)
        elif m == "excited":
            bob, eyes = -abs(round(math.sin(t / 2.5) * 16 * S)), "sparkle"
            la, ra = (-2, 0) if (t // 3) % 2 else (0, -2)
        elif m == "love":
            eyes, cheeks, jx = "happy", True, round(math.sin(t / 10) * 3 * S)
            if t % 25 == 0:
                self.spawn("heart", 1)
        elif m == "shy":
            eyes, cheeks, lx, ly, la, ra = "open", True, 0, e, 1, 1
            jx = round(math.sin(t / 14) * 2 * S)
        elif m == "surprised":
            eyes, mouth, la, ra, bob = "big", "o", -1, -1, -round(4 * S)
        elif m == "sad":
            eyes, la, ra, bob = "sad", 1, 1, round(2 * S)
        elif m == "sleepy":
            eyes = "half"
        elif m == "think":
            lx, ly, ra = e, -e, -1
        elif m == "dizzy":
            eyes, jx = "x", round(math.sin(t / 2) * 4 * S)
        if self.blink and eyes in ("open", "sparkle"):
            eyes = "closed"

        self.ox = W // 2 - 13 * P // 2 + jx
        self.oy = H - 8 * P - round(6 * S) + bob + low * P
        self.pet_top = self.oy - tall * P

        # particles behind the bubble
        base_u = max(1, round(P / 4))
        for p in self.parts:
            u = base_u + (p["age"] // 30 if p["k"] == "z" else 1 if p["k"] == "flash" else 0)
            self.glyph(p["ch"], p["x"], p["y"], SPARKS[p["k"]][1], u)

        v, flip = self.view, self.view_dir < 0
        self.reach = {"laptop": 2.2, "piano": 2.0, "read": 1.6}.get(a, 0) if v == 2 and not m else 0
        if v == 2:
            lx = (1 if not flip else -1) * round(e * 0.7)       # in profile it looks ahead
        self.draw_body(v, flip, -tall, la, ra, legs, eyes, lx, ly, cheeks, mouth, k, t)

        if a in ("laptop", "read", "tea", "piano", "fishing", "selfie") and not m:
            self.draw_prop(a, k, t)

        if m == "dizzy":                               # stars around the head
            for i in range(3):
                ang = t / 6 + i * 2.1
                self.glyph("spark", W / 2 + math.cos(ang) * 6 * P, self.pet_top - 0.8 * P + math.sin(ang) * 1.2 * P,
                           GOLD, max(1, round(P / 4)))

        if s == "think":
            if t % 90 == 0 and not self.fixed_verb:
                self.verb = random.choice(VERBS)
            self.draw_bubble(f"{SPIN[(t // 4) % len(SPIN)]} {self.verb}…")
        elif self.bubble:
            self.draw_bubble(self.bubble)
        else:
            self.bubble_box = None

    def glyph(self, name, x, y, color, u):
        """Draw a tiny pixel picture centered at x, y; u is the size of one of its pixels."""
        rows = GLYPHS[name]
        x0, y0 = x - len(rows[0]) * u / 2, y - len(rows) * u / 2
        for r, row in enumerate(rows):
            col = 0
            while col < len(row):
                if row[col] == "X":
                    end = col
                    while end < len(row) and row[end] == "X":
                        end += 1
                    self.c.create_rectangle(x0 + col * u, y0 + r * u, x0 + end * u, y0 + (r + 1) * u,
                                            fill=color, outline="")
                    col = end
                else:
                    col += 1

    def mpx(self, col, row, w=1, h=1, color=BODY):
        """Like px, but mirrored when it faces left."""
        self.px(13 - col - w if self.flip else col, row, w, h, color)

    def draw_body(self, v, flip, top, la, ra, legs, eyes, lx, ly, cheeks, mouth, k, t):
        """The pixel body from one of five angles. Facing left is the mirror image."""
        c = self.c
        face = v in (0, 1, 2)
        if v == 3:                                    # back three-quarter: the 45° shape, seen from behind
            v, flip = 1, not flip
        elif v == 4:
            v = 0
        self.flip = flip
        m = self.mpx
        near, far = ra, la
        body_h = 6 - top
        if legs != "none":
            cols = {0: (3, 5, 7, 9), 1: (3.8, 5.6, 7.4, 9.2), 2: (4.8, 5.9, 7.8, 8.9)}[v]
            for i, col in enumerate(cols):
                h = 2
                if legs == "walk":
                    h = 1 if (t // (3 if self.running else 5)) % 2 == i % 2 else 2
                elif legs == "kick":
                    h = 1.5 if ((t // 10) + i) % 2 else 1
                elif legs == "dangle":
                    h = 2.5 if ((t // 4) + i) % 2 else 2
                elif legs == "tuck":
                    h = 1
                far_leg = (v == 2 and i in (1, 3)) or (v == 1 and i == 0)
                m(col, 6, 1 if v == 0 else 0.9, h, LEG_FAR if far_leg else LEG)
        if v == 0:
            m(3, top, 7, body_h)
            m(4, top, 2, 0.5, LIGHT)
            m(3, 5.5, 7, 0.5, SHADE)
            for col, lift in ((0, la), (10, ra)):
                m(col, 2 + lift, 3, 2)
                m(col, 3.5 + lift, 3, 0.5, SHADE)
        elif v == 1:
            m(1.5, 2 + far, 2.2, 2, ARM_FAR)                     # the far arm, half hidden
            m(1.5, 3.5 + far, 2.2, 0.5, SHADE)
            m(3.4, top, 6.6, body_h)
            m(3.4, top, 1.1, body_h, SIDE_TONE)                 # the side we see at an angle
            m(5.4, top, 1.8, 0.5, LIGHT)
            m(3.4, 5.5, 6.6, 0.5, SHADE)
            m(10, 2 + near, 2.6, 2)
            m(10, 3.5 + near, 2.6, 0.5, SHADE)
        else:
            m(4.2, top, 5.6, body_h)
            m(4.2, top, 0.6, body_h, SIDE_TONE)
            m(6.4, top, 1.8, 0.5, LIGHT)
            m(4.2, 5.5, 5.6, 0.5, SHADE)
            m(5.8, 2 + near, 2.8 + self.reach, 1.8, ARM_SIDE)   # the near arm, seen from the side
            m(5.8, 3.5 + near, 2.8 + self.reach, 0.3, SHADE)
        if not face:
            return
        spots = {0: [(4, 1, -1), (8, 1, 1)], 1: [(5.3, 0.75, -1), (8.3, 1, 1)], 2: [(8.2, 0.9, 1)]}[v]
        for col, w, side in spots:
            col = 13 - col - w if flip else col
            self.eye(self.ox + col * P + lx, self.oy + P + ly, eyes, -side if flip else side, w)
        if cheeks:
            for col, w in {0: [(3, 1), (9, 1)], 1: [(4.6, 0.7), (9.2, 0.8)], 2: [(7.9, 0.9)]}[v]:
                m(col, 2.7, w, 0.6, CHEEK)
        mid = {0: 6.5, 1: 7.3, 2: 9.0}[v]
        mx = self.ox + (13 - mid if flip else mid) * P
        if mouth == "o":
            c.create_rectangle(mx - 0.35 * P, self.oy + 3.2 * P, mx + 0.35 * P, self.oy + 3.9 * P, fill=DARK, outline="")
        elif mouth == "yawn":
            h = (0.3 + 0.9 * math.sin(min(k, 45) / 45 * math.pi)) * P
            c.create_rectangle(mx - 0.45 * P, self.oy + 3.1 * P, mx + 0.45 * P, self.oy + 3.1 * P + h, fill=DARK, outline="")

    def draw_lake(self, k, t, mc):
        """A little pond lying on the ground in front of it, seen at an angle: shimmer, and ripples on a nibble."""
        c = self.c
        ground = H - round(6 * S)
        cx, half = self.ox + mc(14.4) * P, 4.2 * P
        rows = [0.45, 0.75, 0.92, 1.0, 1.0, 0.9, 0.7]          # an oval, row by row
        rh = 0.32 * P
        top = ground - 1.9 * P
        for i, f in enumerate(rows):
            y0 = top + i * rh
            if y0 >= H:
                break
            c.create_rectangle(cx - half * f, y0, cx + half * f, min(H, y0 + rh + 1),
                               fill="#6FA8DC" if i < 3 else "#5E98CF", outline="")
        for j in range(2):                                     # slow shimmer
            sx = cx - half * 0.6 + ((t // 4 + j * 37) % 50) / 50 * half * 1.2
            c.create_rectangle(sx, top + (1 + 2 * j) * rh, sx + 0.9 * P, top + (1 + 2 * j) * rh + max(1, S),
                               fill="#B8D8F2", outline="")
        if k % 150 > 135:                                      # ripples spreading from the float
            spread = (k % 150 - 135) / 15 * 1.6 * P
            tip_x = self.ox + mc(14.2 if self.view == 2 else 14.4) * P
            for dx in (-1, 1):
                x = tip_x + dx * (0.6 * P + spread)
                c.create_rectangle(x - 0.4 * P, ground - 0.95 * P, x + 0.4 * P, ground - 0.95 * P + max(1, S),
                                   fill="#DCEBF8", outline="")
        for dx in (-1, 1):                                     # two tufts of grass at the shore
            gx = cx + dx * half * 0.95
            c.create_rectangle(gx - 0.15 * P, top + rh, gx + 0.15 * P, top + 3 * rh, fill="#7BAE5A", outline="")
            c.create_rectangle(gx + dx * 0.3 * P - 0.12 * P, top + 1.6 * rh, gx + dx * 0.3 * P + 0.12 * P, top + 3 * rh,
                               fill="#8FC06A", outline="")

    def draw_prop(self, a, k, t):
        """Little things it holds or uses, drawn in front of it (mirrored when it faces left)."""
        c, m = self.c, self.mpx
        mc = (lambda col: 13 - col) if self.flip else (lambda col: col)
        v = self.view if self.view in (0, 1, 2) else 0
        if a == "laptop" and v == 0:
            m(3.8, 3.3, 5.4, 2.3, "#AEB4BA")                        # the lid, seen from behind
            m(3.8, 3.3, 5.4, 0.25, "#C9CED3")
            m(6.25, 4.2, 0.5, 0.5, BODY)                            # a tiny logo
            m(3.4, 5.6, 6.2, 0.35, "#80878E")                       # the base
        elif a == "laptop":                                         # set aside on a little desk; it turns to it
            d0, d1 = (10.4, 15.8) if v == 1 else (10.2, 15.0)
            m(d0, 5.0, d1 - d0, 0.3, "#B08A62")                     # the desk top
            m(d0, 5.3, d1 - d0, 0.12, "#8A6A50")
            m(d0 + 0.3, 5.42, 0.35, 1.58, "#8A6A50")                # desk legs, down to the ground
            m(d1 - 0.65, 5.42, 0.35, 1.58, "#8A6A50")
            if v == 1:                                              # at an angle: the back of the lid
                m(10.7, 4.72, 3.0, 0.28, "#80878E")
                m(10.9, 4.64, 2.2, 0.14, "#9AA1A8")                 # the keyboard
                m(13.2, 2.9, 2.2, 1.85, "#AEB4BA")
                m(13.2, 2.9, 2.2, 0.22, "#C9CED3")
                m(13.0, 3.0, 0.2, 1.72, "#CFE6F5")                  # a sliver of the lit screen, facing it
                m(14.1, 3.6, 0.4, 0.4, BODY)                        # the logo
            else:                                                   # in profile: base, and the lid tilted back
                m(10.5, 4.72, 3.2, 0.28, "#80878E")
                for c0, r0 in ((13.5, 4.2), (13.7, 3.65), (13.9, 3.1), (14.1, 2.55)):
                    m(c0, r0, 0.3, 0.6, "#AEB4BA")
                    m(c0 - 0.15, r0 + 0.05, 0.15, 0.55, "#CFE6F5")  # the screen's glow, toward it
        elif a == "read" and v == 0:
            m(3.6, 3.7, 2.8, 1.9, PAPER)
            m(6.6, 3.7, 2.8, 1.9, PAPER)
            m(6.4, 3.6, 0.2, 2.1, "#8A6A50")                        # the spine
            for i in range(3):
                m(3.9, 4.1 + 0.45 * i, 2.2, 0.15, "#BDB3AA")
                m(6.9, 4.1 + 0.45 * i, 2.2, 0.15, "#BDB3AA")
            if k % 150 < 8:                                         # turning a page
                m(6.6, 3.5, 1.5, 1.9, "#EFE9E2")
        elif a == "read" and v == 1:                                # held out to the side, open at an angle
            m(9.4, 3.5, 2.3, 2.0, PAPER)                            # the near page
            m(11.75, 3.3, 1.3, 1.9, "#EFE9E2")                      # the far page, narrower at this angle
            m(11.6, 3.25, 0.18, 2.3, "#8A6A50")                     # the spine
            for i in range(3):
                m(9.7, 3.9 + 0.45 * i, 1.8, 0.15, "#BDB3AA")
                m(11.95, 3.7 + 0.42 * i, 0.9, 0.13, "#BDB3AA")
            if k % 150 < 8:
                m(10.6, 3.3, 1.0, 1.9, "#EFE9E2")
        elif a == "read":                                           # in profile, held up in front of its face
            m(10.1, 2.3, 0.7, 2.8, PAPER)                           # the pages, edge-on
            for i in range(4):
                m(10.15, 2.6 + 0.6 * i, 0.6, 0.1, "#BDB3AA")        # page edges
            m(10.8, 2.2, 0.3, 3.0, "#8A6A50")                       # the cover
            m(9.9, 2.2, 0.25, 0.5, "#EFE9E2")                       # the top of the open pages
            if k % 150 < 8:
                m(9.7, 1.9, 0.6, 0.5, PAPER)                        # a page flips
        elif a == "tea":
            col, row = self.tea_spot(k % 120 > 80)
            m(col, row, 1.2, 1.3, "#F3EEE8")
            m(col, row + 0.4, 1.2, 0.25, BODY)
            m(col + 1.2, row + 0.3, 0.35, 0.6, "#F3EEE8")           # the handle
        elif a == "piano" and v == 0:
            m(1.6, 4.7, 9.8, 1.1, PAPER)
            for i in range(14):
                x = 1.6 + i * 0.7
                m(x + 0.66, 4.7, 0.06, 1.1, "#BDB3AA")
                if i % 7 not in (2, 6) and i < 13:
                    m(x + 0.47, 4.7, 0.42, 0.65, DARK)
            key = (t // 3 * 5) % 14                                 # the key being played
            m(1.65 + key * 0.7, 5.35, 0.55, 0.4, "#F2C9B8")
            m(1.4, 5.8, 10.2, 0.35, "#3B3330")
        elif a == "piano" and v == 1:                               # set beside it at an angle: the keys run off to the back
            n = 10
            for i in range(n):
                x, y = 10.0 + i * 0.62, 4.7 - i * 0.16
                m(x, y, 0.56, 1.0, PAPER)
                m(x, y + 1.0, 0.62, 0.5, "#3B3330")                 # the case under each key
            for i in range(n - 1):
                if i % 7 not in (2, 6):
                    x, y = 10.0 + i * 0.62, 4.7 - i * 0.16
                    m(x + 0.44, y - 0.08, 0.3, 0.55, DARK)          # black keys, between the white ones
            key = (t // 3 * 5) % 7                                  # it plays the near keys
            m(10.06 + key * 0.62, 4.7 - key * 0.16 + 0.62, 0.44, 0.3, "#F2C9B8")
            m(10.15, 6.2, 0.3, 0.8, "#3B3330")                      # legs
            m(15.45, 4.76, 0.3, 1.9, "#3B3330")
        elif a == "piano":                                          # in profile, in front of it
            m(10.0, 4.55, 2.2, 0.3, PAPER)                          # the keys, edge-on
            m(10.0, 4.55, 2.2, 0.08, "#BDB3AA")
            if (t // 3) % 2:
                m(10.2 + ((t // 6) % 3) * 0.6, 4.62, 0.5, 0.2, "#F2C9B8")   # a key going down
            m(10.0, 4.85, 4.4, 1.15, "#3B3330")                     # the body
            m(12.2, 3.1, 2.2, 1.75, "#3B3330")                      # the back, with a music stand
            m(12.2, 3.1, 2.2, 0.18, "#5A4E49")
            m(12.0, 3.5, 0.2, 1.05, PAPER)                          # sheet music, facing it
            m(10.3, 6.0, 0.3, 1.0, "#3B3330")                       # legs
            m(13.8, 6.0, 0.3, 1.0, "#3B3330")
        elif a == "fishing":
            self.draw_lake(k, t, mc)
            hand, tip = ((8.6, 2.4), (14.2, -1.2)) if self.view == 2 else ((12.6, 1.6), (14.4, -1.4))
            hx, hy = self.ox + mc(hand[0]) * P, self.oy + hand[1] * P
            tx, ty = self.ox + mc(tip[0]) * P, self.oy + tip[1] * P
            c.create_line(hx, hy, tx, ty, fill="#7A5A40", width=max(2, round(2 * S)))
            ground = H - round(6 * S)
            nibble = k % 150 > 135
            by = ground - 0.95 * P + round(math.sin(k / 9) * 1.2 * S) + (3 * S if nibble else 0)
            c.create_line(tx, ty, tx, by, fill="#9A928C", width=1)
            r = 2 * S
            c.create_rectangle(tx - r, by - r, tx + r, by, fill=HEART, outline="")             # the float
            c.create_rectangle(tx - r, by, tx + r, by + r, fill=PAPER, outline="")
        elif a == "selfie":
            m(11.3, -0.6, 0.9, 1.5, DARK)                           # the phone
            m(11.45, -0.4, 0.6, 1.1, "#7FB7E6")

    def tea_spot(self, sip):
        """Where the mug is: in its hand, or at its mouth for a sip (tea is always facing you)."""
        return (8.4, 2.4) if sip else (10.6, 3.4)

    def scene_spot(self, col, row):
        """A spot in the pet's grid as canvas x, y, mirrored when it faces left (for effects coming from a prop)."""
        return self.ox + (13 - col if self.flip else col) * P, self.oy + row * P

    def eye(self, ex, ey, style, side, w=1):
        """One eye; w < 1 makes it narrower, for the far eye at an angle."""
        c = self.c
        ew = P * w                                     # eye width
        g = max(2, round(2.5 * S))                     # glint size
        w3 = max(2, round(3 * S))
        if style == "open":
            c.create_rectangle(ex, ey, ex + ew, ey + 2 * P, fill=DARK, outline="")
        elif style == "closed":
            c.create_rectangle(ex - S, ey + P, ex + ew + S, ey + P + w3, fill=DARK, outline="")
        elif style == "half":
            c.create_rectangle(ex, ey + P, ex + ew, ey + 2 * P, fill=DARK, outline="")
        elif style == "happy":
            c.create_line(ex - 2 * S, ey + 1.2 * P, ex + ew / 2, ey + 0.3 * P, ex + ew + 2 * S, ey + 1.2 * P,
                          fill=DARK, width=w3)
        elif style == "x":
            c.create_line(ex - S, ey, ex + ew + S, ey + 2 * P, fill=DARK, width=w3)
            c.create_line(ex + ew + S, ey, ex - S, ey + 2 * P, fill=DARK, width=w3)
        elif style == "big":
            q = P / 4
            c.create_rectangle(ex - q, ey - q, ex + ew + q, ey + 2 * P, fill=DARK, outline="")
            c.create_rectangle(ex, ey, ex + g, ey + g, fill=PAPER, outline="")
        elif style == "sparkle":
            c.create_rectangle(ex, ey, ex + ew, ey + 2 * P, fill=DARK, outline="")
            c.create_rectangle(ex + S, ey + S, ex + S + g, ey + S + g, fill=PAPER, outline="")
            c.create_rectangle(ex + ew - g, ey + 1.3 * P, ex + ew - g / 2, ey + 1.3 * P + g / 2, fill=PAPER, outline="")
        elif style == "sad":
            c.create_rectangle(ex, ey + 0.8 * P, ex + ew, ey + 2 * P, fill=DARK, outline="")
            inner, outer = (ex + ew + 2 * S, ex - 2 * S) if side < 0 else (ex - 2 * S, ex + ew + 2 * S)
            c.create_line(outer, ey + 0.5 * P, inner, ey + 0.1 * P, fill=DARK, width=w3)

    def draw_bubble(self, text):
        c = self.c
        cx, bottom = W // 2, self.pet_top - 12 * S
        tid = c.create_text(cx, 0, text=text, width=W - 50 * S, justify="center",
                            fill=DARK, font=(FONT, fs(10)), anchor="s")
        x0, y0, x1, y1 = c.bbox(tid)
        c.move(tid, 0, bottom - y1)
        x0, y0, x1, y1 = c.bbox(tid)
        x0, y0, x1, y1 = x0 - 10 * S, y0 - 6 * S, x1 + 10 * S, y1 + 6 * S
        r, tail = 10 * S, 9 * S
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
               cx + tail * 0.7, y1, cx, y1 + tail, cx - tail * 0.7, y1, x0 + r, y1, x0, y1, x0, y1 - r,
               x0, y0 + r, x0, y0]
        c.create_polygon(pts, smooth=True, fill=PAPER, outline=BODY, width=max(2, round(2 * S)))
        c.tag_raise(tid)
        if self.bubble_queue and self.base != "think":   # more to read: click the bubble
            c.create_text(x1 - 6 * S, y1 - 4 * S, text="▸", fill=BODY, font=(SYMBOLS, fs(8)))
        self.bubble_box = (x0, y0, x1, y1)


def already_running():
    """True if a Mini Claude is already open: one pet at a time. The lock goes away when the pet closes."""
    global _one_pet
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        _one_pet = kernel32.CreateMutexW(None, False, "Local\\MiniClaudePet")
        return ctypes.get_last_error() == 183                 # ERROR_ALREADY_EXISTS
    except Exception:
        return False


if already_running():
    sys.exit()
root = tk.Tk()
root.title("Mini Claude")
S = 1.0                                         # keep it small, like the first version
P = round(8 * S)                                # one sprite pixel
W, H = 300, 280           # window; the pet sits at the bottom
pet = Pet(root)
root.mainloop()
