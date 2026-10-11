from pathlib import Path
import shutil
import subprocess
import pytest


def test_frontend_terminal_and_network_error_states():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for frontend unit test")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, str(root / "tests/frontend_error_state.cjs"),
                             str(root / "NV15-Agentic-AI/frontend/app.js")],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    assert "scenarios passed" in result.stdout
