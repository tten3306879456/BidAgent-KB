#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库自动索引工具 (Knowledge Base Auto Indexer)
===================================================
用法: python kb_auto_index.py <文件路径>

功能:
  1. 提取 PDF/Word/TXT 文件文本内容
  2. 自动分类到 5 个知识库类别之一
  3. 提取标准编号、标题、适用范围等元数据
  4. 生成结构化摘要条目（含标书响应要点）
  5. 自动追加到对应的本地 .md 种子文件
  6. 输出分类结果和摘要内容，供审核

依赖: PyPDF2 (pip install PyPDF2)
"""

import sys
import os
import re
import json
from pathlib import Path
from datetime import datetime

# ============================================================
# 配置区 — 优先读取 kb_config.json，找不到则用默认路径
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
                seed_rel = cfg.get("cloud_seed_dir", "01_云端知识库\\种子文件")
                if base and base.exists():
                    return base / seed_rel
                # 如果 base_path 不存在，回退到项目目录结构
                return Path(__file__).parent.parent / "知识库种子内容"
    # 没找到配置文件，用默认路径
    return Path(__file__).parent.parent / "知识库种子内容"

KB_BASE = _load_config()

CATEGORIES = {
    "行业技术标准库": {
        "file": "行业技术标准库_种子版.md",
        "keywords": ["GB", "GBZ", "GB/T", "标准", "规范", "技术要求", "防护",
                      "等保", "安全", "数据", "网络", "云", "软件"],
        "exclude_keywords": ["废标", "报价", "保证金", "资质替代", "招标投标法"],
        "section_header": "## {num}、{title}",
        "template": "standard"
    },
    "标书核心法规汇编": {
        "file": "标书核心法规汇编_v1.0.md",
        "keywords": ["招标投标法", "政府采购法", "实施条例", "管理办法",
                      "暂行规定", "条例", "法规", "中华人民共和国"],
        "exclude_keywords": ["GB", "GBZ", "标准", "报价", "保证金", "资质"],
        "section_header": "## {num}、{title}",
        "template": "law"
    },
    "废标条款模式库": {
        "file": "废标条款模式库_种子版.md",
        "keywords": ["废标", "无效投标", "否决投标", "资格不符",
                      "投标无效", "否决"],
        "exclude_keywords": ["GB", "标准", "报价", "资质替代"],
        "section_header": "## {num}、{title}",
        "template": "pattern"
    },
    "报价与商务法规库": {
        "file": "招投标报价与商务法规专题库_种子版.md",
        "keywords": ["报价", "保证金", "采购", "合同", "中小企业",
                      "价格", "商务", "履约", "付款"],
        "exclude_keywords": ["GB", "GBZ", "标准", "废标", "资质替代"],
        "section_header": "## {num}、{title}",
        "template": "commerce"
    },
    "资质等效替代规则库": {
        "file": "资质等效替代规则库_种子版.md",
        "keywords": ["资质", "认证", "许可", "CMMI", "ISO",
                      "等效", "替代", "等级", "承包"],
        "exclude_keywords": ["GB", "标准", "废标", "报价", "招标投标法"],
        "section_header": "## {num}、{title}",
        "template": "qualification"
    }
}

# 中文数字映射（用于 .md 文件章节编号）
CN_NUMS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
           "十一", "十二", "十三", "十四", "十五"]


# ============================================================
# 核心类
# ============================================================

class KnowledgeBaseAutoIndexer:
    """知识库自动索引器"""

    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.file_name = self.file_path.name
        self.text_content = ""
        self.first_page_text = ""
        self.metadata = {}
        self.category = None
        self.category_config = None
        self.summary_entry = ""
        self.md_file_path = None

    # --------------------------------------------------------
    # Step 1: 提取文本
    # --------------------------------------------------------
    def extract_text(self):
        """根据文件类型提取文本内容"""
        ext = self.file_path.suffix.lower()

        if ext == ".pdf":
            self._extract_pdf()
        elif ext in (".doc", ".docx"):
            self._extract_word()
        elif ext == ".txt":
            self._extract_txt()
        elif ext == ".md":
            self._extract_txt()
        else:
            print(f"[警告] 不支持的文件格式: {ext}，尝试按文本读取")
            self._extract_txt()

        if not self.text_content.strip():
            raise ValueError(f"无法从文件中提取文本: {self.file_path}")

        # 截取前 5000 字符用于分类
        self.first_page_text = self.text_content[:5000]
        print(f"[OK] 文本提取完成，总长度: {len(self.text_content)} 字符")

    def _extract_pdf(self):
        """提取 PDF 文本"""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(self.file_path))
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(text)
                if i >= 9:  # 只提取前 10 页
                    break
            self.text_content = "\n".join(pages_text)

            # 提取 PDF 元数据
            if reader.metadata:
                self.metadata["pdf_title"] = reader.metadata.title or ""
                self.metadata["pdf_author"] = reader.metadata.author or ""
        except Exception as e:
            print(f"[错误] PDF 提取失败: {e}")
            raise

    def _extract_word(self):
        """提取 Word 文本"""
        try:
            from docx import Document
            doc = Document(str(self.file_path))
            self.text_content = "\n".join([p.text for p in doc.paragraphs if p.text])
        except ImportError:
            raise ValueError("需要安装 python-docx: pip install python-docx")

    def _extract_txt(self):
        """提取纯文本"""
        encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
        for enc in encodings:
            try:
                with open(self.file_path, "r", encoding=enc) as f:
                    self.text_content = f.read()
                return
            except (UnicodeDecodeError, Exception):
                continue
        raise ValueError(f"无法解码文件: {self.file_path}")

    # --------------------------------------------------------
    # Step 2: 自动分类
    # --------------------------------------------------------
    def classify(self):
        """基于关键词评分自动分类"""
        scores = {}
        details = {}

        for cat_name, cat_config in CATEGORIES.items():
            score = 0
            matched_keywords = []

            # 文件名匹配（权重 3）
            for kw in cat_config["keywords"]:
                if kw.lower() in self.file_name.lower():
                    score += 3
                    matched_keywords.append(f"[文件名]{kw}")

            # 内容匹配（权重 1）
            content_lower = self.first_page_text.lower()
            for kw in cat_config["keywords"]:
                kw_lower = kw.lower()
                if kw_lower in content_lower:
                    score += 1
                    if f"[内容]{kw}" not in matched_keywords:
                        matched_keywords.append(f"[内容]{kw}")

            # 排除关键词减分（权重 -2）
            for kw in cat_config["exclude_keywords"]:
                if kw.lower() in self.file_name.lower() or kw.lower() in content_lower:
                    score -= 2
                    matched_keywords.append(f"[排除]{kw}")

            scores[cat_name] = score
            details[cat_name] = matched_keywords

        # 选择得分最高的类别
        self.category = max(scores, key=scores.get)
        self.category_config = CATEGORIES[self.category]
        self.md_file_path = KB_BASE / self.category_config["file"]

        # 输出分类详情
        print(f"\n{'='*60}")
        print(f"分类结果: {self.category} (得分: {scores[self.category]})")
        print(f"{'='*60}")
        print(f"各类别得分:")
        for cat, score in sorted(scores.items(), key=lambda x: -x[1]):
            tag = " ← 选中" if cat == self.category else ""
            print(f"  {cat}: {score}{tag}")
            if details[cat]:
                print(f"    匹配关键词: {', '.join(details[cat][:5])}")
        print()

        if scores[self.category] <= 0:
            print("[警告] 所有类别得分均 <= 0，分类可能不准确，请人工确认")

    # --------------------------------------------------------
    # Step 3: 提取元数据
    # --------------------------------------------------------
    def extract_metadata(self):
        """从文本中提取标准编号、标题、日期等元数据"""
        text = self.first_page_text

        # 标准编号: GB/T 22239-2019, GBZ 117-2022, JJF/JJG 等
        # 注意: PDF 中可能使用 em dash (—) 而非 hyphen (-)
        std_patterns = [
            r'(GBZ[/\s]*\d+[—\-:]\d{4})',
            r'(GB/T[/\s]*\d+[—\-:]\d{4})',
            r'(GB[/\s]*\d+[—\-:]\d{4})',
            r'(JJ[FG][/\s]*\d+[—\-:]\d{4})',
            r'(DB[/\s]*\d+[/\s]*\d+[—\-:]\d{4})',  # 地方标准
        ]
        for pattern in std_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # 统一格式: 去除空格，将 em dash 转为 hyphen
                sn = match.group(1).replace(" ", "").replace("—", "-")
                self.metadata["standard_number"] = sn
                break

        # 标题：优先从 PDF 元数据获取，其次从文本行提取
        if self.metadata.get("pdf_title"):
            self.metadata["title"] = self.metadata["pdf_title"].strip()
        else:
            # 从文本行中提取中文标题
            # 标准文件的标题通常是独立的一行纯中文（可含空格），4-40字符
            # 出现在标准编号之后、"Standard"/英文行之前
            lines = text.split('\n')
            sn = self.metadata.get("standard_number", "")
            sn_found = False
            for line in lines[:30]:
                line = line.strip()
                if not line:
                    continue
                # 找到标准编号行后开始寻找标题
                if sn and sn.replace("-", "") in line.replace(" ", "").replace("—", ""):
                    sn_found = True
                    continue
                if not sn_found:
                    continue
                # 跳过"代替"行
                if line.startswith("代替"):
                    continue
                # 跳过英文行
                if re.match(r'^[A-Za-z]', line):
                    continue
                # 跳过日期行
                if re.search(r'\d{4}[-年]\d{1,2}', line):
                    continue
                # 跳过发布机构行
                if "发布" in line and "委员会" in line:
                    continue
                # 检查是否为中文标题行（主要是中文字符）
                chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', line))
                if chinese_chars >= 4 and chinese_chars <= 40:
                    # 去掉尾部"标准"后的空格
                    self.metadata["title"] = line.strip()
                    break

        # 如果还没标题，用文件名
        if not self.metadata.get("title"):
            self.metadata["title"] = self.file_path.stem

        # 发布日期和实施日期
        date_pattern = r'(\d{4})[-年](\d{1,2})[-月](\d{1,2})日?\s*(发布|实施)'
        dates = re.findall(date_pattern, text)
        for d in dates:
            date_str = f"{d[0]}-{d[1]}-{d[2]}"
            if d[3] == "发布":
                self.metadata["publish_date"] = date_str
            elif d[3] == "实施":
                self.metadata["implement_date"] = date_str

        # 替代标准
        replace_pattern = r'代替\s*([\s\S]{0,100}?)(?=\n|$|202\d)'
        replace_match = re.search(replace_pattern, text)
        if replace_match:
            self.metadata["replaces"] = replace_match.group(1).strip()

        # 适用范围（找"范围"章节的实际内容，非目录中的条目）
        # 目录中的"范围"后面通常有省略号或点号，实际内容则直接跟文字
        scope = ""
        # 方法1: 找 "范围" 后面紧跟中文文字（非目录格式）
        scope_pattern = r'范围\s*\n\s*(本标准[^。\n]*。[^。\n]*。?)'
        scope_match = re.search(scope_pattern, text)
        if scope_match:
            scope = scope_match.group(1).strip()
        else:
            # 方法2: 找 "1 范围" 后面的文字（跳过目录中的点号行）
            # 目录格式: "1 范围 ...... 1"  实际内容: "1 范围\n本标准规定了..."
            toc_pattern = r'\d+\s+范围\s*[\.。．]+\s*\d+'  # 目录格式
            content_text = re.sub(toc_pattern, '', text)  # 去掉目录条目
            scope_pattern2 = r'(?:^|\n)\s*1\s*范围\s*\n+([\s\S]{10,300}?)(?=\n\s*2\s|规范性引用|术语和定义)'
            scope_match2 = re.search(scope_pattern2, content_text)
            if scope_match2:
                scope = scope_match2.group(1).strip()
                scope = re.sub(r'\s+', ' ', scope)

        if scope:
            self.metadata["scope"] = scope[:200]
        else:
            # 方法3: 如果找不到，从标题推断
            title = self.metadata.get("title", "")
            if "放射" in title or "辐射" in title or "探伤" in title:
                self.metadata["scope"] = "涉及工业探伤放射防护设计的项目"
            elif "安全" in title:
                self.metadata["scope"] = "涉及信息安全设计的项目"
            elif "数据" in title:
                self.metadata["scope"] = "涉及数据安全管理的项目"
            else:
                self.metadata["scope"] = "涉及该标准技术领域的项目设计"

        # 章节标题列表（提取核心要求线索）
        section_pattern = r'^\s*(\d+)\s+([\u4e00-\u9fa5A-Za-z（）()]+)\s*$'
        sections = re.findall(section_pattern, text, re.MULTILINE)
        if sections:
            self.metadata["sections"] = [(s[0], s[1]) for s in sections[:10]]

        # 打印元数据
        print(f"\n--- 提取到的元数据 ---")
        for k, v in self.metadata.items():
            if k == "sections":
                print(f"  {k}:")
                for num, name in v:
                    print(f"    {num}. {name}")
            else:
                print(f"  {k}: {v}")
        print()

    # --------------------------------------------------------
    # Step 4: 生成摘要条目
    # --------------------------------------------------------
    def generate_summary(self):
        """根据类别模板生成 Markdown 摘要条目"""
        template = self.category_config["template"]

        if template == "standard":
            self.summary_entry = self._gen_standard_summary()
        elif template == "law":
            self.summary_entry = self._gen_law_summary()
        elif template == "pattern":
            self.summary_entry = self._gen_pattern_summary()
        elif template == "commerce":
            self.summary_entry = self._gen_commerce_summary()
        elif template == "qualification":
            self.summary_entry = self._gen_qualification_summary()
        else:
            self.summary_entry = self._gen_generic_summary()

        print(f"\n--- 生成的摘要条目 ---")
        print(self.summary_entry)
        print(f"--- 摘要条目结束 ---\n")

    def _gen_standard_summary(self):
        """行业技术标准库模板"""
        sn = self.metadata.get("standard_number", "")
        title = self.metadata.get("title", self.file_name)
        scope = self.metadata.get("scope", "涉及该标准技术领域的项目设计")

        # 从章节标题提取核心要求
        sections = self.metadata.get("sections", [])
        if sections:
            req_lines = []
            for num, name in sections[:6]:
                req_lines.append(f"- {name}")
            core_reqs = "\n".join(req_lines)
        else:
            core_reqs = "- 参照标准原文具体条款"

        # 生成标书响应要点
        response_points = self._gen_response_points()

        # 替代标准信息
        replaces = self.metadata.get("replaces", "")
        replace_line = f"\n**替代标准**: {replaces}" if replaces else ""

        # 日期信息
        pub_date = self.metadata.get("publish_date", "")
        impl_date = self.metadata.get("implement_date", "")
        date_line = ""
        if pub_date or impl_date:
            date_line = f"\n**发布日期**: {pub_date}  |  **实施日期**: {impl_date}"

        return f"""### {sn} {title}{replace_line}{date_line}

