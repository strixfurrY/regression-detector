import yaml
from pathlib import Path
from .schemas import PromptConfig

def load_prompt(version: str) -> PromptConfig:
    path = Path("prompts") / f"classifier_{version}.yaml"
    return PromptConfig(**yaml.safe_load(path.read_text(encoding="utf-8")))