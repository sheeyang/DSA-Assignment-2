#!/usr/bin/env python3
"""
generate_report.py — produce report/index.html

Compiles everything into a single self-contained HTML file:
  • Summary table (displacement, runtime, memory, input size)
  • Performance plots (displacement vs target, time vs memory, memory vs input)
  • Per-test visualizations (provided + custom), grouped by category
  • Custom test case descriptions
  • All images embedded as base64 so the file is fully portable

Usage:
    python generate_report.py
Output:
    report/index.html
"""

import os
import csv
import base64
import html
from datetime import datetime

ROOT        = os.path.dirname(os.path.abspath(__file__))
VIZ_DIR     = os.path.join(ROOT, 'visualization')
DISP_DIR    = os.path.join(ROOT, 'displacement_vs_target')
TIME_DIR    = os.path.join(ROOT, 'time_vs_memory')
MEM_DIR     = os.path.join(ROOT, 'memory_vs_inputsize')
REPORT_DIR  = os.path.join(ROOT, 'report')

# ── test case metadata ────────────────────────────────────────────────────────

PROVIDED_CASES = [
    'rectangle_with_two_holes',
    'cushion_with_hexagonal_hole',
    'blob_with_two_holes',
    'wavy_with_three_holes',
    'lake_with_two_islands',
    'original_01', 'original_02', 'original_03', 'original_04', 'original_05',
    'original_06', 'original_07', 'original_08', 'original_09', 'original_10',
]

CUSTOM_CASES = [
    'many_holes',
    'dense_outer',
    'narrow_corridor',
    'nested_rings',
    'large_with_many_holes',
]

CUSTOM_DESCRIPTIONS = {
    'many_holes': (
        'Many holes (6 circular holes)',
        'A large outer square containing 6 evenly-spaced circular holes arranged in a 3×2 grid. '
        'Targets topology-aware simplification across 7 simultaneous rings. '
        '<b>Challenge:</b> the algorithm must preserve all 6 holes without accidentally merging or collapsing any ring.'
    ),
    'dense_outer': (
        'High vertex count (400 vertices, single ring)',
        'A single sinusoidally-perturbed ring (r = 1000 + 80·sin(8t)) sampled at 400 vertices. '
        'Targets heap/priority-queue performance under a high-volume vertex stream. '
        '<b>Challenge:</b> many near-collinear points with small displacement — the simplifier must pick the globally '
        'cheapest removals without greedily eliminating almost-free vertices that block better savings later.'
    ),
    'narrow_corridor': (
        'Narrow gap (3-unit clearance between hole and outer ring)',
        'A wide rectangle with a thin rectangular hole only 3 units from the top edge. '
        'Targets near-degenerate topology where any vertex removal on the hole could violate non-intersection. '
        '<b>Challenge:</b> the gap is smaller than typical simplification step sizes, so the algorithm must '
        'respect geometric constraints and halt simplification early to avoid self-intersection.'
    ),
    'nested_rings': (
        'Near-degenerate nesting (inner radius 400, outer 500)',
        'Two concentric 60-vertex circles of radius 500 (exterior) and 400 (hole). '
        'Targets the thin-annulus case where hole and outer ring are geometrically close at all angles. '
        '<b>Challenge:</b> simplifying either ring risks bringing a simplified chord across the other ring, '
        'requiring careful per-triangle displacement accounting.'
    ),
    'large_with_many_holes': (
        'High vertex count × many holes (100-vertex outer + 8 irregular holes)',
        'A 100-vertex outer circle at r=800 with 8 irregular 6-vertex polygon holes placed at r=450, '
        'evenly distributed angularly. Combines the pressure of 9 simultaneous rings with non-trivial hole geometry. '
        '<b>Challenge:</b> the simplifier must budget areal displacement across 9 rings and deal with irregular '
        '(non-convex) hole shapes that have unequal per-vertex displacement costs.'
    ),
}

# ── helpers ───────────────────────────────────────────────────────────────────

