"""Build the profile README visuals (assets/*.svg).

Static cards (hero, what I do, impact, stack, projects, journey, closing) are written from the data below.
GitHub activity and languages are read from GitHub's public pages / API, so the daily workflow keeps them fresh.
Every animation keeps its final frame as the base value: renderers without animation show the finished card.
Standard library only (runs as-is on GitHub Actions).
"""
import datetime as dt
import html
import json
import os
import re
import urllib.request
from pathlib import Path

USER = "narpatganwliya7"
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Ubuntu, Arial, sans-serif"

# palette: midnight cards with aurora accents
# palette: "data editorial" -- paper cards, charcoal hero, vermilion signature colour
BG1, BG2, LINE = "#fffdf8", "#f5f0e6", "#e6ddcc"
INK, TXT, MUTED, DIM = "#17191e", "#2c3038", "#6d707a", "#a39c8d"
CHAR, WHITE, LMUTED, SUN = "#17191e", "#ffffff", "#aeb2bc", "#f2b33d"
# accent names kept short: CYAN = teal, VIOLET = vermilion (signature), GREEN = moss, AMBER = gold, PINK = rose
CYAN, VIOLET, GREEN, AMBER, PINK, BLUE = "#0f7c80", "#e2492b", "#4f8a2b", "#c98a00", "#c2416b", "#2b4a9b"


# ------------------------------------------------------------------ helpers
def esc(s):
    return html.escape(str(s), quote=True)


def tw(s, size, bold=False):
    """Approximate rendered text width (px) for the sans-serif stack above."""
    w = 0.0
    for ch in str(s):
        if ch in "il.,:;'|!ftjI ·()":
            w += 0.30
        elif ch in "mwMW":
            w += 0.84
        elif ch.isupper():
            w += 0.66
        elif ch.isdigit():
            w += 0.56
        else:
            w += 0.54
    return w * size * (1.07 if bold else 1.0)


def defs(extra=""):
    return (f'<defs><linearGradient id="card" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG1}"/>'
            f'<stop offset="1" stop-color="{BG2}"/></linearGradient>'
            f'<linearGradient id="hl" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="{VIOLET}"/><stop offset="1" stop-color="#f0783a"/></linearGradient>'
            f'<radialGradient id="glowA"><stop offset="0" stop-color="{VIOLET}" stop-opacity=".22"/>'
            f'<stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="glowB"><stop offset="0" stop-color="{CYAN}" stop-opacity=".22"/>'
            f'<stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>'
            f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="3" cy="3" r="1.3" '
            f'fill="#ffffff" fill-opacity=".09"/></pattern>{extra}</defs>')


def card(x, y, w, h, r=24, fill="url(#card)", stroke=LINE):
    return (f'<rect x="{x+.5}" y="{y+.5}" width="{w-1}" height="{h-1}" rx="{r}" fill="{fill}" '
            f'stroke="{stroke}"/>')


def text(x, y, s, size=14, fill=TXT, weight=400, anchor="start", ls=0, extra=""):
    l = f' letter-spacing="{ls}"' if ls else ""
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" font-weight="{weight}"{l}{a}{extra}>{esc(s)}</text>'


def clipped(w, h, r, inner, cid="cc"):
    """Glows / decorations clipped to the rounded card so nothing spills past its corners."""
    return (f'<clipPath id="{cid}"><rect x="1" y="1" width="{w-2}" height="{h-2}" rx="{r}"/></clipPath>'
            f'<g clip-path="url(#{cid})">{inner}</g>')


def label(x, y, s, fill=VIOLET, size=12):
    return text(x, y, s.upper(), size, fill, 700, ls=1.8)


