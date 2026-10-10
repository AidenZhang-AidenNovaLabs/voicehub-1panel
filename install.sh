#!/bin/sh
# Installs app-store files only; running containers and databases are untouched.
set -eu

TITLE='VoiceHub · 1Panel'
stage=''
backup=''
app_dir=''
committed=0

ui_msg() {
    if [ -n "${tui:-}" ]; then
        "$tui" --title "$TITLE" --msgbox "$1" 14 76
    else
        printf '\n%s\n\n' "$1" >&2
        printf '%s' '按 Enter 继续…' >&2
        read -r _ || true
    fi
}
ui_yesno() {
    if [ -n "${tui:-}" ]; then
        "$tui" --title "$TITLE" --defaultno --yesno "$1" 16 76
    else
        printf '\n%s\n继续？[y/N] ' "$1" >&2
        read -r answer || return 1
        case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
    fi
}
ui_menu() {
    if [ -n "${tui:-}" ]; then
        "$tui" --title "$TITLE" --backtitle 'Linux 本地应用安装器 · 不操作运行中的容器' \
            --menu '方向键选择，Tab 切换按钮，Enter 确认，Esc 退出。' 17 76 4 \
            install '安装 / 更新本地应用模板' \
            check '检查依赖和 1Panel 目录' \
            delete '仅删除本地应用模板' \
            exit '退出' 3>&1 1>&2 2>&3
    else
        printf '\nVoiceHub · 1Panel Linux 安装器\n' >&2
        printf '%s\n' '1) 安装 / 更新本地应用模板' '2) 检查依赖和 1Panel 目录' '3) 仅删除本地应用模板' '4) 退出' >&2
        printf '%s' '选择 [1-4]: ' >&2
        read -r choice || return 1
        case "$choice" in
            1) printf '%s\n' install ;;
            2) printf '%s\n' check ;;
            3) printf '%s\n' delete ;;
            4) printf '%s\n' exit ;;
            *) return 1 ;;
        esac
    fi
}
fail() {
    printf '%s\n' "$1" >&2
    ui_msg "$1" || true
    exit 1
}
cleanup() {
    if [ -n "$backup" ] && [ "$committed" -eq 0 ] && [ ! -e "$app_dir" ]; then
        if mv "$backup/voicehub" "$app_dir"; then
            printf '%s\n' '旧应用目录已恢复。' >&2
            rmdir "$backup" || true
        else
            printf '恢复失败；旧目录仍保存在 %s/voicehub\n' "$backup" >&2
        fi
    fi
    if [ -n "$stage" ]; then rm -rf -- "$stage"; fi
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP

[ "$(uname -s)" = Linux ] || fail '请在 Linux 1Panel 服务器的交互式终端运行。'
[ -t 0 ] && [ -t 1 ] || fail '需要交互式终端；请下载脚本后执行 sh install.sh，不要管道执行。'
tui=''
if [ -n "${TERM:-}" ] && [ "${TERM:-}" != dumb ] && [ "${VOICEHUB_TEXT:-0}" != 1 ]; then
    if command -v whiptail >/dev/null 2>&1; then
        tui=whiptail
    elif command -v dialog >/dev/null 2>&1; then
        tui=dialog
    fi
fi

if choice=$(ui_menu); then
    :
else
    status=$?
    # whiptail: 1/255 and dialog: 1/255 mean Cancel/Esc, not a backend failure.
    case "$status" in 1|255) exit 0 ;; esac
    tui=''
    printf '%s\n' 'TUI 后端无法运行，回退到文本菜单。' >&2
    choice=$(ui_menu) || exit 0
fi
case "$choice" in
    exit|'') exit 0 ;;
    install|check|delete) : ;;
    *) fail '无效选项。' ;;
esac

for tool in python3 mktemp awk; do
    command -v "$tool" >/dev/null 2>&1 || fail "缺少依赖：$tool。请安装后重试。"
done
if [ "$choice" != delete ]; then
    command -v curl >/dev/null 2>&1 || fail '缺少依赖：curl。请安装后重试。'
