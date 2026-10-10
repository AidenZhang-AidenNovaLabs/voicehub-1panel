#!/usr/bin/env python3
"""Check installer syntax, security guards, text UI and rollback offline."""
import ast
from pathlib import Path
import shlex
import subprocess
import sys
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
download = blocks[-1].split('\nPY\n')[0]
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
for selection, expected in [('1\n', 'install'), ('2\n', 'check'), ('3\n', 'delete'), ('4\n', 'exit')]:
    result = subprocess.run(['sh', '-c', ui + '\ntui=""; ui_menu'], input=selection.encode(), capture_output=True, check=True)
    assert result.stdout.decode('utf-8').strip() == expected
    assert b'1)' in result.stderr
for answer, expected in [('y\n', 0), ('\n', 1), ('n\n', 1)]:
    result = subprocess.run(['sh', '-c', ui + '\ntui=""; ui_yesno "confirm"'], input=answer.encode(), capture_output=True)
    assert result.returncode == expected
delete_branch = text[text.index('if [ "$choice" = delete ]; then'):text.index('if [ "$choice" = check ]; then')]
for answer, protected in [('n', False), ('y', False), ('y', True)]:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        app = root / 'voicehub'
        app.mkdir()
        (app / 'data.yml').write_text('additionalProperties:\n  key: voicehub\n', encoding='utf-8')
        backup_dir = root / '.voicehub.backup.test'
        backup_dir.mkdir()
        if protected:
            (app / '.env').write_text('runtime-config', encoding='utf-8')
        command = '\n'.join([
            'set -eu', ui, 'fail() { exit 1; }', 'tui=""; choice=delete',
            'local_root=' + shlex.quote(str(root)),
            'app_dir=' + shlex.quote(str(app)),
            delete_branch.replace('python3 - ', shlex.quote(sys.executable) + ' - '),
        ])
        result = subprocess.run(['sh', '-c', command], input=(answer + '\n\n').encode(), capture_output=True)
        assert app.exists() == (answer != 'y' or protected), (answer, protected, result.returncode, result.stderr.decode())
        assert result.returncode == (1 if protected else 0), result.stderr
        assert backup_dir.is_dir()
print('OK: syntax, text menu, delete/cancel/runtime protection, backup retention, rollback')