def chip(x, y, s, col, size=13, h=28, solid=False, pad=14, tc=None):
    w = tw(s, size, True) + 2 * pad
    if solid:
        body = f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{h/2}" fill="url(#hl)"/>'
        tc = WHITE
    else:
        body = (f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{h/2}" fill="{col}" fill-opacity=".12" '
                f'stroke="{col}" stroke-opacity=".45"/>')
        tc = tc or TXT
    return body + text(x + w / 2, y + h / 2 + size * .36, s, size, tc, 600, "middle"), w


def fade(delay, dur=0.6, total=2.4):
    """Opacity 0 -> 1 between delay and delay+dur (base value 1: static renderers show the element)."""
    a, b = delay / total, min(.98, (delay + dur) / total)
    return (f'<animate attributeName="opacity" values="0;0;1;1" keyTimes="0;{a:.3f};{b:.3f};1" dur="{total}s" '
            f'fill="freeze"/>')


def rise(delay, dur=0.6, total=2.4, dy=14):
    a, b = delay / total, min(.98, (delay + dur) / total)
    return (f'<animateTransform attributeName="transform" type="translate" values="0 {dy};0 {dy};0 0;0 0" '
            f'keyTimes="0;{a:.3f};{b:.3f};1" dur="{total}s" fill="freeze"/>')


def pulse(cx, cy, r, col, grow=10):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{col}"/><circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{col}" stroke-width="2"><animate attributeName="r" values="{r};{r+grow};{r}" dur="2.2s" '
            f'repeatCount="indefinite"/><animate attributeName="stroke-opacity" values=".9;0;.9" dur="2.2s" '
            f'repeatCount="indefinite"/></circle>')


def svg(w, h, body, title, extra_defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}" role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>'
            f'{defs(extra_defs)}{body}</svg>')


def write(name, content):
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / name).write_text(content, encoding="utf-8")
    print("wrote", name)


# ------------------------------------------------------------------ icons (drawn in a 44 px circle)
def icon(kind, cx, cy, col):
    o = [f'<circle cx="{cx}" cy="{cy}" r="22" fill="{col}" fill-opacity=".14" stroke="{col}" stroke-opacity=".4"/>']
    s = f'stroke="{col}" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "voc":  # speech bubble with lines
        o.append(f'<path d="M{cx-10},{cy-8} h20 a3,3 0 0 1 3,3 v10 a3,3 0 0 1 -3,3 h-11 l-6,5 v-5 h-3 a3,3 0 0 1 -3,-3 '
                 f'v-10 a3,3 0 0 1 3,-3 z" {s}/><path d="M{cx-6},{cy-2} h12 M{cx-6},{cy+3} h8" {s}/>')
    elif kind == "bi":  # bars
        for i, hh in enumerate((8, 14, 20)):
            o.append(f'<rect x="{cx-10+i*8}" y="{cy+9-hh}" width="5" height="{hh}" rx="1.5" fill="{col}"/>')
    elif kind == "ai":  # lightning bolt
        o.append(f'<path d="M{cx+2},{cy-12} L{cx-8},{cy+2} H{cx} L{cx-2},{cy+12} L{cx+8},{cy-2} H{cx} Z" {s}/>')
    elif kind == "ml":  # connected nodes
        pts = [(cx - 9, cy - 7), (cx + 9, cy - 7), (cx, cy + 9), (cx, cy - 1)]
        for a in pts[:3]:
            o.append(f'<line x1="{pts[3][0]}" y1="{pts[3][1]}" x2="{a[0]}" y2="{a[1]}" {s}/>')
        for px, py in pts:
            o.append(f'<circle cx="{px}" cy="{py}" r="3.4" fill="{col}"/>')
    return "".join(o)


