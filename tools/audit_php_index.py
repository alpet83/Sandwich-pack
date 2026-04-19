"""One-off: compare PHP declaration counts vs Sandwich-pack ContentCodePHP entities."""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

logging.disable(logging.CRITICAL)

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lib.php_block import ContentCodePHP  # noqa: E402

# Top-level declarations (rough, on raw text — may overcount strings/comments)
RE_CLASS = re.compile(
    r"^\s*(?:"
    r"(?:abstract|final|readonly)\s+)*"
    r"class\s+[A-Za-z_]\w*",
    re.MULTILINE,
)
RE_ENUM = re.compile(r"^\s*enum\s+[A-Za-z_]\w*", re.MULTILINE)
RE_INTERFACE = re.compile(r"^\s*interface\s+[A-Za-z_]\w*", re.MULTILINE)
RE_TRAIT = re.compile(r"^\s*trait\s+[A-Za-z_]\w*", re.MULTILINE)


def iter_php_files(root: Path):
    for p in root.rglob("*.php"):
        try:
            if p.is_file():
                yield p
        except OSError:
            continue


def main() -> None:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(r"P:\opt\docker\trading-platform-php")
    if not root.is_dir():
        print("Root not found:", root)
        sys.exit(1)

    ts = "2000-01-01T00:00:00Z"
    n_files = 0
    raw_classes = raw_enums = raw_iface = raw_trait = 0
    idx_class = idx_func = idx_iface = idx_trait = idx_enum = idx_method = 0
    gap_files: list[tuple[str, dict[str, int], dict[str, int]]] = []

    for path in iter_php_files(root):
        n_files += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        r_c, r_e, r_i, r_t = (
            len(RE_CLASS.findall(text)),
            len(RE_ENUM.findall(text)),
            len(RE_INTERFACE.findall(text)),
            len(RE_TRAIT.findall(text)),
        )
        raw_classes += r_c
        raw_enums += r_e
        raw_iface += r_i
        raw_trait += r_t

        block = ContentCodePHP(
            content_text=text,
            content_type=".php",
            file_name=rel,
            timestamp=ts,
            file_id=n_files,
        )
        try:
            out = block.parse_content()
        except Exception:
            continue
        ents = out["entities"]
        ic = sum(1 for e in ents if e.get("type") == "class")
        iff = sum(1 for e in ents if e.get("type") == "function")
        ii = sum(1 for e in ents if e.get("type") == "interface")
        it = sum(1 for e in ents if e.get("type") == "trait")
        ie = sum(1 for e in ents if e.get("type") == "enum")
        im = sum(1 for e in ents if "method" in str(e.get("type", "")))
        idx_class += ic
        idx_func += iff
        idx_iface += ii
        idx_trait += it
        idx_enum += ie
        idx_method += im

        raw_total = r_c + r_e + r_i + r_t
        idx_decl = ic + ii + it + ie
        if raw_total > idx_decl + 2 or abs(r_i - ii) > 2 or abs(r_t - it) > 2 or abs(r_e - ie) > 0:
            gap_files.append(
                (
                    rel,
                    {"class": r_c, "enum": r_e, "interface": r_i, "trait": r_t},
                    {
                        "class": ic,
                        "interface": ii,
                        "trait": it,
                        "enum": ie,
                        "function": iff,
                        "method": im,
                    },
                )
            )

    print("Project root:", root)
    print("PHP files scanned:", n_files)
    print("--- Raw line matches (overapprox) ---")
    print("  class:", raw_classes)
    print("  enum:", raw_enums)
    print("  interface:", raw_iface)
    print("  trait:", raw_trait)
    print("--- Indexed entity types ---")
    print("  class:", idx_class, "interface:", idx_iface, "trait:", idx_trait, "enum:", idx_enum)
    print("  function (top-level):", idx_func, "method (incl. abstract):", idx_method)
    print("--- Files with enum/interface/trait or large class gap (sample up to 25) ---")
    shown = 0
    for rel, raw, idx in sorted(gap_files, key=lambda x: -(x[1]["enum"] + x[1]["interface"] + x[1]["trait"])):
        if shown >= 25:
            break
        print(f"  {rel} raw={raw} idx={idx}")
        shown += 1
    print("Total gap-flagged files:", len(gap_files))


if __name__ == "__main__":
    main()
