# DSA Assignment 2

This repository contains a C++ polygon simplifier, a Python test runner, and Python visualization scripts for comparing your output against the provided reference outputs.

## Files

- `simplify.cpp`: main C++ implementation
- `Makefile`: builds the `simplify` executable
- `run_tests.py`: runs all provided test cases and writes your outputs to `test_outputs/`
- `visualize.py`: generates a side-by-side visualization for one test case
- `visualize_all.py`: generates visualizations for every test case
- `test_cases/`: provided input files and expected outputs
- `test_outputs/`: outputs produced by `run_tests.py`
- `visualization/`: PNG images produced by the visualization scripts

## Requirements

- `g++` with C++17 support
- `make`
- Python 3
- Python package: `matplotlib`

Install the Python dependency with:

```bash
pip install -r requirements.txt
```

## Build

Build the simplifier from the project root:

```bash
make
```

On Windows, the current setup is intended to be built through WSL:

```powershell
wsl make
```

This produces the executable `simplify` in the project root.

## Run The Tests

Run all tests from the project root:

```bash
python3 run_tests.py
```

On Windows with WSL:

```powershell
wsl python3 ./run_tests.py
```

What the test runner does:

- runs `simplify` on every input in `test_cases/`
- compares the output summary values against the expected output
- writes your generated outputs into `test_outputs/`

Typical output looks like this:

```text
Test                                      Result
----------------------------------------------------------------------
rectangle_with_two_holes (n=7)            PASS  area_in=...
...
```

## Run A Single Visualization

First generate outputs with the test runner so `test_outputs/` contains your latest results.

Then visualize one case:

```bash
python visualize.py lake_with_two_islands
```

Examples:

```bash
python visualize.py rectangle_with_two_holes
python visualize.py original_01
```

To save the PNG without trying to open it automatically:

```bash
python visualize.py lake_with_two_islands --no-open
```

This script creates a PNG in `visualization/` named like:

```text
visualization/viz_lake_with_two_islands.png
```

Each image shows three panels:

- Input
- My Output
- Expected Output

## Generate All Visualizations

To generate PNGs for every test case:

```bash
python visualize_all.py
```

This saves all images into `visualization/`.

## Run The Simplifier Directly

You can also run the executable directly on one input file:

```bash
./simplify test_cases/input_lake_with_two_islands.csv 17
```

On Windows through WSL:

```powershell
wsl ./simplify ./test_cases/input_lake_with_two_islands.csv 17
```

The program writes CSV rows to standard output, followed by summary lines for:

- total signed area in input
- total signed area in output
- total areal displacement

## Recommended Workflow

1. Build the project with `make` or `wsl make`.
2. Run `python3 run_tests.py` or `wsl python3 ./run_tests.py`.
3. Inspect any generated outputs in `test_outputs/`.
4. Run `python visualize_all.py` to generate the PNGs to allow us to inspect visually.