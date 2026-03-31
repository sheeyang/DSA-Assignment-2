#!/usr/bin/env python3
"""
Plot peak memory usage vs input size (vertex count) for all test cases,
with c·n^k and c·n·log(n) curve fits overlaid.

Counts vertices in each input CSV, then runs simplify with /usr/bin/time -v
(via WSL on Windows) to capture peak RSS.

Output:
    memory_vs_inputsize/memory_vs_inputsize.png
    memory_vs_inputsize/memory_vs_inputsize.csv
  + curve_fits.memory written to dataset_descriptions.json
"""

import sys
import os
import re
import csv
import json
import subprocess
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.optimize import curve_fit

# ── paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
SIMPLIFY     = os.path.join(SCRIPT_DIR, 'simplify')
TEST_DIR     = os.path.join(SCRIPT_DIR, 'test_cases')
MY_TEST_DIR  = os.path.join(SCRIPT_DIR, 'my_test_cases')
OUT_DIR      = os.path.join(SCRIPT_DIR, 'memory_vs_inputsize')

# ── test cases ───────────────────────────────────────────────────────────────
TEST_CASES = [
    ('rectangle_with_two_holes',    'input_rectangle_with_two_holes.csv',     7),
    ('cushion_with_hexagonal_hole', 'input_cushion_with_hexagonal_hole.csv', 13),
    ('blob_with_two_holes',         'input_blob_with_two_holes.csv',         17),
    ('wavy_with_three_holes',       'input_wavy_with_three_holes.csv',       21),
    ('lake_with_two_islands',       'input_lake_with_two_islands.csv',       17),
    ('original_01',                 'input_original_01.csv',                 99),
    ('original_02',                 'input_original_02.csv',                 99),
    ('original_03',                 'input_original_03.csv',                 99),
    ('original_04',                 'input_original_04.csv',                 99),
    ('original_05',                 'input_original_05.csv',                 99),
    ('original_06',                 'input_original_06.csv',                 99),
    ('original_07',                 'input_original_07.csv',                 99),
    ('original_08',                 'input_original_08.csv',                 99),
    ('original_09',                 'input_original_09.csv',                 99),
    ('original_10',                 'input_original_10.csv',                 99),
]

MY_TEST_CASES = [
    ('many_holes',            'input_many_holes.csv',            37),
    ('dense_outer',           'input_dense_outer.csv',           50),
    ('narrow_corridor',       'input_narrow_corridor.csv',        5),
    ('nested_rings',          'input_nested_rings.csv',          20),
    ('large_with_many_holes', 'input_large_with_many_holes.csv', 40),
]

# ── input-size counting ───────────────────────────────────────────────────────

def count_vertices(input_file, test_dir=None):
    """Count total vertices in a CSV input file (rows with numeric ring_id)."""
    path = os.path.join(test_dir or TEST_DIR, input_file)
    count = 0
    with open(path, encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 4:
                continue
            try:
                int(row[0])   # ring_id must be an integer
                float(row[2]) # x must be a float
                count += 1
            except ValueError:
                continue      # skip header / summary lines
    return count


# ── measurement ──────────────────────────────────────────────────────────────

def to_wsl_path(win_path):
    """Convert a Windows path to a WSL /mnt/... path."""
    p = win_path.replace('\\', '/')
    if len(p) >= 2 and p[1] == ':':
        drive = p[0].lower()
        p = f'/mnt/{drive}' + p[2:]
    return p


def build_cmd(input_path, target):
    """Build the command list, wrapping with /usr/bin/time -v."""
    if sys.platform == 'win32':
        wsl_simplify = to_wsl_path(SIMPLIFY)
        wsl_input    = to_wsl_path(input_path)
        return ['wsl', '/usr/bin/time', '-v', wsl_simplify, wsl_input, str(target)]
    return ['/usr/bin/time', '-v', SIMPLIFY, input_path, str(target)]


def parse_peak_rss_kb(stderr_text):
    """Extract 'Maximum resident set size (kbytes)' from /usr/bin/time -v output."""
    m = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', stderr_text)
    return int(m.group(1)) if m else None


def measure_memory(name, input_file, target, test_dir=None):
    """
    Run simplify and return peak_rss_mb, or None on failure.
    """
    input_path = os.path.join(test_dir or TEST_DIR, input_file)
    cmd = build_cmd(input_path, target)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT: {name}")
        return None

    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode}): {name}")
        print(f"    stderr: {result.stderr.strip()[:200]}")
        return None

    rss_kb = parse_peak_rss_kb(result.stderr)
    if rss_kb is None:
        print(f"  WARNING: could not parse peak RSS for {name}")
        print(f"    (is /usr/bin/time installed? try: sudo apt install time)")
        return None

    return rss_kb / 1024.0


# ── curve fitting ─────────────────────────────────────────────────────────────

def fit_power(xs, ys):
    """Fit y = c * x^k.  Returns (c, k) or None."""
    xs, ys = np.array(xs, dtype=float), np.array(ys, dtype=float)
    mask = (xs > 0) & (ys > 0)
    if mask.sum() < 3:
        return None
    try:
        def model(x, log_c, k):
            return log_c + k * np.log(x)
        popt, _ = curve_fit(model, xs[mask], np.log(ys[mask]))
        return np.exp(popt[0]), popt[1]
    except Exception:
        return None


