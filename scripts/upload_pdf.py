#!/usr/bin/env python3
"""通用单文件 COS 上传脚本（qcloud_cos SDK 版）。

本脚本用于将本地文件上传到腾讯云 COS，供 ima 知识库使用。
上传所需的临时凭证（secret_id/secret_key/token/bucket/region/cos_key）
必须通过 ima-mcp 的 create_media 工具获取，然后通过以下任一方式传入：

方式1 — 环境变量（推荐，避免命令行历史泄漏）:
    export COS_SECRET_ID="..."
    export COS_SECRET_KEY="..."
    export COS_TOKEN="..."
    export COS_BUCKET="ima-media-prod-1258344701"
    export COS_REGION="ap-shanghai"
    python upload_pdf.py --file path/to/file.pdf --cos-key "..."

方式2 — 命令行参数:
    python upload_pdf.py \
        --file path/to/file.pdf \
        --secret-id "..." --secret-key "..." --token "..." \
        --bucket "ima-media-prod-1258344701" --region "ap-shanghai" \
        --cos-key "..."

注意：
- 临时凭证有效期通常只有数小时，过期后需重新调用 create_media 获取。
- 切勿将临时凭证硬编码到脚本中或提交到 Git 仓库。
- 本脚本仅完成 COS 上传，上传成功后还需调用 ima-mcp 的 add_knowledge
  将 media_id 关联到知识库。
"""

import argparse
import os
import sys


def get_env_or_arg(name, arg_value, required=True):
    """优先使用命令行参数，其次环境变量。"""
    value = arg_value or os.environ.get(name)
    if required and not value:
        print(f"ERROR: 缺少必要参数/环境变量: {name} (或对应命令行参数)")
        sys.exit(1)
    return value


def main():
    parser = argparse.ArgumentParser(
        description="使用 create_media 返回的临时凭证上传文件到 COS"
    )
    parser.add_argument("--file", required=True, help="待上传的本地文件路径")
    parser.add_argument("--cos-key", required=True, help="COS 目标对象键（create_media 返回）")
    parser.add_argument("--secret-id", default=os.environ.get("COS_SECRET_ID"), help="COS 临时 SecretId")
    parser.add_argument("--secret-key", default=os.environ.get("COS_SECRET_KEY"), help="COS 临时 SecretKey")
    parser.add_argument("--token", default=os.environ.get("COS_TOKEN"), help="COS 临时 Token")
    parser.add_argument("--bucket", default=os.environ.get("COS_BUCKET", "ima-media-prod-1258344701"), help="COS Bucket")
    parser.add_argument("--region", default=os.environ.get("COS_REGION", "ap-shanghai"), help="COS Region")
    parser.add_argument("--content-type", default=None, help="文件 MIME 类型（默认根据扩展名推断）")
    args = parser.parse_args()

    file_path = args.file
    cos_key = args.cos_key
    secret_id = args.secret_id
    secret_key = args.secret_key
    token = args.token
    bucket = args.bucket
    region = args.region

    if not os.path.exists(file_path):
        print(f"ERROR: 文件不存在: {file_path}")
        sys.exit(1)

    # 推断 Content-Type
    content_type = args.content_type
    if not content_type:
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            ".md": "text/markdown",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }
        content_type = content_types.get(ext, "application/octet-stream")

    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        print("ERROR: 缺少 cos-python-sdk-v5，请先安装:")
        print("  pip install cos-python-sdk-v5")
        sys.exit(1)

    config = CosConfig(
        Region=region,
        SecretId=secret_id,
        SecretKey=secret_key,
        Token=token,
        Scheme="https",
    )
    client = CosS3Client(config)

    print(f"Uploading file: {file_path}")
    print(f"Bucket: {bucket}")
    print(f"Key: {cos_key}")

    with open(file_path, "rb") as f:
        file_data = f.read()

    print(f"File size: {len(file_data)} bytes")

    try:
        response = client.put_object(
            Bucket=bucket,
            Body=file_data,
            Key=cos_key,
            ContentType=content_type,
        )
        etag = response.get("ETag", "")
        print(f"ETag: {etag}")
        print("SUCCESS: File uploaded to COS!")
        print("\n下一步：调用 ima-mcp add_knowledge 将 media_id 关联到知识库。")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
