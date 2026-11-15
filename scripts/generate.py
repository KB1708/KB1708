#!/usr/bin/env python3
"""
Terminal-themed SVG cards for a GitHub profile README.

Renders into --out:
  header.svg        animated terminal intro (typing effect)
  neofetch.svg      GitHub stats, neofetch style
  languages.svg     top languages, htop style
  streak.svg        contribution streak
  activity.svg      last-30-days contribution graph
  project-N.svg     one card per project in profile.json
  footer.svg        closing line

Uses only the Python standard library. Data comes from the GitHub GraphQL API
(token in GH_TOKEN or GITHUB_TOKEN). Run with --mock to render sample data offline.
"""
import argparse
import datetime as dt
import json
import math
import os
import random
import sys
import urllib.request
from html import escape

FONT = ("'JetBrains Mono','Fira Code','SF Mono',Menlo,Monaco,Consolas,"
        "'DejaVu Sans Mono','Liberation Mono','Courier New',monospace")
CW = 0.6  # monospace advance width, in em; every text run is pinned to it with textLength

T = {}  # theme colours, filled from profile.json


# --------------------------------------------------------------------------- helpers

def color(name):
    return T.get(name, name)


def txt(x, y, s, fill="text", fs=14, weight=None, anchor=None, glyphs=False,
        extra="", pin=True):
    """Monospace text pinned to an exact width so columns line up in every font."""
    if s == "":
        return ""
    attrs = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'fill="{color(fill)}"', f'font-size="{fs}"']
    if weight:
        attrs.append(f'font-weight="{weight}"')
    if anchor:
        attrs.append(f'text-anchor="{anchor}"')
    if pin:
        attrs.append(f'textLength="{len(s) * fs * CW:.1f}"')
        attrs.append('lengthAdjust="%s"' % ("spacingAndGlyphs" if glyphs else "spacing"))
    return f'<text {" ".join(attrs)} {extra}>{escape(s)}</text>'


def segs(x, y, parts, fs=14, weight=None, extra=""):
    """A line made of differently coloured segments: [(text, colour), ...]."""
    out, col = [], 0
    for s, c in parts:
        out.append(txt(x + col * fs * CW, y, s, c, fs, weight, extra=extra))
        col += len(s)
    return "".join(out)


def fade(delay, inner, dur=0.45):
    return (f'<g class="fade" style="animation-delay:{delay:.2f}s;'
            f'animation-duration:{dur:.2f}s">{inner}</g>')


def fmt(n):
    return f"{n:,}"


