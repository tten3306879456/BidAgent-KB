#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署向导 (setup_wizard.py)
==========================
交互式引导开源用户完成项目部署的全流程。

流程:
  1. 环境检查 (Python 版本 / pip / 操作系统)
  2. 虚拟环境创建 (venv)
  3. 依赖安装 (requirements.txt)
  4. 知识库后端选择与初始化
  5. .env 配置生成
  6. 渠道消息推送配置 (可选)
  7. 验证测试
  8. 生成部署摘要

使用方式:
  python scripts/setup_wizard.py               # 交互式引导
  python scripts/setup_wizard.py --quick        # 快速模式(全默认值)
  python scripts/setup_wizard.py --skip-venv    # 跳过虚拟环境(用当前Python)
  python scripts/setup_wizard.py --check        # 仅检查环境不部署
"""

import os
import sys
import json
import platform
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# ============================================================
# 路径常量
# ============================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "kb_config.json"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
ENV_PATH = PROJECT_ROOT / ".env"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"

# ============================================================
# 终端颜色
# ============================================================
class Color:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"

    @classmethod
    def support_color(cls):
        """检测终端是否支持颜色"""
        return sys.stdout.isatty() and platform.system() != "Windows" or \
               (platform.system() == "Windows" and os.environ.get("WT_SESSION"))


_C = Color.support_color()


def c(text, color):
    if _C:
        return f"{color}{text}{Color.END}"
    return text


def ok(msg):
    print(f"  {c('[OK]', Color.GREEN)} {msg}")


def info(msg):
    print(f"  {c('[INFO]', Color.CYAN)} {msg}")


def warn(msg):
    print(f"  {c('[WARN]', Color.YELLOW)} {msg}")


def err(msg):
    print(f"  {c('[ERROR]', Color.RED)} {msg}")


def header(title, step=None):
    prefix = f"  Step {step}: " if step else "  "
    print()
    print(f"  {c('=' * 56, Color.BLUE)}")
    print(f"  {c(title, Color.BOLD)}")
    print(f"  {c('=' * 56, Color.BLUE)}")
    print()


def banner():
    print()
    print(c("  ╔═══════════════════════════════════════════════════════════╗", Color.CYAN))
    print(c("  ║          标书智能体专家系统 — 部署向导 v1.0                ║", Color.CYAN))
    print(c("  ║          BidAgent-KB Setup Wizard                         ║", Color.CYAN))
    print(c("  ╚═══════════════════════════════════════════════════════════╝", Color.CYAN))
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  {platform.system()} {platform.release()} / Python {sys.version.split()[0]}")
    print(f"  项目根目录: {PROJECT_ROOT}")
    print()


# ============================================================
# Step 1: 环境检查
# ============================================================
def check_environment():
    header("环境检查", 1)

    results = {}

    # Python 版本
    v = sys.version_info
    results["python_version"] = f"{v.major}.{v.minor}.{v.micro}"
    if v.major >= 3 and v.minor >= 8:
        ok(f"Python {results['python_version']}")
    else:
        err(f"Python {results['python_version']} — 需要 3.8+")
        return False, results

    # pip
    try:
        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if pip_result.returncode == 0:
            pip_ver = pip_result.stdout.strip().split(",")[0].replace("pip ", "")
            results["pip_version"] = pip_ver
            ok(f"pip {pip_ver}")
        else:
            err("pip 不可用")
            return False, results
    except Exception as e:
        err(f"pip 检查失败: {e}")
        return False, results

    # Git
    try:
        git_result = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, timeout=5
        )
        if git_result.returncode == 0:
            results["git"] = git_result.stdout.strip()
            ok(results["git"])
        else:
            results["git"] = None
            warn("Git 未安装 (可选, 用于克隆仓库)")
    except Exception:
        results["git"] = None
        warn("Git 未安装 (可选)")

    # 操作系统
    results["os"] = f"{platform.system()} {platform.release()}"
    ok(f"操作系统: {results['os']}")

    # 项目文件完整性
    required_files = [
        "kb_config.json", ".env.example", "requirements.txt",
        "scripts/kb_backend.py", "scripts/kb_local_search.py",
        "scripts/kb_setup.py", "scripts/channel_notify.py"
    ]
    missing = []
    for f in required_files:
        if not (PROJECT_ROOT / f).exists():
            missing.append(f)

    if missing:
        err(f"缺少项目文件: {', '.join(missing)}")
        return False, results
    else:
        ok("项目文件完整性检查通过")

    # 种子文件
    seeds_dir = PROJECT_ROOT / "seeds"
    if seeds_dir.exists():
        seed_count = len(list(seeds_dir.glob("*.md")))
        results["seed_files"] = seed_count
        ok(f"种子文件: {seed_count} 个")
    else:
        warn("seeds/ 目录不存在")
        results["seed_files"] = 0

    return True, results


# ============================================================
# Step 2: 虚拟环境
# ============================================================
def setup_venv(skip_venv=False, quick=False):
    header("虚拟环境", 2)

    if skip_venv:
        info("跳过虚拟环境创建 (--skip-venv)")
        info(f"使用当前 Python: {sys.executable}")
        return sys.executable

    venv_dir = PROJECT_ROOT / "venv"

    if venv_dir.exists():
        if quick:
            info(f"虚拟环境已存在: {venv_dir}")
            python_exe = str(venv_dir / ("Scripts" if platform.system() == "Windows" else "bin") / "python")
            if Path(python_exe).exists():
                return python_exe
        ans = input(f"  虚拟环境已存在 ({venv_dir}), 是否重新创建? (y/n) [n]: ").strip().lower()
        if ans != "y":
            info("保留现有虚拟环境")
            python_exe = str(venv_dir / ("Scripts" if platform.system() == "Windows" else "bin") / "python")
            if Path(python_exe).exists():
                return python_exe
            else:
                warn("虚拟环境 Python 不可用, 使用当前 Python")
                return sys.executable

    info(f"创建虚拟环境: {venv_dir}")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        capture_output=True, text=True, timeout=60
    )

    if result.returncode != 0:
        warn(f"虚拟环境创建失败: {result.stderr[:200]}")
        warn("使用当前 Python 继续")
        return sys.executable

    ok("虚拟环境创建成功")

    # 确定 venv 中的 python 路径
    if platform.system() == "Windows":
        python_exe = str(venv_dir / "Scripts" / "python.exe")
        pip_exe = str(venv_dir / "Scripts" / "pip.exe")
    else:
        python_exe = str(venv_dir / "bin" / "python")
        pip_exe = str(venv_dir / "bin" / "pip")

    # 升级 pip
    info("升级 pip...")
    subprocess.run(
        [python_exe, "-m", "pip", "install", "--upgrade", "pip", "-q"],
        capture_output=True, text=True, timeout=60
    )

    return python_exe


# ============================================================
# Step 3: 依赖安装
# ============================================================
def install_dependencies(python_exe, quick=False):
    header("依赖安装", 3)

    # 基础依赖 (默认后端只需标准库)
    info("安装基础依赖 (PyPDF2, requests)...")

    base_deps = ["PyPDF2>=3.0", "requests>=2.28"]
    result = subprocess.run(
        [python_exe, "-m", "pip", "install"] + base_deps + ["-q"],
        capture_output=True, text=True, timeout=120
    )

    if result.returncode == 0:
        ok("基础依赖安装成功")
    else:
        warn(f"部分依赖安装失败: {result.stderr[:200]}")
        warn("基础功能仍可用 (零依赖模式)")

    # 验证关键模块
    verify_result = subprocess.run(
        [python_exe, "-c", "import PyPDF2; print('PyPDF2 OK')"],
        capture_output=True, text=True
    )
    if verify_result.returncode == 0:
        ok("PyPDF2 验证通过")
    else:
        info("PyPDF2 未安装 (PDF 检索不可用, MD/TXT 正常)")

    return True


# ============================================================
# Step 4: 知识库后端选择
# ============================================================
def select_backend(quick=False):
    header("知识库后端选择", 4)

    if quick:
        info("快速模式: local_search (零依赖)")
        return "local_search"

    print("  请选择知识库后端:\n")
    print(f"  {c('[1]', Color.GREEN)} 本地文件检索 (local_search) — {c('推荐', Color.BOLD)}")
    print("      零安装、零下载、零配置，纯 Python 标准库")
    print("      支持 MD/TXT 文件，PDF 需可选安装 PyPDF2")
    print("      适合：快速上手、个人使用、离线环境\n")
    print(f"  {c('[2]', Color.CYAN)} ima 云端知识库")
    print("      需要 ima 账号，支持多端同步和团队共享")
    print("      适合：团队协作、社区共享\n")
    print(f"  {c('[3]', Color.YELLOW)} 混合模式 (ima + 本地)")
    print("      公共法规知识用 ima 共享库，私有数据用本地检索\n")
    print(f"  {c('[4]', Color.YELLOW)} ChromaDB 语义搜索 — 高级")
    print("      AI 嵌入模型语义搜索，需安装 chromadb + sentence-transformers")
    print("      首次下载中文嵌入模型 ~1.3GB (BAAI/bge-large-zh-v1.5)\n")

    while True:
        choice = input(f"  {c('请选择 (1/2/3/4)', Color.BOLD)} [默认1]: ").strip()
        if not choice:
            choice = "1"
        backend_map = {"1": "local_search", "2": "ima", "3": "both", "4": "chromadb"}
        if choice in backend_map:
            return backend_map[choice]
        warn("无效选择，请重新输入")


# ============================================================
# Step 5: .env 配置生成
# ============================================================
def generate_env(backend_type, quick=False):
    header(".env 配置生成", 5)

    if ENV_PATH.exists() and not quick:
        ans = input(f"  .env 已存在, 是否覆盖? (y/n) [n]: ").strip().lower()
        if ans != "y":
            info("保留现有 .env")
            return

    # 读取模板
    if not ENV_EXAMPLE_PATH.exists():
        warn(".env.example 不存在, 跳过")
        return

    with open(ENV_EXAMPLE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # 根据 backend 类型设置默认值
    env_content = template.replace("KB_BACKEND=local_search", f"KB_BACKEND={backend_type}")
    env_content = env_content.replace("KB_BASE_PATH=./kb_data", f"KB_BASE_PATH={PROJECT_ROOT}")

    # 写入 .env
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(env_content)

    ok(f".env 已生成: {ENV_PATH}")
    info(f"  后端类型: {backend_type}")
    info(f"  项目路径: {PROJECT_ROOT}")

    if backend_type in ("ima", "both"):
        info("  ima 后端需额外配置:")
        info("    KB_PUBLIC_ID / KB_PRIVATE_ID (你的 ima 知识库 ID)")
        info("    或在 kb_config.json 的 shared_kbs 中填入共享库 ID")


# ============================================================
# Step 6: 渠道配置
# ============================================================
def configure_channels(python_exe, quick=False):
    header("渠道消息推送配置 (可选)", 6)

    if quick:
        info("快速模式: 跳过渠道配置")
        return

    print("  可选配置消息推送渠道 (飞书/钉钉/企业微信/微信)")
    print("  配置后可接收标书审核完成等通知\n")

    ans = input("  是否现在配置渠道? (y/n) [n]: ").strip().lower()
    if ans != "y":
        info("跳过渠道配置 (稍后可运行: python scripts/channel_notify.py list)")
        return

    channels = {
        "1": ("feishu", "飞书", ["FEISHU_WEBHOOK_URL", "FEISHU_BOT_SECRET"]),
        "2": ("dingtalk", "钉钉", ["DINGTALK_APP_KEY", "DINGTALK_APP_SECRET", "DINGTALK_WEBHOOK_URL"]),
        "3": ("wecom", "企业微信", ["WECOM_CORP_ID", "WECOM_AGENT_ID", "WECOM_SECRET"]),
        "4": ("wechat", "微信公众号", ["WECHAT_APP_ID", "WECHAT_APP_SECRET", "WECHAT_TOKEN", "WECHAT_ENCODING_AES_KEY"]),
    }

    print()
    for key, (name, display, _) in channels.items():
        print(f"  [{key}] {display}")
    print()

    choice = input("  选择要配置的渠道 (1/2/3/4): ").strip()
    if choice not in channels:
        info("跳过渠道配置")
        return

    channel_key, channel_name, fields = channels[choice]
    print(f"\n  --- 配置 {channel_name} ---\n")

    pairs = []
    for field in fields:
        val = input(f"  {field}: ").strip()
        if val:
            pairs.append(f"{field}={val}")

    if not pairs:
        warn("未填写任何字段, 跳过")
        return

    # 使用 channel_notify.py CLI 更新
    cmd = [python_exe, str(SCRIPT_DIR / "channel_notify.py"),
           "update", channel_key] + pairs + ["--save"]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode == 0:
        ok(f"{channel_name} 配置完成")
        # 测试连接
        test_ans = input(f"  是否测试 {channel_name} 连接? (y/n) [y]: ").strip().lower()
        if test_ans != "n":
            test_result = subprocess.run(
                [python_exe, str(SCRIPT_DIR / "channel_notify.py"), "test", channel_key],
                capture_output=True, text=True, timeout=15
            )
            print(test_result.stdout)
    else:
        warn(f"配置可能未完全成功: {result.stdout[:200]}")


# ============================================================
# Step 7: 验证测试
# ============================================================
def run_verification(python_exe, backend_type):
    header("验证测试", 7)

    # 7.1 知识库目录初始化
    info("创建知识库目录结构...")
    init_result = subprocess.run(
        [python_exe, str(SCRIPT_DIR / "kb_init.py"), str(PROJECT_ROOT / "kb_data")],
        capture_output=True, text=True, timeout=60,
        cwd=str(SCRIPT_DIR)
    )
    if init_result.returncode == 0:
        ok("知识库目录初始化成功")
    else:
        warn("知识库目录初始化跳过 (可能已存在)")

    # 7.2 后端配置
    info("写入后端配置...")
    setup_result = subprocess.run(
        [python_exe, str(SCRIPT_DIR / "kb_setup.py"), "--backend", backend_type, "--quick"],
        capture_output=True, text=True, timeout=60,
        cwd=str(SCRIPT_DIR)
    )

    if setup_result.returncode == 0:
        ok("后端配置写入成功")
    else:
        warn("后端配置有警告 (非致命)")

    # 7.3 本地搜索测试
    if backend_type in ("local_search", "both"):
        info("测试本地搜索...")
        search_result = subprocess.run(
            [python_exe, str(SCRIPT_DIR / "kb_local_search.py"), "投标保证金"],
            capture_output=True, text=True, timeout=15,
            cwd=str(SCRIPT_DIR)
        )
        if search_result.returncode == 0 and search_result.stdout.strip():
            ok("本地搜索验证通过")
        else:
            warn("本地搜索无结果 (种子文件可能未完全导入)")

    # 7.4 渠道通知测试
    info("检查渠道配置...")
    channel_result = subprocess.run(
        [python_exe, str(SCRIPT_DIR / "channel_notify.py"), "list"],
        capture_output=True, text=True, timeout=10,
        cwd=str(SCRIPT_DIR)
    )
    if channel_result.returncode == 0:
        ok("渠道模块正常")

    # 7.5 配置文件检查
    if CONFIG_PATH.exists():
        ok(f"配置文件: {CONFIG_PATH}")
    if ENV_PATH.exists():
        ok(f"环境变量: {ENV_PATH}")

    return True


# ============================================================
# Step 8: 部署摘要
# ============================================================
def print_summary(env_results, backend_type, python_exe, deploy_time):
    header("部署摘要", 8)

    print(f"  {c('═══ 部署完成 ═══', Color.GREEN)}\n")

    summary_items = [
        ("操作系统", env_results.get("os", "Unknown")),
        ("Python", env_results.get("python_version", "Unknown")),
        ("pip", env_results.get("pip_version", "Unknown")),
        ("Git", env_results.get("git", "未安装") or "未安装"),
        ("Python 解释器", python_exe),
        ("项目根目录", str(PROJECT_ROOT)),
        ("知识库后端", backend_type),
        ("种子文件", f"{env_results.get('seed_files', 0)} 个"),
        ("配置文件", "kb_config.json ✓" if CONFIG_PATH.exists() else "kb_config.json ✗"),
        ("环境变量", ".env ✓" if ENV_PATH.exists() else ".env ✗"),
        ("部署时间", deploy_time),
    ]

    for label, value in summary_items:
        print(f"  {c(label, Color.CYAN):.<30s} {value}")

    print()
    print(f"  {c('下一步操作:', Color.BOLD)}")
    print()
    print(f"    1. {c('初始化本地知识库目录:', Color.GREEN)}")
    print(f"       python scripts/kb_init.py ./kb_data")
    print()
    print(f"    2. {c('验证搜索功能:', Color.GREEN)}")
    print(f"       python scripts/kb_local_search.py \"投标保证金\"")
    print()
    print(f"    3. {c('配置消息推送渠道 (可选):', Color.GREEN)}")
    print(f"       python scripts/channel_notify.py list")
    print(f"       python scripts/channel_notify.py update feishu FEISHU_WEBHOOK_URL=https://...")
    print()
    print(f"    4. {c('在 WorkBuddy 中使用标书专家系统:', Color.GREEN)}")
    print(f"       将 expert_prompts/ 中的 9 个专家导入 WorkBuddy 专家中心")
    print()
    print(f"  {c('详细文档:', Color.BOLD)}")
    print(f"    - 部署指南: docs/部署指南.md")
    print(f"    - 知识库使用: guides/知识库使用指南.md")
    print(f"    - 脚本说明: scripts/README.md")
    print()
    print(f"  {c('如遇问题:', Color.YELLOW)}")
    print(f"    - 查看 FAQ: README.md#faq")
    print(f"    - 提交 Issue: https://github.com/tten3306879456/BidAgent-KB/issues")
    print()


# ============================================================
# 主流程
# ============================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="标书智能体专家系统 — 部署向导",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/setup_wizard.py               # 交互式部署
  python scripts/setup_wizard.py --quick        # 快速部署(全默认值)
  python scripts/setup_wizard.py --skip-venv    # 跳过虚拟环境
  python scripts/setup_wizard.py --check        # 仅检查环境
        """
    )
    parser.add_argument("--quick", action="store_true",
                        help="快速模式, 使用全部默认值")
    parser.add_argument("--skip-venv", action="store_true",
                        help="跳过虚拟环境创建, 使用当前 Python")
    parser.add_argument("--check", action="store_true",
                        help="仅检查环境, 不执行部署")
    args = parser.parse_args()

    banner()
    deploy_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Step 1: 环境检查
    env_ok, env_results = check_environment()
    if not env_ok:
        err("环境检查未通过, 请修复后重试")
        sys.exit(1)

    if args.check:
        print(f"\n  {c('环境检查完成 (--check 模式)', Color.GREEN)}")
        sys.exit(0)

    # Step 2: 虚拟环境
    python_exe = setup_venv(skip_venv=args.skip_venv, quick=args.quick)

    # Step 3: 依赖安装
    install_dependencies(python_exe, quick=args.quick)

    # Step 4: 后端选择
    backend_type = select_backend(quick=args.quick)

    # Step 5: .env 生成
    generate_env(backend_type, quick=args.quick)

    # Step 6: 渠道配置
    configure_channels(python_exe, quick=args.quick)

    # Step 7: 验证测试
    run_verification(python_exe, backend_type)

    # Step 8: 摘要
    print_summary(env_results, backend_type, python_exe, deploy_time)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {c('部署已取消 (Ctrl+C)', Color.YELLOW)}\n")
        sys.exit(130)
    except Exception as e:
        print(f"\n  {c(f'部署出错: {e}', Color.RED)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