def fit_nlogn(xs, ys):
    """Fit y = c * x * log(x).  Returns c or None."""
    xs, ys = np.array(xs, dtype=float), np.array(ys, dtype=float)
    mask = (xs > 1) & (ys > 0)
    if mask.sum() < 3:
        return None
    try:
        def model(x, c):
            return c * x * np.log(x)
        popt, _ = curve_fit(model, xs[mask], ys[mask],
                            p0=[ys[mask].mean() / (xs[mask] * np.log(xs[mask])).mean()])
        return popt[0]
    except Exception:
        return None


# ── plotting ─────────────────────────────────────────────────────────────────

SHORT_LABELS = {
    'rectangle_with_two_holes':    'rect_2h',
    'cushion_with_hexagonal_hole': 'cushion',
    'blob_with_two_holes':         'blob_2h',
    'wavy_with_three_holes':       'wavy_3h',
    'lake_with_two_islands':       'lake_2i',
    **{f'original_{i:02d}': f'orig_{i:02d}' for i in range(1, 11)},
    'many_holes':            'many_h',
    'dense_outer':           'dense',
    'narrow_corridor':       'narrow',
    'nested_rings':          'nested',
    'large_with_many_holes': 'large_mh',
}

COLORS = [
    '#2196F3', '#F44336', '#FF9800', '#4CAF50', '#9C27B0',
    '#00BCD4', '#795548', '#607D8B', '#E91E63', '#8BC34A',
    '#FF5722', '#3F51B5', '#009688', '#FFC107', '#673AB7',
]


def plot(results):
    """
    results: list of (name, input_vertices, peak_rss_mb)
    Returns fit_info dict.
    """
    valid = [(n, v, m) for n, v, m in results if v is not None and m is not None]
    if not valid:
        print("No valid data to plot.")
        return {}

    verts_all = [r[1] for r in valid]
    mems_all  = [r[2] for r in valid]

    power_fit = fit_power(verts_all, mems_all)
    nlogn_fit = fit_nlogn(verts_all, mems_all)

    xs = np.linspace(min(verts_all) * 0.9, max(verts_all) * 1.1, 300)

    fig, ax = plt.subplots(figsize=(11, 7))

    for i, (name, verts, mem) in enumerate(valid):
        color = COLORS[i % len(COLORS)]
        ax.scatter(verts, mem, color=color, s=80, zorder=3)
        ax.annotate(SHORT_LABELS.get(name, name), xy=(verts, mem),
                    xytext=(5, 4), textcoords='offset points', fontsize=8, color=color)

    fit_info = {}
    if power_fit:
        c, k = power_fit
        ax.plot(xs, c * xs ** k, 'k--', linewidth=1.4,
                label=f'$c \\cdot n^k$:  c={c:.3e}, k={k:.3f}', zorder=2)
        fit_info['power'] = {'c': float(c), 'k': float(k), 'label': f'c·n^k  (c={c:.3e}, k={k:.3f})'}

    if nlogn_fit:
        c_nl = nlogn_fit
        ax.plot(xs, c_nl * xs * np.log(xs), 'r:', linewidth=1.4,
                label=f'$c \\cdot n \\log n$:  c={c_nl:.3e}', zorder=2)
        fit_info['nlogn'] = {'c': float(c_nl), 'label': f'c·n·log(n)  (c={c_nl:.3e})'}

    ax.set_xlabel('Input size (number of vertices)', fontsize=11)
    ax.set_ylabel('Peak memory usage (MB)', fontsize=11)
    ax.set_title('Peak Memory Usage vs Input Size\nwith curve fits', fontsize=13, fontweight='bold')
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.grid(True, which='minor', linestyle=':', alpha=0.2)
    if fit_info:
        ax.legend(fontsize=9)
    plt.tight_layout()

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'memory_vs_inputsize.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"Saved plot: {out_path}")
    plt.close(fig)
    return fit_info


# ── CSV export + JSON fit save ────────────────────────────────────────────────

def save_csv(results):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'memory_vs_inputsize.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['test_case', 'input_vertices', 'peak_memory_mb'])
        for name, verts, mem in results:
            writer.writerow([
                name,
                verts if verts is not None else '',
                f'{mem:.4f}' if mem is not None else '',
            ])
    print(f"Saved CSV:  {out_path}")


def save_memory_fits(fit_info):
    """Merge memory curve-fit results into dataset_descriptions.json."""
    desc_path = os.path.join(SCRIPT_DIR, 'dataset_descriptions.json')
    if os.path.exists(desc_path):
        with open(desc_path, encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}
    if 'curve_fits' not in data:
        data['curve_fits'] = {}
    data['curve_fits']['memory'] = fit_info
    with open(desc_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"Saved memory curve fits → dataset_descriptions.json")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    all_cases = [(n, f, t, TEST_DIR)     for n, f, t in TEST_CASES] + \
                [(n, f, t, MY_TEST_DIR)  for n, f, t in MY_TEST_CASES]
    print(f"Measuring peak memory vs input size for {len(all_cases)} test cases ...\n")
    col = 36
    print(f"{'Test case':<{col}}  {'Input verts':>12}  {'Peak mem (MB)':>14}")
    print('-' * (col + 30))

    results = []
    for name, input_file, target, tdir in all_cases:
        print(f"  {name:<{col-2}}", end='  ', flush=True)
        verts = count_vertices(input_file, tdir)
        mem   = measure_memory(name, input_file, target, tdir)
        v_str   = str(verts)
        mem_str = f'{mem:.2f}' if mem is not None else 'N/A'
        print(f'{v_str:>12}  {mem_str:>14}')
        results.append((name, verts, mem))

    fit_info = plot(results)
    save_csv(results)
    save_memory_fits(fit_info or {})


if __name__ == '__main__':
    main()
