"""Environment settings take precedence over config.yaml."""
from functools import lru_cache
from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
KEYS = {
    'QDRANT_URL': ('qdrant', 'url'), 'QDRANT_COLLECTION': ('qdrant', 'collection'),
    'OLLAMA_BASE_URL': ('models', 'ollama_base_url'), 'CHAT_MODEL': ('models', 'chat_model'),
    'EMBEDDING_MODEL': ('models', 'embedding_model'), 'REQUEST_TIMEOUT': ('models', 'request_timeout'),
    'TOP_K': ('retrieval', 'top_k'), 'CHUNK_SIZE': ('chunking', 'size_chars'),
    'CHUNK_OVERLAP': ('chunking', 'overlap_chars'), 'EMBED_BATCH_SIZE': ('chunking', 'embed_batch_size'),
    'HDFS_WEB_URL': ('hdfs', 'web_url'), 'HDFS_BASE_PATH': ('hdfs', 'base_path'),
}

@lru_cache(maxsize=1)
def configuration():
    with (ROOT / 'config.yaml').open(encoding='utf-8') as file:
        return yaml.safe_load(file) or {}

def setting(name, default=None):
    if name in os.environ:
        return os.environ[name]
    value = configuration()
    for key in KEYS.get(name, ()):
        value = value.get(key) if isinstance(value, dict) else None
    return value if name in KEYS and value is not None else default
