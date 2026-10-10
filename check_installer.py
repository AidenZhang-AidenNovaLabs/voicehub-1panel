#!/usr/bin/env python3
"""Check installer syntax, security guards, text UI and rollback offline."""
import ast
from pathlib import Path
import shlex
import subprocess
import tempfile

script = Path(__file__).with_name('install.sh')
text = script.read_text(encoding='utf-8')
subprocess.run(['sh', '-n', str(script)], check=True)
assert '--menu' in text and '--gauge' in text and '--defaultno' in text
assert 'whiptail' in text and 'dialog' in text
assert 'VOICEHUB_TEXT' in text and '回退到文本菜单' in text
blocks = text.split("<<'PY'\n")[1:]
for block in blocks:
    ast.parse(block.split('\nPY\n')[0])
download = blocks[1].split('\nPY\n')[0]
for guard in (
    "parsed.netloc != 'codeload.github.com'",
    'not ip.is_global or ip.is_reserved or ip.is_multicast',
    "'--resolve'", "'--noproxy'", "result.stdout != '200'",
    "'..' in path.parts", 'stat.S_ISLNK(mode)',
    'len(files) > 5000', 'not required <= found',
):
    assert guard in download, guard
assert "'--location'" not in download

cleanup = text[text.index('cleanup() {'):text.index('trap cleanup 0')]
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    backup = root / 'backup'
    (backup / 'voicehub').mkdir(parents=True)
    (backup / 'voicehub/old.txt').write_text('preserved')
    stage = root / 'stage'
    stage.mkdir()
    command = '\n'.join([
        'set -eu', cleanup,
        'backup=' + shlex.quote(str(backup)),
        'app_dir=' + shlex.quote(str(root / 'voicehub')),
        'stage=' + shlex.quote(str(stage)), 'committed=0', 'cleanup',
    ])
    subprocess.run(['sh', '-c', command], check=True)
    assert (root / 'voicehub/old.txt').read_text() == 'preserved'
    assert not stage.exists()

ui = text[text.index('ui_msg() {'):text.index('fail() {')]
for selection, expected in [('1\n', 'install'), ('2\n', 'check'), ('3\n', 'exit')]:
    result = subprocess.run(['sh', '-c', ui + '\ntui=""; ui_menu'], input=selection.encode(), capture_output=True, check=True)
    assert result.stdout.decode('utf-8').strip() == expected
    assert b'1)' in result.stderr
for answer, expected in [('y\n', 0), ('\n', 1), ('n\n', 1)]:
    result = subprocess.run(['sh', '-c', ui + '\ntui=""; ui_yesno "confirm"'], input=answer.encode(), capture_output=True)
    assert result.returncode == expected
print('OK: shell/Python syntax, download guard assertions, text menu/confirmation, rollback')
