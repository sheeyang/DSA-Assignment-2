#!/usr/bin/env python3
"""
Plot wall-clock runtime vs peak memory usage for all test cases.

Runs the simplify executable on every test case using /usr/bin/time -v (via WSL
on Windows) to capture peak RSS, and time.perf_counter() for wall-clock time.

Output:
    experiments/plots/runtime/time_vs_memory.png
    experiments/results/time_vs_memory.csv
"""

import sys
import os
import re
import csv
import time
import subprocess
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
SIMPLIFY     = os.path.join(SCRIPT_DIR, 'simplify')
TEST_DIR     = os.path.join(SCRIPT_DIR, 'test_cases')
MY_TEST_DIR  = os.path.join(SCRIPT_DIR, 'my_test_cases')
OUT_DIR      = os.path.join(SCRIPT_DIR, 'time_vs_memory')

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
    ('zigzag_with_hole',      'input_zigzag_with_hole.csv',      30),
    ('large_with_many_holes', 'input_large_with_many_holes.csv', 40),
]

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


def measure(name, input_file, target, test_dir=None):
    """
    Run simplify on input_file with the given target.
    Returns (wall_secs, peak_rss_mb) or (wall_secs, None) if RSS unavailable.
    """
    input_path = os.path.join(test_dir or TEST_DIR, input_file)
    cmd = build_cmd(input_path, target)

    t0 = time.perf_counter()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT: {name}")
        return None, None
    elapsed = time.perf_counter() - t0

    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode}): {name}")
        print(f"    stderr: {result.stderr.strip()[:200]}")
        return elapsed, None

    rss_kb = parse_peak_rss_kb(result.stderr)
    if rss_kb is None:
        print(f"  WARNING: could not parse peak RSS for {name}")
        print(f"    (is /usr/bin/time installed? try: sudo apt install time)")

    rss_mb = rss_kb / 1024.0 if rss_kb is not None else None
    return elapsed, rss_mb


# ── plotting ─────────────────────────────────────────────────────────────────

# Short display labels for the scatter annotations
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
    'zigzag_with_hole':      'zigzag',
    'large_with_many_holes': 'large_mh',
}

COLORS = [
    '#2196F3', '#F44336', '#FF9800', '#4CAF50', '#9C27B0',
    '#00BCD4', '#795548', '#607D8B', '#E91E63', '#8BC34A',
    '#FF5722', '#3F51B5', '#009688', '#FFC107', '#673AB7',
]


def plot(results):
    """
    results: list of (name, wall_secs, peak_rss_mb)
    """
    valid = [(n, t, m) for n, t, m in results if t is not None and m is not None]
    if not valid:
        print("No valid data to plot.")
        return

    names  = [r[0] for r in valid]
    times  = [r[1] for r in valid]
    mems   = [r[2] for r in valid]

    fig, ax = plt.subplots(figsize=(11, 7))

    for i, (name, t, mem) in enumerate(valid):
        color = COLORS[i % len(COLORS)]
        ax.scatter(t, mem, color=color, s=80, zorder=3)
        label = SHORT_LABELS.get(name, name)
        ax.annotate(
            label,
            xy=(t, mem),
            xytext=(5, 4),
            textcoords='offset points',
            fontsize=8,
            color=color,
        )

    ax.set_xlabel('Wall-clock runtime (seconds)', fontsize=11)
    ax.set_ylabel('Peak memory usage (MB)', fontsize=11)
    ax.set_title('Runtime vs Peak Memory Usage\n(per test case)', fontsize=13, fontweight='bold')
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.grid(True, which='minor', linestyle=':', alpha=0.2)

    plt.tight_layout()

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'time_vs_memory.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved plot: {out_path}")
    plt.close(fig)


# ── CSV export ────────────────────────────────────────────────────────────────

def save_csv(results):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'time_vs_memory.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['test_case', 'wall_time_s', 'peak_memory_mb'])
        for name, t, mem in results:
            writer.writerow([
                name,
                f'{t:.6f}' if t is not None else '',
                f'{mem:.4f}' if mem is not None else '',
            ])
    print(f"Saved CSV:  {out_path}")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    all_cases = [(n, f, t, TEST_DIR)    for n, f, t in TEST_CASES] + \
                [(n, f, t, MY_TEST_DIR) for n, f, t in MY_TEST_CASES]
    print(f"Measuring runtime and peak memory for {len(all_cases)} test cases ...\n")
    col = 36
    print(f"{'Test case':<{col}}  {'Time (s)':>10}  {'Peak mem (MB)':>14}")
    print('-' * (col + 28))

    results = []
    for name, input_file, target, tdir in all_cases:
        print(f"  {name:<{col-2}}", end='  ', flush=True)
        wall, mem = measure(name, input_file, target, tdir)
        t_str   = f'{wall:.4f}' if wall is not None else '  N/A  '
        mem_str = f'{mem:.2f}'  if mem  is not None else '  N/A  '
        print(f'{t_str:>10}  {mem_str:>14}')
        results.append((name, wall, mem))

    plot(results)
    save_csv(results)


if __name__ == '__main__':
    main()
