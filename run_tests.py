#!/usr/bin/env python3
"""
Test runner for the APSC simplify executable.

Checks:
  - Total signed area in input  matches expected (within floating-point tolerance)
  - Total signed area in output matches expected (within floating-point tolerance)
  - Total areal displacement is <= expected value
"""

import subprocess
import sys
import re
import os
import json

# Path to the simplify executable (relative to this script's directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SIMPLIFY = os.path.join(SCRIPT_DIR, 'simplify')
TEST_DIR = os.path.join(SCRIPT_DIR, 'test_cases')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'test_outputs')
MY_TEST_DIR = os.path.join(SCRIPT_DIR, 'my_test_cases')
MY_OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'my_test_outputs')

# Each entry: (input_file, target_vertices, expected_output_file)
TEST_CASES = [
    ('input_rectangle_with_two_holes.csv',    7,  'output_rectangle_with_two_holes.txt'),
    ('input_cushion_with_hexagonal_hole.csv', 13, 'output_cushion_with_hexagonal_hole.txt'),
    ('input_blob_with_two_holes.csv',         17, 'output_blob_with_two_holes.txt'),
    ('input_wavy_with_three_holes.csv',       21, 'output_wavy_with_three_holes.txt'),
    ('input_lake_with_two_islands.csv',       17, 'output_lake_with_two_islands.txt'),
    ('input_original_01.csv',                 99, 'output_original_01.txt'),
    ('input_original_02.csv',                 99, 'output_original_02.txt'),
    ('input_original_03.csv',                 99, 'output_original_03.txt'),
    ('input_original_04.csv',                 99, 'output_original_04.txt'),
    ('input_original_05.csv',                 99, 'output_original_05.txt'),
    ('input_original_06.csv',                 99, 'output_original_06.txt'),
    ('input_original_07.csv',                 99, 'output_original_07.txt'),
    ('input_original_08.csv',                 99, 'output_original_08.txt'),
    ('input_original_09.csv',                 99, 'output_original_09.txt'),
    ('input_original_10.csv',                 99, 'output_original_10.txt'),
]

AREA_REL_TOL = 1e-6   # relative tolerance for area comparison

def parse_summary(text):
    """Extract the three summary values from output text."""
    def get(pattern):
        m = re.search(pattern, text)
        if not m:
            raise ValueError(f"Pattern not found: {pattern!r}\nIn text:\n{text[-400:]}")
        return float(m.group(1))
    area_in  = get(r'Total signed area in input:\s*([-+0-9.e]+)')
    area_out = get(r'Total signed area in output:\s*([-+0-9.e]+)')
    disp     = get(r'Total areal displacement:\s*([-+0-9.e]+)')
    return area_in, area_out, disp

def areas_match(a, b, rel_tol=AREA_REL_TOL):
    """Check two area values match within relative tolerance."""
    if a == b == 0.0:
        return True
    return abs(a - b) / max(abs(a), abs(b), 1e-300) <= rel_tol

def run_test(input_file, target, expected_file):
    input_path    = os.path.join(TEST_DIR, input_file)
    expected_path = os.path.join(TEST_DIR, expected_file)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{os.path.splitext(input_file)[0]}_n{target}.txt")

    # Run simplify (via WSL on Windows, or directly on Unix)
    if sys.platform == 'win32':
        wsl_input = input_path.replace('\\', '/').replace('C:', '/mnt/c').replace('c:', '/mnt/c')
        wsl_simplify = SIMPLIFY.replace('\\', '/').replace('C:', '/mnt/c').replace('c:', '/mnt/c')
        cmd = ['wsl', wsl_simplify, wsl_input, str(target)]
    else:
        cmd = [SIMPLIFY, input_path, str(target)]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        return False, f"CRASHED (exit {result.returncode})\n  stderr: {result.stderr.strip()}"

    actual_output = result.stdout
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(actual_output)

    # Parse expected
    with open(expected_path, 'r') as f:
        expected_output = f.read()

    try:
        exp_area_in, exp_area_out, exp_disp = parse_summary(expected_output)
    except ValueError as e:
        return False, f"Could not parse expected output: {e}"

    try:
        act_area_in, act_area_out, act_disp = parse_summary(actual_output)
    except ValueError as e:
        return False, f"Could not parse actual output: {e}"

    failures = []

    if not areas_match(act_area_in, exp_area_in):
        failures.append(
            f"area_in mismatch: got {act_area_in:.6e}, expected {exp_area_in:.6e}"
        )
    if not areas_match(act_area_out, exp_area_out):
        failures.append(
            f"area_out mismatch: got {act_area_out:.6e}, expected {exp_area_out:.6e}"
        )
    if act_disp > exp_disp * (1 + AREA_REL_TOL):
        failures.append(
            f"displacement WORSE: got {act_disp:.6e}, expected <= {exp_disp:.6e}"
        )

    if failures:
        return 'FAIL', '\n  '.join(failures)

    if act_disp < exp_disp * (1 - AREA_REL_TOL):
        return 'BETTER', f'area_in={act_area_in:.6e}  disp={act_disp:.6e}  (expected {exp_disp:.6e})'

    return 'PASS', f'area_in={act_area_in:.6e}  disp={act_disp:.6e}'