# ------------------------------------------------------------------ hero
def hero():
    W, H = 1000, 380
    b = [card(0, 0, W, H, 28, CHAR, CHAR),
         clipped(W, H, 28, f'<rect width="{W}" height="{H}" fill="url(#dots)"/><circle cx="560" cy="0" r="260" fill="url(#glowA)"/>'
                 f'<circle cx="60" cy="380" r="220" fill="url(#glowB)"/>')]
    # availability pill
    pw = tw("Open to work", 14, True) + 54
    b.append(f'<g>{fade(.1, .5)}<rect x="56" y="48" width="{pw:.0f}" height="34" rx="17" fill="{GREEN}" fill-opacity=".1" '
             f'stroke="{GREEN}" stroke-opacity=".5"/>{pulse(78, 65, 5, GREEN, 7)}'
             f'{text(94, 70, "Open to work", 14, WHITE, 600)}</g>')
    b.append(f'<g>{fade(.25, .7)}{rise(.25, .7)}{text(52, 160, "Narpat Ganwliya", 62, WHITE, 800, ls=-1)}</g>')
    b.append(f'<g>{fade(.45, .7)}{text(56, 204, "Data Analyst · AI & Automation", 25, "url(#hl)", 700)}</g>')
    b.append(f'<g>{fade(.6, .7)}{text(56, 244, "Customer analytics · Dashboards · LLM agents · Automation", 16, LMUTED)}'
             f'{text(56, 276, "Turning customer data into decisions, with AI.", 17, SUN, 700)}</g>')
    x = 56
    for i, (s, col) in enumerate((("Paris, France", "#5fc9c4"), ("MSc Big Data & AI", "#f0783a"), ("CX Data Analyst · EV industry", SUN))):
        c, w = chip(x, 306, s, col, 13, 30, tc=WHITE)
        b.append(f'<g>{fade(.8 + i * .12, .5)}{c}</g>')
        x += w + 10

    # mini dashboard window
    wx, wy, ww, wh = 636, 40, 320, 300
    b.append(f'<g>{fade(.3, .8)}{rise(.3, .8, dy=20)}')
    b.append(card(wx, wy, ww, wh, 20, BG1, BG1))
    for i, c in enumerate(("#f87171", "#fbbf24", "#34d399")):
        b.append(f'<circle cx="{wx+22+i*14}" cy="{wy+22}" r="4.5" fill="{c}" fill-opacity=".85"/>')
    b.append(text(wx + ww - 20, wy + 27, "Voice of the Customer · live", 12, MUTED, 600, "end"))
    vals = [30, 44, 37, 56, 50, 70, 63, 84]
    base, bw, gap = wy + 160, 26, 9
    pts = []
    for i, v in enumerate(vals):
        bx = wx + 24 + i * (bw + gap)
        col = BLUE if i % 2 == 0 else CYAN
        d = .5 + i * .08
        k = d / 2.2
        b.append(f'<rect x="{bx}" y="{base-v}" width="{bw}" height="{v}" rx="6" fill="{col}" fill-opacity="{.45 + i*.07:.2f}">'
                 f'<animate attributeName="height" values="0;0;{v};{v}" keyTimes="0;{k:.3f};{min(.97, k+.3):.3f};1" dur="2.2s" fill="freeze"/>'
                 f'<animate attributeName="y" values="{base};{base};{base-v};{base-v}" keyTimes="0;{k:.3f};{min(.97, k+.3):.3f};1" dur="2.2s" fill="freeze"/></rect>')
        pts.append((bx + bw / 2, base - v - 12))
    path = "M" + " L".join(f"{px:.0f},{py:.0f}" for px, py in pts)
    L = 360
    b.append(f'<path d="{path}" fill="none" stroke="{VIOLET}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" '
             f'stroke-dasharray="{L}" stroke-dashoffset="0"><animate attributeName="stroke-dashoffset" values="{L};{L};0;0" '
             f'keyTimes="0;.4;.9;1" dur="3s" fill="freeze"/></path>')
    ex, ey = pts[-1]
    b.append(pulse(round(ex), round(ey), 5, VIOLET, 9))
    b.append(f'<line x1="{wx+18}" y1="{base+1}" x2="{wx+ww-18}" y2="{base+1}" stroke="{LINE}"/>')
    x = wx + 20
    for s, col in (("127k reviews", CYAN), ("41 brands", VIOLET), ("15 topics", BLUE)):
        c, w = chip(x, base + 14, s, col, 12, 26, pad=11)
        b.append(c)
        x += w + 8
    b.append(f'<line x1="{wx+18}" y1="{base+56}" x2="{wx+ww-18}" y2="{base+56}" stroke="{LINE}"/>')
    b.append(label(wx + 20, base + 80, "AI agents", MUTED, 11))
    b.append(text(wx + ww - 20, base + 80, "sentiment · NLP · ML", 11, DIM, 600, "end"))
    x = wx + 20
    for s, solid in (("LLM agents", True), ("n8n", False), ("Python", False), ("SQL", False)):
        c, w = chip(x, base + 92, s, CYAN, 12, 26, solid=solid, pad=11)
        b.append(c)
        x += w + 8
    b.append('</g>')
    write("hero.svg", svg(W, H, "".join(b), "Narpat Ganwliya, Data Analyst, AI and Automation. Open to work from December 2026."))


