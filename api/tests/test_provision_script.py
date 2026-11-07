import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]


def test_running_without_a_customer_id_prints_usage_instead_of_crashing():
    r = subprocess.run([sys.executable, "-m", "scripts.provision"], cwd=API_DIR, capture_output=True, text=True, timeout=60)
    assert r.returncode == 1
    assert "usage: python -m scripts.provision <customer_id>" in r.stderr
    assert "Traceback" not in r.stderr
