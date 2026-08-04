# Banana Slides × Deckforge 迁移最终验收报告

日期：2026-08-04

上游基线：`828bf6dfa535083b4fa6f5bed097655847fe26e5`

工作分支：`migration/deckforge-core`

## 1. 交付结论

核心闭环已在本地真实跑通两次：

```text
上传/输入资料 → 解析 → V1 大纲 → 自然语言修改 V2 → 明确确认大纲
→ 逐页结构化描述 → 明确确认描述 → 模板/文字风格门禁
→ GPT Image 2 逐页生成 → 单页自然语言修改 → 图片版本恢复
→ PPTX / PDF / 图片 ZIP 导出
```

第二次闭环使用真实 Markdown 资料，生成内容中的 `120 家门店`、`11%`、`18%`、`12 家试点`、`8 周`、`7%`、`14%`、`每周 1 小时`、`70%` 均来自上传资料。自然语言优化创建 V2，结构化 diff 记录 2 个 changed page，V1 保留。

## 2. 真实 Provider 验收

- 文本模型：现有中转站配置的 `gpt-5.6`，文本烟雾和两次真实闭环通过。
- 图片模型：现有中转站配置的 `gpt-image-2`。
- G2 单图烟雾：1672×941，成功。
- 第一闭环：2/2 图片成功；单页自然语言编辑创建 V2；恢复 V1 成功。
- 第二闭环：2/2 图片成功；中文、数字、流程图和表格清晰，无空白页。
- 未在报告、代码、截图或 Git 中保存 API Key/baseURL。

## 3. 导出验收

第一闭环：

- `closed-loop.pptx`：2 页，ZIP CRC 正常。
- `closed-loop.pdf`：2 页，每页 720×405 pt（16:9）。
- `closed-loop-images.zip`：2 张图片，ZIP CRC 正常。

第二闭环：

- `retail-ai-e2e.pptx`：2 页，ZIP CRC 正常，约 3.15 MB。
- `retail-ai-e2e.pdf`：2 页，每页 720×405 pt，约 3.12 MB。
- `retail-ai-e2e-images.zip`：2 张图片，约 3.12 MB。

## 4. 数据迁移

只读扫描结果：

| 项目 | 数量 |
|---|---:|
| 工作区 | 6 |
| Deckforge 项目 | 10 |
| 已生成页面 | 59 |
| 大纲版本 | 12 |
| 文件 | 5 |
| 文件总大小 | 6,783,110 bytes |

迁移使用 `D:\AI PPT\artifacts\migration\deckforge-data-copy-20260804` 副本，未修改原 `D:\AI PPT\data`。

- 首次副本演练：10 项目、71 页面（含仅有大纲的页面）、12 大纲版本、5 文件。
- 第二次副本演练：新增 0，跳过 15，证明幂等。
- 正式本地导入：10 项目、71 页面、12 大纲版本、5 文件。
- 冲突：0。
- 错误：0。
- orphan pages：0。
- orphan outline versions：0。

映射与 checksum 保存在 `deckforge_migration_records`。迁移前数据库均通过 SQLite backup API 归档。

## 5. 自动化测试与构建

| 检查 | 结果 |
|---|---|
| 旧 Deckforge | 26 files / 89 tests passed |
| Banana 前端 | 27 files / 203 tests passed |
| Banana 后端 | 621 collected / 614 passed / 7 external-service skips |
| 旧 Deckforge production build | passed |
| Banana frontend production build | passed |
| `docker-compose.prod.yml` immutable image config | passed |
| 真实浏览器验收 | passed |

上游原有 Windows 路径分隔符和临时图片句柄问题已修复；测试模式不再读取本地 `.env`，防止真实 Provider 配置污染测试和失败日志。

## 6. 新增工程能力

- User / Workspace / Membership 与 owner/editor/viewer。
- Project / ReferenceFile / Material / Task 工作区隔离。
- 写 API editor 门禁、成员管理 owner 门禁、跨工作区 404。
- Task 幂等键、取消、刷新恢复、进程重启后 `INTERRUPTED` 终态。
- OutlineVersion 父版本、确认状态、结构化 diff、恢复为新草稿。
- `screenText / visualAssets / layout / speakerNotes / brandConstraints` 描述 schema v2。
- 描述确认门禁、单页描述回滚快照、图片 stale 标记。
- 模板缺失时自动打开配置，批量生图不再返回无解释 400。
- 图片版本切换、恢复和非当前版本删除 API。
- `/live`、`/ready`、`/health/model`。
- 只读扫描器、幂等迁移器、默认新应用入口和 legacy 入口。
- SHA 镜像 CI、禁止 production `latest`、精确部署/回滚手册。

## 7. 未执行的外部动作

- 未配置用户 GitHub Fork `origin`。
- 未向镜像仓库 push，因此还没有真实 registry digest；CI 已在 push 事件中实现 digest 记录。
- 未部署、构建、清理或重启任何远程服务器。
- AGPL-3.0 本地开发不受阻；闭源商业 SaaS 发布前仍需商业授权或法律评估。

## 8. 启动和回滚

启动、数据迁移、服务器只拉镜像发布、健康检查及精确回滚命令见：

- `docs/DECKFORGE_MIGRATION_RUNBOOK.md`
- 根目录 `D:\AI PPT\start-ai-ppt.cmd`
- legacy：`D:\AI PPT\start-deckforge.cmd`
- legacy 数据副本核对：`D:\AI PPT\start-deckforge-readonly.cmd`