# ------------------------------------------------------------------ what I do + latest build + open to
def what_i_do():
    W, H = 1000, 440
    b = [f'<rect width="{W}" height="{H}" rx="30" fill="{BG2}" stroke="{LINE}"/>']
    lx, ly, lw, lh = 22, 22, 590, H - 44
    b.append(card(lx, ly, lw, lh, 22))
    b.append(label(lx + 32, ly + 42, "What I do", VIOLET))
    b.append(text(lx + 32, ly + 74, "What I build, and how I ship it", 22, INK, 700))
    rows = [("voc", CYAN, "Customer analytics & VoC", "NPS, reviews, sentiment analysis, customer KPIs"),
            ("bi", BLUE, "BI & dashboards", "Power BI, Looker Studio, Excel and SQL reporting"),
            ("ai", AMBER, "AI agents & automation", "LLM agents, n8n workflows, Python pipelines, GitHub Actions"),
            ("ml", VIOLET, "Machine learning", "scikit-learn, churn prediction, recommender systems")]
    y = ly + 104
    for i, (k, col, t1, t2) in enumerate(rows):
        b.append(f'<g>{fade(.2 + i * .18, .5)}{icon(k, lx + 56, y + 32, col)}'
                 f'{text(lx + 94, y + 27, t1, 17, INK, 700)}{text(lx + 94, y + 49, t2, 14, MUTED)}</g>')
        if i < len(rows) - 1:
            b.append(f'<line x1="{lx+32}" y1="{y+68}" x2="{lx+lw-32}" y2="{y+68}" stroke="{LINE}"/>')
        y += 70

    rx, rw = 632, W - 632 - 22
    # latest build (gradient card)
    g = ('<linearGradient id="dark" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2a1d5c"/>'
         '<stop offset=".6" stop-color="#14254f"/><stop offset="1" stop-color="#0d3a4a"/></linearGradient>')
    b.append(f'<g>{fade(.3, .6)}' + card(rx, 22, rw, 236, 22, CHAR, CHAR))
    b.append(f'<clipPath id="lb"><rect x="{rx+1}" y="23" width="{rw-2}" height="234" rx="22"/></clipPath>'
             f'<circle cx="{rx+rw-30}" cy="52" r="70" fill="url(#glowA)" clip-path="url(#lb)"/>')
    b.append(f'<rect x="{rx}" y="22" width="{rw}" height="236" rx="22" fill="url(#dots)" clip-path="url(#lb)"/>')
    b.append(label(rx + 28, 62, "Latest build", "#f0783a"))
    b.append(text(rx + 28, 104, "Écoute", 34, WHITE, 800))
    b.append(text(rx + 28, 130, "Always-on Voice of the Customer AI agent", 14, LMUTED))
    b.append(text(rx + 28, 150, "127k reviews · 41 brands · runs daily", 13, "#5fc9c4", 600))
    b.append(f'<line x1="{rx+28}" y1="172" x2="{rx+rw-28}" y2="172" stroke="#ffffff" stroke-opacity=".15"/>')
    b.append(label(rx + 28, 200, "Also built", "#f0783a"))
    b.append(text(rx + 28, 228, "AI Resume Optimizer (n8n)", 18, WHITE, 700) + '</g>')
    # open to
    b.append(f'<g>{fade(.5, .6)}' + card(rx, 274, rw, H - 274 - 22, 22))
    b.append(label(rx + 28, 314, "Open to", GREEN))
    b.append(text(rx + 28, 346, "Data Analyst · BI · AI & Automation", 17, INK, 700))
    b.append(text(rx + 28, 372, "CDI · France, UK, Germany", 14, MUTED))
    b.append(pulse(rx + 34, 393, 4, GREEN, 6) + text(rx + 46, 398, "available from December 2026", 13, GREEN, 600) + '</g>')
    write("what-i-do.svg", svg(W, H, "".join(b), "What I do: customer analytics, BI dashboards, AI agents and automation, machine learning. Latest build: Écoute. Open to Data, BI and AI roles.", g))


# ------------------------------------------------------------------ impact numbers
def impact():
    W, H = 1000, 196
    tiles = [("5h → 20min", "Weekly CX reporting", "automated with Python + AI agents", "EV industry", CYAN),
             ("127k", "Reviews analysed", "by my Voice-of-the-Customer agent", "Écoute", VIOLET),
             ("+15%", "Customer responses", "per month, with an AI review tool", "EV industry", GREEN),
             ("Global", "Dashboard adoption", "my CX dashboards went worldwide", "EV industry", AMBER)]
    b = []
    tw_, gap = 235, 20
    for i, (big, t1, t2, tag, col) in enumerate(tiles):
        x = i * (tw_ + gap)
        size = 42 if len(big) <= 6 else 33
        tg = tw(tag, 11, True) + 20
        b.append(f'<g>{fade(.1 + i * .2, .5, 1.8)}{rise(.1 + i * .2, .5, 1.8)}'
                 + card(x, 0, tw_, H, 22) +
                 f'<rect x="{x+22}" y="0.5" width="54" height="4" rx="2" fill="{col}"/>'
                 f'<rect x="{x+tw_-22-tg:.0f}" y="22" width="{tg:.0f}" height="22" rx="11" fill="{col}" fill-opacity=".14"/>'
                 + text(x + tw_ - 22 - tg / 2, 37, tag, 11, col, 700, "middle")
                 + text(x + 22, 100, big, size, col, 800, ls=-.5)
                 + text(x + 22, 136, t1, 16, INK, 700)
                 + text(x + 22, 160, t2, 13, MUTED) + '</g>')
    write("impact.svg", svg(W, H, "".join(b), "Impact: weekly reporting from 5 hours to 20 minutes, 127k reviews analysed, +15% customer responses, dashboards adopted worldwide"))


