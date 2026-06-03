import re
import subprocess
from pathlib import Path


SECRET_PATTERNS = [
    re.compile(r'FRED_API_KEY\s*=\s*["\'][0-9a-f]{32}["\']'),
    re.compile(r'FRED_API_KEY:\s*["\'][0-9a-f]{32}["\']'),
    re.compile(r'FREDConnector\(api_key=["\'][0-9a-f]{32}["\']\)'),
    re.compile(r'EXCHANGERATE_API_KEY:\s*["\'][0-9a-f]{32}["\']'),
]


def test_tracked_files_do_not_embed_fred_api_keys():
    root = Path(__file__).resolve().parents[3]
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    offenders = []
    for rel_path in tracked:
        path = root / rel_path
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                offenders.append(rel_path)
                break

    assert offenders == []
