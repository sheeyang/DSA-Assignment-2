#!/usr/bin/env python3
"""
Plot total areal displacement vs. target vertex count.

Two plots are produced:
  1. Cross-case scatter — one point per test case at its fixed target.
  2. Per-polygon displacement sweep — multiple targets per dataset, showing
     how areal displacement grows as the target vertex count is reduced.
     This is the primary plot (c) required by the rubric.

Output:
    displacement_vs_target/displacement_vs_target.png   (cross-case scatter)
    displacement_vs_target/displacement_vs_target.csv
    displacement_vs_target/displacement_sweep.png       (per-polygon sweep)
    displacement_vs_target/displacement_sweep.csv
"""

import sys
import os
import re
import csv
import subprocess
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
SIMPLIFY     = os.path.join(SCRIPT_DIR, 'simplify')
TEST_DIR     = os.path.join(SCRIPT_DIR, 'test_cases')
MY_TEST_DIR  = os.path.join(SCRIPT_DIR, 'my_test_cases')
OUT_DIR      = os.path.join(SCRIPT_DIR, 'displacement_vs_target')

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
    ('narrow_corridor',       'input_narrow_corridor.csv',        6),
    ('nested_rings',          'input_nested_rings.csv',          20),
    ('large_with_many_holes', 'input_large_with_many_holes.csv', 40),
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


def run(name, input_file, target, test_dir=None):
    """Return (actual_output_verts, displacement) or (None, None) on failure."""
    input_path = os.path.join(test_dir or TEST_DIR, input_file)
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

# ── per-polygon displacement sweep ────────────────────────────────────────────
# Each entry: (name, input_file, test_dir, [list of target counts to sweep])
# Targets are chosen to give ~10-15 evenly spaced points from just above the
# topology minimum up to the full input vertex count.
SWEEP_CASES = [
    (
        'dense_outer',
        'input_dense_outer.csv',
        MY_TEST_DIR,
        # 1 ring, 400 verts — topology min = 3
        [3, 5, 10, 20, 30, 50, 75, 100, 150, 200, 250, 300, 350, 400],
    ),
    (
        'large_with_many_holes',
        'input_large_with_many_holes.csv',
        MY_TEST_DIR,
        # 9 rings (100 + 8×6 verts) — topology min ≈ 27
        [27, 30, 35, 40, 50, 60, 70, 80, 90, 100, 115, 130, 148],
    ),
    (
        'many_holes',
        'input_many_holes.csv',
        MY_TEST_DIR,
        # 7 rings (4 + 6×12 verts) — topology min ≈ 21
        [21, 25, 28, 32, 37, 42, 50, 58, 65, 76],
    ),
]

SWEEP_COLORS = ['#2196F3', '#FF9800', '#4CAF50']


def run_sweep():
    """Run simplify for every (dataset, target) in SWEEP_CASES.

    Returns list of (name, target, actual_verts, displacement).
    """
    results = []
    total = sum(len(targets) for _, _, _, targets in SWEEP_CASES)
    print(f"\nRunning displacement sweep ({total} runs) ...\n")
    for name, input_file, tdir, targets in SWEEP_CASES:
        print(f"  {name}")
        for target in targets:
            actual_verts, disp = run(name, input_file, target, tdir)
            av_str   = str(actual_verts) if actual_verts is not None else 'N/A'
            disp_str = f'{disp:.3e}' if disp is not None else 'N/A'
            print(f"    target={target:>4}  actual={av_str:>4}  disp={disp_str}")
            results.append((name, target, actual_verts, disp))
    return results


def plot_sweep(sweep_results):
    """Line plot: displacement vs. actual vertex count, one line per dataset."""
    # Group by name
    from collections import defaultdict
    groups = defaultdict(list)
    for name, target, actual_verts, disp in sweep_results:
        if disp is not None and actual_verts is not None:
            groups[name].append((actual_verts, disp))

    if not groups:
        print("No valid sweep data to plot.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    for idx, (name, _input, _tdir, _targets) in enumerate(SWEEP_CASES):
        pts = sorted(groups.get(name, []))
        if not pts:
            continue
        xs, ys = zip(*pts)
        color = SWEEP_COLORS[idx % len(SWEEP_COLORS)]
        ax.plot(xs, ys, '-o', color=color, linewidth=1.8, markersize=5,
                label=name.replace('_', ' '))

    ax.set_xlabel('Actual output vertex count', fontsize=11)
    ax.set_ylabel('Total areal displacement', fontsize=11)
    ax.set_title(
        'Areal Displacement vs. Output Vertex Count\n'
        '(per-polygon sweep — decreasing target from full size to topology minimum)',
        fontsize=12, fontweight='bold',
    )
    ax.invert_xaxis()   # left = fewer vertices (more simplified) → more displacement
    ax.legend(fontsize=9)
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
    ax.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))

    plt.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'displacement_sweep.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved sweep plot: {out_path}")
    plt.close(fig)


def save_sweep_csv(sweep_results):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'displacement_sweep.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['test_case', 'target_vertices', 'actual_vertices', 'areal_displacement'])
        for name, target, actual_verts, disp in sweep_results:
            writer.writerow([
                name,
                target,
                actual_verts if actual_verts is not None else '',
                f'{disp:.6e}' if disp is not None else '',
            ])
    print(f"Saved sweep CSV:  {out_path}")


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
    all_cases = [(n, f, t, TEST_DIR)    for n, f, t in TEST_CASES] + \
                [(n, f, t, MY_TEST_DIR) for n, f, t in MY_TEST_CASES]
    print(f"Measuring areal displacement for {len(all_cases)} test cases ...\n")
    col = 36
    print(f"{'Test case':<{col}}  {'Target':>7}  {'Actual':>7}  {'Displacement':>18}")
    print('-' * (col + 38))

    results = []
    for name, input_file, target, tdir in all_cases:
        print(f"  {name:<{col-2}}", end='  ', flush=True)
        actual_verts, disp = run(name, input_file, target, tdir)
        av_str   = str(actual_verts) if actual_verts is not None else 'N/A'
        disp_str = f'{disp:.6e}' if disp is not None else 'N/A'
        print(f'{target:>7}  {av_str:>7}  {disp_str:>18}')
        results.append((name, target, actual_verts, disp))

    plot(results)
    save_csv(results)

    # ── per-polygon displacement sweep (plot c) ───────────────────────────────
    sweep_results = run_sweep()
    plot_sweep(sweep_results)
    save_sweep_csv(sweep_results)


if __name__ == '__main__':
    main()
