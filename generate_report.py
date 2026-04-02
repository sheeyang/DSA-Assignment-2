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
import json
import re
from datetime import datetime

ROOT        = os.path.dirname(os.path.abspath(__file__))
VIZ_DIR     = os.path.join(ROOT, 'visualization')
DISP_DIR    = os.path.join(ROOT, 'displacement_vs_target')
TIME_DIR    = os.path.join(ROOT, 'time_vs_memory')
MEM_DIR     = os.path.join(ROOT, 'memory_vs_inputsize')
RESULTS_JSON = os.path.join(ROOT, 'test_results.json')
REPORT_CONTENT_JSON = os.path.join(ROOT, 'report_content.json')

# ── load report content from JSON ────────────────────────────────────────────

def load_report_content():
    if not os.path.exists(REPORT_CONTENT_JSON):
        return {}, {}, {}, {}, []
    with open(REPORT_CONTENT_JSON, encoding='utf-8') as f:
        data = json.load(f)
    return (
        data.get('provided', {}),
        data.get('custom', {}),
        data.get('graph_summaries', {}),
        data.get('curve_fits', {}),
        data.get('discussion', []),
    )

PROVIDED_DESCS, CUSTOM_DESCS, _GRAPH_SUMMARIES_PLACEHOLDER, _CURVE_FITS_PLACEHOLDER, _DISCUSSION_PLACEHOLDER = load_report_content()

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


def fmt_result_metric(val):
    if val in (None, ''):
        return '—'
    return fmt_sci(val)


def fmt_result_diff(actual, expected):
    if actual in (None, '') or expected in (None, ''):
        return '—'
    try:
        return f'{float(actual) - float(expected):+.3e}'
    except (ValueError, TypeError):
        return '—'


def first_present(*values):
    for value in values:
        if value not in (None, ''):
            return value
    return None


def extract_metric(message, *patterns):
    if not message:
        return None
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(1)
    return None


def result_metrics(entry):
    message = entry.get('message', '')
    return {
        'input_area': first_present(
            entry.get('input_area_actual'),
            extract_metric(
                message,
                r'input=([-+0-9.eE]+)',
                r'area_in=([-+0-9.eE]+)',
                r'area_in mismatch: got ([-+0-9.eE]+)',
            ),
        ),
        'output_area': first_present(
            entry.get('output_area_actual'),
            extract_metric(
                message,
                r'output=([-+0-9.eE]+)',
                r'area_out=([-+0-9.eE]+)',
                r'area_out mismatch: got ([-+0-9.eE]+)',
            ),
        ),
        'actual_displacement': first_present(
            entry.get('displacement_actual'),
            extract_metric(
                message,
                r'disp=([-+0-9.eE]+)',
                r'displacement WORSE: got ([-+0-9.eE]+)',
            ),
        ),
        'expected_displacement': first_present(
            entry.get('displacement_expected'),
            extract_metric(
                message,
                r'expected=([-+0-9.eE]+)',
                r'\(expected ([-+0-9.eE]+)\)',
                r'displacement WORSE: got [-+0-9.eE]+, expected <= ([-+0-9.eE]+)',
            ),
        ),
    }

# ── test results ─────────────────────────────────────────────────────────────────────

def load_test_results():
    if not os.path.exists(RESULTS_JSON):
        return None
    with open(RESULTS_JSON, encoding='utf-8') as f:
        return json.load(f)


