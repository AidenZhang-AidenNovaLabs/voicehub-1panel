# VoiceHub · 1Panel

将 [VoiceHub](https://github.com/laoshuikaixue/VoiceHub) 校园广播点歌平台安装到 1Panel。仅一个应用容器，数据库选择 **1Panel 已安装的 PostgreSQL**。

- 官方镜像：`ghcr.io/laoshuikaixue/voicehub:latest`
- 版本通道：`latest`；安装/重建时拉取最新镜像，不自动替换运行中的容器
- 架构：amd64 / arm64
- Web 端口：3000（可修改）
- Linux TUI：`whiptail` 优先，`dialog` 备用；方向键、Tab、Enter 操作。无可用后端或终端为 `dumb` 时自动使用普通文本菜单

## Linux TUI 安装

在 Linux 服务器的交互式 SSH 终端运行，不要在 1Panel 计划任务或 `curl | sh` 管道中运行。

Debian / Ubuntu 依赖（自行执行）：

```bash
sudo apt update
sudo apt install whiptail python3 curl
```

RHEL / Rocky / AlmaLinux 可安装 `dialog python3 curl`。`whiptail/dialog` 是可选项；没有时自动回退到数字文本菜单。也可用 `sudo env VOICEHUB_TEXT=1 sh install.sh` 强制文本模式。

一行下载安装器并打开 TUI：

```bash
(f=$(mktemp) && trap 'rm -f "$f"' EXIT && curl --fail --silent --show-error --proto '=https' -o "$f" https://raw.githubusercontent.com/AidenZhang-AidenNovaLabs/voicehub-1panel/main/install.sh && sudo sh "$f")
```

菜单提供“安装/更新本地应用模板”“检查依赖和目录”“仅删除本地应用模板”“退出”。删除选项只删除检测到的 `resource/apps/local/voicehub` 模板（默认 `/opt/1panel/resource/apps/local/voicehub`），不停止容器、不删数据库、不删实际运行数据，也不会删除旧备份目录。

脚本从 `1pctl` 的 `BASE_DIR` 检测本地应用目录；默认位于 `/opt/1panel/resource/apps/local/voicehub`。脚本先验证 HTTPS 主机与 DNS 公网地址，固定已验证 IP、不跟随重定向、不使用代理；检查 ZIP 路径与体积后再安装。现有应用模板目录会保留到 `.voicehub.backup.XXXXXX/voicehub`，取消或失败不覆盖旧目录。**脚本仅复制应用商店模板，不创建或更新运行容器，不修改数据库。**网络无法直连 GitHub 时可使用下方手动方式；不内置第三方代理。

## 在 1Panel 安装应用

1. 先通过 1Panel 安装 PostgreSQL（建议 15）并启动。
2. 在 1Panel 刷新本地应用，安装 `VoiceHub / latest`，选择 PostgreSQL 服务。
3. 填写数据库参数；JWT 密钥首次启动时自动生成，无需填写。首次登录 `admin / admin123` 后立即修改密码；公网访问使用 HTTPS。

数据库绑定字段复用 [官方 Halo 模板](https://github.com/1Panel-dev/appstore/blob/dev/apps/halo/2.26.1/data.yml)。插件与后台备份分别保存在 `./data`、`./backups`；数据库由 1Panel 管理。JWT 密钥以随机 64 字节的 hex 字符串生成，持久化到 `data/.jwt-secret` 并复用；备份和恢复 `data` 目录时务必保留此隐藏文件。

## 手动安装与更新

通过 GitHub 的 **Code → Download ZIP** 下载，复制 `apps/voicehub` 到实际 1Panel 根目录的 `resource/apps/local/voicehub`，再刷新本地应用。替换已有目录前自行备份。

重新运行 TUI 安装器只更新**模板**，不会改变已有安装的运行配置。旧安装迁移到新版配置并重建时，若没有 `data/.jwt-secret`，会生成新密钥，旧登录 token 失效，需重新登录；如需保留旧密钥，应在重建前将其保存到实际安装目录的 `data/.jwt-secret`。若要更新已运行的 VoiceHub，先备份 PostgreSQL 数据库及应用安装目录（保留 `data/.jwt-secret`），然后在 1Panel 执行拉取镜像并重建；没有该操作时，在应用的**实际安装目录**执行：

```bash
docker compose pull voicehub && docker compose up -d --no-deps voicehub
```

不要在 `resource/apps/local/voicehub/latest` 模板目录运行上述命令。自动迁移可能改变数据库，回退镜像不等于回退数据库。

## 验证与限制

```bash
python3 check_package.py
python3 check_installer.py
```

配置与启动包装检查需要 Python 3、Node.js 和 Bash；安装器检查无需访问网络或操作服务器。已进行静态/模拟测试，尚未在实际 Linux 1Panel 环境完成安装、升级或 TUI 显示验收。最新版仅指已发布到官方 `latest` 标签的镜像，不是无人值守实时升级。

完整配置、来源和运行注意见 [INSTALL.md](INSTALL.md)。参考 [napcat-1panel](https://github.com/Fahaxikiii/napcat-1panel) 的“下载到 1Panel 本地应用目录再刷新”发布方式；未复制其删除/代理脚本，也不引入额外后台更新服务。

VoiceHub 和官方 Logo 的许可及权利属于上游项目，参见 [GPL-3.0](https://github.com/laoshuikaixue/VoiceHub/blob/main/LICENSE)。本仓库不包含 VoiceHub 应用源码，只提供容器应用模板。
