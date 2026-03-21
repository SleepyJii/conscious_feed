#!/bin/bash


exec docker exec c10a2e4beef3 python3 <<'EOF'
from playwright.sync_api import sync_playwright
import json

ws = json.load(open("/app/playwright-server/config.json"))["ws_endpoint"]
p = sync_playwright().start()
browser = p.chromium.connect(ws)
page = browser.new_context().new_page()
page.goto("https://example.com")
print(f"title: {page.title()}")
print(f"url: {page.url}")
print(f"paragraphs: {len(page.query_selector_all('p'))}")
page.close()
EOF

