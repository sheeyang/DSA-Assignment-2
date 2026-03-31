#!/usr/bin/env python3
"""
run_all.py — full pipeline runner.

Steps:
  1. make clean && make       (compile simplify inside WSL)
  2. run_tests.py             (validate against provided test cases + run custom ones)
  3. visualize_all.py         (generate all PNGs in visualization/)
  4. plot_displacement_vs_target.py
  5. plot_time_vs_memory.py
  6. plot_memory_vs_inputsize.py

Pass --skip-make to skip the compile step (if already compiled).
Pass --skip-plots to skip steps 4-6 (useful if simplify is broken).
"""

import sys
import os
import subprocess
import argparse
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON     = sys.executable


def banner(title):
    width = 60
    print()
    print('=' * width)
    print(f'  {title}')
    print('=' * width)


def run_step(label, cmd, cwd=SCRIPT_DIR):
    banner(label)
    print(f"  cmd: {' '.join(cmd)}\n")
    t0 = time.perf_counter()
    result = subprocess.run(cmd, cwd=cwd)
    elapsed = time.perf_counter() - t0
    status = 'OK' if result.returncode == 0 else f'FAILED (exit {result.returncode})'
    print(f"\n  [{status}]  {elapsed:.1f}s")
    return result.returncode == 0


def make_step():
    """Run make clean && make (via WSL when called from Windows, directly on Linux)."""
    banner('Step 1 — compile (make clean && make)')
    if sys.platform == 'win32':
        project = SCRIPT_DIR.replace('\\', '/').replace('C:', '/mnt/c').replace('c:', '/mnt/c')
        cmd = ['wsl', 'bash', '-c', f'cd "{project}" && make clean && make']
    else:
        cmd = ['bash', '-c', 'make clean && make']
    print(f"  cmd: {' '.join(cmd)}\n")
    t0 = time.perf_counter()
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    elapsed = time.perf_counter() - t0
    ok = result.returncode == 0
    print(f"\n  [{'OK' if ok else 'FAILED'}]  {elapsed:.1f}s")
    return ok


def main():
    parser = argparse.ArgumentParser(description='Run full DSA-Assignment-2 pipeline.')
    parser.add_argument('--skip-make',  action='store_true', help='Skip make step')
    parser.add_argument('--skip-plots', action='store_true', help='Skip plot steps')
    args = parser.parse_args()

    results = {}
    total_start = time.perf_counter()

    # ── Step 1: compile ───────────────────────────────────────────────────────
    if args.skip_make:
        banner('Step 1 — compile (skipped)')
        results['make'] = None
    else:
        results['make'] = make_step()
        if not results['make']:
            print('\n  Compilation failed. Continuing anyway (binary may still work).')

    # ── Step 2: run tests ─────────────────────────────────────────────────────
    results['run_tests'] = run_step(
        'Step 2 — run_tests.py',
        [PYTHON, 'run_tests.py'],
    )

    # ── Step 3: visualize all ─────────────────────────────────────────────────
    results['visualize_all'] = run_step(
        'Step 3 — visualize_all.py',
        [PYTHON, 'visualize_all.py'],
    )

    # ── Steps 4-6: plots ──────────────────────────────────────────────────────
    if args.skip_plots:
        banner('Steps 4-6 — plots (skipped)')
        results['plot_displacement'] = None
        results['plot_time_mem']     = None
        results['plot_mem_size']     = None
    else:
        results['plot_displacement'] = run_step(
            'Step 4 — plot_displacement_vs_target.py',
            [PYTHON, 'plot_displacement_vs_target.py'],
        )
        results['plot_time_mem'] = run_step(
            'Step 5 — plot_time_vs_memory.py',
            [PYTHON, 'plot_time_vs_memory.py'],
        )
        results['plot_mem_size'] = run_step(
            'Step 6 — plot_memory_vs_inputsize.py',
            [PYTHON, 'plot_memory_vs_inputsize.py'],
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    total_elapsed = time.perf_counter() - total_start
    banner('Summary')
    labels = {
        'make':             'Step 1  compile',
        'run_tests':        'Step 2  run_tests',
        'visualize_all':    'Step 3  visualize_all',
        'plot_displacement': 'Step 4  plot displacement',
        'plot_time_mem':    'Step 5  plot time vs memory',
        'plot_mem_size':    'Step 6  plot memory vs input size',
    }
    any_failed = False
    for key, label in labels.items():
        r = results.get(key)
        if r is None:
            tag = 'SKIPPED'
        elif r:
            tag = 'OK     '
        else:
            tag = 'FAILED '
            any_failed = True
        print(f"  {tag}  {label}")

    print(f"\n  Total time: {total_elapsed:.1f}s")
    sys.exit(1 if any_failed else 0)


if __name__ == '__main__':
    main()
