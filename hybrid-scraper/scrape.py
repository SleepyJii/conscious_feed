from playwright.sync_api import sync_playwright

URL = "https://alifeofa.bearblog.dev/relaxing-is-not-a-waste-of-time/"

def scrape_paragraphs(url):
	with sync_playwright() as p:
		browser = p.chromium.launch(headless=True)
		page = browser.new_page()
		page.goto(url)
		paragraphs = page.query_selector_all("p")
		for p_elem in paragraphs:
			print(p_elem.inner_text())
		browser.close()

if __name__ == "__main__":
	scrape_paragraphs(URL)