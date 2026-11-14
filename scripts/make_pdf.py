"""把 docs/technical-report.html 打印成 PDF（Chromium 引擎，中文字体走系统）。

两遍渲染：第一遍先出 PDF，用 pypdf 找出每个章节实际落在第几页，
把目录里的页码改成真实值，再渲染第二遍。这样目录页码不会和正文对不上。

跑法：python scripts/make_pdf.py
依赖：playwright（用系统 Chrome/Edge）、pypdf
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "technical-report.html"
OUT = ROOT / "docs" / "技术文档-智协台AgentDesk.pdf"

# 目录里的条目顺序，必须与 HTML 中 .toc 的行顺序一致
SECTIONS = [
    "1 项目概述",
    "2 需求分析",
    "3 系统架构设计",
    "4 AI 技术方案",
    "5 核心功能实现",
    "6 测试与部署",
    "7 创新点",
    "8 总结与展望",
    "附录 A",
]

_TOC_ROW = re.compile(r"(<div><span>[^<]+</span><span>)(\d+)(</span></div>)")


def _render(browser, html_path: Path, out_path: Path) -> None:
    page = browser.new_page(viewport={"width": 1240, "height": 1754})
    page.goto(html_path.as_uri())
    page.wait_for_timeout(400)
    page.pdf(
        path=str(out_path),
        format="A4",
        print_background=True,
        display_header_footer=False,
        margin={"top": "18mm", "right": "16mm", "bottom": "16mm", "left": "16mm"},
    )
    page.close()


def _locate_pages(pdf_path: Path) -> list[int]:
    reader = PdfReader(str(pdf_path))
    pages = []
    texts = [(p.extract_text() or "").replace(" ", "").replace("\u3000", "") for p in reader.pages]
    for sec in SECTIONS:
        key = sec.replace(" ", "")
        found = 0
        # 前两页是封面和目录，目录里也写着同样的章节名，必须跳过
        for i, t in enumerate(texts[2:], start=3):
            if key in t:
                found = i
                break
        pages.append(found)
    return pages


def main() -> None:
    if not SRC.exists():
        sys.exit(f"找不到源文件：{SRC}")
    html = SRC.read_text(encoding="utf-8")

    with sync_playwright() as p:
        browser = None
        # 不下载 Playwright 自带 Chromium：直接用系统里已装的 Chrome/Edge，
        # 中文字体和打印行为都与用户实际看到的一致。
        for channel in ("chrome", "msedge"):
            try:
                browser = p.chromium.launch(channel=channel)
                break
            except Exception:  # noqa: BLE001
                continue
        if browser is None:
            browser = p.chromium.launch()

        tmp = OUT.with_suffix(".tmp.pdf")
        _render(browser, SRC, tmp)
        pages = _locate_pages(tmp)
        print("章节页码：", dict(zip([s[:6] for s in SECTIONS], pages)))

        idx = iter(pages)
        fixed = _TOC_ROW.sub(lambda m: f"{m.group(1)}{next(idx)}{m.group(3)}", html)
        SRC.write_text(fixed, encoding="utf-8")
        _render(browser, SRC, OUT)
        browser.close()
    tmp.unlink(missing_ok=True)

    size = OUT.stat().st_size / 1024
    total = len(PdfReader(str(OUT)).pages)
    print(f"已生成 {OUT}（{total} 页，{size:.0f} kB）")


if __name__ == "__main__":
    main()