# ------------------------------------------------------------------ stack
STACK = [("AI & Automation", CYAN, ["AI Agents", "Generative AI / LLMs", "Prompt Engineering", "n8n", "Python Automation",
                                    "Web Scraping", "APIs", "GitHub Actions"]),
         ("Data & BI", BLUE, ["SQL", "Python", "Power BI", "Looker Studio", "Excel", "DuckDB", "ETL Pipelines",
                              "Data Visualisation"]),
         ("Machine Learning", VIOLET, ["scikit-learn", "Sentiment Analysis", "NLP", "Predictive Modelling",
                                       "Recommender Systems", "pandas", "Streamlit"]),
         ("Business", AMBER, ["Voice of the Customer", "NPS", "KPI Reporting", "Market Research", "Data Storytelling",
                              "Stakeholder Communication"])]


def stack():
    W = 1000
    x0, xmax = 250, W - 40
    rows, y = [], 86
    for name, col, items in STACK:
        x, cy, chips = x0, y, []
        for it in items:
            w = tw(it, 13, True) + 28
            if x + w > xmax:
                x, cy = x0, cy + 40
            chips.append((x, cy, it))
            x += w + 9
        rows.append((name, col, y, chips, cy))
        y = cy + 62
    H = y - 14
    b = [card(0, 0, W, H, 26), label(44, 52, "Stack", VIOLET, 13)]
    for gi, (name, col, ry, chips, last) in enumerate(rows):
        b.append(f'<circle cx="48" cy="{ry+14}" r="4.5" fill="{col}"/>' + label(62, ry + 19, name, col, 12))
        for ci, (x, cy, it) in enumerate(chips):
            c, _ = chip(x, cy, it, col, 13, 30)
            b.append(f'<g>{fade(.1 + gi * .15 + ci * .04, .4, 2)}{c}</g>')
        if gi < len(rows) - 1:
            b.append(f'<line x1="44" y1="{last+46}" x2="{W-44}" y2="{last+46}" stroke="{LINE}"/>')
    write("stack.svg", svg(W, H, "".join(b), "Stack: " + "; ".join(f"{n}: {', '.join(i)}" for n, _, i in STACK)))


# ------------------------------------------------------------------ projects (one card per repo, linked from README)
PROJECTS = [
    ("Voice-of-the-Customer-AI", "Écoute: Voice of the Customer AI",
     ["AI agent that reads 127k French app reviews,", "prices each pain point in stars and explains", "complaint spikes on its own."],
     "127,479 reviews · tone accuracy 91%", ["Python", "DuckDB", "LLM agents"], CYAN),
    ("Resume-Optimizer-automated-CV-tailoring-pipeline", "AI Resume Optimizer",
     ["n8n pipeline: scrapes fresh jobs, an AI agent", "matches them to my CV and writes a tailored,", "ATS-friendly version every morning."],
     "Runs daily at 08:00 · no manual steps", ["n8n", "AI agents", "Apify"], AMBER),
    ("movie-recommender-system", "Movie Recommender",
     ["Content-based recommendation engine with", "TMDB data, cosine similarity and a", "Streamlit web app."],
     "scikit-learn · cosine similarity", ["Python", "scikit-learn", "Streamlit"], VIOLET),
    ("Blinkit-Sales-Analysis-Dashboard", "Blinkit Sales Dashboard",
     ["Interactive Power BI dashboard: sales by", "outlet type, size, location and item", "category, with drill-down filters."],
     "Power BI · DAX · Power Query", ["Power BI", "DAX", "BI"], BLUE),
    ("Global-Air-Pollution-Report-Dashboard", "Global Air Pollution",
     ["Power BI report on GHG, CO2 and PM2.5", "trends from 1990 to 2020, with maps and", "the top polluting countries."],
     "30 years · 3 pollution indicators", ["Power BI", "SQL", "Python"], GREEN),
    ("AirBnB-2025-NYC-Listing---Exploratory-Data-Analysis-using-Python", "Airbnb NYC 2025 EDA",
     ["Exploratory analysis of New York Airbnb", "listings: prices, neighbourhoods, room", "types and availability."],
     "pandas · Matplotlib · Seaborn", ["Python", "pandas", "EDA"], PINK),
]