def test_results_section(data):
    if data is None:
        return '''
    <section id="test-results">
      <h2>Test Results</h2>
      <p class="missing">test_results.json not found — run python run_tests.py first.</p>
    </section>'''

    summary = data.get('summary', {})
    passed  = summary.get('passed', 0)
    failed  = summary.get('failed', 0)
    total   = summary.get('total', 0)
    better  = sum(1 for r in data.get('provided', []) if r.get('status') == 'BETTER')
    badge_color = '#2e7d32' if failed == 0 else '#c62828'
    badge_text  = 'ALL PASS' if failed == 0 else f'{failed} FAILED'
    better_note = f' &nbsp;<span style="background:#1565C0;color:#fff;padding:.2rem .5rem;border-radius:4px;font-size:.8rem">{better} BETTER</span>' if better else ''

    def status_cell_html(status, show_validate=True):
        if status == 'BETTER':
            cls, icon = 'better', '\u2605'  # ★
        elif status in ('PASS', 'OK'):
            cls, icon = 'pass', '✔'
        else:
            cls, icon = 'fail', '✘'
        if show_validate:
            return f'<td class="{cls}">{icon} {h(status)}</td>'
        custom_cls = 'ok' if status == 'OK' else cls
        return f'<td class="{custom_cls}">{icon} {h(status)}</td>'

    def rows_html(entries, show_validate=True, include_expected=False):
        out = ''
        for r in entries:
            status = r.get('status', '')
            metrics = result_metrics(r)
            row = f'''<tr>
              <td><a href="#viz-{h(r["name"])}">{h(r["name"])}</a></td>
              <td>{h(r["target"])}</td>
              <td>{fmt_result_metric(metrics["input_area"])}</td>
              <td>{fmt_result_metric(metrics["output_area"])}</td>
              <td>{fmt_result_metric(metrics["actual_displacement"])}</td>'''
            if include_expected:
                row += f'''\n              <td>{fmt_result_metric(metrics["expected_displacement"])}</td>'''
            row += f'''\n              <td>{fmt_result_diff(metrics["actual_displacement"], metrics["expected_displacement"])}</td>
              {status_cell_html(status, show_validate)}
            </tr>'''
            out += row
        return out

    provided = data.get('provided', [])
    custom   = data.get('custom', [])

    return f'''
    <section id="test-results">
      <h2>Test Results
        <span style="float:right;font-size:.85rem;font-weight:600;background:{badge_color};
               color:#fff;padding:.2rem .7rem;border-radius:4px">{passed}/{total} &nbsp;{badge_text}</span>{better_note}
      </h2>
      <h3>Provided test cases</h3>
      <div class="table-wrap">
        <table>
                    <thead><tr><th>Test case</th><th>Target</th><th>Input area</th><th>Output area</th><th>Actual displacement</th><th>Expected displacement</th><th>Diff</th><th>Status</th></tr></thead>
          <tbody>{rows_html(provided, show_validate=True, include_expected=True)}</tbody>
        </table>
      </div>
      <h3 style="margin-top:1.2rem">Custom test cases</h3>
      <div class="table-wrap">
        <table>
                    <thead><tr><th>Test case</th><th>Target</th><th>Input area</th><th>Output area</th><th>Displacement</th><th>Diff</th><th>Status</th></tr></thead>
          <tbody>{rows_html(custom, show_validate=False, include_expected=False)}</tbody>
        </table>
      </div>
    </section>'''

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

def render_plot_summary(summary):
    if not summary:
        return ''

    title = summary.get('title', 'Summary and Interpretation')
    paragraphs = summary.get('paragraphs')
    if not paragraphs:
        text = summary.get('text', '')
        paragraphs = [text] if text else []
    if not paragraphs:
        return ''

    body = ''.join(f'<p>{h(paragraph)}</p>' for paragraph in paragraphs if paragraph)
    return f'''
      <div class="plot-summary">
        <h3>{h(title)}</h3>
        {body}
      </div>'''


def plot_section(title, img_path, csv_path, anchor, summary=None):
    uri = img_b64(img_path)
    rows = load_csv(csv_path)
    img_html = (f'<img src="{uri}" alt="{h(title)}" class="plot-img">'
                if uri else '<p class="missing">Image not generated yet — run the plot script first.</p>')
    summary_html = render_plot_summary(summary)

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
            {summary_html}
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

    desc_dict = CUSTOM_DESCS if is_custom else PROVIDED_DESCS
    if name in desc_dict:
        d = desc_dict[name]
        short     = d.get('short', name)
        prop      = d.get('property', '')
        challenge = d.get('challenge', '')
        desc_html = (
            f'<div class="desc"><b>{h(short)}</b>'
            + (f'<p><b>Property:</b> {h(prop)}</p>' if prop else '')
            + (f'<p><b>Challenge:</b> {h(challenge)}</p>' if is_custom and challenge else '')
            + '</div>'
        )
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
.table-wrap { overflow-x: auto; }

/* plots */
.plot-wrap { text-align: center; margin: .5rem 0 1rem; }
.plot-img  { max-width: 100%; border: 1px solid var(--border); border-radius: 4px; }
.plot-summary { font-size: .9rem; background: #e8f4fd; border-left: 3px solid var(--primary);
                padding: .75rem .9rem; border-radius: 4px; margin: 0 0 1rem; }
