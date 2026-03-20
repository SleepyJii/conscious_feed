import json
import os
from playwright.sync_api import sync_playwright

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "playwright-server", "config.json")
URL = "https://alifeofa.bearblog.dev/relaxing-is-not-a-waste-of-time/"


def load_ws_endpoint() -> str:
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    return config["ws_endpoint"]


def scrape_paragraphs(url: str, ws_endpoint: str) -> list[str]:
    with sync_playwright() as p:
        browser = p.chromium.connect(ws_endpoint)
        page = browser.new_page()
        page.goto(url)
        paragraphs = page.query_selector_all("p")
        texts = [elem.inner_text() for elem in paragraphs]
        page.close()
        return texts


if __name__ == "__main__":
    print("i am alive")
    endpoint = load_ws_endpoint()
    results = scrape_paragraphs(URL, endpoint)
    for text in results:
        print(text)
    print("i am dead")

