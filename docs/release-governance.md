# 发布 / 回滚 规范（Free-Model-Probe 本地化）

> **来源与权威**：公共条款见 `ReSerendipity/.github` 的 `REPOSITORY_GUIDELINES.md` §10（发布 / 分发统一规范）。
> 本文件是本仓按该节模板落地的 `docs/release-governance.md`，只填本仓特有内容，不重写、不抵触 §10 公共条款。

---

## 0. 远端优先（根原则，不可改写）

发布链的构建、打包、扫描、上传、推送**全部在 GitHub Actions 远端完成**；本地只做三件事：改版本位、落 CHANGELOG、`git tag` + `git push`。本地不执行打包 / 镜像构建 / 发布上传。

本仓当前**暂无发布产物**（见 §4 判断依据），因此本节所描述的远端发布链**尚未触发**；一旦将来出现可分发产物，必须按本原则在远端 Actions 中构建，不得在本地产出交付物后手工上传。

## 1. 版本号规范

- 遵循 **SemVer** `MAJOR.MINOR.PATCH`；预发布用 `-alpha.N` / `-beta.N` / `-rc.N`。
- **唯一权威版本位**：待定（负责人+触发条件）——本仓目前无 `pyproject.toml` / `setup.cfg` / `package.json` / `config.yaml` 等版本声明文件，亦无任何 git tag；首个 semver tag 建立时，须同步选定一个唯一权威版本位并回填本节。
- 必须同步的其它版本位：无（当前无版本位）。
- 版本位漂移校验入口：待定（负责人+触发条件）——待权威版本位确定后，参照 TTS-MultiModel `tests/test_version_consistency.py` 建立跨版本位一致性检查。
- 自动化方式：手动 tag（人工）。不使用 release-please。

## 2. CHANGELOG 管理

- 遵循 **Keep a Changelog**：`Added / Changed / Fixed / Deprecated / Removed / Security`。
- 每次合并 `main` 在 `[Unreleased]` 追加；type 映射 `feat→Added`、`fix→Fixed`、`refactor→Changed`。
- 发版时 `[Unreleased]` → `[VERSION] - YYYY-MM-DD`。
- **当前状态**：仓内已建立根 `CHANGELOG.md`（Keep a Changelog 结构，C-12 补建 PR 落地）。当前仍无 `v*` tag / Release，`[Unreleased]` 段仅含提交历史归类；首个正式发布时按 §10.2 将 `[Unreleased]` → `[VERSION] - YYYY-MM-DD`。

## 3. 发布流程（远端）

1. 确认 `[Unreleased]` 条目完整
2. 同步版本位（见 §1 清单）
3. 本地打 tag 并推送：`git tag v<X.Y.Z>` → `git push origin v<X.Y.Z>`
4. 远端凭 tag 触发发布 workflow 构建产物
5. 远端建 **draft Release** 并挂资产 → 人工审核后 `published`
6. 盯到终态：`gh run list` 确认绿；红了当场修或 revert 止损

> 当前阶段：本仓无可分发产物，上述流程**暂不执行**；待出现产物后再建 tag 驱动的 `release.yml`。

## 4. 分发产物与完整性

### 4.1 当前判断：暂无发布产物，发布链待需要时再建

**判断依据（逐项排查）**：

| 排查项 | 本仓现状 | 是否构成可分发产物 |
|---|---|---|
| Python 包（wheel/sdist） | 无 `pyproject.toml` / `setup.py` / `setup.cfg`，亦无 `requirements.txt`；代码以脚本形式直接运行 | 否 |
| 容器镜像（ghcr.io） | 无 `Dockerfile` / `docker-compose.yml`；`.github/workflows/` 下仅 `ci.yml`（语法门禁 + 密钥扫描），无 `docker/build-push-action` | 否 |
| 桌面安装包（Tauri / NSIS / APK） | 无 Tauri 配置、无 Android 工程、无 NSIS 脚本；`webui/server.py` 为纯标准库 `http.server`，由用户本机 `python server.py` 启动 | 否 |
| npm 包 | 无 `package.json` | 否 |
| 可独立交付的二进制 / 归档 | 无构建脚本产出物；`providers/*/最终报告/` 下的 HTML/CSV 是脚本运行时在本地生成的调研产物，非版本化分发物 | 否 |

**结论**：本仓定位为「本地 / 自部署」的模型清单调研与连通性测试工具集（见 `ci.yml` 顶部注释与 README），用户 clone 后直接运行 Python 脚本使用，无需要打包分发的产物。因此**当前不建 `release.yml`、不挂 Release 资产、不生成 SHA256SUMS**。

