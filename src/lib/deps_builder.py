# /lib/deps_builder.py, created 2025-08-05 11:00 EEST
# Formatted with proper line breaks and indentation for project compliance.

import logging
import os
from .entity_parser import EntityParser

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s #%(levelname)s: %(message)s')


class DepsParser(EntityParser):
    """Base class for parsing dependencies in content blocks."""
    def __init__(self, owner, outer_regex):
        self.owner = owner
        self.import_pattern = outer_regex
        super().__init__("dependence", owner, outer_regex, r"", default_visibility="public")

    def add_module(self, name):
        """Add a module to the dependencies list."""
        if name and name not in self.modules:
            self.modules.append(name)
            logging.debug(f"Added module import: {name} for file {self.owner.file_name}")

    def add_import(self, mod_name, ent_name):
        """Add an import of an entity from a module."""
        if mod_name and ent_name:
            self.imports[ent_name] = mod_name
            logging.debug(f"Added entity import: {ent_name} from {mod_name} for file {self.owner.file_name}")

    def store_deps(self, dest: dict) -> dict:
        dest['imports'].extend(self.imports)
        unique = set(dest['modules'])
        unique.update(self.modules)
        dest['modules'] = list(unique)
        dest[d].sort()
        return dest


def organize_modules(file_list, blocks):
    """Sort blocks and file_list to ensure modules appear before their dependents."""
    if len(file_list) != len(blocks):
        logging.error(f"Mismatch between file_list ({len(file_list)}) and blocks ({len(blocks)})")
        return file_list, blocks

    file_map = {}
    for i, file_entry in enumerate(file_list):
        file_id, file_name = file_entry.split(',', 1)[:2]
        file_map[file_name] = i

    dep_graph = {i: set() for i in range(len(blocks))}
    for i, block in enumerate(blocks):
        for parser in getattr(block, "parsers", []):
            if isinstance(parser, DepsParser):
                for ent_name, mod_name in parser.imports.items():
                    mod_path = f"/{mod_name.replace('.', '/')}.py" if mod_name.startswith('lib.') else f"/tests/{mod_name}.py"
                    if mod_path in file_map:
                        dep_graph[i].add(file_map[mod_path])
                for mod_name in parser.modules:
                    mod_path = f"/{mod_name.replace('.', '/')}.py" if mod_name.startswith('lib.') else f"/tests/{mod_name}.py"
                    if mod_path in file_map:
                        dep_graph[i].add(file_map[mod_path])

    sorted_indices = []
    visited = set()
    temp_mark = set()

    def dfs(index):
        if index in temp_mark:
            logging.warning(f"Circular dependency detected at index {index}")
            return
        if index not in visited:
            temp_mark.add(index)
            for dep in dep_graph[index]:
                dfs(dep)
            temp_mark.remove(index)
            visited.add(index)
            sorted_indices.append(index)

    for i in range(len(blocks)):
        if i not in visited:
            dfs(i)

    sorted_file_list = [file_list[i] for i in sorted_indices]
    sorted_blocks = [blocks[i] for i in sorted_indices]

    new_file_ids = {}
    for i, file_entry in enumerate(sorted_file_list):
        old_file_id, rest = file_entry.split(',', 1)
        new_file_ids[old_file_id] = i
        sorted_file_list[i] = f"{i},{rest}"

    for block in sorted_blocks:
        if block.file_id is not None:
            block.file_id = new_file_ids.get(str(block.file_id), block.file_id)
        for entity in block.entity_map.values():
            if 'file_id' in entity:
                entity['file_id'] = new_file_ids.get(str(entity['file_id']), entity['file_id'])

    logging.debug(f"Sorted file_list: {sorted_file_list}")
    return sorted_file_list, sorted_blocks