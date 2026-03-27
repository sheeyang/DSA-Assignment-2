#!/usr/bin/env python3
"""Run visualize.py for every test case and save all PNGs to visualization/."""

import sys
import os
from visualize import TEST_CASES, visualize

if __name__ == '__main__':
    names = sorted(TEST_CASES)
    print(f"Generating {len(names)} visualizations into visualization/\n")
    for name in names:
        print(f"  {name} ...", end=' ', flush=True)
        try:
            visualize(name, open_after=False)
            print("done")
        except Exception as e:
            print(f"ERROR: {e}")
    print("\nAll done.")