def window(w, h, title, body, defs=""):
    """Terminal window chrome around `body`."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" xml:space="preserve">
<defs>
  <filter id="glow" x="-20%" y="-50%" width="140%" height="200%">
    <feGaussianBlur stdDeviation="2.2" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="#ffffff" opacity="0.025"/>
  </pattern>
  <radialGradient id="vig" cx="50%" cy="45%" r="75%">
    <stop offset="60%" stop-color="#000" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000" stop-opacity="0.45"/>
  </radialGradient>
  {defs}
</defs>
<style>
  text {{ font-family: {FONT}; white-space: pre; }}
  .fade {{ animation-name: fade; animation-timing-function: ease-out; animation-fill-mode: backwards; }}
  @keyframes fade {{ from {{ opacity: 0; transform: translateY(3px); }} to {{ opacity: 1; transform: none; }} }}
  .blink {{ animation: blink 1.05s steps(1) infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
</style>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{color('bg')}" stroke="{color('border')}"/>
<path d="M0.5 32 V10.5 a10 10 0 0 1 10 -10 H{w-10.5} a10 10 0 0 1 10 10 V32 Z" fill="{color('panel')}"/>
<line x1="0.5" y1="32" x2="{w-0.5}" y2="32" stroke="{color('border')}"/>
<circle cx="20" cy="16.5" r="5.5" fill="#ff5f56"/>
<circle cx="38" cy="16.5" r="5.5" fill="#ffbd2e"/>
<circle cx="56" cy="16.5" r="5.5" fill="#27c93f"/>
<text x="{w/2:.1f}" y="21" fill="{color('muted')}" font-size="12" text-anchor="middle">{escape(title)}</text>
{body}
<rect x="1" y="33" width="{w-2}" height="{h-34}" rx="9" fill="url(#scan)" pointer-events="none"/>
<rect x="1" y="33" width="{w-2}" height="{h-34}" rx="9" fill="url(#vig)" pointer-events="none"/>
</svg>
'''


def prompt_parts(cfg, path="~"):
    return [(f"{cfg['prompt_user']}@{cfg['prompt_host']}", "accent"), (":", "text"),
            (path, "cyan"), ("$ ", "text")]


# --------------------------------------------------------------------------- header

def render_header(cfg):
    W, X = 850, 28
    fs, lh = 14, 22
    bfs, blh = 15, 16
    cw, bcw = fs * CW, bfs * CW
    speed = 0.055          # seconds per typed character
    out_gap = 0.12         # seconds between output lines

    body, defs = [], []
    y = 32 + 26 + bfs
    t = 0.2
    # banner
    for i, line in enumerate(cfg["banner"]):
        body.append(fade(t, txt(X, y, line, "accent", bfs, glyphs=True,
                                extra='filter="url(#glow)"'), 0.35))
        y += blh
        t += 0.07
    sx = X + len(cfg["banner"][0]) * bcw + 26
    side = cfg.get("banner_side", [])
    sy = y - blh * len(cfg["banner"]) + (blh * len(cfg["banner"]) - 20 * len(side)) / 2 + 2
    for i, (s_text, s_col) in enumerate(side):
        body.append(fade(t + i * 0.12, txt(sx, sy + i * 20, s_text, s_col, 12.5)))
    y += 22
    t += 0.35

    prompt = prompt_parts(cfg)
    plen = sum(len(s) for s, _ in prompt)
    cursor = [(0.0, X + plen * cw, y)]   # (time, x, baseline)

    def show_at(time, inner):
        return (f'<g><set attributeName="visibility" to="hidden" begin="0s" '
                f'dur="{time:.2f}s"/>{inner}</g>')

    for n, step in enumerate(cfg["terminal"]):
        cmd = step["cmd"]
        body.append(show_at(t, segs(X, y, prompt, fs)))
        # typing: clip reveals one character at a time, cursor follows
        cid = f"type{n}"
        widths = ";".join(f"{k * cw:.1f}" for k in range(len(cmd) + 1))
        times = [t + 0.25 + k * speed for k in range(len(cmd) + 1)]
        dur = times[-1] + 0.01
        keyt = ";".join(f"{v / dur:.4f}" for v in [0] + times[1:])
        defs.append(
            f'<clipPath id="{cid}"><rect x="{X + plen * cw:.1f}" y="{y - fs:.1f}" '
            f'width="{len(cmd) * cw + 1:.1f}" height="{fs * 1.5:.1f}"><animate attributeName="width" '
            f'calcMode="discrete" values="{widths}" '
            f'keyTimes="{keyt}" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>')
        body.append(f'<g clip-path="url(#{cid})">{txt(X + plen * cw, y, cmd, "text", fs)}</g>')
        for k, tk in enumerate(times):
            cursor.append((tk, X + (plen + k) * cw, y))
        t = times[-1] + 0.25
        y += lh
        for parts in step["out"]:
            parts = [(p[0], p[1]) for p in parts]
            body.append(show_at(t, segs(X, y, parts, fs)))
            t += out_gap
            y += lh
        t += 0.2
        cursor.append((t, X + plen * cw, y))
    # final prompt + blinking cursor
    body.append(show_at(t, segs(X, y, prompt, fs)))
    cursor.append((t + 0.001, X + plen * cw, y))

    total = cursor[-1][0] + 0.01
    kt = ";".join(f"{c[0] / total:.4f}" for c in cursor)
    xs = ";".join(f"{c[1]:.1f}" for c in cursor)
    ys = ";".join(f"{c[2] - fs + 2:.1f}" for c in cursor)
    first_prompt = cursor[1][0] - 0.25 if len(cursor) > 1 else 0
    body.append(
        f'<g><set attributeName="visibility" to="hidden" begin="0s" dur="{max(first_prompt, 0.01):.2f}s"/>'
        f'<rect class="blink" style="animation-delay:{total:.2f}s" x="{cursor[-1][1]:.1f}" '
        f'y="{cursor[-1][2] - fs + 2:.1f}" width="{cw:.1f}" height="{fs + 3}" fill="{color("accent")}" opacity="0.85">'
        f'<animate attributeName="x" calcMode="discrete" values="{xs}" keyTimes="{kt}" dur="{total:.2f}s" fill="freeze"/>'
        f'<animate attributeName="y" calcMode="discrete" values="{ys}" keyTimes="{kt}" dur="{total:.2f}s" fill="freeze"/>'
        f'</rect></g>')

    H = int(y + 26)
    return window(W, H, f"{cfg['prompt_user']}@{cfg['prompt_host']}: ~ — zsh — {W // 10}x{H // 10}",
                  "\n".join(body), "\n".join(defs))


# --------------------------------------------------------------------------- neofetch

CHIP = [
    "      ┃  ┃  ┃  ┃  ┃      ",
    "   ┏━━┻━━┻━━┻━━┻━━┻━━┓   ",
    " ━━┫                 ┣━━ ",
    " ━━┫    ▄▀▀▄  ▀█▀    ┣━━ ",
    " ━━┫    █▄▄█   █     ┣━━ ",
    " ━━┫    █  █  ▄█▄    ┣━━ ",
    " ━━┫                 ┣━━ ",
    "   ┗━━┳━━┳━━┳━━┳━━┳━━┛   ",
    "      ┃  ┃  ┃  ┃  ┃      ",
]


def uptime(created):
    now = dt.datetime.now(dt.timezone.utc)
    months = (now.year - created.year) * 12 + now.month - created.month
    if now.day < created.day:
        months -= 1
    y, m = divmod(max(months, 0), 12)
    parts = []
    if y:
        parts.append(f"{y} year{'s' if y != 1 else ''}")
    parts.append(f"{m} month{'s' if m != 1 else ''}")
    return ", ".join(parts)


def render_neofetch(cfg, d):
    W, fs, lh = 850, 14, 21
    cw = fs * CW
    X = 36
    afs, alh = 16, 19
    langs = ", ".join(l["name"] for l in d["languages"][:3]) or "—"
    head = f"{d['login']}@github"
    rows = [
        ("Role", f"{cfg['title']} @ {cfg['company']}"),
        ("Uptime", f"{uptime(d['created'])} on GitHub"),
        ("Repos", f"{fmt(d['repos'])}  (★ {fmt(d['stars'])} stars earned)"),
        ("Commits", f"{fmt(d['commits'])} all-time"),
        ("PRs", f"{fmt(d['prs'])}   Issues: {fmt(d['issues'])}"),
        ("Contribs", f"{fmt(d['total'])} total  ·  {fmt(d['this_year'])} this year"),
        ("Contributed", f"{fmt(d['contributed_to'])} repos (last year)"),
        ("Followers", fmt(d["followers"])),
        ("Languages", langs),
        ("Location", cfg["location_short"]),
    ]
    n_lines = 2 + len(rows) + 2
    H = 32 + 30 + n_lines * lh + 18
    art_h = len(CHIP) * alh
    ay = 32 + (H - 32 - art_h) / 2 + afs - 4
    body = []
    for i, line in enumerate(CHIP):
        body.append(fade(0.1 + i * 0.05, txt(X, ay + i * alh, line, "accent", afs, glyphs=True,
                                              extra='filter="url(#glow)"')))
    ix = X + len(CHIP[0]) * afs * CW + 40
    y = 32 + 30 + fs
    t = 0.45
    body.append(fade(t, segs(ix, y, [(d["login"], "accent"), ("@", "text"), ("github", "accent")],
                             fs, "bold")))
    y += lh
    body.append(fade(t, txt(ix, y, "-" * len(head), "muted", fs)))
    y += lh
    key_w = max(len(k) for k, _ in rows) + 2
    for k, v in rows:
        t += 0.08
        body.append(fade(t, segs(ix, y, [(k, "accent"), (":".ljust(key_w - len(k)), "muted"),
                                         (v, "text")], fs)))
        y += lh
    y += lh * 0.35
    palette = ["#30363d", "#ff5f56", "#27c93f", "#ffbd2e", "#58a6ff", "#bc8cff", "#56d4dd", "#c9d1d9"]
    sw = cw * 3
    sq = "".join(f'<rect x="{ix + i * sw:.1f}" y="{y - fs + 2:.1f}" width="{sw:.1f}" height="{fs + 2}" fill="{c}"/>'
                 for i, c in enumerate(palette))
    body.append(fade(t + 0.15, sq))
    return window(W, int(H), f"{d['login']}@github: ~ — neofetch", "\n".join(body))


# --------------------------------------------------------------------------- languages

def render_languages(cfg, d):
    W, H = 420, 262
    fs = 13
    cw = fs * CW
    X = 22
    langs = d["languages"][:6]
    total = sum(l["size"] for l in langs) or 1
    body = [fade(0.1, segs(X, 32 + 28, prompt_parts(cfg) + [("htop --sort=bytes", "text")], 12))]
    y = 32 + 60
    name_w = 11
    bx = X + name_w * cw
    bw = W - bx - 62
    for i, l in enumerate(langs):
        pct = l["size"] / total
        t = 0.25 + i * 0.12
        body.append(fade(t, txt(X, y, l["name"][:name_w - 1], "text", fs)))
        body.append(fade(t, f'<rect x="{bx:.1f}" y="{y - 10}" width="{bw:.1f}" height="11" rx="2" '
                            f'fill="{color("accent")}" opacity="0.08"/>'))
        fw = max(bw * pct, 2)
        delay = t + 0.1
        body.append(f'<rect x="{bx:.1f}" y="{y - 10}" width="{fw:.1f}" height="11" rx="2" fill="{color("accent")}" '
                    f'opacity="{1 - i * 0.11:.2f}"><animate attributeName="width" values="0;0;{fw:.1f}" '
                    f'keyTimes="0;{delay / (delay + 0.9):.3f};1" dur="{delay + 0.9:.2f}s" fill="freeze" '
                    f'calcMode="spline" keySplines="0 0 1 1;0.2 0.8 0.2 1"/></rect>')
        body.append(fade(t + 0.3, txt(W - X, y, f"{pct * 100:5.1f}%", "muted", 12,
                                      anchor="end", pin=False)))
        y += 25
    if not langs:
        body.append(txt(X, y, "no language data yet", "muted", fs))
    body.append(fade(1.2, txt(X, H - 16, f"based on {fmt(d['repos'])} repos · by code size", "muted", 10.5)))
    return window(W, H, "htop — languages", "\n".join(body))


# --------------------------------------------------------------------------- streak

def short(day):
    return day.strftime("%b %d").replace(" 0", " ") if day else "—"


def render_streak(cfg, d):
    W, H = 420, 262
    s = d["streak"]
    cx, cy, r = W / 2, 32 + 118, 46
    body = [fade(0.1, segs(22, 32 + 28, prompt_parts(cfg) + [("git streak --stats", "text")], 12))]
    circ = 2 * math.pi * r
    body.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color("accent")}" '
                f'stroke-opacity="0.12" stroke-width="5"/>')
    body.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color("accent")}" stroke-width="5" '
                f'stroke-linecap="round" stroke-dasharray="{circ:.1f}" stroke-dashoffset="0" '
                f'transform="rotate(-90 {cx} {cy})" filter="url(#glow)">'
                f'<animate attributeName="stroke-dashoffset" values="{circ:.1f};0" dur="2s" '
                f'calcMode="spline" keyTimes="0;1" keySplines="0.2 0.8 0.2 1" fill="freeze"/></circle>')
    num = str(s["current"])
    body.append(fade(0.6, f'<text x="{cx}" y="{cy + 11}" fill="{color("accent")}" font-size="32" '
                          f'font-weight="bold" text-anchor="middle" filter="url(#glow)">{num}</text>'))
    body.append(fade(0.8, f'<text x="{cx}" y="{cy + r + 24}" fill="{color("text")}" font-size="12" '
                          f'text-anchor="middle">current streak</text>'))
    cur_range = (f"{short(s['current_start'])} – {short(s['current_end'])}"
                 if s["current"] else "start one today")
    body.append(fade(0.9, f'<text x="{cx}" y="{cy + r + 40}" fill="{color("muted")}" font-size="10.5" '
                          f'text-anchor="middle">{escape(cur_range)}</text>'))

    def side(x, big, label, sub, delay):
        return fade(delay,
                    f'<text x="{x}" y="{cy + 4}" fill="{color("text")}" font-size="22" font-weight="bold" '
                    f'text-anchor="middle">{escape(big)}</text>'
                    f'<text x="{x}" y="{cy + 26}" fill="{color("accent")}" font-size="11" '
                    f'text-anchor="middle">{escape(label)}</text>'
                    f'<text x="{x}" y="{cy + 42}" fill="{color("muted")}" font-size="10" '
                    f'text-anchor="middle">{escape(sub)}</text>')

    body.append(side(70, fmt(d["total"]), "contributions", f"since {d['created'].strftime('%b %Y')}", 0.4))
    longest_sub = (f"{short(s['longest_start'])} – {short(s['longest_end'])}"
                   if s["longest"] else "—")
    body.append(side(W - 70, f"{s['longest']}d", "longest streak", longest_sub, 0.5))
    for x in (132, W - 132):
        body.append(f'<line x1="{x}" y1="{cy - 40}" x2="{x}" y2="{cy + 46}" stroke="{color("border")}"/>')
    return window(W, H, "streak — ~/contributions", "\n".join(body))


# --------------------------------------------------------------------------- activity

def render_activity(cfg, d):
    W, H = 850, 290
    days = d["calendar"][-31:]
    L, R, Tp, B = 58, 820, 32 + 62, H - 46
    counts = [c for _, c in days] or [0]
    top = max(counts)
    step = max(1, math.ceil(top / 4)) if top else 1
    ymax = step * 4
    n = max(len(days) - 1, 1)

    def px(i):
        return L + (R - L) * i / n

    def py(v):
        return B - (B - Tp) * v / ymax

    body = [fade(0.1, segs(28, 32 + 30, prompt_parts(cfg) +
                           [("git log --since='30 days ago' | plot", "text")], 13))]
    for k in range(5):
        v = step * k
        yy = py(v)
        body.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{R}" y2="{yy:.1f}" stroke="{color("accent")}" '
                    f'stroke-opacity="0.09" stroke-dasharray="3 5"/>')
        body.append(f'<text x="{L - 12}" y="{yy + 4:.1f}" fill="{color("muted")}" font-size="11" '
                    f'text-anchor="end">{v}</text>')
    for i, (day, _) in enumerate(days):
        if i % 5 == 0 or i == len(days) - 1:
            body.append(f'<text x="{px(i):.1f}" y="{B + 22}" fill="{color("muted")}" font-size="10.5" '
                        f'text-anchor="middle">{day.strftime("%b %d")}</text>')
    pts = [(px(i), py(c)) for i, (_, c) in enumerate(days)]
    if pts:
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        length = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) + 10
        area = f"M{pts[0][0]:.1f},{B} L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},{B} Z"
        body.append(f'<path d="{area}" fill="url(#area)" class="fade" style="animation-delay:1.2s;animation-duration:.8s"/>')
        body.append(f'<polyline points="{line}" fill="none" stroke="{color("accent")}" stroke-width="2.2" '
                    f'stroke-linejoin="round" stroke-dasharray="{length:.0f}" stroke-dashoffset="0" filter="url(#glow)">'
                    f'<animate attributeName="stroke-dashoffset" values="{length:.0f};0" dur="2.2s" '
                    f'calcMode="spline" keyTimes="0;1" keySplines="0.3 0.6 0.3 1" fill="freeze"/></polyline>')
        for i, (x, y) in enumerate(pts):
            body.append(fade(0.3 + 1.8 * i / len(pts),
                             f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.8" fill="{color("bg")}" '
                             f'stroke="{color("accent")}" stroke-width="1.6"/>'))
    total30 = sum(counts)
    active = sum(1 for c in counts if c)
    body.append(fade(2.2, f'<text x="{R}" y="{32 + 30}" fill="{color("muted")}" font-size="12" text-anchor="end">'
                          f'{fmt(total30)} contributions · {active}/{len(days)} active days</text>'))
    defs = (f'<linearGradient id="area" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{color("accent")}" stop-opacity="0.28"/>'
            f'<stop offset="100%" stop-color="{color("accent")}" stop-opacity="0"/></linearGradient>')
    return window(W, H, "activity — last 30 days", "\n".join(body), defs)


# --------------------------------------------------------------------------- projects

def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + (1 if cur else 0) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    if cur:
        lines.append(cur)
    return lines


def render_project(cfg, p, meta, idx):
    W, H = 280, 228
    X = 18
    owner, name = p["repo"].split("/")
    body = []
    body.append(fade(0.1 + idx * 0.15, txt(X, 32 + 30, name[:27], "accent", 14.5, "bold",
                                           extra='filter="url(#glow)"')))
    own = owner.lower() == cfg["username"].lower()
    sub = f"github.com/{owner}" if own else f"collab @ github.com/{owner}"
    body.append(fade(0.15 + idx * 0.15, txt(X, 32 + 48, sub[:40], "muted", 10.5)))
    y = 32 + 76
    desc = meta.get("description") if cfg.get("prefer_repo_description") and meta.get("description") else p["description"]
    lines = wrap(desc, 35)
    if len(lines) > 4:
        lines = lines[:4]
        lines[-1] = lines[-1][:32].rstrip(" ,.;:") + "..."
    for i, line in enumerate(lines):
        body.append(fade(0.3 + idx * 0.15 + i * 0.05, txt(X, y, line, "text", 11.5)))
        y += 17
    tags = "  ".join(f"#{t}" for t in p.get("tags", []))
    body.append(fade(0.6 + idx * 0.15, txt(X, H - 44, tags[:38], "cyan", 11)))
    lang = (meta.get("language") or p.get("language") or "")
    lang_color = meta.get("language_color") or color("accent")
    foot = []
    fx = X
    if lang:
        foot.append(f'<circle cx="{fx + 4}" cy="{H - 18}" r="4" fill="{lang_color}"/>')
        foot.append(txt(fx + 13, H - 14, lang, "muted", 11))
        fx += 13 + len(lang) * 11 * CW + 16
    if meta.get("stars") is not None:
        s = f"★ {meta['stars']}   ⑂ {meta['forks']}"
        foot.append(txt(fx, H - 14, s, "muted", 11))
    foot.append(f'<text x="{W - X}" y="{H - 14}" fill="{color("accent_dim")}" font-size="11" '
                f'text-anchor="end">open ↗</text>')
    body.append(fade(0.7 + idx * 0.15, "".join(foot)))
    body.append(f'<line x1="{X}" y1="{H - 32}" x2="{W - X}" y2="{H - 32}" stroke="{color("border")}"/>')
    return window(W, H, "~/projects", "\n".join(body))


# --------------------------------------------------------------------------- footer

def render_footer(cfg):
    W, H = 850, 86
    y = 32 + 32
    parts = prompt_parts(cfg) + [("exit", "text")]
    body = [segs(28, y, parts, 13),
            fade(0.6, txt(28 + (sum(len(s) for s, _ in parts) + 3) * 13 * CW, y,
                          "[process completed] thanks for stopping by.", "muted", 13)),
            f'<rect class="blink" x="{28 + (sum(len(s) for s, _ in parts) + 47) * 13 * CW:.1f}" '
            f'y="{y - 12}" width="{13 * CW:.1f}" height="15" fill="{color("accent")}" opacity="0.85"/>']
    return window(W, H, "session closed", "\n".join(body))


# --------------------------------------------------------------------------- data

def gql(query, variables, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-cards"})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.load(r)
    if res.get("data") is None:
        raise RuntimeError(f"GraphQL error: {res.get('errors')}")
    return res["data"], res.get("errors") or []


USER_Q = """
query($login: String!) {
  user(login: $login) {
    login createdAt
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        name isPrivate stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}"""


def fetch(cfg, token):
    login = cfg["username"]
    data, _ = gql(USER_Q, {"login": login}, token)
    u = data["user"]
    if not u:
        raise RuntimeError(f"user {login} not found")
    created = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)

    # contribution calendar, one aliased block per year (API max range is one year)
    blocks = []
    for year in range(created.year, now.year + 1):
        start = max(dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc), created)
        end = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now)
        blocks.append(
            f'y{year}: contributionsCollection(from: "{start.strftime("%Y-%m-%dT%H:%M:%SZ")}", '
            f'to: "{end.strftime("%Y-%m-%dT%H:%M:%SZ")}") {{ totalCommitContributions '
            f'restrictedContributionsCount contributionCalendar {{ totalContributions '
            f'weeks {{ contributionDays {{ date contributionCount }} }} }} }}')
    cal_q = "query($login: String!) { user(login: $login) { " + " ".join(blocks) + " } }"
    cdata, _ = gql(cal_q, {"login": login}, token)
    days, commits, this_year = {}, 0, 0
    for key, block in cdata["user"].items():
        commits += block["totalCommitContributions"]
        if key == f"y{now.year}":
            this_year = block["contributionCalendar"]["totalContributions"]
        for w in block["contributionCalendar"]["weeks"]:
            for dd in w["contributionDays"]:
                days[dd["date"]] = dd["contributionCount"]

    # projects (may be private or missing; fall back to profile.json)
    metas = []
    if cfg.get("projects"):
        parts = []
        for i, p in enumerate(cfg["projects"]):
            o, n = p["repo"].split("/")
            parts.append(f'p{i}: repository(owner: {json.dumps(o)}, name: {json.dumps(n)}) '
                         f'{{ description stargazerCount forkCount isPrivate primaryLanguage {{ name color }} }}')
        try:
            pdata, _ = gql("query { " + " ".join(parts) + " }", {}, token)
        except Exception as e:  # noqa: BLE001
            print(f"warning: project lookup failed: {e}", file=sys.stderr)
            pdata = {}
        for i in range(len(cfg["projects"])):
            r = (pdata or {}).get(f"p{i}")
            if r and not r["isPrivate"]:
                pl = r.get("primaryLanguage") or {}
                metas.append({"description": r.get("description"), "stars": r["stargazerCount"],
                              "forks": r["forkCount"], "language": pl.get("name"),
                              "language_color": pl.get("color")})
            else:
                metas.append({})

    langs = {}
    stars = 0
    for r in u["repositories"]["nodes"]:
        if not r["isPrivate"]:
            stars += r["stargazerCount"]
        for e in r["languages"]["edges"]:
            nm = e["node"]["name"]
            if nm in cfg.get("hide_languages", ["Jupyter Notebook", "HTML", "CSS", "Shell"]):
                continue
            item = langs.setdefault(nm, {"name": nm, "color": e["node"]["color"], "size": 0})
            item["size"] += e["size"]

    return finish({
        "login": u["login"], "created": created, "followers": u["followers"]["totalCount"],
        "prs": u["pullRequests"]["totalCount"], "issues": u["issues"]["totalCount"],
        "contributed_to": u["repositoriesContributedTo"]["totalCount"],
        "repos": u["repositories"]["totalCount"], "stars": stars, "commits": commits,
        "this_year": this_year, "days": days,
        "languages": sorted(langs.values(), key=lambda l: -l["size"]),
    }), metas


def mock(cfg):
    rnd = random.Random(1708)
    today = dt.date.today()
    days = {}
    for i in range(900):
        day = today - dt.timedelta(days=i)
        busy = rnd.random() < (0.55 if day.weekday() < 5 else 0.25)
        days[day.isoformat()] = rnd.randint(1, 14) if busy or i < 9 else 0
    langs = [("Python", 520000), ("TypeScript", 260000), ("JavaScript", 120000),
             ("SQL", 40000), ("Dockerfile", 9000), ("HCL", 6000)]
    d = {"login": cfg["username"],
         "created": dt.datetime(2022, 7, 4, tzinfo=dt.timezone.utc),
         "followers": 38, "prs": 64, "issues": 17, "contributed_to": 12, "repos": 27,
         "stars": 46, "commits": 1873, "this_year": 912, "days": days,
         "languages": [{"name": n, "color": None, "size": s} for n, s in langs]}
    metas = [{}, {"stars": 9, "forks": 4, "language": "TypeScript", "language_color": "#3178c6"}, {}]
    return finish(d), metas


def finish(d):
    cal = sorted((dt.date.fromisoformat(k), v) for k, v in d["days"].items())
    today = dt.date.today()
    cal = [(k, v) for k, v in cal if k <= today]
    d["calendar"] = cal
    d["total"] = sum(v for _, v in cal)
    # longest streak
    best = (0, None, None)
    run, start = 0, None
    for k, v in cal:
        if v:
            if run == 0:
                start = k
            run += 1
            if run > best[0]:
                best = (run, start, k)
        else:
            run = 0
    # current streak: today counts if active; a quiet today doesn't break yesterday's run
    cur, cs, ce = 0, None, None
    idx = len(cal) - 1
    if idx >= 0 and cal[idx][1] == 0:
        idx -= 1
    while idx >= 0 and cal[idx][1] > 0:
        cur += 1
        cs = cal[idx][0]
        ce = ce or cal[idx][0]
        idx -= 1
    d["streak"] = {"current": cur, "current_start": cs, "current_end": ce,
                   "longest": best[0], "longest_start": best[1], "longest_end": best[2]}
    return d


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="profile.json")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--mock", action="store_true", help="render with sample data, no API calls")
    a = ap.parse_args()

    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    T.update(cfg["theme"])
    os.makedirs(a.out, exist_ok=True)

    if a.mock:
        d, metas = mock(cfg)
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("GH_TOKEN / GITHUB_TOKEN is not set (use --mock for an offline preview)")
        d, metas = fetch(cfg, token)

    files = {
        "header.svg": render_header(cfg),
        "neofetch.svg": render_neofetch(cfg, d),
        "languages.svg": render_languages(cfg, d),
        "streak.svg": render_streak(cfg, d),
        "activity.svg": render_activity(cfg, d),
        "footer.svg": render_footer(cfg),
    }
    for i, p in enumerate(cfg.get("projects", [])):
        files[f"project-{i + 1}.svg"] = render_project(cfg, p, metas[i] if i < len(metas) else {}, i)
    for name, svg in files.items():
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {a.out}/{name} ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()
