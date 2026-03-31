#!/usr/bin/env python3
"""
Polygon simplification visualizer.

Usage:
    python visualize.py <test_name>
    python visualize.py blob_with_two_holes
    python visualize.py original_01
    python visualize.py            # shows list of available tests

Draws three side-by-side plots:
    Input  |  My Output  |  Expected Output

Rings are coloured: ring 0 (exterior) in blue, holes in red/orange/green/...
Vertices are shown as dots; simplified vertices are larger.
"""

import sys
import os
import csv
import re
import collections
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection

# ── paths ────────────────────────────────────────────────────────────────────
ROOT         = os.path.dirname(os.path.abspath(__file__))
TEST_DIR     = os.path.join(ROOT, 'test_cases')
OUT_DIR      = os.path.join(ROOT, 'test_outputs')
MY_TEST_DIR  = os.path.join(ROOT, 'my_test_cases')
MY_OUT_DIR   = os.path.join(ROOT, 'my_test_outputs')

# All provided test cases: name → (target, input_file, expected_file)
TEST_CASES = {
    'rectangle_with_two_holes':    (7,  'input_rectangle_with_two_holes.csv',    'output_rectangle_with_two_holes.txt'),
    'cushion_with_hexagonal_hole': (13, 'input_cushion_with_hexagonal_hole.csv', 'output_cushion_with_hexagonal_hole.txt'),
    'blob_with_two_holes':         (17, 'input_blob_with_two_holes.csv',         'output_blob_with_two_holes.txt'),
    'wavy_with_three_holes':       (21, 'input_wavy_with_three_holes.csv',       'output_wavy_with_three_holes.txt'),
    'lake_with_two_islands':       (17, 'input_lake_with_two_islands.csv',       'output_lake_with_two_islands.txt'),
    **{f'original_{i:02d}': (99, f'input_original_{i:02d}.csv', f'output_original_{i:02d}.txt')
       for i in range(1, 11)},
}

# Custom test cases (no expected output): name → (target, input_file)
MY_TEST_CASES = {
    'many_holes':          (37,  'input_many_holes.csv'),
    'dense_outer':         (50,  'input_dense_outer.csv'),
    'narrow_corridor':     (5,   'input_narrow_corridor.csv'),
    'nested_rings':        (20,  'input_nested_rings.csv'),
    'zigzag_with_hole':    (30,  'input_zigzag_with_hole.csv'),
    'large_with_many_holes': (40, 'input_large_with_many_holes.csv'),
}

RING_COLORS = ['#2196F3', '#F44336', '#FF9800', '#4CAF50', '#9C27B0',
               '#00BCD4', '#795548', '#607D8B']


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_csv_text(text):
    """Return dict {ring_id: [(x,y), ...]} from CSV text (ignores summary lines)."""
    rings = collections.defaultdict(list)
    reader = csv.reader(text.splitlines())
    for row in reader:
        if len(row) < 4:
            continue
        try:
            rid = int(row[0])
            x   = float(row[2])
            y   = float(row[3])
            rings[rid].append((x, y))
        except ValueError:
            continue  # header or summary line
    return dict(rings)


def parse_csv_file(path):
    with open(path, encoding='utf-8') as f:
        return parse_csv_text(f.read())


def parse_output_file(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    rings = parse_csv_text(text)
    disp = None
    m = re.search(r'Total areal displacement:\s*([-+0-9.e]+)', text)
    if m:
        disp = float(m.group(1))
    return rings, disp


# ── drawing ──────────────────────────────────────────────────────────────────

def draw_rings(ax, rings, title, show_vertices=True):
    """Draw all rings on ax."""
    if not rings:
        ax.set_title(title + '\n(no data)')
        ax.axis('off')
        return

    all_x, all_y = [], []
    for rid in sorted(rings):
        pts = rings[rid]
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts] + [pts[0][0]]
        ys = [p[1] for p in pts] + [pts[0][1]]
        color = RING_COLORS[rid % len(RING_COLORS)]
        lw = 2.0 if rid == 0 else 1.5
        ax.plot(xs, ys, color=color, linewidth=lw, zorder=2)
        if show_vertices:
            ax.scatter([p[0] for p in pts], [p[1] for p in pts],
                       color=color, s=30, zorder=3)
        all_x.extend(xs)
        all_y.extend(ys)

    # padding
    if all_x:
        xr = max(all_x) - min(all_x) or 1
        yr = max(all_y) - min(all_y) or 1
        pad = max(xr, yr) * 0.05
        ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
        ax.set_ylim(min(all_y) - pad, max(all_y) + pad)

    ax.set_aspect('equal', adjustable='box')
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.tick_params(labelsize=7)
    ax.grid(True, linestyle='--', alpha=0.3)

    # legend
    handles = [mpatches.Patch(color=RING_COLORS[rid % len(RING_COLORS)],
                               label=f'Ring {rid} ({len(rings[rid])} verts)')
               for rid in sorted(rings)]
    ax.legend(handles=handles, fontsize=7, loc='upper right')


