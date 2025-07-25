# /lib/rust_block.py, updated 2025-07-24 20:16 EEST
import re
import os
import logging
from typing import Dict
from pathlib import Path
from lib.content_block import ContentBlock
from lib.sandwich_pack import SandwichPack

class ContentCodeRust(ContentBlock):
    supported_types = [".rs"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "rustc"
        logging.debug(f"Initialized ContentCodeRust with tag={self.tag}, file_name={file_name}")

    def parse_content(self) -> Dict:
        entities = []
        dependencies = {"modules": [], "imports": [], "calls": []}
        lines = self.content_text.splitlines()
        struct_context = None
        struct_indent = None
        trait_context = None
        trait_indent = None

        # Найти структуры
        struct_pattern = re.compile(r"^(?P<indent>\s*)(?P<vis>pub\s+)?struct\s+(?P<name>\w+)(<.*?>)?\s*{",
                                   re.MULTILINE)
        for match in struct_pattern.finditer(self.content_text):
            struct_name = match.group('name')
            vis = "public" if match.group('vis') else "private"
            start_line = self.content_text[:match.start()].count('\n') + 1
            full_text = self._extract_full_entity(match.start(), match.end())
            entities.append({
                "type": "struct",
                "name": struct_name,
                "visibility": vis,
                "file_id": self.file_id,
                "line_num": start_line,
                "tokens": self._estimate_tokens(full_text)
            })
            struct_indent = len(match.group('indent'))
            struct_context = struct_name

        # Найти трейты
        trait_pattern = re.compile(r"^(?P<indent>\s*)(?P<vis>pub\s+)?trait\s+(?P<name>\w+)(<.*?>)?\s*{",
                                   re.MULTILINE)
        for match in trait_pattern.finditer(self.content_text):
            trait_name = match.group('name')
            vis = "public" if match.group('vis') else "private"
            start_line = self.content_text[:match.start()].count('\n') + 1
            full_text = self._extract_full_entity(match.start(), match.end())
            entities.append({
                "type": "trait",
                "name": trait_name,
                "visibility": vis,
                "file_id": self.file_id,
                "line_num": start_line,
                "tokens": self._estimate_tokens(full_text)
            })

        # Найти реализации трейтов
        impl_pattern = re.compile(r"^(?P<indent>\s*)(?:#\[.*?\]\s*)?(?P<vis>pub\s+)?impl\s+(?P<trait_name>\w+)\s+"
                                 r"for\s+(?P<struct_name>\w+)\s*{", re.MULTILINE)
        for match in impl_pattern.finditer(self.content_text):
            trait_name = match.group('trait_name')
            struct_name = match.group('struct_name')
            vis = "public" if match.group('vis') else "private"
            start_line = self.content_text[:match.start()].count('\n') + 1
            full_text = self._extract_full_entity(match.start(), match.end())
            line_count = full_text.count('\n') + 1
            entities.append({
                "type": "trait",
                "name": trait_name,
                "visibility": vis,
                "file_id": self.file_id,
                "line_num": start_line,
                "tokens": self._estimate_tokens(full_text)
            })
            trait_indent = len(match.group('indent'))
            trait_context = trait_name
            logging.debug(f"Parsed trait impl for {trait_name} on {struct_name} at line {start_line}")
            logging.debug(f"Trait {trait_name} spans {line_count} lines")

            # Сохранить содержимое трейта в файл
            log_dir = Path("/app/logs/rust_parse")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{trait_name}.rs"
            try:
                with log_file.open("w", encoding="utf-8") as f:
                    f.write(full_text)
                logging.debug(f"Saved trait content to {log_file}")
            except Exception as e:
                logging.error(f"Failed to save trait {trait_name} to {log_file}: {str(e)}")

            # Парсинг методов внутри impl
            impl_content = full_text
            fn_pattern = re.compile(r"^(?P<indent>\s*)(?:#\[.*?\]\s*)?(?P<vis>pub\s+)?(?:async\s+)?fn\s+"
                                   r"(?P<name>\w+)\s*\([\s\S]*?\)\s*(->\s*[\w\s:<,>\[\]]+\s*)?\s*{",
                                   re.MULTILINE)
            method_count = 0
            method_names = []
            for fn_match in fn_pattern.finditer(impl_content):
                fn_name = fn_match.group('name')
                vis = "public" if fn_match.group('vis') else "private"
                fn_start_line = start_line + impl_content[:fn_match.start()].count('\n')
                fn_full_text = self._extract_full_entity(fn_match.start(), fn_match.end(), impl_content)
                entities.append({
                    "type": "method",
                    "name": f"{trait_name}::{fn_name}",
                    "visibility": vis,
                    "file_id": self.file_id,
                    "line_num": fn_start_line,
                    "tokens": self._estimate_tokens(fn_full_text)
                })
                method_count += 1
                method_names.append(fn_name)
                logging.debug(f"Parsed method {trait_name}::{fn_name} in trait impl at line {fn_start_line}")
            logging.debug(f"Found {method_count} methods in trait {trait_name}: {', '.join(method_names)}")

        # Найти функции и методы вне impl
        fn_pattern = re.compile(r"^(?P<indent>\s*)(?:#\[.*?\]\s*)?(?P<vis>pub\s+)?(?:async\s+)?fn\s+"
                               r"(?P<name>\w+)\s*\([\s\S]*?\)\s*(->\s*[\w\s:<,>\[\]]+\s*)?\s*{",
                               re.MULTILINE)
        for match in fn_pattern.finditer(self.content_text):
            indent = len(match.group('indent'))
            fn_name = match.group('name')
            vis = "public" if match.group('vis') else "private"
            start_line = self.content_text[:match.start()].count('\n') + 1
            full_text = self._extract_full_entity(match.start(), match.end())
            # Пропустить методы, уже обработанные в impl
            if any(e["line_num"] == start_line and e["type"] == "method" for e in entities):
                continue
            ent_type = "method" if struct_context and indent > struct_indent else "function"
            name = f"{struct_context}::{fn_name}" if struct_context and ent_type == "method" else fn_name
            entities.append({
                "type": ent_type,
                "name": name,
                "visibility": vis,
                "file_id": self.file_id,
                "line_num": start_line,
                "tokens": self._estimate_tokens(full_text)
            })

        # Проверить завершение структуры или трейта
        for i, line in enumerate(lines):
            if (struct_context or trait_context) and line.strip() and not line.strip().startswith('//'):
                indent = len(line) - len(line.lstrip())
                if struct_context and indent <= struct_indent:
                    struct_context = None
                    struct_indent = None
                if trait_context and indent <= trait_indent:
                    trait_context = None
                    trait_indent = None

        module_pattern = re.compile(r"pub\s+mod\s+(\w+);")
        for match in module_pattern.finditer(self.content_text):
            module_name = match.group(1)
            module_path = f"{os.path.dirname(self.file_name)}/{module_name}/mod.rs".replace("\\", "/")
            if not module_path.startswith("/"):
                module_path = f"/{module_path}"
            dependencies["modules"].append(module_name)
        import_pattern = re.compile(r"use\s+crate::([\w:]+)(?:\{([\w,: ]+)\})?;")
        for match in import_pattern.finditer(self.content_text):
            path = match.group(1).replace("::", "/")
            if match.group(2):
                for item in match.group(2).split(","):
                    dependencies["imports"].append(item.strip())
            else:
                dependencies["imports"].append(path.split("/")[-1])
        call_pattern = re.compile(r"\b(\w+)\s*\(")
        for match in call_pattern.finditer(self.content_text):
            dependencies["calls"].append(match.group(1))
        return {"entities": entities, "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}

    def _extract_full_entity(self, start: int, end_header: int, content: str = None) -> str:
        content = content or self.content_text
        brace_count = 1
        i = end_header
        while i < len(content) and brace_count > 0:
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
            i += 1
        return content[start:i] if brace_count == 0 else content[start:end_header]

    def _estimate_tokens(self, content: str) -> int:
        return len(content) // 4

SandwichPack.register_block_class(ContentCodeRust)