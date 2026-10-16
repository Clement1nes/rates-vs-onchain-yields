"""Export report/draft.md to report/report.pdf (markdown -> HTML -> headless Chrome).

Run:  python make_report.py
"""
import re
import subprocess
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
REPORT = ROOT / "report"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 16mm 17mm 16mm 17mm; }
body { font-family: Roboto, Arial, sans-serif; font-size: 9.4pt; line-height: 1.38; color: #0b0b0b; }
h1 { font-size: 17pt; margin: 0 0 2pt 0; font-weight: 700; }
h1 + p { color: #52514e; margin-top: 0; }
h2 { font-size: 12pt; margin: 13pt 0 4pt 0; padding-bottom: 2pt; border-bottom: 0.6pt solid #d8d7d2; }
h3 { font-size: 10.2pt; margin: 9pt 0 3pt 0; }
p { margin: 0 0 5pt 0; }
ul { margin: 0 0 5pt 0; padding-left: 14pt; }
li { margin-bottom: 2.5pt; }
img { width: 72%; display: block; margin: 3pt auto 5pt auto; break-inside: avoid; }
p:has(img) { break-inside: avoid; }
h3 { break-after: avoid; }
code { font-size: 8.2pt; }
h2#data-and-method-notes ~ ul { font-size: 8.4pt; line-height: 1.35; }
h2#data-and-method-notes ~ ul li { margin-bottom: 1.5pt; }
"""


def main():
    md = (REPORT / "draft.md").read_text(encoding="utf8")
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)   # drop the figure-mapping block
    body = markdown.markdown(md, extensions=["extra", "sane_lists", "toc"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>Rates and on-chain dollars</title>" \
           f"<style>{CSS}</style></head><body>{body}</body></html>"
    src = REPORT / "report.html"
    src.write_text(html, encoding="utf8")
    chrome = next(p for p in CHROME_CANDIDATES if Path(p).exists())
    out = REPORT / "report.pdf"
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", src.resolve().as_uri()], check=True, capture_output=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
