"""
input_service.py
Discovers the clinical trial CSV from the configured directory.
No file upload from UI — the file is pre-placed on the server.
"""

import os
from datetime import datetime, timezone


def discover_csv(config: dict) -> dict:
    """
    Locate the CSV file in the configured directory.
    Returns file metadata dict. Raises FileNotFoundError if missing.

    Returns:
        {
            "csv_path": str,
            "file_modified_at": datetime,
            "file_size_bytes": int,
        }
    """
    csv_dir = config["data"]["csv_directory"]
    csv_filename = config["data"]["csv_filename"]
    csv_path = os.path.join(csv_dir, csv_filename)
    abs_path = os.path.abspath(csv_path)

    if not os.path.exists(abs_path):
        raise FileNotFoundError(
            f"CSV file not found at '{abs_path}'. "
            f"Please place '{csv_filename}' in the '{csv_dir}/' directory."
        )

    stat = os.stat(abs_path)
    file_modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    file_size_bytes = stat.st_size

    return {
        "csv_path": abs_path,
        "file_modified_at": file_modified_at,
        "file_size_bytes": file_size_bytes,
    }
