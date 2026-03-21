import { Button } from "@/components/ui/button"
import { HashRouter, Routes, Route, useNavigate } from "react-router-dom";
import { Textarea } from "./components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./components/ui/table";

type ScraperRow = {
  scraperId: string
  websiteUrl: string
  prompt: string
  output: string
}

type ColumnDefinition = {
  key: keyof ScraperRow
  header: string
  className?: string
}

const scraperColumns: ColumnDefinition[] = [
  { key: "scraperId", header: "Scraper ID" },
  { key: "websiteUrl", header: "Website URL", className: "whitespace-normal break-words" },
  { key: "prompt", header: "Prompt", className: "whitespace-normal break-words" },
  { key: "output", header: "Outpcan you make it so that ut", className: "whitespace-normal break-words" },
]

const placeholderScrapers: ScraperRow[] = [
  {
    scraperId: "scraper-001",
    websiteUrl: "https://example.com/blog",
    prompt: "Summarize latest post headlines and author names.",
    output: "3 new posts found; feed entry updated.",
  },
  {
    scraperId: "scraper-002",
    websiteUrl: "https://news.ycombinator.com/",
    prompt: "Capture top 10 titles and outbound links.",
    output: "10 rows inserted to scrape_results.",
  },
  {
    scraperId: "scraper-003",
    websiteUrl: "https://status.openai.com/",
    prompt: "Track incident title, status, and updated timestamp.",
    output: "No incident changes since last run.",
  },
  {
    scraperId: "scraper-004",
    websiteUrl: "https://github.blog/changelog/",
    prompt: "Extract release title, date, and short summary.",
    output: "2 changelog items captured.",
  },
  {
    scraperId: "scraper-005",
    websiteUrl: "https://docs.python.org/3/whatsnew/",
    prompt: "Collect section headings and first paragraph text.",
    output: "Page scraped successfully.",
  },
]

function Home() {
  const navigate = useNavigate()
  return (
    <div className="flex min-h-svh p-6">
      <div className="flex w-full min-w-0 max-w-6xl flex-col gap-4 text-sm leading-loose">
        <div>
          <h1 className="font-medium">Conscious Fleet.</h1>
          <Button className="hover:cursor-pointer mt-2" onClick={() => navigate('/config')}>Config</Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              {scraperColumns.map((column) => (
                <TableHead key={column.key}>{column.header}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {placeholderScrapers.map((scraper) => (
              <TableRow key={scraper.scraperId}>
                {scraperColumns.map((column) => (
                  <TableCell key={column.key} className={column.className}>
                    {scraper[column.key]}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="font-mono text-xs text-muted-foreground">
        </div>
      </div>
    </div>
  )
}

function Config() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col w-1/2 h-screen p-6 gap-4">
      <div className="flex flex-row gap-4">
        <Button onClick={() => navigate('/')} className="w-[15%] cursor-pointer hover:cursor-pointer">Return</Button>
        <Button variant="outline" className="hover:cursor-pointer">Submit Config</Button>
      </div>
      <Textarea className="flex-1"></Textarea>
    </div>
  )
}

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/config" element={<Config />} />
      </Routes>
    </HashRouter>
  )
}

export default App
