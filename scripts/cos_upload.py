#!/usr/bin/env python3
"""通用单文件 COS 上传脚本（urllib 纯标准库版）。

本脚本不依赖 qcloud_cos SDK，仅使用 Python 标准库完成 COS 上传。
上传所需的临时凭证（secret_id/secret_key/token/bucket/region/cos_key/start_time/expired_time）
必须通过 ima-mcp 的 create_media 工具获取，然后通过以下任一方式传入：

方式1 — 环境变量（推荐）:
    export COS_SECRET_ID="..."
    export COS_SECRET_KEY="..."
    export COS_TOKEN="..."
    export COS_BUCKET="ima-media-prod-1258344701"
    export COS_REGION="ap-shanghai"
    export COS_KEY="..."
    export COS_START_TIME="..."
    export COS_EXPIRED_TIME="..."
    python cos_upload.py --file path/to/file.pdf

方式2 — 命令行参数:
    python cos_upload.py \
        --file path/to/file.pdf \
        --secret-id "..." --secret-key "..." --token "..." \
        --bucket "ima-media-prod-1258344701" --region "ap-shanghai" \
        --cos-key "..." --start-time "..." --expired-time "..."

注意：
- 临时凭证有效期通常只有数小时，过期后需重新调用 create_media 获取。
- 切勿将临时凭证硬编码到脚本中或提交到 Git 仓库。
- 本脚本仅完成 COS 上传，上传成功后还需调用 ima-mcp 的 add_knowledge
  将 media_id 关联到知识库。
"""

import argparse
import hashlib
import hmac
import os
import sys
import urllib.request
import urllib.error


def calc_cos_signature(secret_id, secret_key, method, path, headers, key_time):
    sign_key = hmac.new(secret_key.encode(), key_time.encode(), hashlib.sha1).hexdigest()
    header_keys = sorted(headers.keys())
    header_list = ";".join(header_keys)
    url_param_list = ""
    header_str = "&".join(f"{k}={headers[k]}" for k in header_keys)
    format_string = f"{method.lower()}\n/{path}\n{url_param_list}\n{header_str}\n"
    format_string_hash = hashlib.sha1(format_string.encode()).hexdigest()
    string_to_sign = f"sha1\n{key_time}\n{format_string_hash}\n"
    signature = hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()
    auth = (
        f"q-sign-algorithm=sha1"
        f"&q-ak={secret_id}"
        f"&q-sign-time={key_time}"
        f"&q-key-time={key_time}"
        f"&q-header-list={header_list}"
        f"&q-url-param-list={url_param_list}"
        f"&q-signature={signature}"
    )
    return auth


def upload_to_cos(file_path, secret_id, secret_key, token, bucket, region, cos_key, start_time, expired_time, content_type):
    key_time = f"{start_time};{expired_time}"
    host = f"{bucket}.cos.{region}.myqcloud.com"
    url = f"https://{host}/{cos_key}"

    with open(file_path, "rb") as f:
        file_data = f.read()

    sign_headers = {"host": host}
    auth = calc_cos_signature(secret_id, secret_key, "put", cos_key, sign_headers, key_time)

    headers = {
        "Authorization": auth,
        "x-cos-security-token": token,
        "Content-Type": content_type,
        "Content-Length": str(len(file_data)),
        "Host": host,
    }

    req = urllib.request.Request(url, data=file_data, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"  Upload successful! Status: {response.status}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  Upload FAILED! HTTP {e.code}")
        print(f"  Response: {body[:500]}")
        return False
    except Exception as e:
        print(f"  Upload FAILED! Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="使用 create_media 返回的临时凭证上传文件到 COS（标准库版）")
    parser.add_argument("--file", required=True, help="待上传的本地文件路径")
    parser.add_argument("--cos-key", default=os.environ.get("COS_KEY"), help="COS 目标对象键")
    parser.add_argument("--secret-id", default=os.environ.get("COS_SECRET_ID"), help="COS 临时 SecretId")
    parser.add_argument("--secret-key", default=os.environ.get("COS_SECRET_KEY"), help="COS 临时 SecretKey")
    parser.add_argument("--token", default=os.environ.get("COS_TOKEN"), help="COS 临时 Token")
    parser.add_argument("--bucket", default=os.environ.get("COS_BUCKET", "ima-media-prod-1258344701"), help="COS Bucket")
    parser.add_argument("--region", default=os.environ.get("COS_REGION", "ap-shanghai"), help="COS Region")
    parser.add_argument("--start-time", default=os.environ.get("COS_START_TIME"), help="COS 签名开始时间戳")
    parser.add_argument("--expired-time", default=os.environ.get("COS_EXPIRED_TIME"), help="COS 签名过期时间戳")
    parser.add_argument("--content-type", default=None, help="文件 MIME 类型（默认根据扩展名推断）")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: 文件不存在: {args.file}")
        sys.exit(1)

    required = {
        "COS_SECRET_ID": args.secret_id,
        "COS_SECRET_KEY": args.secret_key,
        "COS_TOKEN": args.token,
        "COS_KEY": args.cos_key,
        "COS_START_TIME": args.start_time,
        "COS_EXPIRED_TIME": args.expired_time,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"ERROR: 缺少必要参数/环境变量: {missing}")
        sys.exit(1)

    content_type = args.content_type
    if not content_type:
        ext = os.path.splitext(args.file)[1].lower()
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

    print(f"Uploading file: {args.file}")
    print(f"Bucket: {args.bucket}")
    print(f"Key: {args.cos_key}")

    with open(args.file, "rb") as f:
        file_size = len(f.read())
    print(f"File size: {file_size} bytes")

    success = upload_to_cos(
        args.file, args.secret_id, args.secret_key, args.token,
        args.bucket, args.region, args.cos_key,
        args.start_time, args.expired_time, content_type
    )

    if success:
        print("SUCCESS: File uploaded to COS!")
        print("\n下一步：调用 ima-mcp add_knowledge 将 media_id 关联到知识库。")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
