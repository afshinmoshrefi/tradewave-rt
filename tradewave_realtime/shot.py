"""Headless screenshot helper. Usage: python shot.py <url> <out.png> [full]"""
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
out = sys.argv[2]
full = len(sys.argv) > 3 and sys.argv[3] == "full"
width = int(sys.argv[4]) if len(sys.argv) > 4 else 1440

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
    pg = b.new_page(viewport={"width": width, "height": 900}, device_scale_factor=1)
    pg.goto(url, wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(700)
    pg.screenshot(path=out, full_page=full)
    b.close()
print("shot ->", out, "(full)" if full else "(viewport)")
