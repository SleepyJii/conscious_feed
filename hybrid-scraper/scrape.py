from playwright.sync_api import sync_playwright, Playwright

URL = "https://alifeofa.bearblog.dev/relaxing-is-not-a-waste-of-time/"

class RemoteSyncPlaywright(Playwright):
	"""
	Simple wrapper for Playwright for LLM to later deal with.
	"""
    def __init__(self):
        super().__init__()
		with sync_playwright() as p:
			self.playwright = p
        self.browser = p.chromium.launch(headless=True)
		self.page = browser.new_page()

	def scrape_paragraphs(url : string):
		self.page.goto(url)

		paragraphs = self.page.query_selector_all("p")
		paragraphs_inner_text = []
		for p_elem in paragraphs:
			paragraphs_inner_text.append(p_elem)
		browser.close()
		return paragraphs_inner_text

if __name__ == "__main__":
    playwright = RemoteSyncPlaywright()
	playwright.scrape_paragraphs(URL)