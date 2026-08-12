#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BidAgent-KB 本地管理控制台

启动一个本地 Web 服务器，提供三大功能：
1. 知识库覆盖度分析 — 检测种子文件是否充足，发现缺口并给出上传建议
2. 文件上传界面 — 拖拽上传文件到指定知识库目录（实际拷贝到磁盘）
3. 参数配置界面 — 读写 .env 和 kb_config.json，引导用户完成配置

使用方式:
    python scripts/kb_console.py              # 启动控制台 (默认端口 8765)
    python scripts/kb_console.py --port 9000  # 指定端口
    python scripts/kb_console.py --check      # 仅输出覆盖度分析（不开服务器）

依赖: 仅需 Python 标准库 (http.server, json, os, webbrowser)
"""

import json
import os
import sys
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent

# ==================== 知识库覆盖度分析 ====================

# 5 座共享知识库的定义
SHARED_KBS = {
    "标书法规库": {
        "icon": "📜", "color": "#2563EB",
        "dir": "seeds",
        "keywords": ["招标投标法", "政府采购法", "法规", "条文", "保证金", "报价规则", "废标条款"],
        "expected_files": "3+",
        "suggested_uploads": [
            "最新版《招标投标法》及实施条例条文",
            "地方政府采购实施细则",
            "行业专项招投标管理办法（如交通、水利、信息化）",
            "最新税率政策与报价计算规则",
        ],
        "description": "招投标法律条文、政府采购法、报价规则",
    },
    "标书案例库": {
        "icon": "⚠️", "color": "#F59E0B",
        "dir": "seeds",
        "keywords": ["废标", "案例", "资质不符", "无效投标", "偏离", "等效"],
        "expected_files": "3+",
        "suggested_uploads": [
            "近年废标案例汇总（含废标原因分析）",
            "中标/未中标对比案例",
            "资质等效替代成功/失败案例",
            "评分争议处理案例",
        ],
        "description": "废标条款模式、历史废标案例、资质等效",
    },
    "投标文件编辑模板库": {
        "icon": "📝", "color": "#8B5CF6",
        "dir": "seeds",
        "keywords": ["模板", "封面", "投标函", "授权书", "框架", "响应表", "偏离表"],
        "expected_files": "4+",
        "suggested_uploads": [
            "投标函及授权书标准模板",
            "技术方案目录框架模板",
            "商务报价表模板",
            "项目实施进度计划模板",
            "售后服务承诺书模板",
        ],
        "description": "通用目录、封面、投标函、技术方案框架",
    },
    "软件开发标书知识库": {
        "icon": "💻", "color": "#06B6D4",
        "dir": "seeds",
        "keywords": ["软件", "信息化", "等保", "信创", "云计算", "数据安全", "CMMI"],
        "expected_files": "3+",
        "suggested_uploads": [
            "等保2.0/3.0标准条文与测评要求",
            "信创产品目录与适配要求",
            "云计算服务能力标准",
            "软件架构设计模式参考",
        ],
        "description": "软件行业标准、等保、信创、云计算国标",
    },
    "核工业标书知识库": {
        "icon": "☢️", "color": "#4F46E5",
        "dir": "seeds",
        "keywords": ["核", "HAF", "GBZ", "放射", "核安全", "核级"],
        "expected_files": "2+",
        "suggested_uploads": [
            "HAF系列核安全法规汇编",
            "核级设备资质要求",
            "核工业项目管理规程",
            "放射防护标准更新",
        ],
        "description": "HAF法规、GBZ117放射防护、核级设备",
    },
}

# 6 个本地数据库的定义
LOCAL_DBS = {
    "公司资质库": {
        "icon": "🏢", "color": "#22C55E",
        "dir_name": "02_本地知识库/01_公司资质库",
        "csv_file": "公司资质清单.csv",
        "status": "empty",
        "suggested_uploads": [
            "营业执照扫描件",
            "ISO 9001/14001/27001 认证证书",
            "行业资质证书（如计算机信息系统集成、建筑智能化等）",
            "安全生产许可证",
            "高新技术企业证书",
            "近三年财务审计报告",
        ],
        "description": "企业资质证书、营业执照、认证文件",
    },
    "人员信息库": {
        "icon": "👤", "color": "#22C55E",
        "dir_name": "02_本地知识库/02_人员信息库",
        "csv_file": "人员基本信息表.csv",
        "status": "empty",
        "suggested_uploads": [
            "核心人员简历（项目经理、技术负责人）",
            "人员资格证书（PMP、建造师、高级工程师等）",
            "人员技能矩阵表（技能×人员交叉表）",
            "社保缴纳证明",
        ],
        "description": "人员简历、资格证书、技能矩阵",
    },
    "业绩案例库": {
        "icon": "📊", "color": "#22C55E",
        "dir_name": "02_本地知识库/03_业绩案例库",
        "csv_file": "业绩案例清单.csv",
        "status": "empty",
        "suggested_uploads": [
            "近三年类似项目业绩清单（含合同金额、规模）",
            "项目验收报告或用户证明",
            "中标通知书扫描件",
            "优秀项目案例总结",
        ],
        "description": "历史项目业绩、验收报告、中标通知",
    },
    "报价方案库": {
        "icon": "💰", "color": "#22C55E",
        "dir_name": "02_本地知识库/04_报价方案库",
        "csv_file": "报价历史记录.csv",
        "status": "empty",
        "suggested_uploads": [
            "历史报价记录（项目类型×报价金额×中标结果）",
            "报价计算模板（含税率、利润率参数）",
            "竞争对手报价分析",
        ],
        "description": "历史报价记录、报价计算模板",
    },
    "标书模板库": {
        "icon": "📄", "color": "#22C55E",
        "dir_name": "02_本地知识库/05_标书模板库",
        "csv_file": "标书模板目录.csv",
        "status": "empty",
        "suggested_uploads": [
            "企业自有标书模板库",
            "各类项目标书范本（信息化、工程、采购等）",
            "标准章节模板（技术方案、商务方案、售后服务等）",
        ],
        "description": "企业自有标书模板和范本",
    },
    "技术方案库": {
        "icon": "🔧", "color": "#22C55E",
        "dir_name": "02_本地知识库/06_技术方案库",
        "csv_file": "技术方案资产库.csv",
        "status": "empty",
        "suggested_uploads": [
            "技术方案资产库（可复用方案模块）",
            "技术组件库（架构图、流程图、数据模型）",
            "解决方案模式库（行业×场景）",
            "技术评分要素库（评分项×响应要点）",
        ],
        "description": "技术方案资产、组件库、解决方案模式",
    },
}

# 5 个必填环境变量
REQUIRED_ENVS = [
    {"key": "KB_BASE_PATH", "label": "项目根目录", "required": True, "description": "知识库根目录路径，留空则使用项目根目录"},
    {"key": "KB_PUBLIC_ID", "label": "云端公共知识库ID", "required": True, "description": "ima 公共知识库 ID（可选，留空则使用本地搜索）"},
    {"key": "KB_PRIVATE_ID", "label": "云端私有知识库ID", "required": True, "description": "ima 私有知识库 ID（可选，留空则使用本地搜索）"},
    {"key": "COS_SECRET_ID", "label": "腾讯云密钥ID", "required": True, "description": "腾讯云 COS SecretId（用于文件上传，可选）"},
    {"key": "COS_SECRET_KEY", "label": "腾讯云密钥Key", "required": True, "description": "腾讯云 COS SecretKey（用于文件上传，可选）"},
]

# 4 个渠道配置
CHANNELS = {
    "feishu": {"name": "飞书", "icon": "🐦", "fields": ["FEISHU_WEBHOOK", "FEISHU_SECRET"]},
    "dingtalk": {"name": "钉钉", "icon": "💬", "fields": ["DINGTALK_WEBHOOK", "DINGTALK_SECRET"]},
    "wecom": {"name": "企业微信", "icon": "💼", "fields": ["WECOM_CORP_ID", "WECOM_AGENT_ID", "WECOM_CORP_SECRET"]},
    "wechat": {"name": "微信", "icon": "💚", "fields": ["WECHAT_APP_ID", "WECHAT_APP_SECRET"]},
}


def analyze_coverage():
    """分析知识库覆盖度，返回分析报告"""
    report = {
        "shared_kbs": [],
        "local_dbs": [],
        "env_status": [],
        "channel_status": [],
        "summary": {"total_gaps": 0, "critical_gaps": 0, "suggestions": []},
    }

    # 1. 分析共享知识库
    seeds_dir = PROJECT_ROOT / "seeds"
    config = load_config()

    # 按 shared_content 分类统计种子文件
    shared_content = config.get("shared_content", {}).get("categories", {})
    for cat_key, cat_info in shared_content.items():
        kb_name = cat_info.get("name", cat_key)
        expected_files = cat_info.get("files", [])
        actual_files = []
        for fname in expected_files:
            fpath = seeds_dir / fname
            if fpath.exists():
                fsize = fpath.stat().st_size
                actual_files.append({"name": fname, "size": fsize, "exists": True})
            else:
                actual_files.append({"name": fname, "size": 0, "exists": False})

        kb_def = SHARED_KBS.get(kb_name, {})
        file_count = sum(1 for f in actual_files if f["exists"])
        total_expected = len(expected_files)

        status = "good" if file_count >= total_expected * 0.8 else ("warning" if file_count > 0 else "critical")

        report["shared_kbs"].append({
            "name": kb_name,
            "icon": kb_def.get("icon", "📁"),
            "color": kb_def.get("color", "#64748B"),
            "description": cat_info.get("description", ""),
            "file_count": file_count,
            "total_expected": total_expected,
            "files": actual_files,
            "status": status,
            "suggested_uploads": kb_def.get("suggested_uploads", []),
        })

        if status != "good":
            report["summary"]["total_gaps"] += 1
            if status == "critical":
                report["summary"]["critical_gaps"] += 1

    # 2. 分析本地数据库
    local_db_dir = PROJECT_ROOT / "02_本地知识库"
    for db_name, db_info in LOCAL_DBS.items():
        db_path = PROJECT_ROOT / db_info["dir_name"]
        csv_path = db_path / db_info["csv_file"]

        files = []
        if db_path.exists():
            for f in db_path.iterdir():
                if f.is_file() and not f.name.startswith("."):
                    files.append({"name": f.name, "size": f.stat().st_size})

        csv_exists = csv_path.exists()
        status = "good" if (files or csv_exists) else "empty"

        report["local_dbs"].append({
            "name": db_name,
            "icon": db_info["icon"],
            "color": db_info["color"],
            "description": db_info["description"],
            "file_count": len(files),
            "files": files,
            "csv_template": db_info["csv_file"],
            "csv_exists": csv_exists,
            "path": str(db_path),
            "status": status,
            "suggested_uploads": db_info["suggested_uploads"],
        })

        if status == "empty":
            report["summary"]["total_gaps"] += 1
            report["summary"]["critical_gaps"] += 1

    # 3. 分析环境变量
    env_path = PROJECT_ROOT / ".env"
    env_values = parse_env(env_path) if env_path.exists() else {}

    for env_def in REQUIRED_ENVS:
        val = env_values.get(env_def["key"], "")
        status = "configured" if val.strip() else "missing"
        report["env_status"].append({
            "key": env_def["key"],
            "label": env_def["label"],
            "value": val if val else "",
            "required": env_def["required"],
            "description": env_def["description"],
            "status": status,
        })
        if status == "missing":
            report["summary"]["total_gaps"] += 1

    # 4. 分析渠道配置
    for ch_key, ch_info in CHANNELS.items():
        fields_filled = 0
        fields_total = len(ch_info["fields"])
        for field in ch_info["fields"]:
            if env_values.get(field, "").strip():
                fields_filled += 1
        status = "active" if fields_filled == fields_total else ("partial" if fields_filled > 0 else "inactive")
        report["channel_status"].append({
            "key": ch_key,
            "name": ch_info["name"],
            "icon": ch_info["icon"],
            "fields_filled": fields_filled,
            "fields_total": fields_total,
            "fields": [{"key": f, "value": env_values.get(f, "")} for f in ch_info["fields"]],
            "status": status,
        })

    # 5. 生成建议
    suggestions = []
    for kb in report["shared_kbs"]:
        if kb["status"] == "critical":
            suggestions.append(f"🔴 【{kb['name']}】完全没有文件，请上传：{', '.join(kb['suggested_uploads'][:2])}")
        elif kb["status"] == "warning":
            missing = [f["name"] for f in kb["files"] if not f["exists"]]
            suggestions.append(f"🟡 【{kb['name']}】缺少 {len(missing)} 个文件：{', '.join(missing)}")

    for db in report["local_dbs"]:
        if db["status"] == "empty":
            suggestions.append(f"🔴 【{db['name']}】为空，请上传：{', '.join(db['suggested_uploads'][:2])}")

    missing_envs = [e["key"] for e in report["env_status"] if e["status"] == "missing"]
    if missing_envs:
        suggestions.append(f"🟡 环境变量未配置：{', '.join(missing_envs)}")

    report["summary"]["suggestions"] = suggestions
    return report


def load_config():
    """加载 kb_config.json"""
    config_path = PROJECT_ROOT / "kb_config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def parse_env(env_path):
    """解析 .env 文件"""
    env = {}
    if not env_path.exists():
        return env
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    return env


def save_env(env_path, updates):
    """更新 .env 文件（保留注释和原有内容）"""
    lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = ["# BidAgent-KB 环境变量\n"]

    # 更新已有行
    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # 添加新行
    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    return True


def save_config(config_path, updates):
    """更新 kb_config.json"""
    config = load_config()
    config.update(updates)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return True


# ==================== HTML 前端 ====================

def generate_html():
    """生成管理控制台 HTML 页面"""
    return r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BidAgent-KB 管理控制台</title>
<style>
:root {
  --primary: #2563EB; --primary-light: #EFF6FF;
  --amber: #F59E0B; --amber-light: #FEF3C7;
  --green: #22C55E; --green-light: #DCFCE7;
  --red: #EF4444; --red-light: #FEE2E2;
  --purple: #8B5CF6; --cyan: #06B6D4; --indigo: #4F46E5;
  --bg: #F8FAFC; --surface: #FFFFFF; --border: #E2E8F0;
  --text: #1E293B; --text-secondary: #64748B; --text-muted: #94A3B8;
  --radius: 10px; --font: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--font); background: var(--bg); color: var(--text); }

/* Topbar */
.topbar { background: var(--surface); border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; align-items: center; gap: 24px; position: sticky; top: 0; z-index: 100; }
.topbar h1 { font-size: 18px; font-weight: 700; }
.topbar h1 span { color: var(--primary); }
.topbar-tabs { display: flex; gap: 4px; flex: 1; }
.topbar-tab { padding: 8px 16px; border-radius: 6px; font-size: 14px; font-weight: 500; color: var(--text-secondary); cursor: pointer; border: none; background: none; transition: all 0.15s; }
.topbar-tab:hover { background: #F1F5F9; color: var(--text); }
.topbar-tab.active { background: var(--primary-light); color: var(--primary); }
.topbar-status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); }
.topbar-status .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); }

/* Layout */
.container { max-width: 1100px; margin: 0 auto; padding: 24px; }
.page { display: none; }
.page.active { display: block; }

/* Cards */
.card { background: var(--surface); border-radius: var(--radius); border: 1px solid var(--border); margin-bottom: 16px; overflow: hidden; }
.card-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
.card-title { font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
.card-body { padding: 20px; }

/* Status badges */
.badge { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; }
.badge-good { background: var(--green-light); color: #166534; }
.badge-warning { background: var(--amber-light); color: #854D0E; }
.badge-critical { background: var(--red-light); color: #991B1B; }
.badge-empty { background: #F1F5F9; color: var(--text-muted); }
.badge-configured { background: var(--green-light); color: #166534; }
.badge-missing { background: var(--red-light); color: #991B1B; }
.badge-active { background: var(--green-light); color: #166534; }
.badge-partial { background: var(--amber-light); color: #854D0E; }
.badge-inactive { background: #F1F5F9; color: var(--text-muted); }

/* Coverage grid */
.kb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.kb-item { background: var(--surface); border-radius: var(--radius); border: 1px solid var(--border); padding: 16px; border-top: 3px solid var(--primary); }
.kb-item-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.kb-item-name { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.kb-item-desc { font-size: 12px; color: var(--text-muted); margin-bottom: 12px; }
.kb-item-files { font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; }
.kb-item-files ul { list-style: none; padding: 0; }
.kb-item-files li { padding: 4px 0; display: flex; align-items: center; gap: 6px; }
.kb-item-files .file-icon { font-size: 14px; }

/* Suggestion box */
.suggestion { background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; font-size: 13px; color: #854D0E; line-height: 1.6; }
.suggestion-list { background: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 8px; padding: 12px 16px; margin-top: 8px; }
.suggestion-list-title { font-size: 13px; font-weight: 600; color: #0369A1; margin-bottom: 8px; }
.suggestion-list ul { list-style: none; padding: 0; }
.suggestion-list li { padding: 3px 0; font-size: 12px; color: var(--text-secondary); display: flex; align-items: flex-start; gap: 6px; }
.suggestion-list li::before { content: "▸"; color: var(--primary); flex-shrink: 0; }

/* Upload zone */
.upload-zone { border: 2px dashed var(--border); border-radius: var(--radius); padding: 40px; text-align: center; cursor: pointer; transition: all 0.2s; margin-bottom: 16px; }
.upload-zone:hover, .upload-zone.dragover { border-color: var(--primary); background: var(--primary-light); }
.upload-icon { font-size: 48px; margin-bottom: 12px; }
.upload-text { font-size: 16px; color: var(--text); margin-bottom: 8px; }
.upload-hint { font-size: 13px; color: var(--text-muted); }
.upload-target { font-weight: 600; color: var(--primary); }

/* Target selector */
.target-selector { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.target-chip { padding: 8px 14px; border-radius: 20px; font-size: 13px; font-weight: 500; cursor: pointer; border: 2px solid var(--border); background: var(--surface); color: var(--text-secondary); transition: all 0.15s; display: flex; align-items: center; gap: 6px; }
.target-chip:hover { border-color: var(--primary); }
.target-chip.active { border-color: var(--primary); background: var(--primary-light); color: var(--primary); }
.target-chip .count { background: var(--border); color: var(--text); border-radius: 10px; padding: 1px 6px; font-size: 11px; }
.target-chip.active .count { background: var(--primary); color: white; }

/* File table */
.file-table { width: 100%; border-collapse: collapse; }
.file-table th { text-align: left; padding: 10px 12px; font-size: 12px; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border); text-transform: uppercase; letter-spacing: 0.5px; }
.file-table td { padding: 10px 12px; font-size: 13px; border-bottom: 1px solid var(--border); }
.file-table tr:hover { background: #F8FAFC; }

/* Config form */
.form-group { margin-bottom: 16px; }
.form-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.form-input { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; font-family: var(--font); outline: none; transition: border 0.15s; }
.form-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
.form-hint { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

/* Channel card */
.channel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.channel-card { border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; }
.channel-card.active { border-color: var(--green); background: #F0FDF4; }
.channel-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.channel-name { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.channel-toggle { width: 40px; height: 22px; border-radius: 11px; background: #CBD5E1; position: relative; cursor: pointer; transition: background 0.2s; }
.channel-toggle.active { background: var(--green); }
.channel-toggle::after { content: ''; position: absolute; width: 18px; height: 18px; border-radius: 50%; background: white; top: 2px; left: 2px; transition: left 0.2s; }
.channel-toggle.active::after { left: 20px; }

/* Buttons */
.btn { padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; transition: all 0.15s; display: inline-flex; align-items: center; gap: 6px; }
.btn-primary { background: var(--primary); color: white; }
.btn-primary:hover { background: #1D4ED8; }
.btn-outline { background: var(--surface); color: var(--text); border: 1px solid var(--border); }
.btn-outline:hover { background: #F1F5F9; }
.btn-success { background: var(--green); color: white; }
.btn-danger { background: var(--red); color: white; }
.btn-sm { padding: 6px 12px; font-size: 12px; }

/* Summary banner */
.summary-banner { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.summary-stat { background: var(--surface); border-radius: var(--radius); border: 1px solid var(--border); padding: 16px 20px; text-align: center; }
.summary-stat .num { font-size: 28px; font-weight: 800; }
.summary-stat .label { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

/* Toast */
.toast { position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%) translateY(100px); background: rgba(0,0,0,0.85); color: white; padding: 12px 24px; border-radius: 24px; font-size: 14px; z-index: 999; transition: transform 0.3s; }
.toast.show { transform: translateX(-50%) translateY(0); }
.toast.success { background: var(--green); }
.toast.error { background: var(--red); }

/* Spinner */
.spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border); border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Empty state */
.empty-state { text-align: center; padding: 40px; color: var(--text-muted); }
.empty-state .icon { font-size: 48px; margin-bottom: 12px; }
</style>
</head>
<body>

<div class="topbar">
  <h1>📋 BidAgent-KB <span>管理控制台</span></h1>
  <div class="topbar-tabs">
    <button class="topbar-tab active" onclick="switchPage('coverage')">📊 覆盖度分析</button>
    <button class="topbar-tab" onclick="switchPage('upload')">📤 文件上传</button>
    <button class="topbar-tab" onclick="switchPage('config')">⚙️ 参数配置</button>
  </div>
  <div class="topbar-status"><div class="dot"></div> 本地运行中</div>
</div>

<div class="container">

  <!-- ==================== 页面1：覆盖度分析 ==================== -->
  <div class="page active" id="page-coverage">
    <div id="coverage-content">
      <div style="text-align:center; padding:60px;"><div class="spinner"></div><p style="margin-top:12px;color:var(--text-muted);">正在分析知识库覆盖度...</p></div>
    </div>
  </div>

  <!-- ==================== 页面2：文件上传 ==================== -->
  <div class="page" id="page-upload">
    <div class="card">
      <div class="card-header">
        <div class="card-title">📤 上传文件到知识库</div>
        <button class="btn btn-outline btn-sm" onclick="loadFileList()">🔄 刷新</button>
      </div>
      <div class="card-body">
        <div class="form-group">
          <label class="form-label">选择目标知识库</label>
          <div class="target-selector" id="target-selector"></div>
        </div>
        <div class="upload-zone" id="upload-zone" ondrop="handleDrop(event)" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)" onclick="document.getElementById('file-input').click()">
          <div class="upload-icon">📎</div>
          <div class="upload-text">拖拽文件到此处，或点击选择文件</div>
          <div class="upload-hint">文件将上传到：<span class="upload-target" id="upload-target">seeds/</span></div>
          <div style="margin-top:8px;display:flex;gap:6px;justify-content:center;flex-wrap:wrap;">
            <span style="background:#F1F5F9;padding:2px 8px;border-radius:4px;font-size:11px;color:var(--text-muted);">.md</span>
            <span style="background:#F1F5F9;padding:2px 8px;border-radius:4px;font-size:11px;color:var(--text-muted);">.txt</span>
            <span style="background:#F1F5F9;padding:2px 8px;border-radius:4px;font-size:11px;color:var(--text-muted);">.pdf</span>
            <span style="background:#F1F5F9;padding:2px 8px;border-radius:4px;font-size:11px;color:var(--text-muted);">.docx</span>
            <span style="background:#F1F5F9;padding:2px 8px;border-radius:4px;font-size:11px;color:var(--text-muted);">.csv</span>
          </div>
        </div>
        <input type="file" id="file-input" multiple style="display:none" onchange="handleFileSelect(event)">
        <div id="upload-result"></div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div class="card-title">📋 当前文件列表</div>
      </div>
      <div class="card-body" id="file-list-content">
        <div style="text-align:center;padding:20px;color:var(--text-muted);">请先选择目标知识库</div>
      </div>
    </div>
  </div>

  <!-- ==================== 页面3：参数配置 ==================== -->
  <div class="page" id="page-config">
    <div class="card">
      <div class="card-header">
        <div class="card-title">🔧 环境变量配置</div>
        <button class="btn btn-primary btn-sm" onclick="saveEnv()">💾 保存配置</button>
      </div>
      <div class="card-body">
        <p style="font-size:13px;color:var(--text-secondary);margin-bottom:16px;">配置将保存到项目根目录的 <code style="background:#F1F5F9;padding:2px 6px;border-radius:4px;">.env</code> 文件</p>
        <div id="env-form"><div style="text-align:center;padding:20px;"><div class="spinner"></div></div></div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">💬 消息推送渠道</div>
      </div>
      <div class="card-body">
        <p style="font-size:13px;color:var(--text-secondary);margin-bottom:16px;">配置各渠道的 Webhook 地址和密钥，保存后即可使用 <code style="background:#F1F5F9;padding:2px 6px;border-radius:4px;">channel_notify.py</code> 推送消息</p>
        <div class="channel-grid" id="channel-grid"></div>
        <div style="margin-top:16px;text-align:right;">
          <button class="btn btn-primary" onclick="saveChannels()">💾 保存渠道配置</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">📦 后端配置</div>
      </div>
      <div class="card-body">
        <div class="form-group">
          <label class="form-label">检索后端类型</label>
          <select class="form-input" id="backend-select">
            <option value="local_search">local_search — 本地全文检索（零依赖，推荐）</option>
            <option value="ima">ima — 腾讯云知识库（需配置云端ID）</option>
            <option value="both">both — 混合检索（本地+云端）</option>
            <option value="chromadb">chromadb — 向量语义搜索（需安装依赖，高级）</option>
          </select>
          <div class="form-hint">不同后端的检索能力和依赖不同，详见部署指南</div>
        </div>
        <div style="margin-top:12px;">
          <button class="btn btn-primary" onclick="saveBackend()">💾 保存后端配置</button>
        </div>
      </div>
    </div>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
let coverageData = null;
let currentTarget = 'seeds';

// ========== 页面切换 ==========
function switchPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.topbar-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  document.querySelectorAll('.topbar-tab').forEach((t, i) => {
    if ((page === 'coverage' && i === 0) || (page === 'upload' && i === 1) || (page === 'config' && i === 2)) {
      t.classList.add('active');
    }
  });
  if (page === 'upload') loadFileList();
  if (page === 'config') loadConfig();
}

// ========== Toast ==========
function showToast(msg, type) {
  var toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast show' + (type ? ' ' + type : '');
  setTimeout(function() { toast.className = 'toast'; }, 2500);
}

// ========== 覆盖度分析 ==========
async function loadCoverage() {
  try {
    const resp = await fetch('/api/coverage');
    coverageData = await resp.json();
    renderCoverage();
  } catch(e) {
    document.getElementById('coverage-content').innerHTML = '<div class="empty-state"><div class="icon">❌</div><p>加载失败: ' + e.message + '</p></div>';
  }
}

function renderCoverage() {
  const d = coverageData;
  const s = d.summary;
  let html = '';

  // 统计摘要
  const goodCount = d.shared_kbs.filter(k => k.status === 'good').length + d.local_dbs.filter(k => k.status === 'good').length;
  const warningCount = d.shared_kbs.filter(k => k.status === 'warning').length;
  const criticalCount = s.critical_gaps;
  html += '<div class="summary-banner">';
  html += '<div class="summary-stat"><div class="num" style="color:var(--green);">' + goodCount + '</div><div class="label">已覆盖</div></div>';
  html += '<div class="summary-stat"><div class="num" style="color:var(--amber);">' + warningCount + '</div><div class="label">部分覆盖</div></div>';
  html += '<div class="summary-stat"><div class="num" style="color:var(--red);">' + criticalCount + '</div><div class="label">严重缺失</div></div>';
  html += '<div class="summary-stat"><div class="num" style="color:var(--primary);">' + d.env_status.filter(e => e.status === 'configured').length + '/' + d.env_status.length + '</div><div class="label">环境变量</div></div>';
  html += '</div>';

  // 建议列表
  if (s.suggestions.length > 0) {
    html += '<div class="card"><div class="card-header"><div class="card-title">💡 智能建议</div></div><div class="card-body">';
    s.suggestions.forEach(sug => {
      html += '<div class="suggestion">' + sug + '</div>';
    });
    html += '<div style="margin-top:12px;"><button class="btn btn-primary" onclick="switchPage(\'upload\')">📤 去上传文件</button> <button class="btn btn-outline" onclick="switchPage(\'config\')">⚙️ 去配置参数</button></div>';
    html += '</div></div>';
  } else {
    html += '<div class="card"><div class="card-body" style="text-align:center;padding:30px;"><div style="font-size:48px;">✅</div><p style="margin-top:12px;font-size:16px;font-weight:600;color:var(--green);">知识库覆盖度良好！</p><p style="font-size:13px;color:var(--text-muted);">所有知识库均已配置，无需补充</p></div></div>';
  }

  // 共享知识库
  html += '<div class="card"><div class="card-header"><div class="card-title">📚 共享知识库（' + d.shared_kbs.length + '座）</div></div><div class="card-body">';
  html += '<div class="kb-grid">';
  d.shared_kbs.forEach(kb => {
    const statusMap = {good: '已覆盖', warning: '部分覆盖', critical: '严重缺失'};
    const badgeMap = {good: 'badge-good', warning: 'badge-warning', critical: 'badge-critical'};
    html += '<div class="kb-item" style="border-top-color:' + kb.color + '">';
    html += '<div class="kb-item-header"><div class="kb-item-name">' + kb.icon + ' ' + kb.name + '</div>';
    html += '<span class="badge ' + badgeMap[kb.status] + '">' + statusMap[kb.status] + '</span></div>';
    html += '<div class="kb-item-desc">' + kb.description + '</div>';
    html += '<div class="kb-item-files"><strong>文件 (' + kb.file_count + '/' + kb.total_expected + ')</strong><ul>';
    kb.files.forEach(f => {
      html += '<li><span class="file-icon">' + (f.exists ? '✅' : '❌') + '</span> ' + f.name + (f.exists ? ' <span style="color:var(--text-muted);">(' + formatSize(f.size) + ')</span>' : '') + '</li>';
    });
    html += '</ul></div>';
    if (kb.status !== 'good') {
      html += '<div class="suggestion-list"><div class="suggestion-list-title">📌 建议上传</div><ul>';
      kb.suggested_uploads.forEach(s => { html += '<li>' + s + '</li>'; });
      html += '</ul></div>';
    }
    html += '</div>';
  });
  html += '</div></div></div>';

  // 本地数据库
  html += '<div class="card"><div class="card-header"><div class="card-title">📁 本地知识库（' + d.local_dbs.length + '个）</div></div><div class="card-body">';
  html += '<div class="kb-grid">';
  d.local_dbs.forEach(db => {
    const statusMap = {good: '已配置', empty: '未配置'};
    const badgeMap = {good: 'badge-good', empty: 'badge-empty'};
    html += '<div class="kb-item" style="border-top-color:' + db.color + '">';
    html += '<div class="kb-item-header"><div class="kb-item-name">' + db.icon + ' ' + db.name + '</div>';
    html += '<span class="badge ' + badgeMap[db.status] + '">' + statusMap[db.status] + '</span></div>';
    html += '<div class="kb-item-desc">' + db.description + '</div>';
    html += '<div class="kb-item-files">文件数: <strong>' + db.file_count + '</strong> | CSV模板: ' + (db.csv_exists ? '✅ 已创建' : '❌ 未创建') + '</div>';
    if (db.status === 'empty') {
      html += '<div class="suggestion-list"><div class="suggestion-list-title">📌 建议上传</div><ul>';
      db.suggested_uploads.forEach(s => { html += '<li>' + s + '</li>'; });
      html += '</ul></div>';
    }
    html += '</div>';
  });
  html += '</div></div></div>';

  // 环境变量状态
  html += '<div class="card"><div class="card-header"><div class="card-title">🔐 环境变量状态</div><button class="btn btn-outline btn-sm" onclick="switchPage(\'config\')">⚙️ 去配置</button></div><div class="card-body">';
  html += '<table class="file-table"><thead><tr><th>变量名</th><th>说明</th><th>状态</th></tr></thead><tbody>';
  d.env_status.forEach(e => {
    const badgeMap = {configured: 'badge-configured', missing: 'badge-missing'};
    const statusText = {configured: '✅ 已配置', missing: '❌ 未配置'};
    html += '<tr><td><code>' + e.key + '</code></td><td>' + e.label + '</td><td><span class="badge ' + badgeMap[e.status] + '">' + statusText[e.status] + '</span></td></tr>';
  });
  html += '</tbody></table></div></div>';

  // 渠道状态
  html += '<div class="card"><div class="card-header"><div class="card-title">💬 消息推送渠道</div><button class="btn btn-outline btn-sm" onclick="switchPage(\'config\')">⚙️ 去配置</button></div><div class="card-body">';
  html += '<div class="channel-grid">';
  d.channel_status.forEach(ch => {
    const badgeMap = {active: 'badge-active', partial: 'badge-partial', inactive: 'badge-inactive'};
    const statusText = {active: '✅ 已配置', partial: '🔶 部分配置', inactive: '⚪ 未配置'};
    html += '<div class="channel-card' + (ch.status === 'active' ? ' active' : '') + '">';
    html += '<div class="channel-header"><div class="channel-name">' + ch.icon + ' ' + ch.name + '</div>';
    html += '<span class="badge ' + badgeMap[ch.status] + '">' + statusText[ch.status] + '</span></div>';
    html += '<div style="font-size:12px;color:var(--text-muted);">已填写 ' + ch.fields_filled + '/' + ch.fields_total + ' 个字段</div>';
    html += '</div>';
  });
  html += '</div></div></div>';

  document.getElementById('coverage-content').innerHTML = html;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

// ========== 文件上传 ==========
async function loadFileList() {
  // 加载目标选择器
  if (!coverageData) {
    try {
      const resp = await fetch('/api/coverage');
      coverageData = await resp.json();
    } catch(e) { return; }
  }

  const selector = document.getElementById('target-selector');
  let html = '';
  // 共享知识库 seeds 目录
  html += '<div class="target-chip active" onclick="selectTarget(this, \'seeds\')"><span>📚</span> 共享知识库(seeds/) <span class="count">' + coverageData.shared_kbs.reduce((a, k) => a + k.file_count, 0) + '</span></div>';
  // 本地数据库
  coverageData.local_dbs.forEach(db => {
    const dirName = db.path.split(/[\\/]/).pop();
    const relPath = db.path.replace(/\\/g, '/').split('/').slice(-2).join('/');
    html += '<div class="target-chip" onclick="selectTarget(this, \'' + relPath + '\')"><span>' + db.icon + '</span> ' + db.name + ' <span class="count">' + db.file_count + '</span></div>';
  });
  selector.innerHTML = html;

  loadFiles(currentTarget);
}

function selectTarget(el, target) {
  document.querySelectorAll('.target-chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  currentTarget = target;
  document.getElementById('upload-target').textContent = target;
  loadFiles(target);
}

async function loadFiles(target) {
  try {
    const resp = await fetch('/api/files?dir=' + encodeURIComponent(target));
    const data = await resp.json();
    const content = document.getElementById('file-list-content');
    if (!data.files || data.files.length === 0) {
      content.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>该目录暂无文件</p><p style="font-size:13px;margin-top:4px;">请通过上方上传区域添加文件</p></div>';
      return;
    }
    let html = '<table class="file-table"><thead><tr><th>文件名</th><th>大小</th><th>修改时间</th><th>操作</th></tr></thead><tbody>';
    data.files.forEach(f => {
      html += '<tr><td>' + f.name + '</td><td>' + formatSize(f.size) + '</td><td style="color:var(--text-muted);">' + f.modified + '</td>';
      html += '<td><button class="btn btn-danger btn-sm" onclick="deleteFile(\'' + target + '\', \'' + f.name + '\')">🗑 删除</button></td></tr>';
    });
    html += '</tbody></table>';
    content.innerHTML = html;
  } catch(e) {
    document.getElementById('file-list-content').innerHTML = '<div class="empty-state"><div class="icon">❌</div><p>加载失败</p></div>';
  }
}

async function deleteFile(dir, name) {
  if (!confirm('确定删除 ' + name + ' 吗？')) return;
  try {
    const resp = await fetch('/api/files?dir=' + encodeURIComponent(dir) + '&name=' + encodeURIComponent(name), {method: 'DELETE'});
    const data = await resp.json();
    if (data.success) {
      showToast('已删除 ' + name, 'success');
      loadFiles(currentTarget);
    } else {
      showToast('删除失败: ' + data.message, 'error');
    }
  } catch(e) { showToast('删除失败', 'error'); }
}

function handleDragOver(e) { e.preventDefault(); document.getElementById('upload-zone').classList.add('dragover'); }
function handleDragLeave(e) { e.preventDefault(); document.getElementById('upload-zone').classList.remove('dragover'); }
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('upload-zone').classList.remove('dragover');
  uploadFiles(e.dataTransfer.files);
}
function handleFileSelect(e) { uploadFiles(e.target.files); }

async function uploadFiles(files) {
  if (!files.length) return;
  const result = document.getElementById('upload-result');
  result.innerHTML = '<div style="text-align:center;padding:12px;"><div class="spinner"></div> 正在上传 ' + files.length + ' 个文件...</div>';

  const formData = new FormData();
  formData.append('dir', currentTarget);
  for (const file of files) {
    formData.append('files', file, file.name);
  }

  try {
    const resp = await fetch('/api/upload', {method: 'POST', body: formData});
    const data = await resp.json();
    if (data.success) {
      result.innerHTML = '<div class="suggestion" style="background:var(--green-light);border-color:var(--green);color:#166534;">✅ ' + data.message + '</div>';
      showToast('上传成功 ' + files.length + ' 个文件', 'success');
      loadFiles(currentTarget);
      loadCoverage();
    } else {
      result.innerHTML = '<div class="suggestion" style="background:var(--red-light);border-color:var(--red);color:#991B1B;">❌ ' + data.message + '</div>';
      showToast('上传失败', 'error');
    }
  } catch(e) {
    result.innerHTML = '<div class="suggestion" style="background:var(--red-light);border-color:var(--red);color:#991B1B;">❌ 上传失败: ' + e.message + '</div>';
  }
}

// ========== 参数配置 ==========
async function loadConfig() {
  try {
    const resp = await fetch('/api/config');
    const data = await resp.json();
    renderEnvForm(data.env);
    renderChannels(data.channels);
    document.getElementById('backend-select').value = data.backend || 'local_search';
  } catch(e) { showToast('加载配置失败', 'error'); }
}

function renderEnvForm(envs) {
  let html = '';
  envs.forEach(e => {
    html += '<div class="form-group">';
    html += '<label class="form-label">' + e.key;
    if (e.required) html += ' <span style="color:var(--red);">*</span>';
    html += '</label>';
    html += '<input type="text" class="form-input" id="env-' + e.key + '" value="' + (e.value || '') + '" placeholder="' + e.description + '">';
    html += '<div class="form-hint">' + e.description + '</div>';
    html += '</div>';
  });
  document.getElementById('env-form').innerHTML = html;
}

function renderChannels(channels) {
  let html = '';
  channels.forEach(ch => {
    const isActive = ch.status === 'active';
    html += '<div class="channel-card' + (isActive ? ' active' : '') + '" id="channel-card-' + ch.key + '">';
    html += '<div class="channel-header"><div class="channel-name">' + ch.icon + ' ' + ch.name + '</div>';
    html += '<div class="channel-toggle' + (isActive ? ' active' : '') + '" onclick="toggleChannel(\'' + ch.key + '\')"></div></div>';
    ch.fields.forEach(f => {
      html += '<div class="form-group" style="margin-bottom:8px;">';
      html += '<input type="text" class="form-input" id="ch-' + f.key + '" value="' + (f.value || '') + '" placeholder="' + f.key + '" style="font-size:13px;">';
      html += '</div>';
    });
    html += '</div>';
  });
  document.getElementById('channel-grid').innerHTML = html;
}

function toggleChannel(key) {
  const card = document.getElementById('channel-card-' + key);
  const toggle = card.querySelector('.channel-toggle');
  card.classList.toggle('active');
  toggle.classList.toggle('active');
}

async function saveEnv() {
  const envs = coverageData ? coverageData.env_status : [];
  const updates = {};
  envs.forEach(e => {
    const el = document.getElementById('env-' + e.key);
    if (el) updates[e.key] = el.value;
  });
  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({type: 'env', data: updates})
    });
    const data = await resp.json();
    if (data.success) { showToast('环境变量已保存到 .env', 'success'); loadCoverage(); }
    else { showToast('保存失败: ' + data.message, 'error'); }
  } catch(e) { showToast('保存失败', 'error'); }
}

async function saveChannels() {
  const channels = coverageData ? coverageData.channel_status : [];
  const updates = {};
  channels.forEach(ch => {
    ch.fields.forEach(f => {
      const el = document.getElementById('ch-' + f.key);
      if (el) updates[f.key] = el.value;
    });
  });
  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({type: 'env', data: updates})
    });
    const data = await resp.json();
    if (data.success) { showToast('渠道配置已保存到 .env', 'success'); loadCoverage(); }
    else { showToast('保存失败', 'error'); }
  } catch(e) { showToast('保存失败', 'error'); }
}

async function saveBackend() {
  const backend = document.getElementById('backend-select').value;
  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({type: 'backend', data: backend})
    });
    const data = await resp.json();
    if (data.success) showToast('后端已切换为: ' + backend, 'success');
    else showToast('保存失败', 'error');
  } catch(e) { showToast('保存失败', 'error'); }
}

// ========== 初始化 ==========
loadCoverage();
</script>

</body>
</html>'''


# ==================== HTTP 请求处理器 ====================

class ConsoleHandler(BaseHTTPRequestHandler):
    """管理控制台 HTTP 请求处理器"""

    def log_message(self, format, *args):
        # 静默日志
        pass

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._serve_html()
        elif self.path == '/api/coverage':
            self._serve_json(analyze_coverage())
        elif self.path.startswith('/api/files'):
            self._serve_files()
        elif self.path == '/api/config':
            self._serve_config()
        else:
            self._serve_404()

    def do_POST(self):
        try:
            if self.path == '/api/upload':
                self._handle_upload()
            elif self.path == '/api/config':
                self._handle_config_save()
            else:
                self._serve_404()
        except Exception as e:
            try:
                self._serve_json({"success": False, "message": f"服务器错误: {e}"})
            except Exception:
                pass

    def do_DELETE(self):
        try:
            if self.path.startswith('/api/files'):
                self._handle_delete()
            else:
                self._serve_404()
        except Exception as e:
            try:
                self._serve_json({"success": False, "message": f"服务器错误: {e}"})
            except Exception:
                pass

    def _serve_html(self):
        html = generate_html()
        self._respond(200, "text/html; charset=utf-8", html.encode("utf-8"))

    def _serve_json(self, data):
        self._respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_files(self):
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        dir_name = query.get("dir", ["seeds"])[0]

        # 安全检查：防止目录遍历
        target = (PROJECT_ROOT / dir_name).resolve()
        root = PROJECT_ROOT.resolve()
        try:
            target.relative_to(root)
        except ValueError:
            self._serve_json({"error": "非法路径"})
            return

        if not target.exists():
            self._serve_json({"files": []})
            return

        files = []
        for f in target.iterdir():
            if f.is_file() and not f.name.startswith("."):
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "size": stat.st_size,
                    "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                })

        files.sort(key=lambda x: x["modified"], reverse=True)
        self._serve_json({"files": files})

    def _serve_config(self):
        env_path = PROJECT_ROOT / ".env"
        env_values = parse_env(env_path) if env_path.exists() else {}

        env_list = []
        for env_def in REQUIRED_ENVS:
            env_list.append({
                "key": env_def["key"],
                "label": env_def["label"],
                "value": env_values.get(env_def["key"], ""),
                "required": env_def["required"],
                "description": env_def["description"],
                "status": "configured" if env_values.get(env_def["key"], "").strip() else "missing",
            })

        channel_list = []
        for ch_key, ch_info in CHANNELS.items():
            fields = []
            for field in ch_info["fields"]:
                fields.append({"key": field, "value": env_values.get(field, "")})
            filled = sum(1 for f in fields if f["value"].strip())
            channel_list.append({
                "key": ch_key,
                "name": ch_info["name"],
                "icon": ch_info["icon"],
                "fields": fields,
                "status": "active" if filled == len(fields) else ("partial" if filled > 0 else "inactive"),
            })

        config = load_config()
        backend = config.get("backend", {}).get("type", "local_search") if isinstance(config.get("backend"), dict) else "local_search"

        self._serve_json({"env": env_list, "channels": channel_list, "backend": backend})

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._serve_json({"success": False, "message": "需要 multipart/form-data"})
            return

        # 解析 multipart 表单
        boundary = content_type.split("boundary=")[1].encode()
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))

        parts = body.split(b"--" + boundary)
        dir_name = "seeds"
        files = []

        for part in parts:
            if not part or part == b"--\r\n" or part == b"--":
                continue
            # 去掉前后的 \r\n
            if part.startswith(b"\r\n"):
                part = part[2:]
            if part.endswith(b"\r\n"):
                part = part[:-2]

            # 分离 header 和 content
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue

            header_str = part[:header_end].decode("utf-8", errors="replace")
            content = part[header_end + 4:]

            # 解析 header
            name = None
            filename = None
            for line in header_str.split("\r\n"):
                if "Content-Disposition" in line:
                    for pair in line.split(";"):
                        pair = pair.strip()
                        if pair.startswith("name="):
                            name = pair[6:-1] if pair.endswith('"') else pair[5:]
                        elif pair.startswith("filename="):
                            filename = pair[10:-1] if pair.endswith('"') else pair[9:]

            if name == "dir":
                dir_name = content.decode("utf-8", errors="replace").strip()
            elif name == "files" and filename:
                files.append({"filename": filename, "content": content})

        # 安全检查
        target = (PROJECT_ROOT / dir_name).resolve()
        root = PROJECT_ROOT.resolve()
        try:
            target.relative_to(root)
        except ValueError:
            self._serve_json({"success": False, "message": "非法目标路径"})
            return

        target.mkdir(parents=True, exist_ok=True)

        saved = []
        for f in files:
            fpath = target / f["filename"]
            with open(fpath, "wb") as fp:
                fp.write(f["content"])
            saved.append(f["filename"])

        self._serve_json({
            "success": True,
            "message": f"成功上传 {len(saved)} 个文件到 {dir_name}/：{', '.join(saved)}"
        })

    def _handle_config_save(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._serve_json({"success": False, "message": "JSON 解析失败"})
            return

        if data.get("type") == "env":
            env_path = PROJECT_ROOT / ".env"
            save_env(env_path, data["data"])
            self._serve_json({"success": True, "message": "环境变量已保存"})
        elif data.get("type") == "backend":
            config_path = PROJECT_ROOT / "kb_config.json"
            config = load_config()
            if "backend" not in config or not isinstance(config["backend"], dict):
                config["backend"] = {"type": "local_search"}
            config["backend"]["type"] = data["data"]
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self._serve_json({"success": True, "message": "后端配置已保存"})
        else:
            self._serve_json({"success": False, "message": "未知配置类型"})

    def _handle_delete(self):
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        dir_name = query.get("dir", ["seeds"])[0]
        file_name = query.get("name", [""])[0]

        if not file_name:
            self._serve_json({"success": False, "message": "缺少文件名"})
            return

        target = (PROJECT_ROOT / dir_name / file_name).resolve()
        root = PROJECT_ROOT.resolve()
        try:
            target.relative_to(root)
        except ValueError:
            self._serve_json({"success": False, "message": "非法路径"})
            return

        if target.exists() and target.is_file():
            target.unlink()
            self._serve_json({"success": True, "message": f"已删除 {file_name}"})
        else:
            self._serve_json({"success": False, "message": "文件不存在"})

    def _respond(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_404(self):
        self._respond(404, "text/plain", b"404 Not Found")


# ==================== CLI 入口 ====================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="BidAgent-KB 管理控制台")
    parser.add_argument("--port", type=int, default=8765, help="端口号（默认 8765）")
    parser.add_argument("--check", action="store_true", help="仅输出覆盖度分析报告（不启动服务器）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    if args.check:
        report = analyze_coverage()
        print("\n" + "=" * 60)
        print("  BidAgent-KB 知识库覆盖度分析报告")
        print("=" * 60)

        print(f"\n📊 总览：")
        print(f"  严重缺失: {report['summary']['critical_gaps']} 个")
        print(f"  总缺口数: {report['summary']['total_gaps']} 个")

        print(f"\n📚 共享知识库 ({len(report['shared_kbs'])} 座):")
        for kb in report["shared_kbs"]:
            status_icon = {"good": "✅", "warning": "🟡", "critical": "🔴"}[kb["status"]]
            print(f"  {status_icon} {kb['name']}: {kb['file_count']}/{kb['total_expected']} 个文件")
            if kb["status"] != "good":
                print(f"     建议上传: {', '.join(kb['suggested_uploads'][:2])}")

        print(f"\n📁 本地知识库 ({len(report['local_dbs'])} 个):")
        for db in report["local_dbs"]:
            status_icon = "✅" if db["status"] == "good" else "🔴"
            print(f"  {status_icon} {db['name']}: {db['file_count']} 个文件 | CSV模板: {'已创建' if db['csv_exists'] else '未创建'}")
            if db["status"] == "empty":
                print(f"     建议上传: {', '.join(db['suggested_uploads'][:2])}")

        print(f"\n🔐 环境变量 ({len(report['env_status'])} 个):")
        for e in report["env_status"]:
            status_icon = "✅" if e["status"] == "configured" else "❌"
            print(f"  {status_icon} {e['key']}: {e['status']}")

        print(f"\n💬 消息推送渠道 ({len(report['channel_status'])} 个):")
        for ch in report["channel_status"]:
            status_map = {"active": "✅ 已配置", "partial": "🔶 部分", "inactive": "⚪ 未配置"}
            print(f"  {status_map[ch['status']]} {ch['name']}: {ch['fields_filled']}/{ch['fields_total']} 字段")

        if report["summary"]["suggestions"]:
            print(f"\n💡 智能建议:")
            for sug in report["summary"]["suggestions"]:
                print(f"  {sug}")

        print(f"\n{'=' * 60}")
        print(f"  运行 'python scripts/kb_console.py' 启动交互式管理控制台")
        print(f"{'=' * 60}\n")
        return

    # 启动服务器
    server = HTTPServer(("127.0.0.1", args.port), ConsoleHandler)
    url = f"http://127.0.0.1:{args.port}"

    print(f"\n{'=' * 60}")
    print(f"  BidAgent-KB 管理控制台已启动")
    print(f"{'=' * 60}")
    print(f"  📊 访问地址: {url}")
    print(f"  📂 项目根目录: {PROJECT_ROOT}")
    print(f"  按 Ctrl+C 停止服务器")
    print(f"{'=' * 60}\n")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n服务器已停止。")
        server.server_close()


if __name__ == "__main__":
    main()
