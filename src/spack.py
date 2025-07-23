# /spack.py, updated 2025-07-15 09:57 EEST
import os
import datetime
import logging
import argparse
from pathlib import Path
from lib.sandwich_pack import SandwichPack

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s #%(levelname)s: %(message)s')

def get_file_mod_time(file_path):
    mtime = os.path.getmtime(file_path)
    mod_time = datetime.datetime.fromtimestamp(mtime, datetime.UTC)
    return mod_time.strftime("%Y-%m-%d %H:%M:%SZ")

def is_hidden_file(filepath):
    return any(part.startswith(".") for part in filepath.parts)

def collect_files(root_dir):
    content = []
    root_path = Path(root_dir).parent
    logging.debug(f"Scanning directory: {root_dir}")
    if not os.path.exists(root_dir):
        logging.error(f"Directory {root_dir} does not exist")
        return content
    for file_path in Path(root_dir).rglob("*"):
        if file_path.is_file() and not is_hidden_file(file_path):
            relative_path = f"/{file_path.relative_to(root_path)}".replace("\\", "/")
            extension = Path(file_path).suffix.lower()
            content_type = extension if extension else ""
            if not content_type or not SandwichPack.supported_type(content_type):
                logging.debug(f"Skipping unsupported content_type: {content_type} for {relative_path}")
                continue
            try:
                with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                    text = f.read()
                logging.debug(f"Read {file_path} with encoding: utf-8-sig")
            except UnicodeDecodeError as e:
                logging.warning(f"Non-UTF-8 characters in {file_path}, replaced with �: {e}")
                continue
            mod_time = get_file_mod_time(file_path)
            logging.debug(f"Collected file: {relative_path} with content_type: {content_type}")
            content.append(SandwichPack.create_block(
                content_text=text,
                content_type=content_type,
                file_name=relative_path,
                timestamp=mod_time
            ))
    for file_path in root_path.glob("*.toml"):
        if not is_hidden_file(file_path):
            relative_path = f"/{file_path.name}".replace("\\", "/")
            content_type = ".toml"
            if not SandwichPack.supported_type(content_type):
                logging.debug(f"Skipping unsupported content_type: {content_type} for {relative_path}")
                continue
            try:
                with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                    text = f.read()
                logging.debug(f"Read {file_path} with encoding: utf-8-sig")
            except UnicodeDecodeError as e:
                logging.warning(f"Non-UTF-8 characters in {file_path}, replaced with �: {e}")
                continue
            mod_time = get_file_mod_time(file_path)
            logging.debug(f"Collected file: {relative_path} with content_type: {content_type}")
            content.append(SandwichPack.create_block(
                content_text=text,
                content_type=content_type,
                file_name=relative_path,
                timestamp=mod_time
            ))
    return content

def main():
    logging.info("Starting spack CLI")
    SandwichPack.load_block_classes()
    project_dir = "."
    output_dir = "./sandwiches"
    files_content = collect_files(project_dir)
    if not files_content:
        logging.error("No files collected, exiting")
        raise SystemExit("Error: No files found in the specified directory")
    logging.info(f"Collected {len(files_content)} files")
    parser = argparse.ArgumentParser(
        prog='Sandwich Packer',
        description='Combining all project sources files into sandwich structured several text files',
        epilog='Best for using with chatbots like Grok or ChatGPT')

    parser.add_argument('project_name')
    args = parser.parse_args()
    packer = SandwichPack(args.project_name, max_size=80_000)
    result = packer.pack(files_content)
    os.makedirs(output_dir, exist_ok=True)
    for i, sandwich in enumerate(result["sandwiches"], 1):
        output_file = Path(output_dir) / f"sandwich_{i}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(sandwich)
        logging.info(f"Created {output_file} ({len(sandwich.encode('utf-8'))} bytes)")
    global_index_file = Path(output_dir) / "sandwiches_index.json"
    with open(global_index_file, "w", encoding="utf-8") as f:
        f.write(result["index"])
    global_index_file = Path(output_dir) / "sandwiches_structure.json"
    with open(global_index_file, "w", encoding="utf-8") as f:
        f.write(result["deep_index"])

    logging.info(f"Created {global_index_file}")

if __name__ == "__main__":
    main()