**适用场景**: {scope}

#### 核心要求

{core_reqs}

**标书响应要点**: {response_points}

> 📄 完整标准原文已上传至 ima 知识库，文件名: {self.file_name}"""

    def _gen_law_summary(self):
        """标书核心法规汇编模板"""
        title = self.metadata.get("title", self.file_name)
        scope = self.metadata.get("scope", "招投标活动相关法规要求")

        sections = self.metadata.get("sections", [])
        if sections:
            req_lines = []
            for num, name in sections[:6]:
                req_lines.append(f"| 第{num}条 | {name} | 参照法规原文 |")
            core_reqs = "| 条文 | 核心内容 | 标书响应要点 |\n|------|---------|-------------|\n" + "\n".join(req_lines)
        else:
            core_reqs = "- 参照法规原文具体条文"

        return f"""### {title}

**适用场景**: {scope}

{core_reqs}

> 📄 完整法规原文已上传至 ima 知识库，文件名: {self.file_name}"""

    def _gen_pattern_summary(self):
        """废标条款模式库模板"""
        title = self.metadata.get("title", self.file_name)
        return f"""### {title}

**触发场景**: 参照原文具体条款

| 模式 | 触发关键词 | 法律依据 | 严重等级 |
|------|-----------|---------|---------|
| (参照原文) | (参照原文) | (参照原文) | fatal/warning |

