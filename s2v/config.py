from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load(path: str | Path | None = None) -> dict:
    with open(path or ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