def projects():
    for i, (repo, title, lines, metric, tags, col) in enumerate(PROJECTS):
        W, H = 320, 258
        b = [card(0, 0, W, H, 22),
             clipped(W, H, 22, f'<circle cx="{W-10}" cy="10" r="110" fill="{col}" fill-opacity=".07"/>'),
             f'<circle cx="38" cy="40" r="16" fill="{col}" fill-opacity=".15" stroke="{col}" stroke-opacity=".5"/>',
             f'<path d="M33,35 l-5,5 5,5 M43,35 l5,5 -5,5" stroke="{col}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
             text(64, 46, title, 16 if tw(title, 16, True) < 220 else 14, INK, 700),
             f'<path d="M{W-34},{34} l9,-9 M{W-33},{25} h8 v8" stroke="{MUTED}" stroke-width="1.8" fill="none" stroke-linecap="round"/>']
        for j, ln in enumerate(lines):
            b.append(text(24, 88 + j * 20, ln, 13.5, TXT))
        mw = tw(metric, 12, True) + 24
        b.append(f'<rect x="24" y="160" width="{mw:.0f}" height="26" rx="13" fill="{col}" fill-opacity=".16"/>'
                 + text(24 + mw / 2, 177, metric, 12, col, 700, "middle"))
        x = 24
        for t in tags:
            c, w = chip(x, 204, t, MUTED, 12, 28, pad=12)
            b.append(c)
            x += w + 8
        write(f"project-{i+1}.svg", svg(W, H, "".join(b), f"{title}: {' '.join(lines)}"))


# ------------------------------------------------------------------ journey
def journey():
    W, H = 1000, 240
    steps = [("2019", "BSc Mathematics", "MDSU, India", BLUE),
             ("2022", "Data Analyst", "Hazial Ministration", CYAN),
             ("2023", "Market Analyst", "ARSS Consultancy", GREEN),
             ("2024", "MSc Big Data & AI", "Montpellier BS", VIOLET),
             ("2026", "CX Data Analyst", "EV industry, France", AMBER),
             ("NEXT", "Data / AI role", "CDI · Dec 2026", PINK)]
    b = [card(0, 0, W, H, 26), label(44, 50, "Journey", VIOLET, 13)]
    y, x0, x1 = 126, 96, W - 96
    step = (x1 - x0) / (len(steps) - 1)
    L = x1 - x0
    b.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{LINE}" stroke-width="4" stroke-linecap="round"/>')
    b.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="url(#hl)" stroke-width="4" stroke-linecap="round" '
             f'stroke-dasharray="{L}" stroke-dashoffset="0"><animate attributeName="stroke-dashoffset" values="{L};0;0" '
             f'keyTimes="0;.85;1" dur="2.8s" fill="freeze"/></line>')
    for i, (yr, t1, t2, col) in enumerate(steps):
        x = x0 + i * step
        b.append(f'<g>{fade(.2 + i * .4, .4, 3)}'
                 + text(x, y - 30, yr, 19, col, 800, "middle")
                 + f'<circle cx="{x:.0f}" cy="{y}" r="10" fill="{BG1}" stroke="{col}" stroke-width="4"/>'
                 + f'<circle cx="{x:.0f}" cy="{y}" r="3.5" fill="{col}"/>'
                 + text(x, y + 42, t1, 15, INK, 700, "middle") + text(x, y + 64, t2, 13, MUTED, 400, "middle") + '</g>')
    b.append(f'<circle cx="{x1:.0f}" cy="{y}" r="10" fill="none" stroke="{PINK}" stroke-width="2">'
             f'<animate attributeName="r" values="10;22;10" dur="2.2s" repeatCount="indefinite"/>'
             f'<animate attributeName="stroke-opacity" values=".9;0;.9" dur="2.2s" repeatCount="indefinite"/></circle>')
    write("journey.svg", svg(W, H, "".join(b), "Journey: BSc Mathematics 2019, Data Analyst 2022, Market Analyst 2023, MSc Big Data and AI 2024, CX Data Analyst in the EV industry 2026, next a Data or AI CDI"))