**触发条件**：当本仓出现以下任一情形时，再按 §10 建最小 tag 驱动发布链（`release.yml` + 产物 `SHA256SUMS.txt`）：
- 引入 `pyproject.toml` 并计划发布到 PyPI；
- 新增 `Dockerfile` 并计划推 ghcr.io；
- 新增 Tauri / 桌面安装包构建；
- 其它需要对最终用户分发二进制或归档的场景。

届时本文件 §4.2 起的表格与约束须同步补全。

### 4.2 未来产物的完整性约束（占位，待产物出现时生效）

| 产物 | 构建位置 | 标签 / 命名 | 完整性手段 |
|---|---|---|---|
| 待定（wheel / sdist / 容器镜像 / 归档，视将来形态定） | **远端** | 不可变 semver + sha；**禁 floating `latest`** | `SHA256SUMS.txt`；**不使用 GPG 分离签名**（2026-10-18 裁决） |

- 若将来推容器镜像：推 `ghcr.io`，`packages: write`；tag 取 semver + `sha`，不得以 `latest` 作发布基线；镜像名全小写；发布前经 Trivy `CRITICAL,HIGH`（`ignore-unfixed`）阻断；开 `provenance: true` + `sbom: true`。
- **不引入 `latest`**；**不新建或保留任何 GPG 签名流程**。

## 5. 回滚

- **判定**（满足任一即触发）：`ci.yml` 的 Python 语法门禁（`py_compile`）或 secret-guard 在 main 推送后变红；离线单测 `python -m unittest discover -s tests` 出现回归。
- **执行**：`git revert <bad-commit>`（保历史、可再 forward）；本仓无部署态、无远端服务需回滚。
- **破坏性动作**：重指向 / 删除 tag、移动任何远端 ref → **须仓库所有者单独授权**。本仓当前无 tag，亦无此风险。
- **回滚后验证**：`python -m unittest discover -s tests -v` 全绿；`python -m py_compile $(find . -name '*.py')` 通过。

## 6. SLA / 错误预算

- 本仓为本地工具、无常驻服务、无对外 SLA，**不适用可用性错误预算**。
- 若将来部署为远端服务，再按 §10 补目标可用性与错误预算。

## 7. 发布前检查清单

- [ ] 版本位全部同步（见 §1 清单）
- [ ] CHANGELOG `[Unreleased]` 已改版本 + 日期
- [ ] `python -m unittest discover -s tests -v` 通过
- [ ] `python -m py_compile $(find . -name '*.py')` 全绿（与 `ci.yml` syntax 作业同口径）
- [ ] 镜像类仓（未来若有）：Trivy 阻断通过，豁免已在 `.trivyignore.yaml` 登记理由 + expiration
- [ ] 镜像类仓（未来若有）：`provenance: true` + `sbom: true` 已开
- [ ] **本地未产出任何发布交付物**（全部远端构建）——当前无产物，此条自然满足

---

## 差异点采集清单（本仓取值）

| 占位符 | 采集来源 | 本仓取值 |
|---|---|---|
| 版本位文件与字段 | 仓内版本声明 | 无（待定：首个 tag 建立时选定） |
| 其它需同步版本位 | `grep -rn` 版本串 | 无 |
| 版本一致性校验入口 | `tests/**` | `tests/test_offline.py`（离线纯函数单测，无版本一致性检查）；待定 |
| 自动化方式 | `.github/workflows/` | 手动 tag（无 release-please） |
| 发布 workflow 文件名 | `.github/workflows/` | 无（当前仅 `ci.yml`）；待产物出现时建 `release.yml` |
| 产物形态与标签规则 | 构建 workflow | 无可分发产物（见 §4.1） |
| 完整性手段 | Release 资产清单 | 无（待产物出现后用 `SHA256SUMS.txt`，不用 GPG） |
| 回滚判定阈值 | 运行手册 / 监控 | CI 语法门禁 / secret-guard 变红；离线单测回归 |
| 回滚后验证命令 | `tests/smoke` 等 | `python -m unittest discover -s tests -v` + `py_compile` |
| 技术栈 | 代码结构 | 纯 Python 标准库（无第三方依赖），本地 webui + providers 脚本 |
| 部署目标 | deploy/ / Pages workflow | 本地运行（`python webui/server.py` / `start_webui.bat`），无远端部署 |

## 禁止事项

- 不重写 §10 公共条款（远端优先、tag 驱动、版本位一致、不可变标签、扫描阻断、无 GPG）。
- 不引入 `latest` 作发布基线；不保留或新建 GPG 签名流程。
- 不留空占位符；未确定项已标注「待定（负责人+触发条件）」。
