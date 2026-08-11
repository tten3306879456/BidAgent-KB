#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识库同步管理器 (kb_sync_manager.py)
=====================================
跟踪本地 .md 种子文件的修改状态，辅助同步到 ima 云端知识库。

用法:
  python kb_sync_manager.py check                    检查哪些 .md 文件有更新需要同步
  python kb_sync_manager.py status                   显示所有文件的同步状态
  python kb_sync_manager.py mark <filename>          标记文件已同步（上传成功后调用）
  python kb_sync_manager.py mark-all                 标记所有文件已同步
  python kb_sync_manager.py list                     列出所有跟踪的 .md 文件
  python kb_sync_manager.py upload <file> <creds>    使用 create_media 凭证上传文件到 COS

  <creds> 是 create_media 返回的 JSON 字符串，包含:
    secret_id, secret_key, token, bucket, region, cos_key, media_id

工作流程:
  1. 助手调用 create_media(MCP) 获取上传凭证
  2. 助手调用本脚本 upload 命令上传文件到 COS
  3. 助手调用 add_knowledge(MCP) 关联到知识库
  4. 助手调用本脚本 mark 命令更新同步记录
"""

import os
import sys
import json
import hashlib
import datetime
from pathlib import Path

# ============================================================
# 配置 — 优先读取 kb_config.json，找不到则用默认路径
# ============================================================

def _load_config():
    """加载配置文件，支持多种查找路径"""
    search_paths = [
        Path(__file__).parent / "kb_config.json",           # 脚本同目录
        Path(__file__).parent.parent / "知识库管理" / "kb_config.json",  # 项目内
    ]
    for p in search_paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                base = Path(cfg.get("base_path", ""))
                seed_rel = cfg.get("cloud_seed_dir", r"01_云端知识库\种子文件")
                log_rel = cfg.get("cloud_log_dir", r"01_云端知识库\同步日志")
                kb_id = cfg.get("ima_knowledge_base_id", "001a9d12b7c0755c")
                if base and base.exists():
                    return {
                        "seed_dir": base / seed_rel,
                        "sync_log": base / log_rel / "kb_sync_log.json",
                        "sync_result": base / log_rel / "kb_sync_result.json",
                        "kb_id": kb_id,
                    }
    # 没找到配置文件，用默认路径
    return {
        "seed_dir": Path(__file__).parent.parent / "知识库种子内容",
        "sync_log": Path(__file__).parent / "kb_sync_log.json",
        "sync_result": Path(__file__).parent / "kb_sync_result.json",
        "kb_id": "001a9d12b7c0755c",
    }

_cfg = _load_config()
SCRIPT_DIR = Path(__file__).parent
SEED_DIR = _cfg["seed_dir"]
SYNC_LOG = _cfg["sync_log"]
SYNC_RESULT = _cfg["sync_result"]
KB_ID = _cfg["kb_id"]

# 跳过的非种子文件
SKIP_FILES = {"ima建库操作指引.md"}


# ============================================================
# 工具函数
# ============================================================

def get_file_hash(filepath):
    """计算文件内容的 MD5 哈希"""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def get_file_size(filepath):
    """获取文件大小（人类可读）"""
    size = filepath.stat().st_size
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def load_sync_log():
    """加载同步日志"""
    if SYNC_LOG.exists():
        with open(SYNC_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"files": {}, "last_full_sync": None}


def save_sync_log(log):
    """保存同步日志"""
    with open(SYNC_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def scan_md_files():
    """扫描种子目录中的 .md 文件"""
    md_files = []
    if not SEED_DIR.exists():
        return md_files
    for f in sorted(SEED_DIR.glob("*.md")):
        if f.name in SKIP_FILES:
            continue
        md_files.append(f)
    return md_files


def format_time(iso_str):
    """格式化时间字符串"""
    if not iso_str:
        return "从未"
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str


# ============================================================
# 命令实现
# ============================================================

def cmd_check():
    """检查哪些 .md 文件有更新需要同步"""
    log = load_sync_log()
    md_files = scan_md_files()

    needs_sync = []
    up_to_date = []
    new_files = []

    for f in md_files:
        current_hash = get_file_hash(f)
        mod_time = datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat()
        size = get_file_size(f)

        if f.name not in log["files"]:
            new_files.append({
                "name": f.name,
                "path": str(f),
                "hash": current_hash,
                "modified": mod_time,
                "size": size,
                "status": "NEW"
            })
        else:
            entry = log["files"][f.name]
            if entry.get("hash") != current_hash:
                needs_sync.append({
                    "name": f.name,
                    "path": str(f),
                    "hash": current_hash,
                    "modified": mod_time,
                    "size": size,
                    "last_synced": entry.get("last_synced"),
                    "status": "UPDATED"
                })
            else:
                up_to_date.append({
                    "name": f.name,
                    "last_synced": entry.get("last_synced"),
                    "status": "SYNCED"
                })

    # 输出报告
    total = len(needs_sync) + len(new_files) + len(up_to_date)
    print(f"{'=' * 60}")
    print(f"  知识库同步检查报告")
    print(f"  检查时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  种子目录: {SEED_DIR}")
    print(f"  知识库ID: {KB_ID}")
    print(f"{'=' * 60}")
    print(f"\n  文件总数: {total}")
    print(f"  需要同步: {len(needs_sync) + len(new_files)}")
    print(f"  已是最新: {len(up_to_date)}")

    if new_files:
        print(f"\n{'─' * 60}")
        print(f"  新文件（从未同步到 ima）: {len(new_files)} 个")
        print(f"{'─' * 60}")
        for item in new_files:
            print(f"\n  [{item['status']}] {item['name']}")
            print(f"       路径: {item['path']}")
            print(f"       大小: {item['size']}")
            print(f"       修改: {format_time(item['modified'])}")

    if needs_sync:
        print(f"\n{'─' * 60}")
        print(f"  已更新（内容有变化，需重新上传）: {len(needs_sync)} 个")
        print(f"{'─' * 60}")
        for item in needs_sync:
            print(f"\n  [{item['status']}] {item['name']}")
            print(f"       路径: {item['path']}")
            print(f"       大小: {item['size']}")
            print(f"       修改: {format_time(item['modified'])}")
            print(f"       上次同步: {format_time(item['last_synced'])}")

    if up_to_date:
        print(f"\n{'─' * 60}")
        print(f"  已是最新（无需操作）: {len(up_to_date)} 个")
        print(f"{'─' * 60}")
        for item in up_to_date:
            print(f"  [{item['status']}] {item['name']}  (上次同步: {format_time(item['last_synced'])})")

    # 输出 JSON 供程序化处理
    result = {
        "check_time": datetime.datetime.now().isoformat(),
        "total": total,
        "needs_sync": len(needs_sync) + len(new_files),
        "up_to_date": len(up_to_date),
        "files_to_sync": new_files + needs_sync,
        "kb_id": KB_ID
    }
    
    result_path = SYNC_RESULT
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'=' * 60}")
    print(f"  结果已保存: {result_path}")
    print(f"{'=' * 60}")
    
    return result


def cmd_status():
    """显示所有文件的同步状态"""
    log = load_sync_log()
    md_files = scan_md_files()

    print(f"\n{'=' * 70}")
    print(f"  知识库同步状态总览")
    print(f"{'=' * 70}")
    print(f"  {'文件名':<40} {'状态':<10} {'上次同步':<20} {'大小':<10}")
    print(f"  {'─' * 66}")

    for f in md_files:
        current_hash = get_file_hash(f)
        size = get_file_size(f)

        if f.name not in log["files"]:
            status = "NEW"
            last_synced = "从未"
        else:
            entry = log["files"][f.name]
            if entry.get("hash") != current_hash:
                status = "UPDATED"
            else:
                status = "SYNCED"
            last_synced = format_time(entry.get("last_synced"))

        # 截断文件名
        display_name = f.name[:38] + ".." if len(f.name) > 40 else f.name
        print(f"  {display_name:<40} {status:<10} {last_synced:<20} {size:<10}")

    last_full = format_time(log.get("last_full_sync"))
    print(f"\n  上次完整同步: {last_full}")
    print(f"  同步日志: {SYNC_LOG}")
    print(f"{'=' * 70}\n")


def cmd_mark(filename):
    """标记文件已同步"""
    log = load_sync_log()
    filepath = SEED_DIR / filename

    if not filepath.exists():
        # 尝试模糊匹配
        matches = list(SEED_DIR.glob(f"*{filename}*"))
        if len(matches) == 1:
            filepath = matches[0]
            filename = filepath.name
        else:
            print(f"ERROR: 文件未找到: {filename}")
            if matches:
                print(f"  可能的匹配: {[m.name for m in matches]}")
            return False

    current_hash = get_file_hash(filepath)
    now = datetime.datetime.now().isoformat()

    log["files"][filename] = {
        "hash": current_hash,
        "last_synced": now,
        "path": str(filepath),
        "sync_count": log.get("files", {}).get(filename, {}).get("sync_count", 0) + 1
    }

    save_sync_log(log)
    print(f"OK: 已标记 '{filename}' 为已同步")
    print(f"     同步时间: {format_time(now)}")
    print(f"     文件哈希: {current_hash[:16]}...")
    print(f"     累计同步: {log['files'][filename]['sync_count']} 次")
    return True


def cmd_mark_all():
    """标记所有文件已同步"""
    log = load_sync_log()
    md_files = scan_md_files()
    now = datetime.datetime.now().isoformat()
    count = 0

    for f in md_files:
        current_hash = get_file_hash(f)
        log["files"][f.name] = {
            "hash": current_hash,
            "last_synced": now,
            "path": str(f),
            "sync_count": log.get("files", {}).get(f.name, {}).get("sync_count", 0) + 1
        }
        count += 1

    log["last_full_sync"] = now
    save_sync_log(log)
    print(f"OK: 已标记 {count} 个文件为已同步")
    print(f"     完整同步时间: {format_time(now)}")


def cmd_list():
    """列出所有跟踪的 .md 文件"""
    md_files = scan_md_files()
    log = load_sync_log()

    print(f"\n{'=' * 60}")
    print(f"  跟踪的种子文件 ({len(md_files)} 个)")
    print(f"{'=' * 60}")

    for i, f in enumerate(md_files, 1):
        size = get_file_size(f)
        current_hash = get_file_hash(f)
        mod_time = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

        if f.name in log["files"]:
            synced = format_time(log["files"][f.name].get("last_synced"))
            in_log = "YES"
        else:
            synced = "从未"
            in_log = "NO"

        print(f"\n  {i}. {f.name}")
        print(f"     路径: {f}")
        print(f"     大小: {size}")
        print(f"     修改: {mod_time}")
        print(f"     同步: {synced}")

    print(f"\n{'=' * 60}\n")


def cmd_upload(file_path, creds_json):
    """使用 create_media 凭证上传文件到 COS"""
    try:
        creds = json.loads(creds_json)
    except json.JSONDecodeError as e:
        print(f"ERROR: 凭证JSON解析失败: {e}")
        return False

    required = ["secret_id", "secret_key", "token", "bucket", "region", "cos_key"]
    for key in required:
        if key not in creds:
            print(f"ERROR: 凭证缺少字段: {key}")
            return False

    file_path = Path(file_path)
    if not file_path.exists():
        print(f"ERROR: 文件不存在: {file_path}")
        return False

    # 确定 ContentType
    ext = file_path.suffix.lower()
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
        print("ERROR: cos-python-sdk-v5 未安装，正在安装...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cos-python-sdk-v5", "-q"])
        from qcloud_cos import CosConfig, CosS3Client

    # 创建 COS 客户端
    config = CosConfig(
        Region=creds["region"],
        SecretId=creds["secret_id"],
        SecretKey=creds["secret_key"],
        Token=creds["token"],
        Scheme="https"
    )
    client = CosS3Client(config)

    # 读取文件
    with open(file_path, "rb") as f:
        file_data = f.read()

    file_size = len(file_data)
    print(f"上传文件: {file_path.name}")
    print(f"文件大小: {file_size} bytes ({file_size / 1024:.1f} KB)")
    print(f"目标: {creds['bucket']}/{creds['cos_key']}")

    try:
        response = client.put_object(
            Bucket=creds["bucket"],
            Body=file_data,
            Key=creds["cos_key"],
            ContentType=content_type
        )
        etag = response.get("ETag", "")
        print(f"\nSUCCESS: 文件上传成功!")
        print(f"  ETag: {etag}")
        if "media_id" in creds:
            print(f"  media_id: {creds['media_id']}")
            print(f"\n下一步: 调用 add_knowledge(media_id='{creds['media_id']}', knowledge_base_id='{KB_ID}')")
        return True
    except Exception as e:
        print(f"\nFAILED: 上传失败: {e}")
        return False


# ============================================================
# 主入口
# ============================================================

def print_usage():
    print("""