def img_b64(path):
    """Return a base64 data URI for a PNG, or None if file doesn't exist."""
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('ascii')
    return f'data:image/png;base64,{data}'


def load_csv(path):
    """Return list-of-dicts from a CSV file, or [] if not found."""
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def fmt_sci(val):
    try:
        v = float(val)
        if v == 0:
            return '0'
        return f'{v:.3e}'
    except (ValueError, TypeError):
        return val or '—'


def fmt_f(val, decimals=3):
    try:
        return f'{float(val):.{decimals}f}'
    except (ValueError, TypeError):
        return val or '—'


def h(text):
    return html.escape(str(text))

# ── data loading ──────────────────────────────────────────────────────────────

disp_rows = {r['test_case']: r for r in load_csv(os.path.join(DISP_DIR, 'displacement_vs_target.csv'))}
time_rows = {r['test_case']: r for r in load_csv(os.path.join(TIME_DIR, 'time_vs_memory.csv'))}
mem_rows  = {r['test_case']: r for r in load_csv(os.path.join(MEM_DIR,  'memory_vs_inputsize.csv'))}


def merged(name):
    d = disp_rows.get(name, {})
    t = time_rows.get(name, {})
    m = mem_rows.get(name, {})
    return {
        'target':    d.get('target_vertices', '—'),
        'actual':    d.get('actual_vertices', '—'),
        'disp':      d.get('areal_displacement', ''),
        'time':      t.get('wall_time_s', ''),
        'peak_mem':  t.get('peak_memory_mb', m.get('peak_memory_mb', '')),
        'input_v':   m.get('input_vertices', ''),
    }

# ── HTML generation ───────────────────────────────────────────────────────────

def plot_section(title, img_path, csv_path, anchor):
    uri = img_b64(img_path)
    rows = load_csv(csv_path)
    img_html = (f'<img src="{uri}" alt="{h(title)}" class="plot-img">'
                if uri else '<p class="missing">Image not generated yet — run the plot script first.</p>')

    # build table from CSV
    if rows:
        headers = list(rows[0].keys())
        thead = ''.join(f'<th>{h(c)}</th>' for c in headers)
        tbody = ''
        for r in rows:
            cells = ''
            for k, v in r.items():
                if 'displacement' in k:
                    v = fmt_sci(v)
                elif 'time' in k or 'memory' in k:
                    v = fmt_f(v, 4)
                cells += f'<td>{h(v)}</td>'
            tbody += f'<tr>{cells}</tr>'
        table_html = f'<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>'
    else:
        table_html = '<p class="missing">CSV not found — run the plot script first.</p>'

    return f'''
    <section id="{anchor}">
      <h2>{h(title)}</h2>
      <div class="plot-wrap">{img_html}</div>
      <details>
        <summary>Raw data</summary>
        {table_html}
      </details>
    </section>'''


def viz_card(name, is_custom=False):
    img_path = os.path.join(VIZ_DIR, f'viz_{name}.png')
    uri = img_b64(img_path)
    r = merged(name)

    badge = '<span class="badge custom">custom</span>' if is_custom else '<span class="badge provided">provided</span>'
    img_html = (f'<img src="{uri}" alt="viz_{h(name)}" class="viz-img">'
                if uri else '<p class="missing">Not yet visualized.</p>')

    stats = f'''
      <div class="stats">
        <span>Input: <b>{h(r["input_v"])}</b> verts</span>
        <span>Target: <b>{h(r["target"])}</b></span>
        <span>Actual: <b>{h(r["actual"])}</b></span>
        <span>Displacement: <b>{fmt_sci(r["disp"])}</b></span>
        <span>Runtime: <b>{fmt_f(r["time"], 4)}s</b></span>
        <span>Peak mem: <b>{fmt_f(r["peak_mem"], 2)} MB</b></span>
      </div>'''

    if is_custom and name in CUSTOM_DESCRIPTIONS:
        short, desc = CUSTOM_DESCRIPTIONS[name]
        desc_html = f'<div class="desc"><b>{h(short)}</b><p>{desc}</p></div>'
    else:
        desc_html = ''

    return f'''
    <div class="viz-card" id="viz-{h(name)}">
      <h3>{h(name.replace("_", " ").title())} {badge}</h3>
      {desc_html}
      {stats}
      {img_html}
    </div>'''


