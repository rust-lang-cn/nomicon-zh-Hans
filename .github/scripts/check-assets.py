#!/usr/bin/env python3
"""检查构建产物中 <link>/<script> 引用的本地资源是否都存在。

mdBook 会给静态资源文件名加上内容哈希，自定义模板一旦和 mdBook 版本脱节，
页面引用的 JS/CSS 就会全部 404，而 `mdbook build` 本身不会报错。
"""
import glob
import os
import re
import sys

book = sys.argv[1] if len(sys.argv) > 1 else "book"
pages = glob.glob(os.path.join(book, "**", "*.html"), recursive=True)
if not pages:
    sys.exit(f"no html files found under {book!r}")

ref = re.compile(r'<(?:link|script)\b[^>]*?\b(?:href|src)="([^"]+)"')
checked = 0
missing = []
for page in pages:
    with open(page, encoding="utf-8") as f:
        html = f.read()
    for url in ref.findall(html):
        if re.match(r"(?:[a-z]+:)?//|data:", url):
            continue
        checked += 1
        target = os.path.normpath(os.path.join(os.path.dirname(page), re.split(r"[?#]", url)[0]))
        if not os.path.exists(target):
            missing.append(f"{page}: {url}")

for line in missing[:50]:
    print(f"MISSING {line}")
print(f"checked {checked} local asset refs in {len(pages)} pages, {len(missing)} missing")
sys.exit(1 if missing else 0)
