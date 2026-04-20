#!/usr/bin/env python3

# Next things TODO (most likely in this order): 
#   - Do Cron
#   - Maybe make the baseline reliability and first-run behavior better and safer (maybe by seperating where they run; also, see notes in Word and what Chat said)
#   - Maybe add exclusion/ignore rules to answer this: What should I skip inside the monitored directories I choose in the config file. They would be added to the config file
#   - Maybe use pathlib module (instead of os) where you can
#   - When reading the binary of a large file, reading all at once is risky. So maybe read in chunks
#   - Maybe add file permission and/or ownership tracking (see Chat #8 and notes)
#   - Maybe add summary reporting per scan (see Chat #7)
#   - Maybe add file type in metadata
#   - Maybe add option to have log entries be sent to the user via email (and/or something else like to the terminal and/or a phone number)
#   - Figure out error checking (see notes). Ask Chat to teach you how to do error checking (probably including try…catch) for this project (especially with dictionaries and nested dictionaries) without giving any answers
#   - Figure out the right folders to monitor in Linux and why. Also, if you do exclusions, figure out the right stuff to exclude/ignore in Linux
#   - Fix, clean up and add comments
#   - Figure out what the permissions on each file in your project should be

# Cron entry for the script to run once a month on the last day of the month at 11:59pm:
# 59 23 31 * * /courses/cscn345/sp26/cjcleere/labs/theCronJob2.txt

import os
import hashlib
import json
from datetime import datetime

# MONITOR_DIRECTORY = os.path.expanduser("~/python-linux-fim-hids/test-monitor-directory/")
# BASELINE_FILE = os.path.expanduser("~/python-linux-fim-hids/baseline.json")
# LOG_FILE = os.path.expanduser("~/python-linux-fim-hids/audit.log")

BASE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIRECTORY, "config.json")

def load_config():
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    return config

def scan_directories(config):
    file_metadata = {}
    for directory in config["monitored_directories"]:
        for root, _, files in os.walk(os.path.expanduser(directory)):  # expands ~ to user's home directory
            for file in files:
                file_path = os.path.join(root, file)
                file_metadata[file_path] = {
                    "hash": calculate_hash(file_path),
                    "last_modified": os.path.getmtime(file_path),
                    "size": os.path.getsize(file_path)
                }
    return file_metadata

def calculate_hash(file_path):
    file_hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    file_hasher.update(file_bytes)
    return file_hasher.hexdigest()

def write_baseline(config, file_metadata):
    with open(os.path.expanduser(config["baseline_file"]), "w") as f:
        json.dump(file_metadata, f, indent=4, sort_keys=True)  # Cleaner format and sorted alphabetically

def load_baseline(config):
    with open(os.path.expanduser(config["baseline_file"]), "r") as f:
        baseline_hashes = json.load(f)
    return baseline_hashes

def compare_hashes(baseline_hashes, current_hashes, file_changes):
    for file_path in current_hashes:
        if file_path not in baseline_hashes:  
            file_changes["NEW"].append(file_path)
    for file_path, metadata in baseline_hashes.items():
        if file_path not in current_hashes:   
            file_changes["DELETED"].append(file_path)
        elif metadata.get("hash") != current_hashes.get(file_path, {}).get("hash"):  # .get(...) is safer here
            file_changes["MODIFIED"].append(file_path)

def log_changes(config, file_changes, baseline_metadata, current_metadata):
    with open(os.path.expanduser(config["log_file"]), "a") as f:
        for event_type, file_pathes in file_changes.items():
            for file_path in file_pathes:
                timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                if event_type == "NEW":
                    size = current_metadata[file_path]["size"]
                    readable_last_modified = datetime.fromtimestamp(current_metadata[file_path]["last_modified"]).strftime("%Y-%m-%dT%H:%M:%S")
                    f.write(f'{timestamp} event={event_type} path="{file_path}" size={size} last_modified="{readable_last_modified}"\n')
                elif event_type == "DELETED":
                    size = baseline_metadata[file_path]["size"]
                    readable_last_modified = datetime.fromtimestamp(baseline_metadata[file_path]["last_modified"]).strftime("%Y-%m-%dT%H:%M:%S")
                    f.write(f'{timestamp} event={event_type} path="{file_path}" size={size} last_modified="{readable_last_modified}"\n')
                else:
                    size_old = baseline_metadata[file_path]["size"]
                    size_new = current_metadata[file_path]["size"]
                    readable_last_modified_old = datetime.fromtimestamp(baseline_metadata[file_path]["last_modified"]).strftime("%Y-%m-%dT%H:%M:%S")
                    readable_last_modified_new = datetime.fromtimestamp(current_metadata[file_path]["last_modified"]).strftime("%Y-%m-%dT%H:%M:%S")
                    f.write(f'{timestamp} event={event_type} path="{file_path}" size_old={size_old} size_new={size_new} last_modified_old="{readable_last_modified_old}" last_modified_new="{readable_last_modified_new}"\n')
        
def main():

    file_changes = {
        "NEW": [],
        "DELETED": [],
        "MODIFIED": []
    }

    config = load_config()

    # ChatGPT's (error checking) recommendation:

    #baseline_path = config.get("baseline_file")

    # if not baseline_path:
    #     raise ValueError("baseline_file is missing from config")

    # baseline_path = os.path.expanduser(baseline_path)

    # if not os.path.exists(baseline_path) or os.path.getsize(baseline_path) == 0:
    # ...

    if not os.path.exists(os.path.expanduser(config["baseline_file"])) or os.path.getsize(os.path.expanduser(config["baseline_file"])) == 0:  # If there is no baseline

        # Scans MONITOR_DIRECTORY recursively, and creates a dictionary of the paths (keys) and hashes (values) of all the files that are recursively in the directory and returns it back to main to store in baseline_hashes
        baseline_metadata = scan_directories(config)

        # Opens the JSON baseline file to write to, and writes the dictionary (that was created from the scan) of file paths and hashes to the file
        write_baseline(config, baseline_metadata)

    # Loads the baseline from the JSON baseline file and returns it (as a dictionary) back to main to store in baseline_hashes
    baseline_metadata = load_baseline(config)

    # Scans MONITOR_DIRECTORY recursively, and creates a dictionary of the paths (keys) and hashes (values) of all the files that are recursively in the directory and returns it back to main to store in current_hashes
    current_metadata = scan_directories(config)

    # Compares current hashes and baseline hashes, and stores the detected changes (and the files they happened to) in the file_changes dictionary
    compare_hashes(baseline_metadata, current_metadata, file_changes)

    # Writes the detected changes (and the files they happened to) to LOG_FILE
    log_changes(config, file_changes, baseline_metadata, current_metadata)

    # If changes were detected (i.e., if any of the three values in the file_changes dictionary aren't empty), update the JSON baseline file so next time the script runs it will use the correct baseline
    if file_changes["NEW"] or file_changes["DELETED"] or file_changes["MODIFIED"]:
        write_baseline(config, current_metadata)

if __name__ == "__main__":
    main()