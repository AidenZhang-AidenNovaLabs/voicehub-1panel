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

assert 'envKey: JWT_SECRET' not in form
assert '${JWT_SECRET}' not in compose
assert './config/jwt-secret.cjs:/app/1panel-jwt-secret.cjs:ro' in compose
command_line = next(line.strip()[2:] for line in compose.splitlines() if line.strip().startswith('- "JWT_SECRET='))
command = json.loads(command_line).replace("$$", "$")
assert command.endswith("node scripts/deploy.js\nexec node .output/server/index.mjs\n")
assert shutil.which("node") and shutil.which("sh"), "Install Node.js and Bash to run wrapper checks"
subprocess.run(["sh", "-n", "-c", command], check=True)

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    shutil.copyfile(APP / 'latest/config/jwt-secret.cjs', root / '1panel-jwt-secret.cjs')
    (root / "scripts").mkdir()
    (root / ".output" / "server").mkdir(parents=True)
    (root / "scripts" / "deploy.js").write_text(
        'process.stdout.write("deployed\\n"); process.exit(Number(process.env.FAIL_DEPLOY || 0));', encoding="utf-8"
    )
    (root / ".output" / "server" / "index.mjs").write_text(
        'console.log(JSON.stringify(process.env.DATABASE_URL));', encoding="utf-8"
    )
    env = {**os.environ, "PANEL_DB_HOST": "1Panel-postgresql-test", "PANEL_DB_PORT": "5432", "PANEL_DB_NAME": "voicehub_test", "PANEL_DB_USER": "voicehub_user"}
    env.pop('JWT_SECRET', None)
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
    secret = subprocess.run(["node", str(root / "1panel-jwt-secret.cjs")], cwd=root, capture_output=True, text=True, check=True).stdout
    assert len(secret) == 128 and (root / ".data/.jwt-secret").is_file()
    assert subprocess.run(["node", str(root / "1panel-jwt-secret.cjs")], cwd=root, capture_output=True, text=True, check=True).stdout == secret
    with tempfile.TemporaryDirectory() as other:
        independent = subprocess.run(["node", str(root / "1panel-jwt-secret.cjs")], cwd=other, capture_output=True, text=True, check=True).stdout
        assert independent != secret
    for change in ({"PANEL_DB_HOST": ""}, {"PANEL_DB_PORT": "invalid"}, {"FAIL_DEPLOY": "7"}):
        result = subprocess.run(["sh", "-ec", command], cwd=root, env={**env, **change}, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode != 0, change
        assert '"postgresql://' not in result.stdout, "Server started after prerequisite failure"
    (root / '.data/.jwt-secret').write_text('short', encoding='utf-8')
    result = subprocess.run(['sh', '-ec', command], cwd=root, env=env, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode != 0 and not result.stdout
    assert (root / '.data/.jwt-secret').read_text() == 'short'
print("OK: auto JWT generation/reuse/isolation, invalid-secret rejection, URL encoding, fail-fast startup")
