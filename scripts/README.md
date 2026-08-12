# 知识库管理脚本说明

本目录包含标书智能体项目的知识库管理脚本。

## 目录

| 脚本 | 功能 | 是否需要 ima 账号 |
|---|---|---|
| `kb_setup.py` | 一键初始化知识库后端 | 可选 |
| `kb_init.py` | 创建本地知识库目录结构 | 否 |
| `kb_backend.py` | 后端抽象层（local_search / ima / chromadb / both） | 否 |
| `kb_local_search.py` | 本地全文检索后端（默认，零依赖） | 否 |
| `kb_ima.py` | ima 云端检索后端 | 是 |
| `kb_chromadb.py` | ChromaDB 向量检索后端（高级） | 否 |
| `kb_auto_index.py` | 自动索引本地种子文件 | 否 |
| `kb_sync_manager.py` | 跟踪种子文件变更、辅助同步到 ima | 是（同步时） |
| `upload_pdf.py` | 单文件 COS 上传（qcloud_cos SDK 版） | 是（上传时） |
| `cos_upload.py` | 单文件 COS 上传（Python 标准库版） | 是（上传时） |
| `upload_new_seeds.py` | 批量 COS 上传 | 是（上传时） |

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

SDK 版脚本 `upload_pdf.py` 用法相同，但依赖 `cos-python-sdk-v5`：

```bash
pip install cos-python-sdk-v5
python upload_pdf.py --file ../seeds/标书核心法规汇编_v1.0.md --cos-key "..."
```

## 批量上传示例

1. 准备 manifest JSON 文件（每个文件对应一组 create_media 凭证）：

```json
[
  {
    "path": "../seeds/行业技术标准库_种子版.md",
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