fi
panelctl=$(command -v 1pctl 2>/dev/null) || fail '找不到 1pctl；请在安装了 1Panel 的服务器上运行。'
[ -f "$panelctl" ] && [ -r "$panelctl" ] || fail '无法读取 1pctl。'
base_dir=$(awk '/^[[:space:]]*BASE_DIR=/ {sub(/^[[:space:]]*BASE_DIR=/, ""); print; exit}' "$panelctl")
base_dir=$(python3 - "$base_dir" <<'PY'
import sys
from pathlib import Path
value = sys.argv[1].strip()
if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
    value = value[1:-1]
p = Path(value)
if not p.is_absolute() or any(c in value for c in '\n\r$`') or p == Path('/'):
    sys.exit('1pctl BASE_DIR 无效；未执行其中任何 shell 内容。')
print(p.resolve())
PY
) || fail '无法安全解析 1pctl BASE_DIR。'
local_root="$base_dir/1panel/resource/apps/local"
[ -d "$local_root" ] && [ -w "$local_root" ] || fail "本地应用目录不存在或不可写：$local_root"
app_dir="$local_root/voicehub"
[ ! -L "$app_dir" ] || fail "拒绝替换符号链接：$app_dir"
if [ -e "$app_dir" ]; then
    [ -d "$app_dir" ] && [ -f "$app_dir/data.yml" ] || fail "目标不是已识别的应用目录：$app_dir"
fi
if [ "$choice" = delete ]; then
    if [ ! -d "$app_dir" ]; then
        ui_msg "未找到本地应用模板：\n$app_dir\n\n运行中的容器、数据库和备份目录未修改。"
        exit 0
    fi
    if [ ! -f "$app_dir/data.yml" ] || [ -L "$app_dir" ]; then
        fail "目标不是可识别的 VoiceHub 本地应用目录，已拒绝删除：$app_dir"
    fi
    if ui_yesno "仅删除本地应用模板？\n\n$app_dir\n\n不会停止容器，不会删除数据库，不会删除应用实际安装目录或运行数据。"; then
        python3 - "$local_root" "$app_dir" <<'PY'
from pathlib import Path
import re
import shutil
import sys
root, app = map(Path, sys.argv[1:])
if app.is_symlink() or app.parent.resolve() != root.resolve() or app.name != 'voicehub':
    sys.exit('目标不在本地应用模板目录，已拒绝删除。')
metadata = app / 'data.yml'
if not app.is_dir() or metadata.is_symlink() or not metadata.is_file():
    sys.exit('目标不是可识别的本地应用模板，已拒绝删除。')
if not re.search(r'^\s+key:\s*[\"\x27]?voicehub[\"\x27]?\s*$', metadata.read_text(encoding='utf-8'), re.M):
    sys.exit('应用标识不是 voicehub，已拒绝删除。')
if (app / '.env').exists():
    sys.exit('目标含运行配置 .env，已拒绝删除；请核对路径。')
shutil.rmtree(app)
PY
        ui_msg "本地应用模板已删除。\n\n运行中的容器、数据库和运行数据未修改。"
    else
        ui_msg '已取消，未删除任何文件。'
    fi
    exit 0
fi

if [ "$choice" = check ]; then
    ui_msg "依赖检查通过。

界面：${tui:-文本模式}
工具：python3 / curl / mktemp / awk
目标：$app_dir

仅安装应用模板；数据库与运行容器不变。"
    exit 0
fi
if ui_yesno "来源：AidenZhang-AidenNovaLabs/voicehub-1panel（main）\n\n目标：$app_dir\n\n若目标已存在，将保留完整备份。不会自动安装或更新容器。\n\n继续？"; then
    :
else
    exit 0
fi
stage=$(mktemp -d "$local_root/.voicehub.stage.XXXXXX")

progress_run() {
    if [ -n "${tui:-}" ]; then
        "$tui" --title "$TITLE" --gauge '正在验证 DNS、下载并检查应用包…' 9 76 0
    else
        while IFS= read -r line; do
            case "$line" in 10) printf '%s\n' '正在下载并检查官方应用包…' >&2 ;; 100) printf '%s\n' '校验完成。' >&2 ;; esac
        done
    fi
}

