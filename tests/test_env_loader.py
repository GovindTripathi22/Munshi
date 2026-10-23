# tests/test_env_loader.py
from pathlib import Path
from munshi.config import load_env_file, MunshiConfig

def test_env_example_parses_with_app_loader():
    example_path = Path(__file__).resolve().parent.parent / ".env.example"
    assert example_path.exists()

    parsed = load_env_file(example_path)
    assert "COMPANY_NAME" in parsed
    assert "HOME_STATE_CODE" in parsed
    assert "HIGH_VALUE_THRESHOLD" in parsed
    assert parsed["HOME_STATE_CODE"] == "27"
    assert float(parsed["HIGH_VALUE_THRESHOLD"]) == 50000.00