.plot-summary h3 { color: var(--primary); font-size: .98rem; margin: 0 0 .35rem; }
.plot-summary p + p { margin-top: .55rem; }

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

/* test result status cells */
td.pass   { color: #2e7d32; font-weight: 600; }
td.better { color: #1565C0; font-weight: 600; }
td.fail   { color: #c62828; font-weight: 600; }
td.ok     { color: #1565C0; font-weight: 600; }

/* misc */
.missing { color: var(--muted); font-style: italic; padding: .5rem; }
details { margin-top: .8rem; }
summary { cursor: pointer; color: var(--primary); font-size: .9rem; }
summary:hover { text-decoration: underline; }
footer { text-align: center; padding: 2rem; font-size: .8rem; color: var(--muted); }

/* discussion */
.discussion-entry { margin-bottom: 1.2rem; }
.discussion-entry h3 { color: var(--primary); margin-bottom: .35rem; }
.discussion-entry p  { font-size: .9rem; line-height: 1.65; color: var(--text); }
'''


def build_html():
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    test_data = load_test_results()

    # Re-load report content at build time so summaries and curve fits are up to date
    _, _, graph_summaries, curve_fits, discussion = load_report_content()

    nav_links = ''.join([
        '<a href="#test-results">Test Results</a>',
        '<a href="#summary">Summary</a>',
        '<a href="#displacement-scatter">Displacement Scatter</a>',
        '<a href="#displacement-sweep">Displacement Sweep</a>',
        '<a href="#runtime-size">Runtime vs Input Size</a>',
        '<a href="#time-memory">Runtime vs Memory</a>',
        '<a href="#memory-size">Memory vs Input Size</a>',
        '<a href="#curve-fits">Curve Fits</a>',
        '<a href="#discussion">Discussion</a>',
        '<a href="#datasets">Dataset Descriptions</a>',
        '<a href="#provided-viz">Provided Visualizations</a>',
        '<a href="#custom-viz">Custom Visualizations</a>',
    ])

    summary_sec = f'''
    <section id="summary">
      <h2>Results Summary</h2>
      {summary_table(PROVIDED_CASES, "Provided test cases")}
      {summary_table(CUSTOM_CASES,   "Custom test cases")}
    </section>'''

    disp_scatter_intro = '''
    <section id="displacement-intro" style="background:#e3f2fd;border-color:#90caf9;padding:1rem 1.5rem">
      <h2 style="border-color:#1565C0">Displacement vs Target Vertex Count — Two Views</h2>
      <p style="font-size:.9rem">
        <b>Cross-case scatter</b> (below left): one point per test case at its fixed
        requested target — useful for comparing geometric difficulty across datasets.<br>
        <b>Per-polygon sweep</b> (below right, <em>plot c per rubric</em>): the same
        polygon is simplified at many different target counts, showing how areal
        displacement grows as vertices are removed. Three custom datasets are swept:
        <em>dense_outer</em> (1&nbsp;ring, 400&nbsp;verts), <em>large_with_many_holes</em>
        (9&nbsp;rings, 148&nbsp;verts), and <em>many_holes</em> (7&nbsp;rings, 76&nbsp;verts).
        The x-axis is inverted so the right edge is maximally simplified.
      </p>
    </section>'''

    disp_sec = plot_section(
        'Areal Displacement vs Target Vertex Count (cross-case scatter)',
        os.path.join(DISP_DIR, 'displacement_vs_target.png'),
        os.path.join(DISP_DIR, 'displacement_vs_target.csv'),
        'displacement-scatter',
    )

    disp_sweep_sec = plot_section(
        'Areal Displacement vs Output Vertex Count — Per-Polygon Sweep (plot c)',
        os.path.join(DISP_DIR, 'displacement_sweep.png'),
        os.path.join(DISP_DIR, 'displacement_sweep.csv'),
        'displacement-sweep',
        graph_summaries.get('displacement-sweep'),
    )
    runtime_size_sec = plot_section(
        'Runtime vs Input Size (with curve fits)',
        os.path.join(TIME_DIR, 'runtime_vs_inputsize.png'),
        os.path.join(TIME_DIR, 'time_vs_memory.csv'),
        'runtime-size',
        graph_summaries.get('runtime-size'),
    )
    time_sec = plot_section(
        'Wall-Clock Runtime vs Peak Memory Usage',
        os.path.join(TIME_DIR, 'time_vs_memory.png'),
        os.path.join(TIME_DIR, 'time_vs_memory.csv'),
        'time-memory',
    )
    mem_sec = plot_section(
        'Peak Memory Usage vs Input Size (with curve fits)',
        os.path.join(MEM_DIR, 'memory_vs_inputsize.png'),
        os.path.join(MEM_DIR, 'memory_vs_inputsize.csv'),
        'memory-size',
        graph_summaries.get('memory-size'),
    )

    # ── curve fits section ────────────────────────────────────────────────────
    def fit_table(fits, label):
        if not fits:
            return f'<p class="missing">{h(label)}: not yet computed — run the plot scripts first.</p>'
        rows = ''
        for key, info in fits.items():
            rows += f'<tr><td>{h(key)}</td><td style="font-family:monospace">{h(info.get("label",""))}</td></tr>'
        return (f'<h3>{h(label)}</h3>'
                f'<table><thead><tr><th>Model</th><th>Fitted expression</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>')

    curve_fits_sec = f'''
    <section id="curve-fits">
      <h2>Scaling Analysis — Curve Fits</h2>
      <p style="font-size:.85rem;color:var(--muted);margin-bottom:.8rem">
        Two models are fitted to each metric: a power law
        <em>y = c &middot; n<sup>k</sup></em> and a quasi-linear
        <em>y = c &middot; n log n</em>.  The fitted constants are shown below
        and overlaid on the corresponding plots above.
      </p>
      {fit_table(curve_fits.get('runtime', {}), 'Runtime scaling')}
      {fit_table(curve_fits.get('memory',  {}), 'Memory scaling')}
    </section>'''

    # ── discussion / interpretation section ──────────────────────────────────
    if discussion:
        discussion_items = ''
        for entry in discussion:
            heading = h(entry.get('heading', ''))
            text    = h(entry.get('text', ''))
            discussion_items += f'''
          <div class="discussion-entry">
            <h3>{heading}</h3>
            <p>{text}</p>
          </div>'''
        discussion_sec = f'''
    <section id="discussion">
      <h2>Discussion and Interpretation of Results</h2>
      {discussion_items}
    </section>'''
    else:
        discussion_sec = ''

    # ── dataset descriptions section ──────────────────────────────────────────
    def desc_rows(descs, names, include_challenge=True):
        rows = ''
        for name in names:
            d = descs.get(name, {})
            rows += (f'<tr>'
                     f'<td><a href="#viz-{h(name)}">{h(name)}</a></td>'
                     f'<td>{h(d.get("property", "—"))}</td>')
            if include_challenge:
                rows += f'<td>{h(d.get("challenge", "—"))}</td>'
            rows += '</tr>'
        return rows

    datasets_sec = f'''
    <section id="datasets">
      <h2>Dataset Descriptions</h2>
      <h3>Custom test cases</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Targeted property</th><th>Why it is challenging</th></tr></thead>
          <tbody>{desc_rows(CUSTOM_DESCS, CUSTOM_CASES, include_challenge=True)}</tbody>
        </table>
      </div>
      <h3 style="margin-top:1.2rem">Provided test cases</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Targeted property</th></tr></thead>
          <tbody>{desc_rows(PROVIDED_DESCS, PROVIDED_CASES, include_challenge=False)}</tbody>
        </table>
      </div>
    </section>'''

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
  {test_results_section(test_data)}
  {summary_sec}
  {disp_scatter_intro}
  {disp_sec}
  {disp_sweep_sec}
  {runtime_size_sec}
  {time_sec}
  {mem_sec}
  {curve_fits_sec}
  {discussion_sec}
  {datasets_sec}
  {provided_sec}
  {custom_sec}
</main>
<footer>Generated by generate_report.py &nbsp;·&nbsp; {now}</footer>
</body>
</html>'''


def main():
    out_path = os.path.join(ROOT, 'report.html')
    print('Building report ...')

    content = build_html()
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)

    size_kb = os.path.getsize(out_path) / 1024
    print(f'Saved: {out_path}  ({size_kb:.0f} KB)')

    # Try to open in browser
    import subprocess
    import sys
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
