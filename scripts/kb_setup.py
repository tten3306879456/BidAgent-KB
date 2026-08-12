#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库一键初始化脚本 — 新用户首次使用时运行

功能:
  1. 检查 Python 环境
  2. 引导选择知识库后端 (local_search / ima / both / chromadb)
  3. 初始化知识库
  4. 导入种子文件
  5. 验证搜索功能
  6. 写入配置

使用方式:
  python kb_setup.py                          # 交互式引导
  python kb_setup.py --backend local_search   # 指定后端(默认)
  python kb_setup.py --quick                  # 快速模式(全默认值)
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def check_python_version():
    """检查 Python 版本"""
    print_header("Step 1: 检查 Python 环境")
    version = sys.version_info
    print(f"  Python: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("  [ERROR] 需要 Python 3.8+，请升级 Python。")
        return False
    print("  [OK] Python 版本符合要求。")
    return True


def select_backend(args):
    """引导选择后端"""
    print_header("Step 2: 选择知识库后端")

    if args.get("backend"):
        backend = args["backend"]
        print(f"  通过参数指定后端: {backend}")
        return backend

    if args.get("quick"):
        print("  快速模式: 使用 local_search (本地检索，零依赖)")
        return "local_search"

    print("  请选择知识库后端:")
    print()
    print("  [1] 本地文件检索 (local_search) — 推荐")
    print("      零安装、零下载、零配置，纯Python标准库")
    print("      支持MD/TXT文件，PDF需可选安装PyPDF2")
    print("      适合：快速上手、个人使用、离线环境")
    print()
    print("  [2] ima 云端知识库")
    print("      需要ima账号，支持多端同步和团队共享")
    print("      适合：团队协作、需要共享公共知识库")
    print()
    print("  [3] 混合模式 (ima + 本地检索)")
    print("      公共法规知识用ima共享库，私有数据用本地检索")
    print("      适合：既要共享又要本地数据")
    print()
    print("  [4] ChromaDB 本地向量库 — 高级")
    print("      语义搜索(不是关键词匹配)，需安装chromadb+sentence-transformers")
    print("      首次下载模型~90MB，适合有技术能力的团队")
    print()

    while True:
        choice = input("  请输入选择 (1/2/3/4) [默认1]: ").strip()
        if not choice:
            choice = "1"

        backend_map = {"1": "local_search", "2": "ima", "3": "both", "4": "chromadb"}
        if choice in backend_map:
            return backend_map[choice]
        print("  无效选择，请重新输入。")


def install_optional_deps(backend_type):
    """安装可选依赖"""
    print_header("Step 3: 检查依赖")

    # local_search: 只需要可选安装 PyPDF2
    if backend_type in ("local_search", "both"):
        try:
            import PyPDF2
            print("  [OK] PyPDF2 已安装 (PDF文件支持已启用)")
        except ImportError:
            print("  [INFO] PyPDF2 未安装 (PDF文件不可检索)")
            ans = input("  是否安装 PyPDF2 以支持PDF文件? (y/n) [y]: ").strip().lower()
            if ans != "n":
                subprocess.run([sys.executable, "-m", "pip", "install", "PyPDF2", "-q"])
                print("  [OK] PyPDF2 安装成功")
            else:
                print("  [INFO] 跳过，仅支持MD/TXT文件")

    elif backend_type == "chromadb":
        for pkg in ["chromadb", "sentence-transformers", "PyPDF2"]:
            try:
                __import__(pkg.replace("-", "_").replace("sentence-transformers", "sentence_transformers"))
                print(f"  [OK] {pkg} 已安装")
            except ImportError:
                print(f"  [INFO] 安装 {pkg}...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pkg, "-q"],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    print(f"  [WARN] {pkg} 安装失败: {result.stderr[:200]}")
                else:
                    print(f"  [OK] {pkg} 安装成功")

    elif backend_type == "ima":
        print("  [INFO] ima 后端无需额外依赖")
        print("         认证通过 WorkBuddy 的 ima-mcp 连接器或 .env 配置")

    return True


def init_local_search(config):
    """初始化本地检索后端"""
    print_header("Step 4: 初始化本地知识库")

    from kb_backend import create_backend
    # 确保用 local_search
    config["backend"]["type"] = "local_search"
    kb = create_backend(config)

    result = kb.init()
    print(f"  {result['message']}")

    if not result["success"]:
        print("  [ERROR] 初始化失败")
        return False, None

    # 导入种子文件
    print("\n  --- 导入种子文件 ---")
    import_result = kb.import_seed_files()
    print(f"  导入结果: 成功 {import_result['success']}/{import_result['total']}")
    for d in import_result["details"]:
        status = "[OK]" if d["success"] else "[MISS]"
        print(f"    {status} {d['file']}")

    # 验证搜索
    print("\n  --- 验证搜索功能 ---")
    test_queries = [
        "废标条款 资质不符",
        "等保2.0 网络安全",
        "报价 低于成本价",
        "资质替代 CMMI",
    ]
    all_passed = True
    for query in test_queries:
        results = kb.search(query, limit=1)
        if results:
            print(f"    [OK] '{query}' → {results[0]['source']} (score: {results[0]['score']})")
        else:
            print(f"    [WARN] '{query}' → 无结果")
            all_passed = False

    if all_passed:
        print("\n  [OK] 搜索验证全部通过！")
    else:
        print("\n  [INFO] 部分查询无结果，可能种子文件不完整")

    return True, kb


def init_ima(config):
    """初始化 ima 后端"""
    print_header("Step 4: 配置 ima 知识库")

    print("  ima 后端需要以下配置:")
    print()
    print("  1. 你需要一个腾讯 ima 账号 (https://ima.qq.com)")
    print("  2. 如果你使用 WorkBuddy，请确保已连接 ima-mcp 连接器")
    print("  3. 如果不使用 WorkBuddy，请在 .env 中配置认证信息")
    print()

    public_id = config.get("backend", {}).get("ima", {}).get("public_kb_id", "")
    private_id = config.get("backend", {}).get("ima", {}).get("private_kb_id", "")

    if public_id:
        print(f"  [OK] 公共知识库 ID: {public_id}")
    else:
        print("  [INFO] 公共知识库 ID 未配置")
        print("         请从开源项目README获取公共库ID并填入配置")

    if private_id:
        print(f"  [OK] 私有知识库 ID: {private_id}")
    else:
        print("  [INFO] 私有知识库 ID 未配置")
        print("         请创建你的 ima 知识库后，将 ID 填入配置")

    print()
    print("  [INFO] ima 后端初始化完成")
    print("         种子文件通过 WorkBuddy 对话上传到 ima 知识库")

    return True, None


def write_config(backend_type, config):
    """写入最终配置"""
    print_header("Step 5: 写入配置文件")

    config_path = SCRIPT_DIR / "kb_config.json"

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {}

    existing["backend"] = existing.get("backend", {})
    existing["backend"]["type"] = backend_type
    existing["last_setup"] = datetime.now().isoformat()
    existing["setup_backend"] = backend_type

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"  [OK] 配置已写入: {config_path}")
    print(f"  后端类型: {backend_type}")


def print_summary(backend_type, success, kb):
    """打印设置摘要"""
    print_header("设置完成")

    if success:
        print("  恭喜！知识库已就绪。")
        print()
        print(f"  后端: {backend_type}")

        if kb:
            info = kb.get_info()
            print(f"  文件数: {info.get('file_count', 0)}")
            print(f"  支持格式: {info.get('supported_formats', [])}")

        print()
        print("  接下来你可以:")
        print("    1. 创建本地知识库目录: python kb_init.py \"./kb_data\"")
        print("    2. 上传新的法规PDF: python kb_auto_index.py <文件路径>")
        print("    3. 检查同步状态: python kb_sync_manager.py status")
        print("    4. 在 WorkBuddy 中使用标书专家系统")
        print()
        print("  如有问题，请查看 README.md 中的 FAQ。")
    else:
        print("  设置未完全成功，请检查上方的错误信息。")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="知识库一键初始化")
    parser.add_argument("--backend", choices=["local_search", "ima", "both", "chromadb"],
                        default="local_search",
                        help="指定后端类型 (默认: local_search)")
    parser.add_argument("--quick", action="store_true",
                        help="快速模式，使用全部默认值")
    args = parser.parse_args()

    print_header("标书智能体知识库 — 一键初始化")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  脚本目录: {SCRIPT_DIR}")

    # Step 1: 检查 Python
    if not check_python_version():
        sys.exit(1)

    # Step 2: 选择后端
    backend_type = select_backend(vars(args))

    # Step 3: 安装依赖
    install_optional_deps(backend_type)

    # Step 4: 加载配置
    from kb_backend import load_config
    config = load_config()

    # Step 5: 初始化后端
    success = False
    kb = None

    if backend_type == "local_search":
        success, kb = init_local_search(config)
    elif backend_type == "ima":
        success, kb = init_ima(config)
    elif backend_type == "both":
        # 先初始化本地检索
        success, kb = init_local_search(config)
        if success:
            print("\n  --- 接着配置 ima 后端 ---")
            ima_success, _ = init_ima(config)
            success = success and ima_success
    elif backend_type == "chromadb":
        from kb_backend import create_backend
        config["backend"]["type"] = "chromadb"
        kb = create_backend(config)
        result = kb.init()
        print(f"  {result['message']}")
        success = result["success"]
        if success:
            import_result = kb.import_seed_files()
            print(f"  导入结果: 成功 {import_result['success']}/{import_result['total']}")

    # Step 6: 写入配置
    write_config(backend_type, config)

    # Step 7: 摘要
    print_summary(backend_type, success, kb)


if __name__ == "__main__":
    main()
