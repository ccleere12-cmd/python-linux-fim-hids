#!/usr/bin/env python3

# Example cron entry to run every 5 mins: 
# */5 * * * * /usr/bin/python3 /home/cjcleere/python-fim-hids/fim_hids.py >> /home/cjcleere/python-fim-hids/cron.log 2>&1

import os
import json
import hashlib
from datetime import datetime

BASE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIRECTORY, "config.json")

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")} ERROR: Config file not found: {CONFIG_FILE}')
        return None
    except json.JSONDecodeError as e:
        print(f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")} ERROR: Config file contains invalid JSON: {CONFIG_FILE} ({e})')
        return None

    required_keys = [
        "monitored_directories",
        "baseline_file",
        "log_file",
        "excluded_directories",
        "excluded_extensions"
    ]

    key_is_missing = False

    for key in required_keys:
        if key not in config:
            print(f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")} ERROR: Missing config key: {key}')
            key_is_missing = True

    if key_is_missing:
        return None

    return config

def check_baseline_status(config):
    baseline_path = os.path.expanduser(config["baseline_file"])

    if not os.path.exists(baseline_path):
        return True, False  # missing baseline

    if baseline_is_invalid(config):
        return False, True  # invalid baseline 

    return False, False  # baseline exists and is valid

def baseline_is_invalid(config):
    baseline_path = os.path.expanduser(config["baseline_file"])

    if os.path.getsize(baseline_path) == 0:
        return True

    try:
        with open(baseline_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return True

    return False

def log_baseline_error(baseline_is_missing, baseline_is_invalid, config):
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    with open(os.path.expanduser(config["log_file"]), "a") as f:
        if baseline_is_missing:
            f.write(f'{timestamp} event=BASELINE_MISSING path="{os.path.expanduser(config["baseline_file"])}"\n')
        elif baseline_is_invalid:
            f.write(f'{timestamp} event=BASELINE_INVALID path="{os.path.expanduser(config["baseline_file"])}"\n')

def scan_directories(config):
    file_metadata = {}

    for directory in config["monitored_directories"]:
        for root, dirs, files in os.walk(os.path.expanduser(directory)):  # expands ~ to user's home directory
            dirs[:] = [d for d in dirs if d not in config["excluded_directories"]]

            for file in files:
                if not file.endswith(tuple(config["excluded_extensions"])):
                    file_path = os.path.join(root, file)

                    # If the file can't be opened or read, returns None
                    file_hash = calculate_hash(file_path)
                    
                    if file_hash is None:
                        continue
                    
                    try:
                        file_metadata[file_path] = {
                            "hash": file_hash,
                            "last_modified": os.path.getmtime(file_path),
                            "size": os.path.getsize(file_path)
                        }
                    except OSError as e:
                        print(f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")} WARNING: Could not get metadata for file: {file_path} ({e})')
                
    return file_metadata

def calculate_hash(file_path):
    file_hasher = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(4096)  # 4 KB chunk
                if not chunk:  # If chunk is empty
                    break
                file_hasher.update(chunk)

        return file_hasher.hexdigest()
    except OSError as e:
        print(f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")} WARNING: Could not read file: {file_path} ({e})')
        return None

def write_baseline(config, file_metadata):
    try:
        with open(os.path.expanduser(config["baseline_file"]), "w") as f:
            json.dump(file_metadata, f, indent=4, sort_keys=True)  # Cleaner format and sorted alphabetically
            return True
    except OSError as e:
        print(f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")} ERROR: Could not write baseline file: {config["baseline_file"]} ({e})')
        return False

def log_baseline_fix(baseline_is_missing, baseline_is_invalid, config):
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    with open(os.path.expanduser(config["log_file"]), "a") as f:
        if baseline_is_missing:
            f.write(f'{timestamp} event=BASELINE_CREATED path="{os.path.expanduser(config["baseline_file"])}"\n')
        elif baseline_is_invalid:
            f.write(f'{timestamp} event=BASELINE_RECREATED path="{os.path.expanduser(config["baseline_file"])}"\n')

def load_baseline(config):
    with open(os.path.expanduser(config["baseline_file"]), "r") as f:
        baseline_metadata = json.load(f)

    return baseline_metadata

def detect_file_changes(baseline_metadata, current_metadata, file_changes):
    for file_path in current_metadata:
        if file_path not in baseline_metadata:  
            file_changes["NEW"].append(file_path)

    for file_path, metadata in baseline_metadata.items():
        if file_path not in current_metadata:   
            file_changes["DELETED"].append(file_path)
        elif metadata.get("hash") != current_metadata.get(file_path, {}).get("hash"):  # .get(...) is safer here
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
                elif event_type == "MODIFIED":
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

    # Load the information from config.json and store it in a dictionary called config. If config.json is
    # missing, has invalid JSON, or any of the required keys are missing, then print error and return None.
    config = load_config()
    if config is None:
        return

    # Return (baseline_is_missing, baseline_is_invalid) and store in two variables:
    # - If baseline is missing return (True, False).  
    # - If baseline is invalid (empty or bad JSON) return (False, True).
    # - If baseline exists and is valid return (False, False).
    baseline_is_missing, baseline_is_invalid = check_baseline_status(config)  # Tuple unpacking

    if baseline_is_missing or baseline_is_invalid:
        
        # If baseline is missing, then log that error in audit.log.
        # If baseline is invalid, then log that error in audit.log.
        log_baseline_error(baseline_is_missing, baseline_is_invalid, config)

        # Create or recreate the baseline by scanning the directories recursively (while ignoring the necessary file extensions
        # and directories) and creating a snapshot of each file and its metadata. Then store in baseline_metadata (a dictionary)
        baseline_metadata = scan_directories(config)
 
        # Open the JSON baseline file, and write the baseline_metadata dictionary to the file
        if write_baseline(config, baseline_metadata):  # Function returns True if successful, and False if unsuccessful

            # If writing the baseline was successful, log in audit.log that the baseline
            # was created (if it was missing) or recreated (if it was previously invalid)
            log_baseline_fix(baseline_is_missing, baseline_is_invalid, config)
        else:
            return
    else:
        # Load the baseline from the JSON baseline file and return it 
        # (as a dictionary) back to main to store in baseline_metadata
        baseline_metadata = load_baseline(config)

        # Scan directories recursively to get a current snapshot of each file and
        # its metadata. Then return it back to main to store in current_metadata
        current_metadata = scan_directories(config)

        # Find file changes by comparing baseline_metadata with current_metadata (store these changes in the file_changes dictionary):
        # - If any files are in current_metadata and not in baseline_metadata -> new file
        # - If any files are in baseline_metadata and not in current_metadata -> deleted file
        # - If any files have a different hash in baseline_metadata and current_metadata -> modified file
        detect_file_changes(baseline_metadata, current_metadata, file_changes)

        # Write the detected changes (along with the files they happened to and the metadata of the files) to audit.log
        log_changes(config, file_changes, baseline_metadata, current_metadata)

        # If changes were detected (i.e., if any of the three values in the file_changes dictionary are not 
        # empty), update the JSON baseline file so next time the script runs it will use the correct baseline
        if file_changes["NEW"] or file_changes["DELETED"] or file_changes["MODIFIED"]:
            if not write_baseline(config, current_metadata):  # Function returns True if successful, and False if unsuccessful
                return

if __name__ == "__main__":
    main()