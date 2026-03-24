#!/usr/bin/env python3
"""
Universal Sandwich-pack runner.

Packs any project and optionally updates .github/copilot-instructions.md.
The Sandwich-pack library is loaded from the same directory as this script,
so it works regardless of where it is called from.

Usage:
    python spack_agent.py                          # pack project in cwd
    python spack_agent.py --project /path/to/proj  # pack specific project
    python spack_agent.py --pack-only              # pack only, skip instructions update
    python spack_agent.py --update-only            # update instructions from existing index
    python spack_agent.py --project-name myproj    # override project name (default: dir name)
    python spack_agent.py --instructions /path/to/copilot-instructions.md
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
# The lib/ directory lives beside this script — no hardcoded absolute paths.
SPACK_LIB = Path(__file__).parent

SPACK_FILES_BEGIN    = "<!-- SPACK:files:begin -->"
SPACK_FILES_END      = "<!-- SPACK:files:end -->"
SPACK_ENTITIES_BEGIN = "<!-- SPACK:entities:begin -->"
SPACK_ENTITIES_END   = "<!-- SPACK:entities:end -->"

logging.basicConfig(level=logging.INFO, format="%(asctime)s #%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── Packing ───────────────────────────────────────────────────────────────────

def run_pack(project_root: Path, project_name: str) -> str:
    sys.path.insert(0, str(SPACK_LIB))
    from lib.sandwich_pack import SandwichPack  # type: ignore[import]

    output_dir = project_root / "sandwiches"
    index_file = output_dir / "sandwiches_index.jsl"

    def get_file_mod_time(file_path):
        import datetime
        mtime = os.path.getmtime(file_path)
        mod_time = datetime.datetime.fromtimestamp(mtime, datetime.UTC)
        return mod_time.strftime("%Y-%m-%d %H:%M:%SZ")

    SKIP_DIRS = {"node_modules", ".nuxt", ".output", "dist", "sandwiches", ".git", "coverage"}

    log.info(f"Scanning {project_root} ...")
    SandwichPack.load_block_classes()
    blocks = []

    for file_path in project_root.rglob("*"):
        if not file_path.is_file():
            continue
        rel_parts = file_path.relative_to(project_root).parts
        if any(p.startswith(".") or p in SKIP_DIRS for p in rel_parts):
            continue

        ext = file_path.suffix.lower()
        if not ext or not SandwichPack.supported_type(ext):
            continue

        relative_path = "/" + str(file_path.relative_to(project_root.parent)).replace("\\", "/")
        try:
            text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception as e:
            log.warning(f"Skip {file_path}: {e}")
            continue

        blocks.append(SandwichPack.create_block(
            content_text=text,
            content_type=ext,
            file_name=relative_path,
            timestamp=get_file_mod_time(file_path),
        ))

    log.info(f"Collected {len(blocks)} files")
    if not blocks:
        log.error("No files collected, aborting")
        sys.exit(1)

    packer = SandwichPack(project_name)
    result = packer.pack(blocks)

    output_dir.mkdir(exist_ok=True)
    for i, sandwich in enumerate(result["sandwiches"], 1):
        out = output_dir / f"sandwich_{i}.txt"
        out.write_text(sandwich + "\nINDEX_COPY:\n" + result["index"], encoding="utf-8")
        log.info(f"  sandwich_{i}.txt  ({len(sandwich.encode())} bytes)")

    index_file.write_text(result["index"] + "STRUCTURE: " + result["deep_index"], encoding="utf-8")
    (output_dir / "sandwiches_structure.json").write_text(result["deep_index"], encoding="utf-8")
    log.info(f"Index: {index_file}  ({index_file.stat().st_size} bytes)")

    return result["index"]


# ── Instructions update ───────────────────────────────────────────────────────

def load_index_from_file(project_root: Path) -> str:
    index_file = project_root / "sandwiches" / "sandwiches_index.jsl"
    if not index_file.exists():
        log.error(f"Index not found: {index_file}")
        sys.exit(1)
    raw = index_file.read_text(encoding="utf-8")
    return raw.split("STRUCTURE:")[0].strip()


def build_instructions_sections(index_json: str) -> tuple[str, str]:
    """Return (files_section, entities_section) as markdown tables."""
    try:
        idx = json.loads(index_json)
    except json.JSONDecodeError as e:
        log.error(f"Cannot parse index JSON: {e}")
        return ("*(parse error)*", "*(parse error)*")

    files: list[str] = idx.get("files", [])
    entities: list[str] = idx.get("entities", [])
    context_date: str = idx.get("context_date", "")

    # ── files table ──────────────────────────────────────────────────────────
    lines_files = [
        f"*Generated: {context_date} — {len(files)} files*",
        "",
        "| # | file | tokens | updated |",
        "|---|------|--------|---------|",
    ]
    for entry in files:
        parts = entry.split(",")
        if len(parts) >= 5:
            fid, name, _md5, tokens, ts = parts[0], parts[1], parts[2], parts[3], parts[4]
            lines_files.append(f"| {fid} | `{name}` | {tokens} | {ts} |")

    # ── entities table ────────────────────────────────────────────────────────
    from collections import defaultdict
    by_file: dict[int, list[str]] = defaultdict(list)
    for e in entities:
        parts = e.split(",")
        if len(parts) >= 6:
            try:
                fid = int(parts[4])
                by_file[fid].append(e)
            except ValueError:
                pass

    fid_to_name: dict[int, str] = {}
    for entry in files:
        parts = entry.split(",")
        if len(parts) >= 2:
            try:
                fid_to_name[int(parts[0])] = parts[1]
            except ValueError:
                pass

    lines_ent = [
        f"*{len(entities)} entities across {len(by_file)} files*",
        "",
    ]
    for fid in sorted(by_file.keys()):
        fname = fid_to_name.get(fid, f"file_{fid}")
        lines_ent.append(f"**`{fname}`**")
        lines_ent.append("")
        lines_ent.append("| vis | type | parent | name | lines | tokens |")
        lines_ent.append("|-----|------|--------|------|-------|--------|")
        for e in by_file[fid]:
            p = e.split(",")
            if len(p) >= 7:
                vis, etype, parent, name, _fid, lines, tokens = p[0], p[1], p[2], p[3], p[4], p[5], p[6]
                lines_ent.append(f"| {vis} | {etype} | {parent} | `{name}` | {lines} | {tokens} |")
        lines_ent.append("")

    return "\n".join(lines_files), "\n".join(lines_ent)


def inject_section(content: str, begin_marker: str, end_marker: str, new_body: str) -> str:
    """Replace content between markers. Markers themselves are preserved."""
    start = content.find(begin_marker)
    end   = content.find(end_marker)
    if start == -1 or end == -1:
        log.warning(f"Marker not found in instructions: {begin_marker!r}")
        return content
    before = content[: start + len(begin_marker)]
    after  = content[end:]
    return before + "\n" + new_body + "\n" + after


def update_instructions(index_json: str, instructions_path: Path) -> None:
    if not instructions_path.exists():
        log.warning(f"copilot-instructions.md not found: {instructions_path}")
        return

    content = instructions_path.read_text(encoding="utf-8")
    files_section, entities_section = build_instructions_sections(index_json)
    content = inject_section(content, SPACK_FILES_BEGIN,    SPACK_FILES_END,    files_section)
    content = inject_section(content, SPACK_ENTITIES_BEGIN, SPACK_ENTITIES_END, entities_section)
    instructions_path.write_text(content, encoding="utf-8")
    log.info(f"Updated {instructions_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sandwich-pack universal runner — pack any project and update instructions",
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help="Root directory of the project to pack (default: current working directory)",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Project name used in pack metadata (default: project directory name)",
    )
    parser.add_argument(
        "--instructions",
        type=Path,
        default=None,
        help="Path to copilot-instructions.md (default: <project>/.github/copilot-instructions.md)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pack-only",   action="store_true",
                       help="Pack only, skip instructions update")
    group.add_argument("--update-only", action="store_true",
                       help="Update instructions from existing index, skip packing")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = (args.project or Path.cwd()).resolve()
    project_name = args.project_name or project_root.name
    instructions = (
        args.instructions or project_root / ".github" / "copilot-instructions.md"
    ).resolve()

    if args.update_only:
        index_json = load_index_from_file(project_root)
        update_instructions(index_json, instructions)
        return

    index_json = run_pack(project_root, project_name)

    if not args.pack_only:
        update_instructions(index_json, instructions)


if __name__ == "__main__":
    main()