> 📄 完整文件已上传至 ima 知识库，文件名: {self.file_name}"""

    def _gen_commerce_summary(self):
        """报价与商务法规库模板"""
        title = self.metadata.get("title", self.file_name)
        scope = self.metadata.get("scope", "招投标报价与商务条款相关要求")

        return f"""### {title}

**适用场景**: {scope}

| 核心条款 | 内容摘要 | 标书响应要点 |
|---------|---------|-------------|
| (参照原文) | (参照原文) | 参照法规原文响应 |

> 📄 完整文件已上传至 ima 知识库，文件名: {self.file_name}"""

    def _gen_qualification_summary(self):
        """资质等效替代规则库模板"""
        title = self.metadata.get("title", self.file_name)
        return f"""### {title}

| 原资质要求 | 等效资质 | 替代条件 | 法规依据 |
|-----------|---------|---------|---------|
| (参照原文) | (参照原文) | (参照原文) | (参照原文) |

> 📄 完整文件已上传至 ima 知识库，文件名: {self.file_name}"""

    def _gen_generic_summary(self):
        """通用模板"""
        title = self.metadata.get("title", self.file_name)
        return f"""### {title}

**适用场景**: 参照原文

> 📄 完整文件已上传至 ima 知识库，文件名: {self.file_name}"""

    def _gen_response_points(self):
        """根据标题关键词生成标书响应要点（只检查标题，避免全文误匹配）"""
        title = self.metadata.get("title", "")
        scope = self.metadata.get("scope", "")
        # 只用标题和适用范围判断，不用全文
        check_text = f"{title} {scope}"
        points = []

        # 辐射/放射防护
        if any(kw in check_text for kw in ["放射", "辐射", "探伤", "屏蔽"]):
            points.append("技术方案中需说明辐射防护设计、屏蔽计算、监测设备配置及人员防护方案")
        # 网络安全
        if any(kw in check_text for kw in ["网络安全", "等保", "等级保护"]):
            points.append("技术方案中需明确等保级别、安全措施清单及合规依据")
        # 数据安全
        if any(kw in check_text for kw in ["数据安全", "个人信息", "隐私", "数据保护"]):
            points.append("技术方案中需说明数据分类分级、加密存储、脱敏处理及数据生命周期管理")
        # 物理安全/机房
        if any(kw in check_text for kw in ["物理安全", "机房", "防火", "防雷"]):
            points.append("技术方案中需说明机房等级、物理安全措施及应急方案")
        # 软件工程
        if any(kw in check_text for kw in ["软件工程", "软件文档", "开发", "生存周期"]):
            points.append("技术方案中需说明开发流程规范、质量保障措施及交付文档清单")
        # 云计算
        if any(kw in check_text for kw in ["云计算", "云服务", "IaaS", "PaaS", "SaaS"]):
            points.append("技术方案中需明确云服务模式、部署架构及云安全合规方案")
        # 职业卫生/健康
        if any(kw in check_text for kw in ["职业卫生", "职业病", "职业健康"]):
            points.append("技术方案中需说明职业健康监护、防护设施及作业场所监测方案")
        # 通用
        if not points:
            points.append("技术方案中需引用本标准编号，说明符合性及具体实施措施")
        # 通用
        if not points:
            points.append("技术方案中需引用本标准编号，说明符合性及具体实施措施")

        return "；".join(points)

    # --------------------------------------------------------
    # Step 5: 更新 .md 文件
    # --------------------------------------------------------
    def update_md_file(self):
        """将摘要条目追加到对应的 .md 种子文件"""
        if not self.md_file_path or not self.md_file_path.exists():
            print(f"[错误] .md 文件不存在: {self.md_file_path}")
            return False

        # 读取现有内容
        with open(self.md_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 检查是否已存在相同条目（避免重复）
        check_key = self.metadata.get("standard_number", "") or self.metadata.get("title", "")
        if check_key and check_key in content:
            print(f"[跳过] 条目已存在: {check_key}")
            return False

        # 找到插入位置：在"使用说明"之前，或在文件末尾
        insert_marker = "## 使用说明"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 构建新章节
        # 统计现有章节数
        section_count = len(re.findall(r'^## [一二三四五六七八九十]+、', content, re.MULTILINE))
        next_num = CN_NUMS[section_count] if section_count < len(CN_NUMS) else str(section_count + 1)

        new_section = f"""
