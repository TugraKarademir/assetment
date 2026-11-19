import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)  # yapılandırma göreli yollarla okunur
os.environ["SCORING_ITEMS"] = "config/items.yaml"  # birim testleri sentetik 4 soruluk rubrikle çalışır
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def fernet_key():
    from scoring.anonymize import generate_key
    return generate_key()


@pytest.fixture
def bank():
    from scoring.config import load_items
    return load_items()
