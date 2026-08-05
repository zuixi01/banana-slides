# Banana Slides × Deckforge 本地运行、迁移、发布与回滚手册

## 1. 当前产品入口

- 新应用目录：`D:\AI PPT\banana-slides-next`
- 新应用前端：`http://127.0.0.1:3011`
- 新应用后端：`http://127.0.0.1:5011`
- 存活检查：`GET /live`
- 就绪检查：`GET /ready`
- 模型配置检查：`GET /health/model`（只返回是否配置，不返回密钥或 baseURL）
- 旧 Deckforge 保留在 `D:\AI PPT`，没有删除或覆盖。

双击 `D:\AI PPT\start-ai-ppt.cmd` 启动新应用。命令行方式：

```powershell
cd 'D:\AI PPT\banana-slides-next'
npm run start:local
```

停止由脚本启动的本地服务：

```powershell
cd 'D:\AI PPT\banana-slides-next'
npm run stop:local
```

日志位于 `.runtime\backend.stderr.log`、`.runtime\backend.stdout.log`、`.runtime\frontend.stderr.log`。

## 2. 首次安装

```powershell
cd 'D:\AI PPT\banana-slides-next'
uv sync --extra test
cd frontend
npm ci
```

模型中转站配置只写入被 Git 忽略的 `.env`。可从 `.env.deckforge.example` 复制字段名；不要在终端、日志、截图或提交中输出真实 Key。

## 3. Deckforge 数据迁移

迁移器禁止把活动中的旧数据目录作为输入。先创建副本，再只对副本扫描：

```powershell
cd 'D:\AI PPT\banana-slides-next'
.\.venv\Scripts\python.exe scripts\migration\scan_deckforge.py `
  --source 'D:\AI PPT\artifacts\migration\deckforge-data-copy-20260804' `
  --report artifacts\migration\G10_DECKFORGE_SCAN.json
```

正式导入前，先使用 SQLite backup API 备份 Banana 数据库。导入命令必须同时带两个安全开关：

```powershell
.\.venv\Scripts\python.exe scripts\migration\migrate_deckforge.py `
  --source 'D:\AI PPT\artifacts\migration\deckforge-data-copy-20260804' `
  --database backend\instance\database.db `
  --uploads uploads `
  --report artifacts\migration\G10_MIGRATION_APPLIED.json `
  --confirm-source-is-copy --apply
```

迁移映射记录在 `deckforge_migration_records`。相同源 ID 与 checksum 重复执行只会跳过，不重复创建；源内容发生变化时记录 conflict，不覆盖已迁移结果。

## 4. 旧系统核对入口

原入口保持不变：

```powershell
cd 'D:\AI PPT'
.\start-deckforge.cmd
```

只使用迁移前副本进行核对：

```powershell
cd 'D:\AI PPT'
.\start-deckforge-readonly.cmd
```

该入口把 `DATA_ROOT_PATH` 指向归档副本，不写入原 `data` 目录。

## 5. CI 和不可变镜像

`.github/workflows/deckforge-migration-ci.yml` 执行：

1. Python 3.11 后端测试。
2. Node 20 前端测试和生产构建。
3. mock provider 关键浏览器闭环。
4. 构建 all-in-one 镜像。
5. push 事件只推送 `sha-<完整 Git SHA>`，并把镜像 digest 写入 Job Summary。

`docker-compose.prod.yml` 没有默认镜像，也不接受项目提供的 `latest` 默认值。发布时必须显式设置：

```text
DOCKER_IMAGE_BACKEND=registry.example/banana-backend:sha-<git-sha>
DOCKER_IMAGE_FRONTEND=registry.example/banana-frontend:sha-<git-sha>
```

也可以使用 `image@sha256:<digest>`。

当前已验收的 all-in-one CI 镜像：

```text
ghcr.io/zuixi01/banana-slides:sha-be2433a3f78f52560a7c364968383f715dcaa4e7
ghcr.io/zuixi01/banana-slides@sha256:f347a382823c6362ba939d619e87f11f25ab943b9e36dad12685c1bd712f79d3
```

来源：GitHub Actions Run `30973030886`。正式发布优先使用第二行 digest 引用；不要改写成 `latest`。

### 5.1 本地 all-in-one 镜像验收

Docker Desktop 不可用时，可在 D 盘隔离的 `Ubuntu-24.04` WSL 构建环境使用 Buildah/Podman；这只用于本地验收，不替代 CI 推送和服务器拉取不可变镜像的发布流程。

```powershell
wsl -d Ubuntu-24.04 -u root -- bash -lc "export STORAGE_DRIVER=vfs; buildah bud --format docker --isolation chroot --layers -f '/mnt/d/AI PPT/banana-slides-next/Dockerfile.allinone' --build-arg APP_COMMIT_SHA=<full-git-sha> --build-arg APP_COMMIT_SHORT_SHA=<short-git-sha> -t localhost/banana-slides-deckforge:sha-<short-git-sha> '/mnt/d/AI PPT/banana-slides-next'"

