#!/usr/bin/env python3
"""批量 COS 上传脚本（urllib 签名版）。

本脚本用于一次性上传多个种子文件到 COS，供 ima 知识库使用。
上传所需的临时凭证由 ima-mcp 的 create_media 工具逐个文件获取。

使用方法:
    1. 为每个待上传文件调用 ima-mcp create_media，获取 cos_credential JSON。
    2. 将这些信息汇总成一个 manifest JSON 文件（见下方格式）。
    3. 运行本脚本:
        python upload_new_seeds.py --manifest upload_manifest.json

manifest.json 示例:
    [
      {
        "path": "D:/BidAgent-KB/seeds/标书核心法规汇编_v1.0.md",
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

注意：
- 临时凭证有效期通常只有数小时，过期后需重新调用 create_media 获取。
- 切勿将 manifest 文件提交到 Git 仓库（已加入 .gitignore 建议项）。
- 本脚本仅完成 COS 上传，上传成功后还需调用 ima-mcp 的 add_knowledge
  将 media_id 关联到知识库。
"""

import argparse
import hashlib
import hmac
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path


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


def upload_to_cos(file_path, cos_credential, content_type):
    secret_id = cos_credential["secret_id"]
    secret_key = cos_credential["secret_key"]
    token = cos_credential["token"]
    bucket = cos_credential["bucket_name"]
    region = cos_credential["region"]
    cos_key = cos_credential["cos_key"]
    start_time = cos_credential["start_time"]
    expired_time = cos_credential["expired_time"]

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
    parser = argparse.ArgumentParser(description="批量上传种子文件到 COS")
    parser.add_argument("--manifest", required=True, help="包含文件列表和 COS 凭证的 JSON 清单文件")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: 清单文件不存在: {manifest_path}")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        files = json.load(f)

    if not isinstance(files, list):
        print("ERROR: manifest 文件必须是一个 JSON 数组")
        sys.exit(1)

    results = []
    for i, f in enumerate(files):
        path = f.get("path", "")
        media_id = f.get("media_id", "")
        content_type = f.get("content_type", "text/markdown")
        cred = f.get("cos_credential", {})

        name = Path(path).name if path else f"<unknown-{i}>"
        print(f"\n[{i+1}/{len(files)}] Uploading: {name}")
        print(f"  media_id: {media_id}")

        required = ["secret_id", "secret_key", "token", "bucket_name", "region", "cos_key", "start_time", "expired_time"]
        missing = [k for k in required if k not in cred]
        if missing:
            print(f"  ERROR: cos_credential 缺少字段: {missing}")
            results.append({"file": path, "media_id": media_id, "success": False})
            continue

        success = upload_to_cos(path, cred, content_type)
        results.append({"file": path, "media_id": media_id, "success": success})

    print("\n--- Summary ---")
    for r in results:
        status = "OK" if r["success"] else "FAILED"
        name = Path(r["file"]).name if r["file"] else "<unknown>"
        print(f"  {status}: {name} -> media_id: {r['media_id']}")

    print("\n--- Media IDs for add_knowledge ---")
    for r in results:
        if r["success"]:
            print(r["media_id"])

    failed = [r for r in results if not r["success"]]
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
