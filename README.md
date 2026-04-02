# DSA Assignment 2

This repository contains a C++ polygon simplifier, Python test/experiment runners, performance plot scripts, and an HTML report generator.

> **Quick look:** open `report.html` in any browser to see a fully self-contained report with all results, plots, and visualizations.

## Files

### Source & Build

| File | Description |
|---|---|
| `simplify.cpp` | Main C++ implementation |
| `Makefile` | Builds the `simplify` executable |
| `requirements.txt` | Python package dependencies |

### Scripts

| Script | Description |
|---|---|
| `run_all.py` | Full pipeline runner — compile → test → visualize → plot |
| `run_tests.py` | Validates all test cases and writes outputs to `test_outputs/` |
| `visualize.py` | Side-by-side visualization for a single test case |
| `visualize_all.py` | Generates PNGs for every test case |
| `plot_displacement_vs_target.py` | Plots areal displacement vs. target vertex count |
| `plot_time_vs_memory.py` | Plots runtime vs. peak memory and runtime vs. input size |
| `plot_memory_vs_inputsize.py` | Plots peak memory usage vs. input size with curve fits |
| `generate_report.py` | Produces a self-contained `report.html` |

### Data & Output

| File / Directory | Description |
|---|---|
| `report.html` | Generated HTML report — open in browser |
| `report_content.json` | Dataset descriptions, graph summaries, and curve-fit notes used by the report |
| `test_results.json` | JSON summary produced by `run_tests.py` |
| `test_cases/` | Provided input CSVs and expected output files |
| `test_outputs/` | Outputs produced by `run_tests.py` for provided cases |
| `my_test_cases/` | Custom input CSVs |
| `my_test_outputs/` | Outputs for custom test cases |
| `visualization/` | PNG side-by-side images for every test case |
| `displacement_vs_target/` | CSVs and PNGs for displacement plots |
| `time_vs_memory/` | CSVs and PNGs for runtime/memory plots |
| `memory_vs_inputsize/` | CSV and PNG for memory vs. input-size plot |

## Requirements

- `g++` with C++17 support
- `make`
- Python 3
- Python packages: `matplotlib`, `numpy`, `scipy`

Install Python dependencies with:

```bash
pip install -r requirements.txt
```

## Build

Build the simplifier from the project root:

```bash
make
```

On Windows, build through WSL:

```powershell
wsl make
```

This produces the `simplify` executable in the project root.

## Full Pipeline (Recommended)

`run_all.py` runs every step in order: compile, test, visualize, and all three plots.

```bash
python run_all.py
```

On Windows:

```powershell
python run_all.py
```

Optional flags:

- `--skip-make` — skip the compile step if already built
- `--skip-plots` — skip the three plot scripts

## Run The Tests

```bash
python3 run_tests.py
```

On Windows with WSL:

```powershell
wsl python3 ./run_tests.py
```

What the test runner does:

- runs `simplify` on every input in `test_cases/` and `my_test_cases/`
- compares output summary values against expected outputs
- writes generated outputs into `test_outputs/` and `my_test_outputs/`
- saves a `test_results.json` summary

Typical output:

```text
Test                                      Result
----------------------------------------------------------------------
rectangle_with_two_holes (n=7)            PASS  area_in=...
...
```

## Visualizations

### Single case

```bash
python visualize.py lake_with_two_islands
python visualize.py lake_with_two_islands --no-open   # save PNG without opening
```

Creates `visualization/viz_lake_with_two_islands.png` showing three panels: Input | My Output | Expected Output.

### All cases

```bash
python visualize_all.py
```

Saves a PNG for every test case (provided + custom) into `visualization/`.

## Performance Plots

Each script saves its output into its own subdirectory and can be run independently after building.

### Displacement vs. Target vertex count

```bash
python plot_displacement_vs_target.py
```

Outputs:
- `displacement_vs_target/displacement_vs_target.png` — cross-case scatter
- `displacement_vs_target/displacement_sweep.png` — per-polygon sweep across many targets
- Corresponding `.csv` data files

### Runtime vs. Memory

```bash
python plot_time_vs_memory.py
```

Outputs:
- `time_vs_memory/time_vs_memory.png` — runtime vs. peak memory scatter
- `time_vs_memory/runtime_vs_inputsize.png` — runtime vs. input vertex count with curve fits
- `time_vs_memory/time_vs_memory.csv`

### Memory vs. Input Size

```bash
python plot_memory_vs_inputsize.py
```

Outputs:
- `memory_vs_inputsize/memory_vs_inputsize.png` — peak RSS vs. vertex count with curve fits
- `memory_vs_inputsize/memory_vs_inputsize.csv`

> **Note (Windows):** The memory-measurement scripts use `/usr/bin/time -v` via WSL to capture peak RSS. They will not work without WSL.

## Generate HTML Report

```bash
python generate_report.py
```

Produces `report.html` — a fully self-contained file with all images embedded as base64. Open it in any browser; no server or internet connection needed.

The report includes:

- Summary table (displacement, runtime, memory, input size)
- All three performance plots
- Per-test visualizations grouped by category (provided + custom)
- Custom dataset descriptions and graph summaries from `report_content.json`

## Run The Simplifier Directly

```bash
./simplify test_cases/input_lake_with_two_islands.csv 17
```

On Windows through WSL:

```powershell
wsl ./simplify ./test_cases/input_lake_with_two_islands.csv 17
```

The program writes CSV rows to stdout, followed by summary lines for:

- total signed area in input
- total signed area in output
- total areal displacement