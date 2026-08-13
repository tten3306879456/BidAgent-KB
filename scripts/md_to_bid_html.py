#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md_to_bid_html.py — 投标文档 Markdown → HTML 转换器
=====================================================
按「投标文件编辑模板库」排版规范（seeds/投标文件通用框架与封面模板.md 4.1 格式规范）生成 HTML：
  - 纸张 A4，页边距 上2.5cm / 下2.5cm / 左2.5cm / 右2cm
  - 正文宋体小四(12pt)、标题黑体三号(16pt)/四号(14pt)、表格宋体五号(10.5pt)
  - 1.5 倍行距；打印页码底部居中「第 X 页 / 共 Y 页」
  - 封面独立一页；目录自动生成（两级，锚点跳转 + 前导符）

用法:
  python md_to_bid_html.py <输入.md> <输出.html> [--title 封面主标题] [--subtitle 封面副标题]

说明:
  - 若 md 以 <div ...> 封面块开头，该块原样作为封面（投标文件格式）
  - 否则自动生成封面：主标题 + 副标题 + 元信息（引用块中 **字段**：值 自动提取）
  - 正文中若含手写「## 目录」块，将被自动目录替换
"""
import re
import sys
import html as html_mod
from pathlib import Path

import markdown

# ---------------------------------------------------------------------------
# 模板 CSS（投标文件编辑模板库 4.1 格式规范）
# ---------------------------------------------------------------------------
TEMPLATE_CSS = r"""
:root {
  --ink: #1a1a1a;
  --muted: #555;
  --line: #999;
  --accent: #8a1f1f;        /* 标书红（印章/重点） */
  --band: #f4f4f0;          /* 表格表头浅底 */
}
* { box-sizing: border-box; margin: 0; padding: 0; }

/* ---------- 打印版式：A4 + 模板页边距 + 页码 ---------- */
@page {
  size: A4;
  margin: 2.5cm 2cm 2.5cm 2.5cm;   /* 上 下 左(装订侧) 右 */
  @bottom-center {
    content: "第 " counter(page) " 页 / 共 " counter(pages) " 页";
    font-family: "宋体", SimSun, serif;
    font-size: 9pt;
    color: #333;
  }
}

body {
  font-family: "宋体", "SimSun", "NSimSun", serif;
  font-size: 12pt;                 /* 正文宋体小四 */
  line-height: 1.5;                /* 1.5 倍行距 */
  color: var(--ink);
  background: #e9e9e4;
}

