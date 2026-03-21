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
        print(f"Connecting to: {ws_endpoint}")
        browser = p.chromium.connect(ws_endpoint)
        print(f"Connected. Browser version: {browser.version}")
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        print(f"Navigating to: {url}")
        response = page.goto(url)
        print(f"Response status: {response.status if response else 'None'}")
        print(f"Page title: {page.title()}")
        print(f"Page URL: {page.url}")
        paragraphs = page.query_selector_all("p")
        print(f"Found {len(paragraphs)} <p> elements")
        texts = [elem.inner_text() for elem in paragraphs]
        print(f"Extracted {len(texts)} texts, first 100 chars of each:")
        for i, t in enumerate(texts):
            print(f"  [{i}] {t[:100]!r}")
        page.close()
        return texts


if __name__ == "__main__":
    print("i am alive")
    endpoint = load_ws_endpoint()
    results = scrape_paragraphs(URL, endpoint)
    for text in results:
        print(text)
    print("i am dead")

