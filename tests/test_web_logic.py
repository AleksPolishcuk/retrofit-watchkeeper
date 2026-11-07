"""The review log logic of the cockpit (web/src/reviews.ts) runs under Node's own test runner; this makes `make test` cover it."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "web"


def node_version():
    node = shutil.which("node")
    if not node:
        return None
    m = re.match(r"v(\d+)\.(\d+)", subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


@pytest.mark.skipif((node_version() or (0, 0)) < (22, 18), reason="needs Node 22.18 or newer (strips TypeScript types itself)")
def test_review_log_logic_passes_under_node():
    r = subprocess.run(["node", "--test", "tests/*.test.ts"], cwd=WEB, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
    assert re.search(r"# pass \d+", r.stdout) and "# fail 0" in r.stdout