# ── main ─────────────────────────────────────────────────────────────────────

def visualize(name, open_after=True):
    is_custom = name in MY_TEST_CASES
    if not is_custom and name not in TEST_CASES:
        print(f"Unknown test: {name!r}")
        print("Provided:", ', '.join(sorted(TEST_CASES)))
        print("Custom:  ", ', '.join(sorted(MY_TEST_CASES)))
        sys.exit(1)

    def vcount(rings):
        return sum(len(v) for v in rings.values()) if rings else 0

    if is_custom:
        target, inp_file = MY_TEST_CASES[name]
        my_file  = f"input_{name}_n{target}.txt"
        inp_path = os.path.join(MY_TEST_DIR, inp_file)
        my_path  = os.path.join(MY_OUT_DIR,  my_file)

        input_rings = parse_csv_file(inp_path)
        my_rings, my_disp = None, None
        if os.path.exists(my_path):
            my_rings, my_disp = parse_output_file(my_path)
        else:
            print(f"My output not found: {my_path}")
            print("Run python run_tests.py first to generate it.")

        inp_title = f"Input  ({vcount(input_rings)} vertices)"
        my_title  = (f"My Output  ({vcount(my_rings)} verts)\n"
                     f"disp = {my_disp:.4g}" if my_rings else "My Output\n(not generated)")

        fig, axes = plt.subplots(1, 2, figsize=(13, 6))
        fig.suptitle(f"Custom Test: {name}  (target={target})", fontsize=13, fontweight='bold')
        draw_rings(axes[0], input_rings, inp_title)
        draw_rings(axes[1], my_rings if my_rings else {}, my_title)

    else:
        target, inp_file, exp_file = TEST_CASES[name]
        my_file  = f"input_{name}_n{target}.txt"
        inp_path = os.path.join(TEST_DIR, inp_file)
        exp_path = os.path.join(TEST_DIR, exp_file)
        my_path  = os.path.join(OUT_DIR,  my_file)

        input_rings         = parse_csv_file(inp_path)
        exp_rings, exp_disp = parse_output_file(exp_path)
        my_rings, my_disp   = None, None
        if os.path.exists(my_path):
            my_rings, my_disp = parse_output_file(my_path)
        else:
            print(f"My output not found: {my_path}")
            print("Run python run_tests.py first to generate it.")

        inp_title = f"Input  ({vcount(input_rings)} vertices)"
        my_title  = (f"My Output  ({vcount(my_rings)} verts)\n"
                     f"disp = {my_disp:.4g}" if my_rings else "My Output\n(not generated)")
        exp_title = (f"Expected  ({vcount(exp_rings)} verts, target {target})\n"
                     f"disp = {exp_disp:.4g}" if exp_disp is not None
                     else f"Expected  ({vcount(exp_rings)} verts)")

        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle(f"Test: {name}", fontsize=13, fontweight='bold')
        draw_rings(axes[0], input_rings, inp_title)
        draw_rings(axes[1], my_rings if my_rings else {}, my_title)
        draw_rings(axes[2], exp_rings, exp_title)

    plt.tight_layout()

    # Save to file (works in all environments), then try to open it
    os.makedirs(os.path.join(ROOT, 'visualization'), exist_ok=True)
    out_img = os.path.join(ROOT, 'visualization', f'viz_{name}.png')
    fig.savefig(out_img, dpi=150, bbox_inches='tight')
    print(f"Saved: {out_img}")
    if open_after:
        try:
            import subprocess as _sp, sys as _sys
            if _sys.platform == 'win32':
                _sp.Popen(['explorer', out_img])
            elif _sys.platform == 'darwin':
                _sp.Popen(['open', out_img])
            else:
                _sp.Popen(['xdg-open', out_img])
        except Exception:
            pass
    plt.close(fig)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Provided test cases:")
        for name, (target, inp, exp) in sorted(TEST_CASES.items()):
            print(f"  {name}  (target={target})")
        print("\nCustom test cases:")
        for name, (target, inp) in sorted(MY_TEST_CASES.items()):
            print(f"  {name}  (target={target})")
        print("\nUsage: python visualize.py <test_name> [--no-open]")
        print("  --no-open  save without opening")
        sys.exit(0)

    args = sys.argv[1:]
    open_after = '--no-open' not in args
    name = next(a for a in args if not a.startswith('--'))
    visualize(name, open_after=open_after)
