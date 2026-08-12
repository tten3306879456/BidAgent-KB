# 变更记录

所有重要变更记录在此文件中。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

---

## [v1.3.0] - 2026-08-12

### 新增
- **部署向导** `scripts/setup_wizard.py` — 交互式引导开源用户完成全流程部署（环境检查→虚拟环境→依赖安装→后端选择→.env生成→渠道配置→验证测试），支持 `--quick` / `--check` / `--skip-venv` 参数
- **部署指南** `docs/部署指南.md` — 完整的开源用户部署文档，覆盖三种部署模式（快速/标准/完整）、知识库后端配置、渠道配置、WorkBuddy 专家导入、常见问题排查、升级指南
- **Makefile** — 一键命令（make setup / make quick / make check / make search / make channels / make send / make clean 等）
- **渠道消息推送** `scripts/channel_notify.py` — 飞书/钉钉/企业微信/微信四个渠道，纯标准库实现，支持 `update_credentials()` 动态凭证更新、CLI `update --save` 持久化、`--test` 更新后测试
- **交互界面原型** `docs/交互界面原型.html` 新增第7节渠道配置（飞书/钉钉/企业微信/微信），精简环境变量为5条必填项

### 修复
- 修复 `kb_init.py` 过时路径引用：`知识库种子内容` → `seeds`，`本地知识库搭建指南` → `guides/本地知识库搭建指南`
- 修复 `scripts/.env.example` 引用已删除的 `upload_pdf.py` → `cos_upload.py`
- 修复 `kb_ima.py` 的 `resolve_kb()` 方法参数名不匹配（`kb_name_or_id` → `kb_name`）
- 修复 `kb_auto_index.py` 空 `base_path` 误判问题 + 回退目录名错误

### 变更
- `.env.example` 新增 4 个渠道共 13 条环境变量模板
- `kb_config.json` 的 `script_files` 注册 `setup_wizard.py` 和 `channel_notify.py`
- `scripts/README.md` 新增「首次部署」章节和 `setup_wizard.py` / `channel_notify.py` 文档
- `.gitignore` 新增 `scripts/kb_sync_result.json`（运行时数据含本地路径）
- 重置 `scripts/kb_sync_result.json` 为初始空状态
- 清理临时文件 `.tmp_update_env.py`
- README 快速开始章节新增部署向导入口和部署指南链接

---

## [v1.2.1] - 2026-08-12

### 修复
- 同步更新开源用户互动界面，使其与 5 座知识库架构一致：
  - `README.md`：修复 7 处不同步（架构图种子描述、方案A文件列表 7→15、方案B知识库表格旧4库→新5库、配置示例 public_kb_id→shared_kbs、共享知识库章节 3 库"待创建"→全部 5 座"已建成"、目录结构种子列表、FAQ 种子文件数）
  - `CONTRIBUTING.md`：贡献类型和社区共享库章节更新为 5 座 KB 体系
  - `guides/知识库使用指南.md`：v1.0→v2.0，修复 13 处不同步（架构图、目录结构、种子文件表、自动分类规则、示例输出、数据安全分级表、附录配置示例）
  - `scripts/README.md`：manifest 示例引用已删除文件 → 当前文件
  - `scripts/upload_new_seeds.py`：docstring 引用已删除文件 → 当前文件
  - `seeds/ima建库操作指引.md`：文件计数 13→15
  - `seeds/软件开发标书知识库_种子版.md`：交叉引用旧文件名 → 新文件名

---

## [v1.2.0] - 2026-08-12

### 新增
- 在 ima 云端创建 3 个新共享知识库：标书法规库、标书案例库、投标文件编辑模板库
- 互联网检索 2024-2025 年最新知识，新增多个种子文件：
  - `标书法规库_2024-2025新增法规.md`（8部新法规要点）
  - `标书案例库_2024-2025典型案例.md`（10个典型废标案例）
  - `软件行业标准_2024-2025更新.md`（9项新标准更新，含信创/等保81项高风险判例等）
- 从互联网搜集标书写作模板，新增 4 个模板文件填充投标文件编辑模板库：
  - `投标文件通用框架与封面模板.md`（标准目录结构、封面格式、编排规范）
  - `商务标书模板_投标函与响应表.md`（投标函/授权书/报价表/开标一览表模板）
  - `技术标书模板_信息化项目方案框架.md`（信息化项目技术方案五章框架）
  - `评分响应与偏离表模板集.md`（偏离表/评分索引表/业绩表/承诺函模板）
- `kb_config.json` 扩展为 5 个共享知识库配置，`shared_kbs` 字典 + `shared_content.categories` 全新职责描述
- `ima建库操作指引.md` 和 `共享知识库贡献指南.md` 更新为 5 座知识库体系

### 变更
- **重新定义 5 座共享知识库职责（互斥）**：
  - 标书法规库 = 招投标法律条文
  - 标书案例库 = 废标案例
  - 投标文件编辑模板库 = 投标编辑模板
  - 软件开发标书知识库 = 软件行业标准
  - 核工业标书知识库 = 核工业标准
- 拆分 `行业技术标准库_种子版.md` 为 `行业技术标准_软件开发部分.md`（→软件开发库）和 `GBZ117等核工业标准.md`（→核工业库）
- 重命名 `标书模板库_2024-2025标准更新.md` → `软件行业标准_2024-2025更新.md`（归位软件开发库）
- 删除冗余的 `upload_pdf.py`（SDK 版单文件上传），功能由 `cos_upload.py`（标准库版，零依赖）统一承担
- 清理 `scripts/README.md` 和 `README.md` 中关于 `upload_pdf.py` 的过时引用
- `kb_config.json` 的 `seed_files` 从 7 个扩展为 15 个，`script_files` 从 3 个扩展为 7 个

### 修复
- 修复 6 个维护脚本以适配 5 座多 KB 路由架构：
  - `kb_ima.py` (P0)：整体重写 v2.0，新增 `resolve_kb()` 路由方法，支持按文件名自动路由到对应知识库
  - `kb_sync_manager.py` (P0)：修复 `shared_kbs` 配置读取路径、空 `base_path` 误判问题，新增 KB 归属跟踪
  - `kb_backend.py` (P0)：修复 `both` 模式判断条件，检查 `shared_kbs` 而非旧的单 KB 字段
  - `kb_auto_index.py` (P1)：重写 CATEGORIES 字典为 5 库 15 文件，新增 `template` 模板类型和摘要生成方法
  - `kb_init.py` (P1)：更新默认配置，移除 `ima_knowledge_base_id`，`seed_files` 更新为 15 个
  - `kb_setup.py` (P2)：`init_ima` 函数显示 5 座 `shared_kbs` 配置状态
- 解决 COS 临时凭证失效导致的 2 个文件上传失败
- 解决 `media_id` 笔误导致的 1 个文件 `add_knowledge` 入库失败
- 解决 `kb_sync_manager.py` 空 `base_path` 导致 `Path("")` = `.` 误判为存在的路径

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
