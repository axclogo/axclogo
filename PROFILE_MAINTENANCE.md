# 个人主页图片维护

README 展示仓库 `output` 分支里的静态 SVG，访问时不再调用第三方图片生成服务。
图片由 GitHub Actions 更新；某个模块生成失败时继续展示该模块上一次成功的图片。

## 唯一工作流

入口：[`Update Profile Assets`](https://github.com/axclogo/axclogo/actions/workflows/profile-assets.yml)。

| Job | 职责 | 写仓库权限 |
| --- | --- | --- |
| validate | 配置、生成器、失败回退测试 | 无 |
| cards | 总览、语言和每个项目的深浅色卡片 | 无 |
| activity | 贡献曲线、连续贡献、固定标题动画 | 无 |
| snake | 深浅色贡献蛇图 | 无 |
| publish | 校验、保留失败模块旧图、统一提交、汇总状态 | 仅此 job 拥有 |

- 每天 UTC 00:23（北京时间 08:23）执行，实际启动可能延迟。
- 修改工作流、脚本、配置或依赖并推送 `main` 时自动执行；PR 只运行验证。
- 随时可在 Actions 页选择 **Run workflow** 手动执行。
- 同一分支的执行串行排队，避免多个发布任务相互覆盖。
- 第三方 Action 固定到提交 SHA；卡片库固定版本并提交 `package-lock.json`。
- 使用 Actions 自动提供的 `GITHUB_TOKEN`，不再使用 `METRICS_TOKEN` 或常驻个人令牌。
- 只按默认令牌能访问的数据生成统计，不承诺包含私有仓库数据。

## 配置与输出

编辑 [`profile.config.json`](profile.config.json) 维护用户、分类、项目列表、颜色和卡片选项。
分类可通过 `columns` 设置每行卡片数量（1、2 或 3，默认 2）；AxcBedrock 系列设为 3，将 Swift、Dart、Kotlin 三套库横向并排展示在同一行，每张卡片宽度为 29%。
新增项目无需复制工作流步骤。`output` 是发布分支；如迁移分支，需同时调整工作流 checkout/push 目标。

| 模块 | `output` 分支路径 |
| --- | --- |
| 总览 | `cards/stats-{light,dark}.svg` |
| 语言 | `cards/languages-{light,dark}.svg` |
| 项目 | `cards/repo-项目名-{light,dark}.svg` |
| 连续贡献 | `activity/streak-{light,dark}.svg` |
| 活动曲线 | `activity/graph-{light,dark}.svg` |
| 蛇图 | `github-contribution-grid-snake.svg`、`github-contribution-grid-snake-dark.svg` |
| 标题动画 | `headings/分类ID.svg` |
| 更新状态 | `status.json` 和该分支的 `README.md` |

动态产物只存放在 `output`，主分支不再保留没有被引用的旧 SVG。
蛇图沿用原有文件名，保证迁移期间旧 README 的引用仍有效。

修改配置后重新生成 README 并测试：

```sh
npm ci --ignore-scripts
python3 scripts/profile.py readme
npm test
python3 scripts/profile.py check
```

本地生成需要自行通过环境变量提供 GitHub API 令牌；不要把令牌写入配置或提交到仓库。

```sh
npm run cards
python3 scripts/profile.py headings
python3 scripts/profile.py activity
```

## 统计口径

- 总览、语言、项目卡片使用固定版本的 GitHub Readme Stats Core，由 Actions 内部直接请求 GitHub API。
- 语言统计是仓库代码语言分布，不代表个人熟练程度。
- 连续贡献与活动曲线使用 GitHub GraphQL contribution calendar 的日期和贡献数量。
- 连续贡献展示**最近 365 个 UTC 日期**中的当前连续天数、最长连续天数、贡献总数。最长连续天数不是账号注册以来的历史纪录；当前连续天数也受这个窗口限制。
- 当前 UTC 日期尚未产生贡献时，允许延续到昨天的连续记录；昨天也没有贡献则归零。
- 曲线展示最近 31 天。当前日期尚未结束，因此当天数据可能不完整。
- 每个标题是本地 SVG 动画，支持系统“减少动态效果”设置，不需要在线打字服务。

## 失败时的行为

1. 生成器先写临时构建目录，生成阶段没有仓库写入权限。
2. 每张图片必须是有效 SVG，并且不包含已知错误提示、脚本或外部图片资源。
3. 每个项目的深浅色版本一起验证、一起替换。贡献图的四张图片也作为一个模块更新。
4. 失败或缺失的模块保留上一次图片和 `last_success`；其他成功模块仍可发布。
5. 发布完成后，存在失败模块会将工作流标为失败，不能用绿色运行掩盖旧数据。
6. `status.json` 记录本次尝试、源码提交、运行链接及各模块最后成功时间。状态报告也写入 Actions summary。

`updated` 表示本次成功；`retained` 表示失败但仍有旧图；`missing` 表示尚无可用图片。
状态文件记录真实尝试时间，因此每日执行通常会产生一次 `output` 分支提交。
发布只做普通 push，不 force-push；冲突或权限问题会明确失败，不覆盖他人的更新。

## 运行检查与恢复

在 [output 分支](https://github.com/axclogo/axclogo/tree/output)查看状态表。一般最后成功时间不应超过两天。
超过两天时先看工作流是否运行，再看具体失败 job；更新停滞不会自动使已经发布的 SVG 消失。

- **401 / Bad credentials**：确认工作流使用 `github.token`，不要换回旧 `METRICS_TOKEN`。
- **403 / 无法推送**：检查仓库 Actions 权限、`publish` 的 `contents: write` 和 `output` 分支规则。
- **API 限流或临时网络失败**：旧图会保留，等待次日或手动重跑。
- **SVG 校验失败**：查看失败模块与生成库更新，不能跳过校验直接覆盖图片。
- **工作流被停用**：在 Actions 页面重新启用，再手动运行一次。
- **首次初始化**：必须先生成完整图片并核验状态，再将 README 切换到新路径。

GitHub 对长期无仓库活动的公开仓库可能暂停定时任务，且定时触发不保证准点。
本方案通过产物与状态提交持续记录活动，但不把它当作永不暂停的保证。
同一个被停用的工作流无法自我监控或自我恢复；如需无人值守的强提醒，需要额外独立的监控来源。
可在 GitHub 的 Notifications 设置中开启 Actions 失败通知；本仓库不会擅自创建邮件、Issue 或第三方通知。

官方规则：[schedule 的限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 本次整合前的盘点（2026-11-24）

| 原项目 | 问题 | 处理 |
| --- | --- | --- |
| `Github Data Board.yml` | 长期无活动停用；下载第三方错误图；输出与提交路径不一致；README 没有引用 | 删除，以 cards job 替代 |
| `Generate Snake.yml` | 长期无活动停用；旧令牌返回 401；最近产物停在 2026-06-12 | 合并到 snake job，使用自动令牌 |
| `assets/data_board_*.svg` | 内容是 `Maximum retries exceeded` 错误卡片 | 删除 |
| `assets/github-contribution-grid-snake.svg` | 主分支遗留文件，没有被当前 README 引用 | 删除，保留 output 分支产物 |
| README 的统计、项目卡片、贡献图 | 依赖多个外部在线生成服务 | 改为引用 output 分支静态 SVG |
| README 的分类标题 | 固定文字依赖外部打字服务 | 仓库内生成动画 SVG |

升级依赖时先改锁文件和固定版本，运行测试并核验实际图片，再合并；不要自动追随最新版本。
