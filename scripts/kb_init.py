#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库目录初始化脚本 (kb_init.py)
===================================
一键创建完整的知识库目录结构，复制种子文件、管理脚本和CSV模板。

用法:
  python kb_init.py "./kb_data"          创建目录结构并复制文件
  python kb_init.py "./kb_data" --force   覆盖已存在的目录
  python kb_init.py --help                显示帮助
"""

import sys
import os
import json
import shutil
from pathlib import Path

# ============================================================
# 配置
# ============================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
SEED_SOURCE = PROJECT_ROOT / "seeds"
TEMPLATE_SOURCE = PROJECT_ROOT / "guides" / "本地知识库搭建指南"
GUIDE_SOURCE = PROJECT_ROOT / "guides" / "知识库使用指南.md"


def load_config(config_path=None):
    """加载配置文件"""
    if config_path is None:
        # 优先从项目根目录的 kb_config.json 加载（完整配置）
        config_path = PROJECT_ROOT / "kb_config.json"
        if not config_path.exists():
            # 回退到 scripts 目录
            config_path = SCRIPT_DIR / "kb_config.json"
    if Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "cloud_seed_dir": "01_云端知识库/种子文件",
        "cloud_script_dir": "01_云端知识库/管理脚本",
        "cloud_log_dir": "01_云端知识库/同步日志",
        "local_kb_dir": "02_本地知识库",
        "upload_staging_dir": "03_待上传",
        "template_dir": "04_CSV模板",
        "local_databases": {
            "company_qualification": "01_公司资质库",
            "personnel": "02_人员信息库",
            "performance": "03_业绩案例库",
            "pricing": "04_报价方案库",
            "template": "05_标书模板库",
            "technical_solution": "06_技术方案库",
        },
        "seed_files": [
            "废标条款模式库_种子版.md",
            "标书核心法规汇编_v1.0.md",
            "招投标报价与商务法规专题库_种子版.md",
            "资质等效替代规则库_种子版.md",
            "核工业标书知识库_种子版.md",
            "软件开发标书知识库_种子版.md",
            "标书法规库_2024-2025新增法规.md",
            "标书案例库_2024-2025典型案例.md",
            "行业技术标准_软件开发部分.md",
            "GBZ117等核工业标准.md",
            "软件行业标准_2024-2025更新.md",
            "投标文件通用框架与封面模板.md",
            "商务标书模板_投标函与响应表.md",
            "技术标书模板_信息化项目方案框架.md",
            "评分响应与偏离表模板集.md",
        ],
        "template_files": [
            "公司资质清单_模板.csv",
            "人员基本信息表_模板.csv",
            "人员技能矩阵表_模板.csv",
            "业绩案例清单_模板.csv",
            "报价历史记录_模板.csv",
            "标书模板目录_模板.csv",
            "技术方案资产库_模板.csv",
            "技术组件库_模板.csv",
            "解决方案模式库_模板.csv",
            "技术评分要素库_模板.csv",
        ],
        "script_files": [
            "kb_backend.py",
            "kb_local_search.py",
            "kb_ima.py",
            "kb_setup.py",
            "kb_auto_index.py",
            "kb_sync_manager.py",
            "kb_init.py",
        ],
    }


def create_dirs(base, config):
    """创建完整目录结构"""
    dirs = [
        base,
        base / config["cloud_seed_dir"],
        base / config["cloud_script_dir"],
        base / config["cloud_log_dir"],
        base / config["local_kb_dir"],
        base / config["upload_staging_dir"],
        base / config["template_dir"],
    ]
    local_kb_base = base / config["local_kb_dir"]
    for db_dir in config["local_databases"].values():
        dirs.append(local_kb_base / db_dir)
    dirs.append(local_kb_base / "05_标书模板库" / "模板文件")
    
    # 共享内容目录
    dirs.append(base / "shared_content")
    dirs.append(base / "shared_content" / "标书范文")
    dirs.append(base / "shared_content" / "标书范文" / "商务标书")
    dirs.append(base / "shared_content" / "标书范文" / "技术标书")
    dirs.append(base / "shared_content" / "标书范文" / "报价方案")

    print("\n--- 创建目录结构 ---")
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  OK  {d.relative_to(base)}")


def copy_files(base, config, src_dir, file_list, label):
    """通用文件复制"""
    dst_dir = None
    if label == "种子文件":
        dst_dir = base / config["cloud_seed_dir"]
    elif label == "管理脚本":
        dst_dir = base / config["cloud_script_dir"]
    elif label == "CSV模板":
        dst_dir = base / config["template_dir"]

    print(f"\n--- 复制{label} ---")
    copied = 0
    for fname in file_list:
        src = src_dir / fname
        if dst_dir is None:
            continue
        dst = dst_dir / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  OK  {fname}")
            copied += 1
        else:
            print(f"  !!  源文件不存在: {src}")
    return copied


def copy_guide(base):
    """复制使用指南"""
    print("\n--- 复制使用指南 ---")
    if GUIDE_SOURCE.exists():
        shutil.copy2(GUIDE_SOURCE, base / "使用指南.md")
        print("  OK  使用指南.md")
        return 1
    print(f"  !!  源文件不存在: {GUIDE_SOURCE}")
    return 0


def generate_config(base, config):
    """在目标目录生成本地配置文件"""
    local_config = config.copy()
    local_config["base_path"] = str(base)
    config_path = base / "kb_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(local_config, f, ensure_ascii=False, indent=2)
    print("\n--- 生成配置文件 ---")
    print(f"  OK  kb_config.json (base_path={base})")


def create_readme(base):
    """在待上传目录创建说明"""
    readme = base / "03_待上传" / "README.txt"
    with open(readme, "w", encoding="utf-8") as f:
        f.write(
            "待上传目录\n"
            "==========\n\n"
            "将需要上传到ima云端知识库的PDF/文件放在此目录。\n\n"
            "上传步骤:\n"
            "1. 将文件放入此目录\n"
            "2. 运行: python kb_auto_index.py \"文件路径\"\n"
            "3. 在WorkBuddy对话中说: 帮我把这个文件上传到知识库\n"
            "4. 上传成功后可删除本地文件\n"
        )
    print("  OK  03_待上传/README.txt")


def create_gitignore(base):
    """创建.gitignore"""
    with open(base / ".gitignore", "w", encoding="utf-8") as f:
        f.write(
            "# 知识库数据 - 含敏感信息，禁止提交Git\n"
            "02_本地知识库/\n"
            "*.csv\n"
            "*.json\n"
            "03_待上传/\n"
            "01_云端知识库/同步日志/\n"
        )
    print("  OK  .gitignore")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="知识库目录初始化工具 - 一键创建完整知识库目录结构",
    )
    parser.add_argument("target", nargs="?", default="./kb_data",
                        help="目标路径 (默认: ./kb_data)")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的目录")
    parser.add_argument("--config", default=None, help="指定配置文件路径")
    args = parser.parse_args()

    base = Path(args.target)
    config = load_config(args.config) if args.config else load_config()

    print("=" * 60)
    print("  知识库目录初始化工具 kb_init.py")
    print("=" * 60)
    print(f"  目标路径: {args.target}")

    # 检查目录是否存在
    if base.exists() and any(base.iterdir()):
        if not args.force:
            print(f"\n!! 目录已存在且非空: {base}")
            print(f"   如需覆盖: python kb_init.py \"{args.target}\" --force")
            sys.exit(1)
        else:
            print(f"\n!! --force 模式: 清空目录 {base}")
            shutil.rmtree(base, ignore_errors=True)
            # 如果目录仍然存在（权限/回收站问题），尝试清空内容
            if base.exists():
                for item in base.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)

    # 1. 创建目录
    create_dirs(base, config)

    # 2. 复制种子文件
    seed_count = copy_files(base, config, SEED_SOURCE, config["seed_files"], "种子文件")

    # 3. 复制管理脚本
    script_count = copy_files(base, config, SCRIPT_DIR, config["script_files"], "管理脚本")

    # 4. 复制CSV模板
    template_count = copy_files(base, config, TEMPLATE_SOURCE, config["template_files"], "CSV模板")

    # 5. 复制使用指南
    guide_count = copy_guide(base)

    # 6. 生成配置文件
    generate_config(base, config)

    # 7. 创建辅助文件
    print("\n--- 创建辅助文件 ---")
    create_readme(base)
    create_gitignore(base)

    # 汇总
    print("\n" + "=" * 60)
    print("  初始化完成!")
    print("=" * 60)
    print(f"  目录: {args.target}")
    print(f"  种子文件: {seed_count} 个")
    print(f"  管理脚本: {script_count} 个")
    print(f"  CSV模板: {template_count} 个")
    print(f"  使用指南: {guide_count} 个")
    print()
    print("  下一步:")
    print("  1. 从 04_CSV模板\\ 复制模板到 02_本地知识库\\ 对应目录")
    print("  2. 开始录入数据")
    print("  3. 有新法规PDF时放到 03_待上传\\ 然后运行 kb_auto_index.py")
    print("  4. 详见 使用指南.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