知识库同步管理器
================

用法:
  python kb_sync_manager.py check                  检查哪些 .md 文件有更新需要同步
  python kb_sync_manager.py status                 显示所有文件的同步状态
  python kb_sync_manager.py mark <filename>        标记文件已同步
  python kb_sync_manager.py mark-all               标记所有文件已同步
  python kb_sync_manager.py list                   列出所有跟踪的 .md 文件
  python kb_sync_manager.py upload <file> <creds>  上传文件到 COS

示例:
  python kb_sync_manager.py check
  python kb_sync_manager.py status
  python kb_sync_manager.py mark 行业技术标准库_种子版.md
  python kb_sync_manager.py mark-all
  python kb_sync_manager.py upload "D:\\path\\to\\file.md" '{"secret_id":"...","secret_key":"...","token":"...","bucket":"...","region":"...","cos_key":"...","media_id":"..."}'
""")


def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    cmd = sys.argv[1].lower()

    if cmd == "check":
        cmd_check()
    elif cmd == "status":
        cmd_status()
    elif cmd == "mark":
        if len(sys.argv) < 3:
            print("ERROR: 请指定文件名")
            print("  用法: python kb_sync_manager.py mark <filename>")
            return
        cmd_mark(sys.argv[2])
    elif cmd == "mark-all":
        cmd_mark_all()
    elif cmd == "list":
        cmd_list()
    elif cmd == "upload":
        if len(sys.argv) < 4:
            print("ERROR: 请指定文件路径和凭证JSON")
            print('  用法: python kb_sync_manager.py upload <file> \'{"secret_id":"...",...}\'')
            return
        cmd_upload(sys.argv[2], sys.argv[3])
    else:
        print(f"ERROR: 未知命令: {cmd}")
        print_usage()


if __name__ == "__main__":
    main()