/* ---------- 屏幕预览：A4 纸张卡片 ---------- */
.sheet {
  width: 210mm;
  min-height: 297mm;
  margin: 14px auto;
  padding: 2.5cm 2cm 2.5cm 2.5cm;
  background: #fff;
  box-shadow: 0 2px 18px rgba(0,0,0,.18);
  page-break-after: always;
}
@media print {
  body { background: #fff; }
  .sheet { width: auto; min-height: auto; margin: 0; padding: 0;
           box-shadow: none; page-break-after: always; }
  .sheet:last-child { page-break-after: auto; }
  a { color: inherit; text-decoration: none; }
}

/* ---------- 标题：黑体 ---------- */
h1, h2, h3, h4 { font-family: "黑体", "SimHei", "Microsoft YaHei", sans-serif; color: #000; }
h1 { font-size: 16pt; margin: 26pt 0 14pt; padding-bottom: 8pt;
     border-bottom: 2px solid #000; page-break-before: always; }
h2 { font-size: 14pt; margin: 20pt 0 10pt; }
h3 { font-size: 12pt; margin: 14pt 0 8pt; }
h4 { font-size: 12pt; margin: 10pt 0 6pt; }
h1:first-of-type, .no-break { page-break-before: avoid; }
p { margin: 6pt 0; text-align: justify; }
strong { font-weight: 700; }
em { font-style: italic; }
a { color: #1456a0; text-decoration: none; }

/* ---------- 封面 ---------- */
.cover {
  display: flex; flex-direction: column; justify-content: center;
  min-height: 100vh; text-align: center;
  page-break-after: always;
}
.cover .project {
  font-family: "黑体", "SimHei", sans-serif;
  font-size: 26pt; line-height: 1.4; font-weight: 700;
  margin-bottom: 6mm;
}
.cover .doc-title {
  font-family: "黑体", "SimHei", sans-serif;
  font-size: 40pt; letter-spacing: 1.2em; font-weight: 700;
  margin: 8mm 0 12mm; padding-left: 1.2em;
}
.cover .divider { width: 70mm; border-top: 2.5px solid #000; margin: 4mm auto 12mm; }
.cover .meta { margin-top: 6mm; font-size: 14pt; line-height: 2.1; text-align: center; }
.cover .meta p { text-align: center; }
.cover .meta strong { font-family: "黑体", "SimHei", sans-serif; font-weight: 700; }
.cover .seal { margin-top: 14mm; font-size: 12pt; color: var(--muted); }
.cover .note { margin-top: 8mm; font-size: 11pt; color: var(--muted); }

/* ---------- 目录 ---------- */
.toc-wrap { page-break-after: always; }
.toc-title { font-family: "黑体", "SimHei", sans-serif; font-size: 18pt;
             text-align: center; margin: 4mm 0 8mm; }
.toc { list-style: none; }
.toc li { display: flex; align-items: baseline; margin: 5pt 0; }
.toc .dots { flex: 1 1 auto; border-bottom: 1px dotted var(--line); margin: 0 6px; transform: translateY(-3px); }
.toc a { color: var(--ink); }
.toc li.l1 { font-weight: 700; font-size: 12.5pt; margin-top: 12pt; }
.toc li.l2 { padding-left: 2em; font-size: 11.5pt; }
.toc .no { font-family: "黑体", "SimHei", sans-serif; }
@media print { .toc a::after { content: target-counter(attr(href), page); } }

/* ---------- 表格：宋体五号 + 细边框 ---------- */
table { border-collapse: collapse; width: 100%; margin: 10pt 0;
        font-family: "宋体", SimSun, serif; font-size: 10.5pt;   /* 表格宋体五号 */
        page-break-inside: auto; }
th, td { border: 0.5pt solid #000; padding: 4pt 6pt; vertical-align: top;
         word-break: break-word; }
th { background: var(--band); font-family: "黑体", "SimHei", sans-serif;
     font-weight: 700; text-align: center; }
tr { page-break-inside: avoid; }
tbody tr:nth-child(even) { background: #fafaf7; }

/* ---------- 引用/代码/列表 ---------- */
blockquote { margin: 8pt 0 8pt 1em; padding: 6pt 12pt; color: var(--muted);
             border-left: 3px solid var(--line); background: #f8f8f5; }
blockquote p { margin: 3pt 0; }
code { font-family: Consolas, "Courier New", monospace; font-size: 9.5pt;
       background: #f2f2ec; padding: 1px 4px; border-radius: 2px; }
pre { margin: 8pt 0; padding: 8pt 10pt; background: #f2f2ec; border: 0.5pt solid #ddd;
      overflow-x: auto; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 9pt; line-height: 1.45;
           white-space: pre-wrap; word-break: break-word; }
ul, ol { margin: 6pt 0 6pt 2em; }
li { margin: 3pt 0; }
hr { border: none; border-top: 1px solid var(--line); margin: 14pt 0; }

/* ---------- 响应式 ---------- */
@media screen and (max-width: 900px) {
  .sheet { width: 100%; margin: 0 0 10px; padding: 18px; min-height: auto; }
  .cover { min-height: 80vh; }
}
"""


def slugify(text: str) -> str:
    """生成标题锚点 id（保留中英文，去除标点）"""
    s = re.sub(r"[\s\W_]+", "-", text.strip()).strip("-")
    return s or "sec"


def build_cover(title: str, subtitle: str, meta: list) -> str:
    rows = "".join(
        f"<p><strong>{html_mod.escape(k)}</strong>：{html_mod.escape(v)}</p>" for k, v in meta
    )
    sub = f"<div class='doc-title'>{html_mod.escape(subtitle)}</div>" if subtitle else ""
    return (
        f"<section class='cover'>"
        f"<div class='project'>{html_mod.escape(title)}</div>"
        f"{sub}"
        f"<div class='divider'></div>"
        f"<div class='meta'>{rows}</div>"
        f"<div class='seal'>投标人（盖章）：＿＿＿＿＿＿＿＿＿＿＿＿　法定代表人（签字）：＿＿＿＿＿＿</div>"
        f"<div class='note'>本文件为智能体模拟投标产物，用于流程验证与模板演示</div>"
        f"</section>"
    )


def parse_cover_block(md_text: str):
    """若 md 以 <div ...> 封面块开头，返回 (封面原始HTML, 剩余md)。"""
    stripped = md_text.lstrip()
    if stripped.startswith("<div"):
        end = stripped.find("</div>")
        if end != -1:
            block = stripped[: end + len("</div>")]
            rest = stripped[end + len("</div>") :]
            return block, rest
    return None, md_text


def extract_meta_from_quote(md_text: str) -> list:
    """从文件头引用块中提取 **字段**：值 元信息。"""
    meta = []
    for m in re.finditer(r"^\>\s*\*\*(.+?)\*\*\s*[:：]\s*(.+?)\s*$", md_text, re.M):
        meta.append((m.group(1), m.group(2)))
    return meta


def strip_toc_section(md_text: str) -> str:
    """移除手写「## 目录」块（到下一个一级/二级标题为止），由自动目录替换。"""
    m = re.search(r"^##\s*目录\s*$", md_text, re.M)
    if not m:
        return md_text
    nxt = re.search(r"^#{1,2}\s", md_text[m.end() :], re.M)
    cut = m.end() + (nxt.start() if nxt else len(md_text) - m.end())
    return md_text[: m.start()] + md_text[cut:]


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    title = next((a for a in sys.argv if a.startswith("--title=")), None)
    subtitle = next((a for a in sys.argv if a.startswith("--subtitle=")), None)
    title = title.split("=", 1)[1] if title else None
    subtitle = subtitle.split("=", 1)[1] if subtitle else None

    raw = src.read_text(encoding="utf-8")

    # 1) 封面
    cover_block, body_md = parse_cover_block(raw)
    meta = extract_meta_from_quote(body_md)
    if cover_block:
        # 封面块内为 markdown 内容（<div> 包裹），需先转换再嵌入
        inner = re.sub(r"^<div[^>]*>|</div>\s*$", "", cover_block, flags=re.S)
        cover_md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])
        cover = f"<section class='cover'>{cover_md.convert(inner)}</section>"
    else:
        # 主标题取第一个一级标题
        m1 = re.search(r"^#\s+(.+?)\s*$", body_md, re.M)
        main_title = title or (m1.group(1) if m1 else src.stem)
        if m1:
            body_md = body_md[: m1.start()] + body_md[m1.end():]  # 移除主标题（已入封面）
        # 移除引用块元信息（已提取）
        q = re.search(r"^\>\s.*\n(?:\>\s.*\n)*", body_md, re.M)
        if q:
            body_md = body_md[: q.start()] + body_md[q.end():]
        cover = build_cover(main_title, subtitle or "全流程模拟测试报告", meta)

    # 2) 手写目录替换
    body_md = strip_toc_section(body_md)

    # 3) 正文转换
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])
    body = md.convert(body_md)

    # 4) 标题锚点 + 目录
    used = {}
    toc_items = []
    for m in re.finditer(r"<h([12])>(.*?)</h1?2?>", body, re.S):
        lvl, txt = int(m.group(1)), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        base = slugify(txt)
        n = used.get(base, 0)
        used[base] = n + 1
        hid = base if n == 0 else f"{base}-{n}"
        body = body.replace(m.group(0), f"<h{lvl} id='{hid}'>{m.group(2)}</h{lvl}>", 1)
        toc_items.append((lvl, hid, txt))

    if toc_items:
        lis = []
        for lvl, hid, txt in toc_items:
            lis.append(f"<li class='l{lvl}'><a href='#{hid}'>{html_mod.escape(txt)}</a><span class='dots'></span></li>")
        toc = (f"<section class='toc-wrap'><div class='toc-title'>目　录</div>"
               f"<ul class='toc'>{''.join(lis)}</ul></section>")
    else:
        toc = ""

    # 5) 组装
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_mod.escape(title or src.stem)}</title>
<style>{TEMPLATE_CSS}</style>
</head>
<body>
<div class="sheet">{cover}</div>
{toc and f'<div class="sheet">{toc}</div>' or ''}
<div class="sheet">{body}</div>
</body>
</html>"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(doc, encoding="utf-8")
    print(f"✅ 已生成: {dst}  ({len(doc)//1024} KB, 标题 {len(toc_items)} 个)")


if __name__ == "__main__":
    main()
