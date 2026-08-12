# 知识库管理脚本说明

本目录包含标书智能体项目的知识库管理脚本。

## 首次部署

**新用户请先运行部署向导：**

```bash
# 交互式部署（推荐）
python scripts/setup_wizard.py

# 快速部署（全默认值）
python scripts/setup_wizard.py --quick --skip-venv

# 仅检查环境
python scripts/setup_wizard.py --check
```

详细部署步骤见 [部署指南](../docs/部署指南.md)。

## 目录

| 脚本 | 功能 | 是否需要 ima 账号 |
|---|---|---|
| `setup_wizard.py` | 部署向导（首次使用，交互式引导） | 否 |
| `kb_setup.py` | 一键初始化知识库后端 | 可选 |
| `kb_init.py` | 创建本地知识库目录结构 | 否 |
| `kb_backend.py` | 后端抽象层（local_search / ima / chromadb / both） | 否 |
| `kb_local_search.py` | 本地全文检索后端（默认，零依赖） | 否 |
| `kb_ima.py` | ima 云端检索后端 | 是 |
| `kb_chromadb.py` | ChromaDB 向量检索后端（高级） | 否 |
| `kb_auto_index.py` | 自动索引本地种子文件 | 否 |
| `kb_sync_manager.py` | 跟踪种子文件变更、辅助同步到 ima | 是（同步时） |
| `cos_upload.py` | 单文件 COS 上传（Python 标准库版，零依赖） | 是（上传时） |
| `upload_new_seeds.py` | 批量 COS 上传 | 是（上传时） |
| `channel_notify.py` | 渠道消息推送（飞书/钉钉/企业微信/微信） | 否 |

## 上传到 ima 知识库的工作流程

由于 ima 上传需要腾讯云 COS 临时凭证，完整流程需要 **WorkBuddy AI 助手** 和 **本地脚本** 配合：

```
你/AI 在 WorkBuddy 中调用 ima-mcp create_media
        ↓
获得临时凭证（secret_id, secret_key, token, bucket, region, cos_key, media_id）
        ↓
将凭证填入 .env 或传给脚本参数
        ↓
运行本目录下的上传脚本
        ↓
你/AI 在 WorkBuddy 中调用 ima-mcp add_knowledge 完成入库
```

## 单文件上传示例

### 方式1：环境变量（推荐）

```bash
cd scripts
cp .env.example .env
# 编辑 .env 填入 create_media 返回的临时凭证
python cos_upload.py --file ../seeds/标书核心法规汇编_v1.0.md
# 使用完成后
rm .env
```

### 方式2：命令行参数

```bash
python cos_upload.py \
  --file ../seeds/标书核心法规汇编_v1.0.md \
  --secret-id "..." --secret-key "..." --token "..." \
  --bucket "ima-media-prod-1258344701" --region "ap-shanghai" \
  --cos-key "..." --start-time "..." --expired-time "..."
```

## 批量上传示例

1. 准备 manifest JSON 文件（每个文件对应一组 create_media 凭证）：

```json
[
  {
    "path": "../seeds/标书核心法规汇编_v1.0.md",
    "media_id": "markdown_...",
    "cos_credential": {
      "secret_id": "...",
      "secret_key": "...",
      "token": "...",
      "bucket_name": "ima-media-prod-1258344701",
      "region": "ap-shanghai",
      "cos_key": "2/.../file_manager/....md",
      "start_time": "1786337999",
      "expired_time": "1786381199"
    },
    "content_type": "text/markdown"
  }
]
```

2. 运行批量上传：

```bash
python upload_new_seeds.py --manifest upload_manifest.json
```

3. 脚本会输出所有成功上传的 `media_id`，然后由 AI 调用 `add_knowledge` 入库。

## 安全提醒

- `.env`、`*_manifest.json` 等含凭证的文件**严禁提交到 Git**，已加入项目根目录 `.gitignore`。
- COS 临时凭证有效期通常只有数小时，过期后需重新调用 `create_media`。
- 上传完成后应立即删除或清空本地 `.env` 和 manifest 文件。
- 上传到 ima 共享库的内容必须是公开/脱敏知识，**禁止上传公司敏感数据**。

## 渠道消息推送

`channel_notify.py` 提供统一接口向飞书、钉钉、企业微信、微信公众号推送通知消息，纯 Python 标准库实现，零第三方依赖。

### 支持渠道

| 渠道 | 推送方式 | 必填环境变量 |
|------|---------|-------------|
| 飞书 | Webhook 机器人 | `FEISHU_WEBHOOK_URL` |
| 钉钉 | Webhook 机器人（支持加签） | `DINGTALK_WEBHOOK_URL` |
| 企业微信 | 应用消息 API | `WECOM_CORP_ID` + `WECOM_SECRET` + `WECOM_AGENT_ID` |
| 微信公众号 | 客服消息 API | `WECHAT_APP_ID` + `WECHAT_APP_SECRET` |

### 配置

在项目根目录 `.env` 文件中填写渠道环境变量（参考 `.env.example`），或通过交互界面原型导出。

### 使用方式

```bash
# 列出已配置的渠道
python channel_notify.py list

# 测试所有已配置渠道的连接
python channel_notify.py test

# 测试单个渠道
python channel_notify.py test feishu

# 发送文本消息到所有渠道
python channel_notify.py send "标书审核完成，请查阅"

# 发送到指定渠道
python channel_notify.py send "消息内容" -c dingtalk

# 以 Markdown 格式发送
python channel_notify.py send "## 标题\n正文内容" --markdown

# 指定接收人（企业微信/微信）
python channel_notify.py send "消息" --touser @all
```

### 模块导入

```python
from channel_notify import notify_all, test_all, load_notifiers

# 发送到所有已配置渠道
results = notify_all("标书审核完成", title="通知")
# -> {"feishu": {"success": True, "message": "..."}, ...}

# 测试连接
results = test_all()

# 获取已配置的通知器列表
notifiers = load_notifiers()
for n in notifiers:
    print(f"{n.display_name}: configured={n.is_configured()}")
```