def summary_table(names, label):
    rows_html = ''
    for name in names:
        r = merged(name)
        rows_html += f'''<tr>
          <td><a href="#viz-{h(name)}">{h(name)}</a></td>
          <td>{h(r["input_v"])}</td>
          <td>{h(r["target"])}</td>
          <td>{h(r["actual"])}</td>
          <td>{fmt_sci(r["disp"])}</td>
          <td>{fmt_f(r["time"], 4)}</td>
          <td>{fmt_f(r["peak_mem"], 2)}</td>
        </tr>'''
    return f'''
    <h3>{h(label)}</h3>
    <table>
      <thead><tr>
        <th>Test case</th><th>Input verts</th><th>Target</th><th>Actual</th>
        <th>Areal displacement</th><th>Runtime (s)</th><th>Peak mem (MB)</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>'''


CSS = '''
:root {
  --bg: #f8f9fa; --surface: #fff; --border: #dee2e6;
  --primary: #2196F3; --custom: #FF9800; --provided: #4CAF50;
  --text: #212529; --muted: #6c757d;
  font-size: 15px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }
a { color: var(--primary); text-decoration: none; }
a:hover { text-decoration: underline; }

/* layout */
header { background: var(--primary); color: #fff; padding: 2rem 2.5rem; }
header h1 { font-size: 1.8rem; }
header p  { opacity: .85; margin-top: .3rem; }
nav  { background: #1565C0; padding: .6rem 2.5rem; position: sticky; top: 0; z-index: 100;
       display: flex; gap: 1.5rem; flex-wrap: wrap; }
nav a { color: #fff; font-size: .9rem; opacity: .85; }
nav a:hover { opacity: 1; text-decoration: none; }
main { max-width: 1400px; margin: 0 auto; padding: 2rem 2.5rem; }
section { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
          padding: 1.5rem; margin-bottom: 2rem; }
h2 { font-size: 1.3rem; margin-bottom: 1rem; border-bottom: 2px solid var(--primary); padding-bottom: .4rem; }
h3 { font-size: 1.05rem; margin: 1rem 0 .5rem; }

/* tables */
table { width: 100%; border-collapse: collapse; font-size: .85rem; margin-top: .8rem; }
th { background: #e3f2fd; text-align: left; padding: .45rem .7rem; border: 1px solid var(--border); }
td { padding: .4rem .7rem; border: 1px solid var(--border); }
tr:nth-child(even) td { background: #fafafa; }
tr:hover td { background: #e8f4fd; }

/* plots */
.plot-wrap { text-align: center; margin: .5rem 0 1rem; }
.plot-img  { max-width: 100%; border: 1px solid var(--border); border-radius: 4px; }

/* viz grid */
.viz-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(560px, 1fr)); gap: 1.5rem; }
.viz-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; }
.viz-card h3 { font-size: 1rem; margin-bottom: .4rem; display: flex; align-items: center; gap: .5rem; }
.viz-img  { width: 100%; border-radius: 4px; margin-top: .6rem; border: 1px solid var(--border); }

/* stats strip */
.stats { display: flex; flex-wrap: wrap; gap: .4rem 1.2rem; font-size: .82rem;
         background: var(--bg); border-radius: 4px; padding: .4rem .6rem; margin: .4rem 0; }
.stats span { color: var(--muted); }
.stats b { color: var(--text); }

/* description */
.desc { font-size: .85rem; background: #fff8e1; border-left: 3px solid var(--custom);
        padding: .5rem .8rem; border-radius: 4px; margin-bottom: .5rem; }
.desc p { margin-top: .3rem; color: #555; }

/* badges */
.badge { font-size: .72rem; font-weight: 600; padding: .15rem .45rem;
         border-radius: 3px; text-transform: uppercase; letter-spacing: .04em; }
.badge.custom   { background: #fff3e0; color: #e65100; }
.badge.provided { background: #e8f5e9; color: #2e7d32; }

/* misc */
.missing { color: var(--muted); font-style: italic; padding: .5rem; }
details { margin-top: .8rem; }
summary { cursor: pointer; color: var(--primary); font-size: .9rem; }
summary:hover { text-decoration: underline; }
footer { text-align: center; padding: 2rem; font-size: .8rem; color: var(--muted); }
'''