## {next_num}、{self.metadata.get("title", self.file_name)}（自动索引 {timestamp}）

{self.summary_entry}
"""

        if insert_marker in content:
            # 在"使用说明"之前插入
            new_content = content.replace(insert_marker, new_section + "\n" + insert_marker)
        else:
            # 追加到文件末尾
            new_content = content.rstrip() + "\n" + new_section

        # 写回文件
        with open(self.md_file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"[OK] 已更新: {self.md_file_path}")
        print(f"     新增章节: {next_num}、{self.metadata.get('title', self.file_name)}")
        return True

    # --------------------------------------------------------
    # Step 6: 输出报告
    # --------------------------------------------------------
    def print_report(self):
        """输出最终报告"""
        print(f"\n{'='*60}")
        print(f"自动索引完成报告")
        print(f"{'='*60}")
        print(f"文件: {self.file_name}")
        print(f"分类: {self.category}")
        print(f"MD文件: {self.md_file_path.name if self.md_file_path else 'N/A'}")
        print(f"标准编号: {self.metadata.get('standard_number', 'N/A')}")
        print(f"标题: {self.metadata.get('title', 'N/A')}")
        if self.metadata.get("publish_date"):
            print(f"发布日期: {self.metadata['publish_date']}")
        if self.metadata.get("implement_date"):
            print(f"实施日期: {self.metadata['implement_date']}")
        print(f"\n下一步操作:")
        print(f"  1. 检查上方摘要内容是否准确")
        print(f"  2. 如需修改，编辑: {self.md_file_path}")
        print(f"  3. 上传原文件到 ima 知识库")
        print(f"  4. 重新上传更新后的 .md 到 ima 知识库")
        print(f"{'='*60}")

    # --------------------------------------------------------
    # 主流程
    # --------------------------------------------------------
    def run(self):
        """主执行流程"""
        print(f"\n{'='*60}")
        print(f"知识库自动索引工具 v1.0")
        print(f"{'='*60}")
        print(f"输入文件: {self.file_path}")
        print(f"文件大小: {self.file_path.stat().st_size / 1024:.1f} KB")

        # Step 1: 提取文本
        self.extract_text()

        # Step 2: 分类
        self.classify()

        # Step 3: 提取元数据
        self.extract_metadata()

        # Step 4: 生成摘要
        self.generate_summary()

        # Step 5: 更新 .md
        self.update_md_file()

        # Step 6: 报告
        self.print_report()

        # 输出 JSON 结果（供程序化调用）
        result = {
            "file_name": self.file_name,
            "category": self.category,
            "md_file": self.md_file_path.name if self.md_file_path else None,
            "metadata": {k: v for k, v in self.metadata.items() if k != "sections"},
            "sections": [{"num": s[0], "name": s[1]} for s in self.metadata.get("sections", [])],
            "summary": self.summary_entry,
            "timestamp": datetime.now().isoformat()
        }
        return result


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python kb_auto_index.py <文件路径>")
        print("示例: python kb_auto_index.py \"D:\\标准文件\\GBZ117-2022.pdf\"")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"[错误] 文件不存在: {file_path}")
        sys.exit(1)

    indexer = KnowledgeBaseAutoIndexer(file_path)
    result = indexer.run()

    # 保存 JSON 结果
    json_path = Path(file_path).with_suffix(".index.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] JSON 结果已保存: {json_path}")
