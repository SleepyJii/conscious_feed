from playwright.sync_api import sync_playwright, Playwright

URL = "https://alifeofa.bearblog.dev/relaxing-is-not-a-waste-of-time/"

class DelegatedPlaywright(Playwright):
    def __init__(self):
        super().__init__()
		with sync_playwright() as p:
			self.playwright = p
        self.browser = p.chromium.launch(headless=True)
		self.page = browser.new_page()

	def scrape_paragraphs(url):
		self.page.goto(url)

		paragraphs = self.page.query_selector_all("p")
		for p_elem in paragraphs:
			print(p_elem.inner_text())
		browser.close()

if __name__ == "__main__":
	scrape_paragraphs(URL)