# Custom test cases (no expected output — just run and save)
MY_TEST_CASES = [
    ('input_many_holes.csv',            37),
    ('input_dense_outer.csv',           50),
    ('input_narrow_corridor.csv',        5),
    ('input_nested_rings.csv',          20),
    ('input_large_with_many_holes.csv', 40),
]

def run_custom(input_file, target):
    """Run simplify on a custom test case and save output; no validation."""
    input_path = os.path.join(MY_TEST_DIR, input_file)
    os.makedirs(MY_OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(MY_OUTPUT_DIR, f"{os.path.splitext(input_file)[0]}_n{target}.txt")

    if sys.platform == 'win32':
        wsl_input    = input_path.replace('\\', '/').replace('C:', '/mnt/c').replace('c:', '/mnt/c')
        wsl_simplify = SIMPLIFY.replace('\\', '/').replace('C:', '/mnt/c').replace('c:', '/mnt/c')
        cmd = ['wsl', wsl_simplify, wsl_input, str(target)]
    else:
        cmd = [SIMPLIFY, input_path, str(target)]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        return False, f"CRASHED (exit {result.returncode})\n  stderr: {result.stderr.strip()}"

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(result.stdout)

    try:
        _, _, disp = parse_summary(result.stdout)
        return True, f'disp={disp:.6e}'
    except ValueError:
        return True, 'ran OK (no summary parsed)'


def main():
    passed = 0
    failed = 0
    col = 40  # width for test name column

    print(f"{'Test':<{col}}  {'Result'}")
    print('-' * (col + 30))

    provided_results = []
    for input_file, target, expected_file in TEST_CASES:
        name = input_file.replace('input_', '').replace('.csv', '')
        display = name + f' (n={target})'
        try:
            status, msg = run_test(input_file, target, expected_file)
        except subprocess.TimeoutExpired:
            status, msg = 'FAIL', 'TIMEOUT'
        except Exception as e:
            status, msg = 'FAIL', str(e)

        print(f"{display:<{col}}  {status}  {msg}")
        if status != 'FAIL':
            passed += 1
        else:
            failed += 1
        provided_results.append({'name': name, 'target': target, 'status': status, 'message': msg})

    print('-' * (col + 30))
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")

    # ── Custom test cases (run-only, no validation) ───────────────────────────
    print()
    print(f"{'Custom Test':<{col}}  {'Result'}")
    print('-' * (col + 30))

    custom_results = []
    for input_file, target in MY_TEST_CASES:
        name = input_file.replace('input_', '').replace('.csv', '')
        display = name + f' (n={target})'
        try:
            ok, msg = run_custom(input_file, target)
        except subprocess.TimeoutExpired:
            ok, msg = False, 'TIMEOUT'
        except Exception as e:
            ok, msg = False, str(e)
        status = 'OK' if ok else 'FAIL'
        print(f"{display:<{col}}  {status}  {msg}")
        custom_results.append({'name': name, 'target': target, 'status': status, 'message': msg})

    print('-' * (col + 30))

    # ── Save JSON results ─────────────────────────────────────────────────────
    results_path = os.path.join(SCRIPT_DIR, 'test_results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'provided': provided_results,
            'custom':   custom_results,
            'summary':  {'passed': passed, 'failed': failed, 'total': passed + failed},
        }, f, indent=2)
    print(f"\nResults saved to: {results_path}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
