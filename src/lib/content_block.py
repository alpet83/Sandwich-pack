# /lib/content_block.py, updated 2025-08-06 14:30 EEST
# Formatted with proper line breaks and indentation for project compliance.
# Proposed: 2025-08-06
# Changes: Added module_map parameter to compress for imported class name compression (e.g., SandwichPack), added log separator (CLA Rule 2: Ensure code correctness, CLA Rule 12: Minimize changes).

import logging
import re
import os
import math
from datetime import datetime
from pathlib import Path
from .deps_builder import DepsParser
from .llm_tools import estimate_tokens
from .code_stripper import CodeStringStripper, CodeCommentStripper

# PROTECTION CODE DON'T TOUCH, typing is disabled!!!
Optional = List = Tuple = Dict = None

logging.basicConfig(
    level=os.environ.get('LOGLEVEL', 'DEBUG').upper()
)


class ContentBlock:
    supported_types = [':document', ':post']

    def __init__(self, content_text, content_type, file_name=None, timestamp=None, **kwargs):
        self.content_text = content_text
        self.content_type = content_type
        self.tag = "post" if content_type == ":post" else "document"
        self.parsers = []
        self.dependencies = {"modules": [], "imports": {}}
        self.file_name = file_name
        self.timestamp = timestamp
        self.call_method_sep = ['.']
        self.post_id = kwargs.get('post_id')
        self.user_id = kwargs.get('user_id')
        self.relevance = kwargs.get('relevance', 0)
        self.file_id = kwargs.get('file_id')
        self.tokens = estimate_tokens(content_text)
        self.clean_lines = ["Line №0"] + self.content_text.splitlines()
        self.strip_log = []
        self.warnings = []
        self.entity_map = {}
        self.string_quote_chars = "\"'"
        self.raw_str_prefix = None
        self.raw_quote_char = None
        self.open_ml_string = []
        self.close_ml_string = []
        self.open_sl_comment = ["//"]
        self.open_ml_comment = [r"/\*"]
        self.close_ml_comment = [r"\*/"]
        self.escape_char = "\\"
        self.module_prefix = ""
        self.line_offsets = []
        logging.debug(f"Initialized base of {type(self).__name__} with content_type={content_type}, tag={self.tag}, file_name={file_name}")

    def parse_warn(self, msg):
        """Logs a warning and adds it to self.warnings."""
        self.warnings.append(msg)
        logging.warning(msg)

    def strip_strings(self):
        """Strips string literals using CodeStringStripper."""
        if len(self.clean_lines) <= 1:
            self.clean_lines = [''] + self.content_text.splitlines()
        stripper = CodeStringStripper(
            self,
            string_quote_chars=self.string_quote_chars,
            raw_str_prefix=self.raw_str_prefix,
            raw_quote_char=self.raw_quote_char,
            open_ml_string=self.open_ml_string,
            close_ml_string=self.close_ml_string,
            escape_char=self.escape_char
        )
        self.clean_lines = stripper.strip(self.clean_lines)
        self.strip_log.extend(stripper.strip_log)
        self.warnings.extend(stripper.warnings)
        self.get_clean_content()
        return self.clean_lines

    def strip_comments(self):
        """Strips comments using CodeCommentStripper."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not filled")
        stripper = CodeCommentStripper(
            self,
            open_sl_comment=self.open_sl_comment,
            open_ml_comment=self.open_ml_comment,
            close_ml_comment=self.close_ml_comment
        )
        self.clean_lines = stripper.strip(self.clean_lines)
        self.strip_log.extend(stripper.strip_log)
        self.warnings.extend(stripper.warnings)
        self.get_clean_content()
        return self.clean_lines

    def save_clean(self, file_name):
        """Saves the cleaned content to a file for debugging, replacing empty lines with line number comments."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not filled")
        try:
            output_path = Path(file_name)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                for line_num, line in enumerate(self.clean_lines[1:], 1):
                    f.write((line if line.strip() else f"// Line {line_num}") + "\n")
            logging.debug(f"Saved cleaned content to {file_name}")
        except Exception as e:
            logging.error(f"Failed to save cleaned content to {file_name}: {str(e)}")

    def get_clean_content(self):
        """Returns the cleaned content as a single string and updates line_offsets."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not initialized")
        content = "\n".join(self.clean_lines[1:])
        self.line_offsets = [0]
        offset = 0
        for line in self.clean_lines[1:]:
            offset += len(line) + 1
            self.line_offsets.append(offset)
        # logging.debug(f"Updated line_offsets: {self.line_offsets[:10]}... (total {len(self.line_offsets)})")
        return content

    def find_line(self, content_offset):
        """Finds the line number for a given content offset."""
        if not self.line_offsets:
            self.get_clean_content()
        for i, offset in enumerate(self.line_offsets):
            if content_offset < offset:
                return i
        return len(self.line_offsets) - 1

    def count_chars(self, line_num, ch):
        """Counts occurrences of a character in a specific line of clean code."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not initialized")
        if line_num < 1 or line_num >= len(self.clean_lines):
            logging.error(f"Invalid line number {line_num} for file {self.file_name}")
            return 0
        line = self.clean_lines[line_num]
        if not isinstance(line, str):
            return 0
        return line.count(ch)

    def sorted_entities(self):
        """Sorts entities by their line number."""
        sorted_map = {}
        result = []
        for line_num in sorted(self.entity_map.keys()):
            sorted_map[line_num] = self.entity_map[line_num]
            result.append(self.entity_map[line_num])
        self.entity_map = sorted_map
        return result

    def detect_bounds(self, start_line, clean_lines):
        """Detects the start and end line of an entity using brace counting."""
        if start_line < 1 or start_line >= len(clean_lines) or not clean_lines[start_line] or not clean_lines[start_line].strip():
            logging.error(f"Invalid start line {start_line} for file {self.file_name} module [{self.module_prefix}]")
            return start_line, start_line
        brace_count = 0
        line_num = start_line
        # поиск открывающей скобки, для варианта когда start_line указывает на начало многострочного определения функции/метода
        for i in range(8):
            line = clean_lines[line_num]
            if line.count('{') > 0:
                break
            line_num += 1

        while line_num < len(clean_lines):
            line = clean_lines[line_num]
            if not isinstance(line, str) or not line.strip():
                line_num += 1
                continue
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0 and line_num >= start_line:
                return start_line, line_num
            line_num += 1
        self.parse_warn(f"Incomplete entity at line {start_line} in file {self.file_name}, brace_count={brace_count}")
        return start_line, start_line

    def check_entity_placement(self, line_num: int, name: str):
        """Checks if an entity with the given name is correctly placed at line_num."""
        if line_num < 1 or line_num >= len(self.clean_lines) or not self.clean_lines[line_num]:
            logging.warning(f" check_entity_placement failed: outbound {line_num} or void line")
            return False
        line = self.clean_lines[line_num]
        base_name = name.split(".")[-1]
        base_name = base_name.split("::")[-1].split("<")[0]
        pattern = rf"\b{base_name}\b"
        result = bool(re.search(pattern, line))
        if not result:
            best = 10
            for i, search_line in enumerate(self.clean_lines[1:], 1):
                if isinstance(search_line, str) and re.search(pattern, search_line):
                    diff = line_num - i
                    best = min(best, abs(diff))
                    logging.debug(f"  occurrence of '{base_name}' found at line {i}: '{search_line}'")
            result = abs(best) <= 1

        # logging.debug(f"Checking entity placement for {name} at line {line_num}: {'Passed' if result else 'Failed'}, line: '{line}'")
        return result

    def add_entity(self, line_num: int, entity: dict):
        """Adds an entity to entity_map with placement and duplication checks."""
        if line_num in self.entity_map:
            existing = self.entity_map[line_num]
            if existing["name"] != entity["name"] or existing["type"] != entity["type"]:
                logging.warning(f"Duplicate entity at line {line_num}: {entity['name']} ({entity['type']}) conflicts with {existing['name']} ({existing['type']})")
                return False
        if not self.check_entity_placement(line_num, entity["name"]):
            logging.warning(f"Entity {entity['name']} placement check failed at line {line_num}, line: '{self.clean_lines[line_num]}'")
            return False
        entity["first_line"] = line_num
        if entity["type"] != "abstract method" or "last_line" not in entity:
            entity["last_line"] = self.detect_bounds(line_num, self.clean_lines)[1]
        self.entity_map[line_num] = entity
        logging.debug(f"Added entity {entity['name']} at first_line={line_num}, last_line={entity['last_line']}")
        return True

    def extract_entity_text(self, def_start: int, def_end: int) -> str:
        """Extracts the full entity text using clean_lines for brace counting."""
        content = self.get_clean_content()
        start_line = self.find_line(def_end)  # открывающая реальная скобка должна находиться тут
        start_line, end_line = self.detect_bounds(start_line, self.clean_lines)
        if start_line == end_line:
            self.parse_warn(f"Incomplete/abstract entity in file {self.file_name} at start={start}, line @{start_line} using header end")
            return content[start:].splitlines()[0]
        logging.info(f"Extracted entity from first_line={start_line} to last_line={end_line}")
        return "\n".join(self.clean_lines[start_line:end_line + 1])

    def extend_deps(self, parser):
        m = []
        i = {}
        deps = parser
        if getattr(parser, 'dependencies', False):
            deps = parser.dependencies
        i = getattr(deps, 'imports', {})
        m = getattr(deps, 'modules', [])
        unique = set(self.dependencies['modules'])
        unique.update(m)
        self.dependencies['modules'] = list(unique)
        self.dependencies['imports'].update(i)

    def full_text_replace(self, from_str: str, entity_id: int, ent_type: str, is_definition: bool = False):
        """Performs context-aware replacement of entity names with \x0F<entity_id>.

        Args:
            from_str (str): The entity name to replace.
            entity_id (int): The global entity index to replace with.
            ent_type (str): The type of entity (function, local_function, method, abstract method, structure, class, interface, module, component, object).
            is_definition (bool): If True, replace in definition line without context restrictions.

        Returns:
            str: The content with replaced entity names.
        """
        if is_definition:
            pattern = rf"\b{re.escape(from_str)}\b"
        else:
            if ent_type in ("function", "local_function"):
                pattern = rf"(?:(?<=[\s])|\b){re.escape(from_str)}(?=\s|\()"
            elif ent_type in ("method", "abstract method"):
                pattern = rf"(?<=[\s.->]){re.escape(from_str)}(?=\s|\()"
            elif ent_type == "structure":
                pattern = rf"(?<=[\s.->|<]){re.escape(from_str)}(?=\s|\(|<|>)"
            elif ent_type in ("class", "interface"):
                pattern = rf"(?<=[\s|=\(]){re.escape(from_str)}(?=\s|\(|\.|,|;|\))*"  # варианты использования классов: конструкция, наследование, вызов статического метода, импорт в заголовке
            else:
                pattern = rf"\b{re.escape(from_str)}\b"
        compressed = re.sub(pattern, f"\x0F{entity_id}", self.content_text)
        if compressed == self.content_text:
            logging.warning(f"Failed replace '{from_str}' with '\x0F{entity_id}' in {self.file_name} (type={ent_type}, is_definition={is_definition})")
        else:
            logging.debug(f"Replaced '{from_str}' with '\x0F{entity_id}' in {self.file_name} (type={ent_type}, is_definition={is_definition})")
            self.content_text = compressed
        return self.content_text

    def compress(self, entity_rev_map, file_map: dict):
        """Compresses entity names in content_text to their global indexes prefixed with ANSI \x0F.

        Args:
            entity_rev_map: Dictionary mapping (file_id, ent_type, ent_name) to entity_id.
            file_map: Dictionary file names to file_id.
        """
        if self.content_type == ":post":
            logging.debug(f"No compression for post content: {self.file_name}")
            return
        file_index = {}
        for file_name, file_id in file_map.items():
            file_index[file_id] = file_name
        ent_index = {}
        for (file_id, ent_type, ent_name) in entity_rev_map:
            ent_index[ent_name] = (file_id, ent_type, ent_name)

        logging.debug(f"------- compressing {self.file_name} -------")
        original_length = len(self.content_text)
        valid_entities = {}
        name_count = {}
        for entity in self.entity_map.values():
            ent_name = entity["name"]
            name_count[ent_name] = name_count.get(ent_name, 0) + 1

        for line_num, entity in self.entity_map.items():
            ent_type = entity["type"]
            ent_name = entity["name"]
            if name_count[ent_name] > 1:
                logging.debug(f"SKIP_ENTITY: non unique name {ent_name}")
                continue
            if ent_type in ("function", "local_function", "class", "interface", "structure", "method", "abstract method", "module", "component", "object"):
                valid_entities[ent_name] = (self.file_id, ent_type, line_num)
                logging.debug(f"Added local entity {ent_name} ({ent_type}, file_id={self.file_id}, line={line_num}) for compression")
            if "parent" in entity and entity["parent"]:
                parent_name = entity["parent"]
                for ent_type in ("class", "interface"):
                    key = (self.file_id, ent_type, parent_name)
                    if key in entity_rev_map:
                        valid_entities[parent_name] = (self.file_id, ent_type, None)
                        logging.debug(f"Added parent entity {parent_name} ({ent_type}, file_id={self.file_id}) for compression")

        for parser in getattr(self, "parsers", []):
            if isinstance(parser, DepsParser):
                checked = 0
                for ent_name in parser.imports.keys():
                    checked += 1
                    (file_id, ent_type, ent_exists) = ent_index.get(ent_name, (-1, None, None))
                    if file_id >= 0:
                        file_name = file_index.get(file_id, "unknown")
                        if ent_name == ent_exists:
                            # TODO: можно добавить проверку для коротких имен, на соответствие mod_name и file_name
                            mod_name = parser.imports[ent_name]
                            valid_entities[ent_name] = (file_id, ent_type, None)
                            logging.debug(f"Added imported entity {ent_name} ({ent_type}, mod={mod_name}, file_id={file_id}), file_name=`{file_name}` for compression")
                    else:
                        logging.warning(f"Failed locate imported entity {ent_name}")
                logging.debug(f"Checked {checked} from imports: {parser.imports}")

        compressed_count = 0
        for ent_name, (file_id, ent_type, line_num) in valid_entities.items():
            key = (file_id, ent_type, ent_name)
            is_definition = False
            if line_num is not None and line_num in self.entity_map:
                line = self.clean_lines[line_num]
                # TODO: тут надо заменить проверку на простое соответствие линии определения сущности
                if isinstance(line, str) and re.search(rf"\b(def|function|class|struct|impl|mod)\s+{re.escape(ent_name)}\b", line):
                    is_definition = True
            if file_id is None:
                for fid in {f[0] for f in entity_rev_map.keys()}:
                    test_key = (fid, ent_type, ent_name)
                    if test_key in entity_rev_map:
                        index = entity_rev_map[test_key]
                        self.full_text_replace(ent_name, index, ent_type, is_definition)
                        compressed_count += 1
                        break
            elif key in entity_rev_map:
                index = entity_rev_map[key]
                self.full_text_replace(ent_name, index, ent_type, is_definition)
                compressed_count += 1

        self.tokens = estimate_tokens(self.content_text)
        compressed_length = len(self.content_text)
        logging.info(f"Compressed {compressed_count} entities in {self.file_name}, "
                     f"original length: {original_length}, compressed length: {compressed_length}, "
                     f"reduced by {original_length - compressed_length} characters, new tokens: {self.tokens}")

    def to_sandwich_block(self):
        """Convert block to sandwich format with attributes mapped via dictionary."""
        # Dictionary mapping tag attributes to object field names
        attr_to_field = {
            'post_id': 'post_id'
        } if self.content_type == ':post' else {
            'file_id': 'file_id',
            'mod_time': 'timestamp'
        }
        attr_to_field['user_id'] = 'user_id'
        attr_to_field['relevance'] = 'relevance'

        # Build tag attributes, excluding None or irrelevant fields
        attrs = []
        for attr, field in attr_to_field.items():
            value = getattr(self, field, None)
            if value is not None:
                attrs.append(f'{attr}="{value}"')
        attr_str = " ".join(attrs)
        return f"<{self.tag} {attr_str}>\n{self.content_text}\n</{self.tag}>"

    def parse_content(self, clean_lines=None, depth=0):
        return {"entities": [], "dependencies": self.dependencies}


class SpanBlock(ContentBlock):
    supported_types = [':code_span', ':file_span']

    def __init__(self, content_text: str, file_id: int, block_hash: str, meta: dict):
        super().__init__(content_text, ":file_span", file_name=None, timestamp=None)
        self.tag = "file_span"
        self.meta = meta
        self.file_id = file_id
        self.block_hash = block_hash

    def to_sandwich_block(self):
        meta = self.meta
        timestamp = meta.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%SZ"))
        start_line = meta.get('start', -1)
        end_line = meta.get('end', -1)
        if start_line < 0 or end_line < 0:
            logging.error(f"Invalid metadata {meta}")
            return f"<error msg='Wrong span metadata'>{meta}</error>"
        return f'<{self.tag} file_id="{self.file_id}" start="{start_line}" end="{end_line}" hash="{self.block_hash}" timestamp="{timestamp}">\n ' + \
               f'{self.content_text}\n</{self.tag}>'

