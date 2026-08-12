# 变更记录

所有重要变更记录在此文件中。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

---

## [v1.1.0] - 2026-08-11

### 新增
- 新增 `expert_prompts/` 目录，导出 9 个专家 Prompt 文件（.md + plugin.json + README）
- 新增 `CONTRIBUTING.md` 社区贡献指南
- 新增 `CHANGELOG.md` 版本变更记录
- 新增 `shared_content/标书范文/` 目录结构
- 新增 `scripts/.env.example` 环境变量模板
- 新增 `scripts/README.md` 脚本使用说明
- README 新增「知识库搭建指南」章节（方案A: 种子文件随仓库 + 方案B: ima 共享知识库）

### 修复
- 清理 `upload_pdf.py`、`upload_new_seeds.py`、`cos_upload.py` 中的硬编码 COS 临时凭证
- 全局替换个人 ima 知识库 ID 为 `<YOUR_IMA_KB_ID>` 占位符（8个文件）
- `kb_config.json` 的 `base_path` 从 `D:\KB_manager` 改为空字符串（跨平台兼容）
- 重置 `kb_sync_log.json` 和 `kb_sync_result.json` 为初始状态
- 清理 `scripts/__pycache__/` 编译缓存
- 文档中"张臻的知识库"统一改为"你的知识库"
- 设计文档中 tencent-docs 状态从"未连接"改为"需连接"（开源通用描述）
- `guides/知识库使用指南.md` 清理个人 KB ID 和旧工作区路径
- `.gitignore` 新增 `upload_manifest*.json` 等含凭证临时文件的忽略规则

### 变更
- README 目录结构更新：`知识库管理/` → `scripts/`，`知识库种子内容/` → `seeds/`
- `kb_sync_manager.py` 默认 KB ID 改为空字符串
- `kb_init.py` 默认 KB ID 改为空字符串

---

## [v1.0.0] - 2026-08-10

### 新增
- 9 个专家智能体设计完成并部署（bid-analysis / tender-review / resource-matching / commercial-bid / technical-architect / technical-bid-writer / technical-review / bid-review / document-formatting）
- 5 个种子知识文件（废标条款模式库 / 标书核心法规汇编 / 行业技术标准库 / 招投标报价与商务法规专题库 / 资质等效替代规则库）
- 1 个行业技术标准 PDF（GBZ117-2022 工业探伤放射防护标准）
- 知识库管理脚本套件（11 个 .py + 3 个 .json）
- 系统设计文档（936 行，覆盖 9 个专家详细设计）
- 本地知识库搭建指南 + 10 个 CSV 模板
- ima 云端知识库部署（7 文件已同步）
- 模拟招标文件功能测试（解析专家评分 9.4/10）
- 真实招标实例功能测试（尚义县智慧政务项目，综合评分 8.7/10）
- MIT 开源许可证
- `.gitignore` 配置
