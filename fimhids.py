#!/usr/bin/env python3

# Cron entry for the script to run once a month on the last day of the month at 11:59pm:
# 59 23 31 * * /courses/cscn345/sp26/cjcleere/labs/theCronJob2.txt

import os
import hashlib
import json

MONITOR_FOLDER = os.path.expanduser("~/fimhids-periodic/test-monitor-folder/")
BASELINE_FILE = os.path.expanduser("~/fimhids-periodic/baseline.json")
LOG_FILE = os.path.expanduser("~/fimhids-periodic/audit.log")

def scan_folder(folder):
    file_hashes = {}
    for root, _, files in os.walk(folder):
        for file in files:
            file_path = os.path.join(root, file)
            file_hash = calculate_hash(file_path)
            file_hashes[file_path] = file_hash
    return file_hashes

def calculate_hash(file_path):
    file_hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    file_hasher.update(file_bytes)
    return file_hasher.hexdigest()

def write_baseline(file_hashes):
    with open(BASELINE_FILE, "w") as f:
        json.dump(file_hashes, f, indent=4, sort_keys=True)  # Cleaner format and sorted alphabetically

def read_baseline():
    with open(BASELINE_FILE, "r") as f:
        baseline_hashes = json.load(f)
    return baseline_hashes

def compare_hashes(baseline_hashes, current_hashes, file_changes):
    for file_path, file_hash in current_hashes.items():
        if file_path not in baseline_hashes:  # If new file detected
            file_changes["[NEW]"].append(file_path)
    for file_path, file_hash in baseline_hashes.items():
        if file_path not in current_hashes:  # If deleted file detected 
            file_changes["[DELETED]"].append(file_path)
        elif file_hash != current_hashes.get(file_path):  # If modified file detected
            file_changes["[MODIFIED]"].append(file_path)

def log_changes(file_changes):
    with open(LOG_FILE, "a") as f:
        for change_type, file_pathes in file_changes.items():
            for file_path in file_pathes:
                f.write(f"{change_type} {file_path}\n")
        
def main():
    file_changes = {
        "[NEW]": [],
        "[DELETED]": [],
        "[MODIFIED]": []
    }

    if not os.path.exists(BASELINE_FILE) or os.path.getsize(BASELINE_FILE) == 0:  # If there is no baseline

        # Scans MONITOR_FOLDER recursively, and creates a dictionary of the paths (keys) and hashes (values) of all the files that are recursively in the folder and returns it back to main to store in baseline_hashes
        baseline_hashes = scan_folder(MONITOR_FOLDER)

        # Opens the JSON baseline file to write to, and writes the dictionary (that was created from the scan) of file paths and hashes to the file
        write_baseline(baseline_hashes)

    # Reads the baseline from the JSON baseline file and returns it (as a dictionary) back to main to store in baseline_hashes
    baseline_hashes = read_baseline()

    # Scans MONITOR_FOLDER recursively, and creates a dictionary of the paths (keys) and hashes (values) of all the files that are recursively in the folder and returns it back to main to store in current_hashes
    current_hashes = scan_folder(MONITOR_FOLDER)

    # Compares current hashes and baseline hashes, and stores the detected changes (and the files they happened to) in the file_changes dictionary
    compare_hashes(baseline_hashes, current_hashes, file_changes)

    # Writes the detected changes (and the files they happened to) to LOG_FILE
    log_changes(file_changes)

    # If changes were detected (i.e., if any of the three values in the file_changes dictionary aren't empty), update the JSON baseline file so next time the script runs it will use the correct baseline
    if file_changes["[NEW]"] or file_changes["[DELETED]"] or file_changes["[MODIFIED]"]:
        write_baseline(current_hashes)

if __name__ == "__main__":
    main()