"""
findwhereleftoff.py

Author: Oliver Appleby

Description:
This script checks local chunked CSV exports from Google Earth Engine
to identify which chunks are missing and which have completed, by scanning
the folder structure on disk. It is designed to help you plan re-exports
to PlotToSat if gaps exist.

Usage:
    1. Edit the BASE_FOLDER_PATH and other configuration variables below.
    2. Run:
       python findwhereleftoff.py

Dependencies:
    Python 3 standard libraries (os, re)

Notes:
    - By default, checks years 2015–2022. Adjust YEARS if needed.
    - Does not require Google Drive API or internet access.
"""

import os
import re

##===================##
###~ CONFIGURATION ~###
##===================##

# Edit this to point to your local folder of downloaded GEE CSVs
BASE_FOLDER_PATH = r"/path/to/your/local/export/folder"

# Countries to check, change to relevant countries
COUNTRIES = ["Finland", "Sweden", "Norway"]

# Years to check
YEARS = list(range(2015, 2023))

# Total plots per country (used to calculate remaining)
TOTAL_PLOTS = {
    "Finland": 2172,
    "Sweden": 10017,
    "Norway": 26,
}

# === HELPER FUNCTIONS ===

def get_country_folder_path(base_path, country, year):
    return os.path.join(base_path, f"Greenbelts_S2_{country}_{year}")

def is_csv_file(filename):
    return filename.lower().endswith(".csv")

def extract_end_index(filename):
    match = re.search(r"_(\d+)_(\d+)_S\d+_mean\.csv$", filename)
    return int(match.group(2)) if match else -1

# === MAIN SCRIPT ===

def check_countries(year):
    grand_total = 0
    grand_done = 0
    export_ranges_lines = []

    for country in COUNTRIES:
        print(f"\n=== Checking {country} {year} ===")
        folder = get_country_folder_path(BASE_FOLDER_PATH, country, year)

        if not os.path.exists(folder):
            print("Folder not found. Skipping.")
            continue

        all_files = os.listdir(folder)
        csv_files = [
            f for f in all_files
            if os.path.isfile(os.path.join(folder, f)) and is_csv_file(f)
        ]

        max_index = max((extract_end_index(f) for f in csv_files), default=-1)
        total = TOTAL_PLOTS.get(country, 0)
        done = max_index + 1 if max_index >= 0 else 0
        remaining = max(total - done, 0)

        grand_total += total
        grand_done += done

        if csv_files:
            last_file = max(csv_files, key=extract_end_index)
            print(f"Found {len(csv_files)} CSV file(s).")
            print(f"Last exported file: {last_file}")
        else:
            print("No CSV files found.")
            last_file = "N/A"

        print(f"Plots done: {done} / {total}")
        print(f"Remaining: {remaining}")

        # Collect lines for the suggested export_ranges
        export_ranges_lines.append(f"    ('{country}', {year}): ({done}, {total}),")

    # === SUMMARY ===
    print("\n=== OVERALL PROGRESS ===")
    print(f"Total plots across all countries: {grand_total}")
    print(f"Total done: {grand_done}")
    print(f"Remaining: {grand_total - grand_done}")

    print("\n=== SUGGESTED EXPORT RANGES FOR PLOTTOSAT ===")
    print("export_ranges = {")
    for line in export_ranges_lines:
        print(line)
    print("}")

# Run for each year
for year in YEARS:
    check_countries(year)
