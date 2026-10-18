# Changelog

本项目的所有重要变更均记录于此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> 本仓库目前**尚未建立版本化发布**：无 `v*` git tag、无 GitHub Release，因此暂无真实版本号与发布日期。以下条目按 `docs/release-governance.md` §10.2 口径依据提交标题归类（`feat→Added`、`fix→Fixed`、`refactor→Changed`）；首个版本化发布时，将 `[Unreleased]` 转为 `[VERSION] - YYYY-MM-DD`。

## [Unreleased]

### Added

- feat(modelscope): 探测留痕，dead 候选后续轮自动跳过并记账

### Fixed

- fix(modelscope): 详情缓存改绝对 TTL（不再滑动续期，兑现 readme 的 24h 上限）；meta.json 落 bench_warns
- fix(openrouter): 删除从测试脚本源码里正则抠 API_KEY 的兜底（密钥不应作为跨文件回退源）
- fix(openrouter): 无 API KEY 时不再请求 /auth/key，也不再落 key_info.json；with 语句收口文件句柄
