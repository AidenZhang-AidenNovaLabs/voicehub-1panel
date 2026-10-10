# VoiceHub · 1Panel 本地应用（滚动 latest）

## 安装

1. 在 1Panel 应用商店安装 PostgreSQL（建议 15，与 VoiceHub 官方部署一致），确认它处于运行状态且加入 `1panel-network`。应用包不会创建第二个 PostgreSQL 容器，不支持 MySQL/MariaDB。
2. 将压缩包里的 `apps/voicehub` 整个目录复制到服务器 `/opt/1panel/resource/apps/local/voicehub`。若 1Panel 使用了自定义根目录，应使用实际根目录下的 `resource/apps/local/voicehub`。已有同名应用目录时先备份，不要盲目覆盖。
3. 在 1Panel 刷新“本地应用”，安装 VoiceHub，选择 `latest`。在“数据库服务”选择已安装的 PostgreSQL，填写/保留数据库名、用户及随机密码，填写 JWT 密钥。仅开放 Web 端口（默认 3000）。

JWT 密钥可以在服务器终端生成：

```bash
openssl rand -hex 32
```

填入输出的 64 位字符串；每次安装独立生成，不与数据库密码共用。以后更新时保留原 JWT 密钥。

表单复用官方 Halo 的 `PANEL_DB_TYPE` → `PANEL_DB_HOST` 数据库绑定格式，只保留 PostgreSQL 选项。数据库/用户的创建由 1Panel 数据库绑定流程处理，本包没有建库 hook。若复用已有数据库，用户必须具有数据库/schema/相关对象的创建和修改权限；推荐用新数据库，不要连接含其他应用表的数据库。

官方启动流程会同步数据库并初始化管理员。打开 `http://服务器地址:安装端口`，首次登录 `admin / admin123` 后立即修改密码。在修改前不要对公网开放；公网使用建议在 1Panel 网站中配置 HTTPS 反向代理。

## 获取最新版本

- 使用官方 `ghcr.io/laoshuikaixue/voicehub:latest`，并设置 `pull_policy: always`。
- 安装及执行 Compose 创建/更新时查询镜像仓库，拉取最新发布到 `latest` 的镜像。镜像尚未构建/发布、无法连接 GHCR 或不支持服务器架构时不能保证取得新版本。
- `latest` 是滚动通道，不是上游真实版本号；1Panel 不会因此产生新的应用版本条目。
- 已运行容器不会实时自行更新。普通重启不保证更新，不含 Watchtower、自动更新任务或新数据库容器。

更新前先在 1Panel 备份此应用的 PostgreSQL 数据库，并备份应用安装目录（含 `.env`、`data`、`backups`）。上游启动包含自动迁移，失败时可能回退到 `drizzle-kit push --force`；不要跳过备份。旧镜像回退不能自动撤销数据库迁移。

如 1Panel 当前版本没有明确的“拉取镜像并重建”操作，从应用详情找到**实际安装目录**（不是 `resource/apps/local` 包目录），打开该目录终端执行：

```bash
# 先完成数据库备份，再在此应用实际安装目录执行：
docker compose pull voicehub && docker compose up -d --no-deps voicehub
docker compose logs --tail=100 voicehub
```

这会重建同一个 1Panel 管理的 VoiceHub 容器，保留容器名、`.env`、绑定数据库和数据目录，不安装另一套容器。更新完成后检查 1Panel 状态与日志；可能有短暂不可用。

## 最小适配范围

- 一个 VoiceHub 服务：官方镜像、官方 `node scripts/deploy.js` 与服务启动顺序。
- 1Panel 标准容器名、外部网络、端口参数和 Apps 标签。
- 通过所选 PostgreSQL 服务的 `PANEL_DB_HOST/PANEL_DB_PORT` 连接。不设置跨 Compose 的 `depends_on`；所选数据库应先运行。
- 一段 Compose 内启动命令对数据库用户名/密码进行 URI 编码，避免 `%`、`@`、`:` 等字符破坏连接；不修改 VoiceHub 源码。内网连接按官方 Compose 使用 `sslmode=disable`，不适用于公网外部数据库。
- `./data:/app/.data` 持久化插件运行文件，`./backups:/app/backups` 持久化后台备份。应用以官方镜像的 root 用户运行，无额外权限 hook。

Redis、OAuth、WebAuthn 和域名等扩展选项未加入最小表单。包宣告 amd64/arm64（官方 latest 镜像提供这两个架构）；没有额外守护服务或生命周期脚本。

## 校验结果与复核

已通过官方包基础校验及 `check_package.py`：单容器、数据库子选择器、变量声明、最新镜像拉取策略、数据目录、密码编码回环、失败时不启动服务器。`latest` 浮动标签警告是本任务要求，非遗漏。

本机无 Docker/1Panel，**未进行真实 Compose 解析、镜像拉取、安装或升级运行测试**。脚本只测试生成配置和原样启动包装逻辑，不证明实际数据库迁移成功。

在本地工作区复核（需 Python 3、Node.js 和 Bash，无额外依赖）：

```bash
python check_package.py
```

若在测试服务器安装，可在真实安装目录执行 `docker compose config --quiet` 检查配置；这不会打印密码。完整 `docker compose config` 可能显示秘密，不要将其结果公开。

## 来源

官方源码与模板通过 Playwright MCP 读取：

- [1Panel Halo 数据库安装字段](https://github.com/1Panel-dev/appstore/blob/dev/apps/halo/2.26.1/data.yml) / [连接方式](https://github.com/1Panel-dev/appstore/blob/dev/apps/halo/2.26.1/docker-compose.yml)
- [VoiceHub 官方预构建 Compose](https://github.com/laoshuikaixue/VoiceHub/blob/main/docker-compose/docker-compose-prebuild-github.yml)
- [Dockerfile](https://github.com/laoshuikaixue/VoiceHub/blob/main/Dockerfile) / [部署逻辑](https://github.com/laoshuikaixue/VoiceHub/blob/main/scripts/deploy.js) / [数据库同步](https://github.com/laoshuikaixue/VoiceHub/blob/main/scripts/db-sync.js)
- [插件存储](https://github.com/laoshuikaixue/VoiceHub/blob/main/server/utils/music-source-plugins/store.ts) / [备份存储](https://github.com/laoshuikaixue/VoiceHub/blob/main/server/api/admin/backup/export.post.ts)
- [镜像构建](https://github.com/laoshuikaixue/VoiceHub/blob/main/.github/workflows/docker-build.yml) / [更新注意](https://github.com/laoshuikaixue/VoiceHub/blob/main/UPGRADE.md)

Logo 来自官方 `public/assets/logo.png`，经 MCP 浏览器捕获。VoiceHub 及图标权利归上游作者，使用遵循上游 [GPL-3.0 许可](https://github.com/laoshuikaixue/VoiceHub/blob/main/LICENSE)。包不嵌入应用源码，只引用官方镜像。

中间规格为 `voicehub-appspec.json`，使用现成 `generate_app_package.py` 生成。生成后只做两项包内调整：去掉自动生成的重复顶层 `PANEL_DB_HOST` 字段（它已有子选择器），并加 `pull_policy: always`；直接重新生成会需要重做这两项，不修改 skill 生成器。
