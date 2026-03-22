import { useEffect, useState } from "react"
import { fetchFeedItems, fetchScraperData, type FeedItem } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { buttonStyles } from "@/lib/global-styles"

export function Feed() {
  const [items, setItems] = useState<FeedItem[]>([])
  const [scraperOptions, setScraperOptions] = useState<Array<{ id: string; name: string }>>([])
  const [filterScraper, setFilterScraper] = useState("")
  const [filterSearch, setFilterSearch] = useState("")
  const [limit, setLimit] = useState(50)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchScraperData().then((scrapers) => {
      setScraperOptions(scrapers.map((s) => ({ id: s.scraperId, name: s.name || s.scraperId })))
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    fetchFeedItems({ scraper_id: filterScraper || undefined, limit }).then((data) => {
      if (!cancelled) {
        setItems(data)
        setLoading(false)
      }
    })

    return () => { cancelled = true }
  }, [filterScraper, limit])

  const filtered = filterSearch
    ? items.filter((item) => {
        const q = filterSearch.toLowerCase()
        return (
          item.title.toLowerCase().includes(q) ||
          item.content.toLowerCase().includes(q) ||
          item.scraperName.toLowerCase().includes(q)
        )
      })
    : items

  return (
    <div className="mx-auto max-w-3xl">
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b bg-background pb-4">
        <select
          className="rounded-md border bg-background px-3 py-1.5 text-sm"
          value={filterScraper}
          onChange={(e) => setFilterScraper(e.target.value)}
        >
          <option value="">All sources</option>
          {scraperOptions.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>

        <input
          type="text"
          placeholder="Search..."
          className="rounded-md border bg-background px-3 py-1.5 text-sm"
          value={filterSearch}
          onChange={(e) => setFilterSearch(e.target.value)}
        />

        <select
          className="rounded-md border bg-background px-3 py-1.5 text-sm"
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
        >
          <option value={25}>25 items</option>
          <option value={50}>50 items</option>
          <option value={100}>100 items</option>
        </select>

        <span className="ml-auto text-xs text-muted-foreground">
          {loading ? "Loading..." : `${filtered.length} items`}
        </span>
      </div>

      <div className="divide-y">
        {filtered.map((item) => (
          <article key={item.id} className="py-5">
            <div className="mb-1 flex items-baseline gap-2">
              <span className="text-xs text-muted-foreground">{item.scraperName}</span>
              <span className="text-xs text-muted-foreground">&middot;</span>
              <time className="text-xs text-muted-foreground">{item.scrapedAt}</time>
            </div>
            {item.pageUrl ? (
              <a href={item.pageUrl} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:underline">
                {item.title || "Untitled"}
              </a>
            ) : (
              <h3 className="text-sm font-medium">{item.title || "Untitled"}</h3>
            )}
            {item.content && (
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground line-clamp-3">
                {item.content}
              </p>
            )}
          </article>
        ))}
        {!loading && filtered.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">No feed items found.</p>
        )}
      </div>

      {!loading && items.length >= limit && (
        <div className="flex justify-center py-6">
          <Button variant="outline" className={buttonStyles} onClick={() => setLimit((l) => l + 50)}>
            Load more
          </Button>
        </div>
      )}
    </div>
  )
}
