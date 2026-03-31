#!/usr/bin/env python3
"""
Plot total areal displacement vs. target vertex count for all test cases.

Runs the simplify executable on every test case and parses
"Total areal displacement:" from its output.

Output:
    displacement_vs_target/displacement_vs_target.png
    displacement_vs_target/displacement_vs_target.csv
"""

import sys
import os
import re
import csv
import subprocess
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SIMPLIFY   = os.path.join(SCRIPT_DIR, 'simplify')
TEST_DIR   = os.path.join(SCRIPT_DIR, 'test_cases')
OUT_DIR    = os.path.join(SCRIPT_DIR, 'displacement_vs_target')

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

# ── helpers ───────────────────────────────────────────────────────────────────

def to_wsl_path(win_path):
    p = win_path.replace('\\', '/')
    if len(p) >= 2 and p[1] == ':':
        p = f'/mnt/{p[0].lower()}' + p[2:]
    return p


def build_cmd(input_path, target):
    if sys.platform == 'win32':
        return ['wsl', to_wsl_path(SIMPLIFY), to_wsl_path(input_path), str(target)]
    return [SIMPLIFY, input_path, str(target)]


def parse_displacement(text):
    m = re.search(r'Total areal displacement:\s*([-+0-9.eE]+)', text)
    return float(m.group(1)) if m else None


def run(name, input_file, target):
    """Return (actual_output_verts, displacement) or (None, None) on failure."""
    input_path = os.path.join(TEST_DIR, input_file)
    cmd = build_cmd(input_path, target)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT: {name}")
        return None, None

    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode}): {name}")
        print(f"    stderr: {result.stderr.strip()[:200]}")
        return None, None

    disp = parse_displacement(result.stdout)
    if disp is None:
        print(f"  WARNING: could not parse displacement for {name}")

    # Count actual output vertices (data rows in stdout)
    actual_verts = 0
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) >= 4:
            try:
                int(row[0]); float(row[2])
                actual_verts += 1
            except ValueError:
                pass

    return actual_verts if actual_verts > 0 else None, disp


# ── plotting ──────────────────────────────────────────────────────────────────

SHORT_LABELS = {
    'rectangle_with_two_holes':    'rect_2h',
    'cushion_with_hexagonal_hole': 'cushion',
    'blob_with_two_holes':         'blob_2h',
    'wavy_with_three_holes':       'wavy_3h',
    'lake_with_two_islands':       'lake_2i',
    **{f'original_{i:02d}': f'orig_{i:02d}' for i in range(1, 11)},
}

COLORS = [
    '#2196F3', '#F44336', '#FF9800', '#4CAF50', '#9C27B0',
    '#00BCD4', '#795548', '#607D8B', '#E91E63', '#8BC34A',
    '#FF5722', '#3F51B5', '#009688', '#FFC107', '#673AB7',
]


def plot(results):
    """results: list of (name, target, actual_verts, displacement)"""
    valid = [(n, tgt, av, d) for n, tgt, av, d in results if d is not None]
    if not valid:
        print("No valid data to plot.")
        return

    fig, ax = plt.subplots(figsize=(11, 7))

    for i, (name, target, actual_verts, disp) in enumerate(valid):
        color = COLORS[i % len(COLORS)]
        ax.scatter(target, disp, color=color, s=80, zorder=3)
        label = SHORT_LABELS.get(name, name)
        # annotate with actual vertex count if it differs from target
        suffix = f'\n(actual {actual_verts})' if actual_verts and actual_verts != target else ''
        ax.annotate(
            label + suffix,
            xy=(target, disp),
            xytext=(5, 4),
            textcoords='offset points',
            fontsize=8,
            color=color,
        )

    ax.set_xlabel('Target vertex count', fontsize=11)
    ax.set_ylabel('Total areal displacement', fontsize=11)
    ax.set_title('Areal Displacement vs Target Vertex Count\n(per test case)', fontsize=13, fontweight='bold')
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.grid(True, which='minor', linestyle=':', alpha=0.2)
    ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
    ax.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))

    plt.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'displacement_vs_target.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved plot: {out_path}")
    plt.close(fig)


# ── CSV export ────────────────────────────────────────────────────────────────

def save_csv(results):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'displacement_vs_target.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['test_case', 'target_vertices', 'actual_vertices', 'areal_displacement'])
        for name, target, actual_verts, disp in results:
            writer.writerow([
                name,
                target,
                actual_verts if actual_verts is not None else '',
                f'{disp:.6e}' if disp is not None else '',
            ])
    print(f"Saved CSV:  {out_path}")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Measuring areal displacement for {len(TEST_CASES)} test cases ...\n")
    col = 36
    print(f"{'Test case':<{col}}  {'Target':>7}  {'Actual':>7}  {'Displacement':>18}")
    print('-' * (col + 38))

    results = []
    for name, input_file, target in TEST_CASES:
        print(f"  {name:<{col-2}}", end='  ', flush=True)
        actual_verts, disp = run(name, input_file, target)
        av_str   = str(actual_verts) if actual_verts is not None else 'N/A'
        disp_str = f'{disp:.6e}' if disp is not None else 'N/A'
        print(f'{target:>7}  {av_str:>7}  {disp_str:>18}')
        results.append((name, target, actual_verts, disp))

    plot(results)
    save_csv(results)


if __name__ == '__main__':
    main()