wsl -d Ubuntu-24.04 -u root -- bash -lc "export STORAGE_DRIVER=vfs; podman run -d --name banana-g11-final -p 127.0.0.1:18080:80 -v /var/lib/banana-slides/instance:/app/backend/instance -v /var/lib/banana-slides/uploads:/app/uploads localhost/banana-slides-deckforge:sha-<short-git-sha>"
```

验收：

```powershell
curl.exe -fsS http://127.0.0.1:18080/health
curl.exe -fsS http://127.0.0.1:18080/live
curl.exe -fsS http://127.0.0.1:18080/ready
```

未注入模型凭据的隔离容器中，`/health/model` 返回 503 `missing_credentials` 是预期结果。生产环境必须配置凭据并要求该接口返回 200。

## 6. 服务器标准发布（本次未执行）

服务器只作为部署目标。任何远程发布前，先执行并汇总：

```bash
uptime
free -h
swapon --show
df -h
df -ih
docker system df
docker compose ps
```

资源达到项目 `AGENTS.md` 的任一熔断阈值时停止。通过后记录当前镜像作为回滚目标，只执行：

```bash
export DOCKER_IMAGE_BACKEND='<immutable-backend-image>'
export DOCKER_IMAGE_FRONTEND='<immutable-frontend-image>'
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:5011/live
curl -fsS http://127.0.0.1:5011/ready
```

不在服务器运行 build、npm、uv、prune、缓存清理或源码修改。

## 7. 精确回滚

### 7.1 立即回到旧 Deckforge

不修改新应用数据，停止新应用并启动旧入口：

```powershell
cd 'D:\AI PPT\banana-slides-next'
npm run stop:local
cd 'D:\AI PPT'
.\start-deckforge.cmd
```

### 7.2 回滚 Banana 数据库迁移且保留失败现场

必须先停止新应用。以下命令把当前数据库另存为失败现场，再复制迁移前备份，不删除任何文件：

```powershell
cd 'D:\AI PPT\banana-slides-next'
npm run stop:local
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item backend\instance\database.db "artifacts\migration\database-before-rollback-$stamp.db"
Copy-Item artifacts\migration\banana-pre-deckforge-import-20260804.db backend\instance\database.db
npm run start:local
```

若只需回滚 G6 描述 schema，使用 `banana-pre-g6-description-schema-20260804.db`；若需回滚工作区迁移，使用 `banana-pre-g3-workspaces-20260804.db`。

### 7.3 生产镜像回滚

把发布前记录的两个镜像 SHA/digest 设回环境变量，然后执行 pull/up/健康检查：

```bash
export DOCKER_IMAGE_BACKEND='<previous-backend-image@digest>'
export DOCKER_IMAGE_FRONTEND='<previous-frontend-image@digest>'
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
curl -fsS http://127.0.0.1:5011/ready
```

## 8. 许可证

本二开继续保留 Banana Slides 的 AGPL-3.0、版权和 NOTICE。若要闭源商业 SaaS 发布，必须在生产发布前取得商业授权或完成独立法律评估；这不阻止当前本地开发与验收。
