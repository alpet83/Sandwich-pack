# /spack_verify.py, created 2025-08-06 18:43 EEST
# Verifies presence of opening tags for each file_id in sandwich files, checking start_line from sandwiches_structure.json

import json
import logging
import re
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s #%(levelname)s: %(message)s'
)

def verify_sandwiches(index_file, structure_file, sandwich_dir="."):
    """Verify opening tags for each file_id in sandwiches, matching start_line from structure."""
    try:
        sandwich_path = Path(sandwich_dir)
        # Load sandwiches_index.json
        with open(sandwich_path / index_file, "r", encoding="utf-8") as f:
            index = json.load(f)
        file_map = {int(line.split(",")[0]): line.split(",")[1] for line in index["files"]}
        logging.info(f"Loaded {len(file_map)} files from {index_file}")

        # Load sandwiches_structure.json
        with open(sandwich_path/ structure_file, "r", encoding="utf-8") as f:
            structure = json.load(f)
        sandwiches = structure["sandwiches"]
        logging.info(f"Loaded {len(sandwiches)} sandwich entries from {structure_file}")

        # Track found and missing file_ids
        found_files = set()
        missing_files = set(file_map.keys())

        # Process each sandwich file
        for sandwich in sandwiches:
            sandwich_file = sandwich_path / sandwich["file"]
            if not sandwich_file.exists():
                logging.error(f"Sandwich file {sandwich_file} not found in {sandwich_dir}")
                continue

            with open(sandwich_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Check each block in the sandwich
            for block in sandwich["blocks"]:
                file_id = block["file_id"]
                start_line = block["start_line"]
                file_name = file_map.get(file_id, f"Unknown (file_id={file_id})")

                # Verify start_line is within bounds
                if start_line < 1 or start_line > len(lines):
                    logging.warning(f"Start line {start_line} out of range for file_id={file_id} ({file_name}) in {sandwich_file}")
                    continue

                # Check for opening tag at start_line
                line = lines[start_line - 1].strip()
                tag_pattern = r'<\s*(python|php|jss|rustc|tss|vue)\s+[^>]*file_id="' + str(file_id) + r'"[^>]*>'
                if re.match(tag_pattern, line):
                    logging.info(f"Opening tag found for file_id={file_id} ({file_name}) at start_line={start_line} in {sandwich_file}: {line}")
                    found_files.add(file_id)
                else:
                    logging.warning(f"Opening tag not found for file_id={file_id} ({file_name}) at start_line={start_line} in {sandwich_file}. Line: {line}")

        # Report missing files
        missing_files -= found_files
        if missing_files:
            logging.error(f"Missing files: {', '.join(f'file_id={fid} ({file_map.get(fid, "Unknown")})' for fid in sorted(missing_files))}")
        else:
            logging.info("All files from sandwiches_index.json found in sandwiches")

        return len(missing_files) == 0

    except Exception as e:
        logging.error(f"Verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    index_file = "sandwiches_index.json"
    structure_file = "sandwiches_structure.json"
    sandwich_dir = "./sandwiches"  # Adjust if sandwiches are in a different directory
    success = verify_sandwiches(index_file, structure_file, sandwich_dir)
    if not success:
        logging.error("Verification failed: Some files are missing or have incorrect start lines")