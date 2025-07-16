# /lib/sandwich_pack.py, updated 2025-07-16 14:33 EEST
import hashlib
import importlib.util
import os
import logging
import datetime
import json
import traceback
from pathlib import Path
from typing import List, Dict, Optional
from .content_block import ContentBlock

def compute_md5(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()

def estimate_tokens(content: str) -> int:
    return len(content) // 4

class SandwichPack:
    _block_classes = []

    def __init__(self, max_size: int = 80_000, system_prompt: Optional[str] = None):
        self.max_size = max_size
        self.system_prompt = system_prompt
        self.datasheet = {
            "project_root": "/app",
            "backend_address": "http://localhost:8080",
            "frontend_address": "http://vps.vpn:8008",
            "resources": {
                "database": "sqlite:///app/data/multichat.db",
                "log_file": "/app/logs/colloquium_core.log"
            }
        }
        self.busy_ids = set()

    @classmethod
    def register_block_class(cls, block_class):
        logging.debug(f"Registering block class: {block_class.__name__}")
        cls._block_classes.append(block_class)

    @classmethod
    def load_block_classes(cls):
        for module in Path(__file__).parent.glob("*_block.py"):
            module_name = module.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, module)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                logging.debug(f"Loaded module: {module_name}")
            except Exception as e:
                logging.error(f"Failed to load module {module_name}: {str(e)}")

    @classmethod
    def supported_type(cls, content_type: str) -> bool:
        for block_class in cls._block_classes:
            if content_type in block_class.supported_types:
                logging.debug(f"Supported content_type={content_type} by {block_class.__name__}")
                return True
        logging.debug(f"Content_type={content_type} falls back to ContentBlock")
        return content_type in ContentBlock.supported_types

    @classmethod
    def create_block(cls, content_text: str, content_type: str, file_name: Optional[str] = None, timestamp: Optional[str] = None, **kwargs) -> ContentBlock:
        for block_class in cls._block_classes:
            if content_type in block_class.supported_types:
                logging.debug(f"Creating block with {block_class.__name__} for content_type={content_type}")
                return block_class(content_text, content_type, file_name, timestamp, **kwargs)
        logging.debug(f"Creating default ContentBlock for content_type={content_type}")
        return ContentBlock(content_text, content_type, file_name, timestamp, **kwargs)

    def generate_unique_file_id(self) -> int:
        file_id = 0
        while file_id in self.busy_ids:
            file_id += 1
        self.busy_ids.add(file_id)
        logging.debug(f"Generated unique file_id={file_id}")
        return file_id

    def pack(self, blocks: List[ContentBlock], users: List[Dict] = None) -> Dict[str, any]:
        try:
            self.busy_ids.clear()
            file_map = {}
            file_list = []
            entity_map = {}
            entities_list = []
            name_to_locations = {}

            # Собираем занятые file_id
            for block in blocks:
                if block.content_type != ":post" and block.file_id is not None:
                    self.busy_ids.add(block.file_id)
                    logging.debug(f"Added to busy_ids: file_id={block.file_id}, file_name={block.file_name}")

            for block in blocks:
                if block.content_type != ":post" and block.file_name:
                    file_id = block.file_id if block.file_id is not None else self.generate_unique_file_id()
                    file_map[block.file_name] = file_id
                    file_list.append(f"{file_id},{block.file_name},{compute_md5(block.to_sandwich_block())},{block.tokens},{block.timestamp}")
                    logging.debug(f"Added to file_list: file_id={file_id}, file_name={block.file_name}")
                parsed = block.parse_content()
                logging.debug(f"Parsed block: content_type={block.content_type}, file_name={block.file_name}, entities={parsed['entities']}")
                if block.file_name and parsed["entities"]:
                    for ent in parsed["entities"]:
                        key = (block.file_name, ent["type"], ent["name"])
                        if key not in entity_map:
                            entity_map[key] = len(entities_list)
                            vis_short = "pub" if ent["visibility"] == "public" else "prv"
                            entities_list.append(f"{vis_short},{ent['type']},{ent['name']},{ent['tokens']}")
                            name_to_locations.setdefault(ent["name"], []).append((block.file_name, ent["type"]))

            current_size = 0
            current_tokens = 0
            current_content = []
            current_index = []
            current_file_index = 1
            sandwiches = []
            global_index = {
                "packer_version": "0.3.0",
                "context_date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ"),
                "templates": {
                    "filelist": "file_id,file_name,md5,tokens,timestamp",
                    "entities": "vis(pub/prv),type,name,tokens",
                    "users": "user_id,username,role"
                },
                "dep_format": "modules: details[:file_id] (str); imports: index (int) or details[:file_id] (str); calls: index (int)",
                "datasheet": self.datasheet,
                "files": file_list,
                "entities": entities_list,
                "users": users or [],
                "sandwiches": []
            }

            current_line = 1
            for block in blocks:
                parsed = block.parse_content()
                block_str = block.to_sandwich_block()
                block_size = len(block_str.encode("utf-8"))
                block_tokens = block.tokens
                block_lines = block_str.count("\n") + 1

                if current_size + block_size > self.max_size or current_tokens + block_tokens > 20_000:
                    sandwiches.append("".join(current_content))
                    global_index["sandwiches"].append({
                        "file": f"sandwich_{current_file_index}.txt",
                        "blocks": current_index
                    })
                    current_file_index += 1
                    current_content = []
                    current_index = []
                    current_size = 0
                    current_tokens = 0
                    current_line = 1

                block_data = {
                    "start_line": current_line
                }
                if block.content_type == ":post":
                    block_data["post_id"] = block.post_id
                    logging.debug(f"Block data for post: post_id={block.post_id}, type={type(block.post_id)}")
                else:
                    block_data["file_id"] = block.file_id if block.file_id is not None else file_map.get(block.file_name)
                    logging.debug(f"Block data for file: file_id={block_data['file_id']}, file_name={block.file_name}, type={type(block_data['file_id'])}")
                deps = parsed["dependencies"]
                if deps["imports"]:
                    block_data["imports"] = deps["imports"]
                if deps["modules"]:
                    block_data["modules"] = deps["modules"]
                if deps["calls"]:
                    block_data["calls"] = deps["calls"]
                if block.file_name and parsed["entities"]:
                    ent_uids = [entity_map[(block.file_name, e["type"], e["name"])] for e in parsed["entities"]]
                    block_data["entities"] = sorted(ent_uids)
                logging.debug(f"Appending block_data: {block_data}, entities={parsed['entities']}")
                current_content.append(block_str + "\n")
                current_index.append(block_data)
                current_size += block_size
                current_tokens += block_tokens
                current_line += block_lines

            if current_content:
                sandwiches.append("".join(current_content))
                global_index["sandwiches"].append({
                    "file": f"sandwich_{current_file_index}.txt",
                    "blocks": current_index
                })

            return {"index": json.dumps(global_index, indent=2), "sandwiches": sandwiches}
        except Exception as e:
            logging.error(f"#ERROR: Failed to pack blocks: {str(e)}")
            traceback.print_exc()
            raise