# ------------------------------------------------------------------ closing
def closing():
    W, H = 1000, 200
    g = ('<linearGradient id="close" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1c1646"/>'
         '<stop offset=".5" stop-color="#132447"/><stop offset="1" stop-color="#0d3440"/></linearGradient>')
    b = [card(0, 0, W, H, 28, CHAR, CHAR),
         clipped(W, H, 28, f'<rect width="{W}" height="{H}" fill="url(#dots)"/><circle cx="160" cy="0" r="200" fill="url(#glowA)"/>'
                 f'<circle cx="860" cy="200" r="200" fill="url(#glowB)"/>'),
         text(W / 2, 86, "Data that listens. Automation that ships.", 30, WHITE, 800, "middle"),
         text(W / 2, 122, "From customer reviews to dashboards to AI agents: systems that turn noise into decisions.", 15, LMUTED, 400, "middle"),
         text(W / 2, 158, "Thanks for stopping by ✦", 13, SUN, 700, "middle", ls=1)]
    write("closing.svg", svg(W, H, "".join(b), "Data that listens. Automation that ships.", g))


# ------------------------------------------------------------------ live GitHub data
def get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-readme-builder", "Accept": "application/vnd.github+json"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read().decode("utf-8")
    return data if raw else json.loads(data)


def contributions():
    page = get(f"https://github.com/users/{USER}/contributions", raw=True)
    level, count = {}, {}
    for m in re.finditer(r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="([^"]+)"[^>]*data-level="(\d)"', page):
        level[m.group(2)] = (m.group(1), int(m.group(3)))
    for m in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        n = re.match(r"(\d+) contribution", m.group(2))
        count[m.group(1)] = int(n.group(1)) if n else 0
    days = sorted((d, lv, count.get(cid, 0)) for cid, (d, lv) in level.items())
    return days


def streaks(days):
    best = cur = 0
    for _, _, n in days:
        cur = cur + 1 if n > 0 else 0
        best = max(best, cur)
    current = 0
    for i, (_, _, n) in enumerate(reversed(days)):
        if n > 0:
            current += 1
        elif i == 0:
            continue  # today without a commit yet does not break the streak
        else:
            break
    return current, best


def activity(days, user, repos):
    W = 1000
    total = sum(n for _, _, n in days)
    active = sum(1 for _, _, n in days if n > 0)
    cur, best = streaks(days)
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    tiles = [(total, "Contributions", "last 12 months"), (active, "Active days", "days with a commit"),
             (cur, "Current streak", "consecutive days"), (best, "Best streak", "longest run")]
    # heatmap geometry
    weeks = {}
    for d, lv, n in days:
        dd = dt.date.fromisoformat(d)
        wk = (dd - dt.timedelta(days=(dd.weekday() + 1) % 7))
        weeks.setdefault(wk, {})[(dd.weekday() + 1) % 7] = lv
    wlist = sorted(weeks)[-53:]
    cell, gap = 13, 3.4
    gw = len(wlist) * (cell + gap) - gap
    gx = (W - gw) / 2
    gy = 262
    H = gy + 7 * (cell + gap) + 66
    b = [card(0, 0, W, H, 26), label(44, 52, "GitHub activity", VIOLET, 13),
         text(W - 44, 52, f"Updated {dt.date.today().isoformat()}", 12, DIM, 600, "end")]
    tw_, tg = 214, 15
    for i, (num, t1, t2) in enumerate(tiles):
        x = 44 + i * (tw_ + tg)
        fill = CHAR if i == 0 else BG2
        nc, sc, mc = (WHITE, WHITE, LMUTED) if i == 0 else (INK, INK, MUTED)
        b.append(f'<g>{fade(.1 + i * .15, .5, 1.6)}<rect x="{x}" y="76" width="{tw_}" height="112" rx="18" fill="{fill}" '
                 f'stroke="{LINE if i else "none"}"/>' + text(x + 22, 128, f"{num:,}", 38, nc, 800)
                 + text(x + 22, 156, t1, 15, sc, 700) + text(x + 22, 175, t2, 12, mc, 500) + '</g>')
    x = 44
    for s in (f"{user.get('public_repos', 0)} public repos", f"{stars} star" + ("s" if stars != 1 else ""), f"{user.get('followers', 0)} follower" + ("s" if user.get("followers", 0) != 1 else ""),
              f"{user.get('following', 0)} following"):
        c, w = chip(x, 206, s, MUTED, 12, 28, pad=16)
        b.append(c)
        x += w + 10
    colors = ["#eee6d6", "#f6c5a8", "#ef8f60", "#e2492b", "#9e2f18"]
    for wi, wk in enumerate(wlist):
        for dow, lv in weeks[wk].items():
            b.append(f'<rect x="{gx + wi*(cell+gap):.1f}" y="{gy + dow*(cell+gap):.1f}" width="{cell}" height="{cell}" rx="3.5" '
                     f'fill="{colors[min(lv, 4)]}"/>')
    ly = gy + 7 * (cell + gap) + 30
    b.append(text(W - 44 - 5 * (cell + 4) - 44, ly + 11, "Less", 12, DIM, 600, "end"))
    for i, c in enumerate(colors):
        b.append(f'<rect x="{W - 44 - 36 - (5 - i) * (cell + 4)}" y="{ly}" width="{cell}" height="{cell}" rx="3.5" fill="{c}"/>')
    b.append(text(W - 44, ly + 11, "More", 12, DIM, 600, "end"))
    b.append(text(44, ly + 11, "Contribution calendar · last 12 months", 12, DIM, 600))
    write("activity.svg", svg(W, H, "".join(b), f"GitHub activity: {total} contributions in the last year, {active} active days, best streak {best} days"))