def build_html():
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    nav_links = ''.join([
        '<a href="#summary">Summary</a>',
        '<a href="#displacement">Displacement vs Target</a>',
        '<a href="#time-memory">Runtime vs Memory</a>',
        '<a href="#memory-size">Memory vs Input Size</a>',
        '<a href="#provided-viz">Provided Visualizations</a>',
        '<a href="#custom-viz">Custom Visualizations</a>',
    ])

    summary_sec = f'''
    <section id="summary">
      <h2>Results Summary</h2>
      {summary_table(PROVIDED_CASES, "Provided test cases")}
      {summary_table(CUSTOM_CASES,   "Custom test cases")}
    </section>'''

    disp_sec = plot_section(
        'Areal Displacement vs Target Vertex Count',
        os.path.join(DISP_DIR, 'displacement_vs_target.png'),
        os.path.join(DISP_DIR, 'displacement_vs_target.csv'),
        'displacement',
    )
    time_sec = plot_section(
        'Wall-Clock Runtime vs Peak Memory Usage',
        os.path.join(TIME_DIR, 'time_vs_memory.png'),
        os.path.join(TIME_DIR, 'time_vs_memory.csv'),
        'time-memory',
    )
    mem_sec = plot_section(
        'Peak Memory Usage vs Input Size',
        os.path.join(MEM_DIR, 'memory_vs_inputsize.png'),
        os.path.join(MEM_DIR, 'memory_vs_inputsize.csv'),
        'memory-size',
    )

    provided_cards = ''.join(viz_card(n, is_custom=False) for n in PROVIDED_CASES)
    custom_cards   = ''.join(viz_card(n, is_custom=True)  for n in CUSTOM_CASES)

    provided_sec = f'''
    <section id="provided-viz">
      <h2>Provided Test Case Visualizations</h2>
      <p style="font-size:.85rem;color:var(--muted);margin-bottom:1rem">
        Each card shows: Input | My Output | Expected Output
      </p>
      <div class="viz-grid">{provided_cards}</div>
    </section>'''

    custom_sec = f'''
    <section id="custom-viz">
      <h2>Custom Test Case Visualizations</h2>
      <p style="font-size:.85rem;color:var(--muted);margin-bottom:1rem">
        Each card shows: Input | My Output &nbsp;(no expected — custom datasets)
      </p>
      <div class="viz-grid">{custom_cards}</div>
    </section>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DSA Assignment 2 — Polygon Simplification Report</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Polygon Simplification — Results Report</h1>
  <p>DSA Assignment 2 &nbsp;|&nbsp; Generated {now}</p>
</header>
<nav>{nav_links}</nav>
<main>
  {summary_sec}
  {disp_sec}
  {time_sec}
  {mem_sec}
  {provided_sec}
  {custom_sec}
</main>
<footer>Generated by generate_report.py &nbsp;·&nbsp; {now}</footer>
</body>
</html>'''


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    out_path = os.path.join(REPORT_DIR, 'index.html')
    print('Building report ...')

    content = build_html()
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)

    size_kb = os.path.getsize(out_path) / 1024
    print(f'Saved: {out_path}  ({size_kb:.0f} KB)')

    # Try to open in browser
    import subprocess, sys
    try:
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', out_path])
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', out_path])
        else:
            subprocess.Popen(['xdg-open', out_path])
    except Exception:
        pass


if __name__ == '__main__':
    main()
