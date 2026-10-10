#!/usr/bin/env python3
"""Check the package and run its URL/startup wrapper without Docker."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
APP = ROOT / "apps" / "voicehub"
compose = (APP / "latest" / "docker-compose.yml").read_text(encoding="utf-8")
form = (APP / "latest" / "data.yml").read_text(encoding="utf-8")
assert re.findall(r"^  (\w+):$", compose, re.M) == ["voicehub"]
assert "image: ghcr.io/laoshuikaixue/voicehub:latest" in compose
assert "    pull_policy: always" in compose
assert 'container_name: "${CONTAINER_NAME}"' in compose
assert '"${PANEL_APP_PORT_HTTP}:3000"' in compose
assert "external: true" in compose and "createdBy: Apps" in compose
assert "./data:/app/.data" in compose and "./backups:/app/backups" in compose
assert "depends_on:" not in compose and "privileged:" not in compose
assert "docker.sock" not in compose and "5432:5432" not in compose
assert form.count("envKey: PANEL_DB_HOST") == 1
assert re.search(r"- child:\n\s+default:.*\n\s+envKey: PANEL_DB_HOST\n\s+required: true\n\s+type: service", form)
assert "type: apps" in form
assert re.findall(r"value: (\w+)", form) == ["postgresql"]
declared = set(re.findall(r"envKey: (\w+)", form))
referenced = set(re.findall(r"\$\{(\w+)\}", compose))
assert referenced - declared == {"CONTAINER_NAME", "PANEL_DB_PORT"}
for directory in ("data", "backups"):
    assert (APP / "latest" / directory / ".gitkeep").is_file()
assert not (APP / "latest" / "scripts").exists()
logo = (APP / "logo.png").read_bytes()
assert logo.startswith(b"\x89PNG\r\n\x1a\n") and len(logo) > 1000

command_line = next(line.strip()[2:] for line in compose.splitlines() if line.strip().startswith('- "DATABASE_URL='))
command = json.loads(command_line).replace("$$", "$")
assert command.endswith("node scripts/deploy.js\nexec node .output/server/index.mjs\n")
assert shutil.which("node") and shutil.which("sh"), "Install Node.js and Bash to run wrapper checks"
subprocess.run(["sh", "-n", "-c", command], check=True)

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root / "scripts").mkdir()
    (root / ".output" / "server").mkdir(parents=True)
    (root / "scripts" / "deploy.js").write_text(
        'process.stdout.write("deployed\\n"); process.exit(Number(process.env.FAIL_DEPLOY || 0));', encoding="utf-8"
    )
    (root / ".output" / "server" / "index.mjs").write_text(
        'console.log(JSON.stringify(process.env.DATABASE_URL));', encoding="utf-8"
    )
    env = {**os.environ, "PANEL_DB_HOST": "1Panel-postgresql-test", "PANEL_DB_PORT": "5432", "PANEL_DB_NAME": "voicehub_test", "PANEL_DB_USER": "voicehub_user", "JWT_SECRET": "0123456789abcdef" * 4}
    for password in ("simple", "a%40b", "p@ss:word/#?% 中文", "quote'\"$`\\!", "line\nbreak"):
        env["PANEL_DB_USER_PASSWORD"] = password
        result = subprocess.run(["sh", "-ec", command], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", check=True)
        lines = result.stdout.splitlines()
        assert lines[0] == "deployed", lines
        url = urlsplit(json.loads(lines[1]))
        assert url.scheme == "postgresql" and url.hostname == env["PANEL_DB_HOST"].lower()
        assert url.port == 5432
        assert unquote(url.username) == env["PANEL_DB_USER"]
        assert unquote(url.password) == password
        assert unquote(url.path[1:]) == env["PANEL_DB_NAME"]
        assert parse_qs(url.query) == {"sslmode": ["disable"]}
    for change in ({"JWT_SECRET": "short"}, {"PANEL_DB_HOST": ""}, {"PANEL_DB_PORT": "invalid"}, {"FAIL_DEPLOY": "7"}):
        result = subprocess.run(["sh", "-ec", command], cwd=root, env={**env, **change}, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode != 0, change
        assert '"postgresql://' not in result.stdout, "Server started after prerequisite failure"
print("OK: one container, PostgreSQL selector, rolling pull, persistence, URL encoding, fail-fast startup")