if ! (
    printf '10\n'
    if python3 - "$stage" 2>"$stage/error.log" <<'PY'
import ipaddress
import os
from pathlib import Path, PurePosixPath
import socket
import stat
import subprocess
import sys
from urllib.parse import urlsplit
from zipfile import ZipFile

stage = Path(sys.argv[1])
url = 'https://codeload.github.com/AidenZhang-AidenNovaLabs/voicehub-1panel/zip/refs/heads/main'
parsed = urlsplit(url)
if parsed.scheme != 'https' or parsed.netloc != 'codeload.github.com':
    sys.exit('拒绝非官方 HTTPS 地址。')
addresses = {ipaddress.ip_address(row[4][0]) for row in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)}
if not addresses or any(not ip.is_global or ip.is_reserved or ip.is_multicast for ip in addresses):
    sys.exit('DNS 包含本地、私有或保留地址，拒绝请求。')
ip = sorted(addresses, key=lambda a: (a.version, int(a)))[0]
pin = str(ip) if ip.version == 4 else '[' + str(ip) + ']'
archive = stage / 'source.zip'
# Pin the checked address; disable proxies and redirects to avoid a second unvalidated host.
result = subprocess.run([
    'curl', '--fail', '--silent', '--show-error', '--noproxy', '*',
    '--proto', '=https', '--connect-timeout', '15', '--max-time', '180',
    '--max-filesize', '20971520', '--resolve', parsed.hostname + ':443:' + pin,
    '--output', str(archive), '--write-out', '%{http_code}', url,
], capture_output=True, text=True)
if result.returncode or result.stdout != '200':
    sys.exit('下载失败（不接受重定向）：' + (result.stderr.strip() or result.stdout))
if archive.stat().st_size > 20 * 1024 * 1024:
    sys.exit('压缩包超过 20 MiB。')
with ZipFile(archive) as z:
    files = z.infolist()
    if len(files) > 5000 or sum(f.file_size for f in files) > 50 * 1024 * 1024:
        sys.exit('压缩包解压体积过大。')
    required = {'data.yml', 'logo.png', 'README.md', 'latest/data.yml', 'latest/docker-compose.yml', 'latest/config/jwt-secret.cjs'}
    found = set()
    roots = set()
    for entry in files:
        path = PurePosixPath(entry.filename)
        mode = entry.external_attr >> 16
        if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or stat.S_ISLNK(mode):
            sys.exit('压缩包存在不安全路径或符号链接。')
        parts = path.parts
        if len(parts) < 4 or parts[1:3] != ('apps', 'voicehub') or entry.is_dir():
            continue
        roots.add(parts[0])
        relative = PurePosixPath(*parts[3:])
        found.add(str(relative))
        target = stage / 'voicehub' / str(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with z.open(entry) as src, target.open('xb') as dst:
            import shutil
            shutil.copyfileobj(src, dst)
    if len(roots) != 1 or not required <= found:
        sys.exit('压缩包缺少必要 1Panel 应用文件。')
PY
    then
        printf '100\n'
    else
        : >"$stage/failed"
        printf '100\n'
    fi
) | progress_run; then
    fail '进度窗口被取消；未替换旧目录。'
fi
if [ -f "$stage/failed" ]; then
    detail=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text())' "$stage/error.log")
    fail "下载或校验失败；原应用目录未修改。\n$detail"
fi
[ -d "$stage/voicehub" ] || fail '应用包准备失败；原目录未修改。'
if [ -d "$app_dir" ]; then
    backup=$(mktemp -d "$local_root/.voicehub.backup.XXXXXX")
    mv "$app_dir" "$backup/voicehub" || fail '备份失败；未安装新目录。'
fi
mv "$stage/voicehub" "$app_dir" || fail '替换失败，将恢复旧目录。'
committed=1
ui_msg "完成。请在 1Panel 刷新本地应用并安装 VoiceHub / latest。\n\n目标：$app_dir\n备份：${backup:-无}\n\n选择已安装的 PostgreSQL；JWT 密钥自动生成，无需填写。备份 data 目录时保留隐藏文件 .jwt-secret，首次登录后修改默认管理员密码。\n\n运行中的容器未修改。"