LANG_COLORS = {"Python": "#2b4a9b", "Jupyter Notebook": "#c98a00", "HTML": "#e2492b", "CSS": "#0f7c80",
               "PLpgSQL": "#4f8a2b", "SCSS": "#c2416b", "JavaScript": "#e0a526", "SQL": "#4f8a2b", "Shell": "#8a8f99", "TSQL": "#0f7c80"}


def languages(repos):
    tot = {}
    for r in repos:
        if r.get("fork") or r["name"] == USER:
            continue
        try:
            for lang, n in get(r["languages_url"]).items():
                tot[lang] = tot.get(lang, 0) + n
        except Exception as e:
            print("languages skip", r["name"], e)
    tot.pop("Jupyter Notebook", None)  # notebook JSON (outputs, images) would drown everything else
    s = sum(tot.values()) or 1
    items = sorted(((k, v / s) for k, v in tot.items()), key=lambda kv: -kv[1])
    main, rest = items[:6], sum(p for _, p in items[6:])
    if rest > 0:
        main.append(("Other", rest))
    W = 1000
    rows = (len(main) + 1) // 2
    H = 140 + rows * 38 + 20
    b = [card(0, 0, W, H, 26), label(44, 52, "Languages", VIOLET, 13),
         text(W - 44, 52, "Public repos · notebooks excluded", 12, DIM, 600, "end")]
    x, bw = 44, W - 88
    b.append(f'<clipPath id="bar"><rect x="44" y="80" width="{bw}" height="16" rx="8"/></clipPath><g clip-path="url(#bar)">')
    for i, (k, p) in enumerate(main):
        w = bw * p
        b.append(f'<rect x="{x:.1f}" y="80" width="{w + 1:.1f}" height="16" fill="{LANG_COLORS.get(k, "#64748b")}">'
                 f'<animate attributeName="width" values="0;0;{w+1:.1f};{w+1:.1f}" keyTimes="0;{.1+i*.08:.2f};{.5+i*.06:.2f};1" dur="2s" fill="freeze"/></rect>')
        x += w
    b.append('</g>')
    for i, (k, p) in enumerate(main):
        cx = 44 + (i % 2) * 480
        cy = 140 + (i // 2) * 38
        b.append(f'<circle cx="{cx+7}" cy="{cy-5}" r="7" fill="{LANG_COLORS.get(k, "#64748b")}"/>'
                 + text(cx + 26, cy, k, 16, TXT, 600) + text(cx + 430, cy, f"{p*100:.1f}%", 15, MUTED, 600, "end"))
    write("languages.svg", svg(W, H, "".join(b), "Languages: " + ", ".join(f"{k} {p*100:.1f}%" for k, p in main)))


def main():
    hero(); what_i_do(); impact(); stack(); projects(); journey(); closing()
    try:
        user = get(f"https://api.github.com/users/{USER}")
        repos = get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
        activity(contributions(), user, repos)
        languages(repos)
    except Exception as e:  # keep yesterday's cards when GitHub is unreachable
        print("live data skipped:", e)


if __name__ == "__main__":
    main()
