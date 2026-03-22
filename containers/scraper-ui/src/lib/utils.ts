import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export type ScraperRow = {
  rowId: string
  scraperId: string
  name: string
  targetUrl: string
  scrapingPrompt: string
  cronSchedule: string
  repairPolicy: string[]
  category: string
  runTimeout: number
  agentNotes: string
  containerState: string
  monitoringHealth: string
  monitoringLastRun: string
  monitoringTotalRuns: number
}

type ColumnDefinition = {
  key: keyof ScraperRow
  header: string
  className?: string
  scrollable?: boolean
}

export const scraperColumns: ColumnDefinition[] = [
  { key: "scraperId", header: "ID", className: "whitespace-nowrap" },
  { key: "name", header: "Name", className: "whitespace-nowrap" },
  { key: "targetUrl", header: "URL", className: "whitespace-nowrap max-w-[150px] truncate" },
  { key: "scrapingPrompt", header: "Prompt", className: "max-w-[200px]", scrollable: true },
  { key: "cronSchedule", header: "Cron", className: "whitespace-nowrap" },
  { key: "repairPolicy", header: "Policy", className: "whitespace-nowrap" },
  { key: "category", header: "Category", className: "whitespace-nowrap" },
  { key: "agentNotes", header: "Agent Notes", className: "max-w-[200px]", scrollable: true },
  { key: "containerState", header: "State", className: "whitespace-nowrap" },
  { key: "monitoringHealth", header: "Health", className: "whitespace-nowrap" },
  { key: "monitoringLastRun", header: "Last Run", className: "whitespace-nowrap" },
  { key: "monitoringTotalRuns", header: "Runs", className: "whitespace-nowrap" },
]

type RawMonitoring = {
  health?: string
  last_run?: string
  total_runs?: number
}

type RawScraperRow = {
  scraper_id?: string
  name?: string
  target_url?: string
  scraping_prompt?: string
  cron_schedule?: string
  repair_policy?: string[]
  category?: string
  run_timeout?: number
  agent_notes?: string
  container_state?: string
  monitoring?: RawMonitoring
}

function toScraperRow(row: RawScraperRow, index: number): ScraperRow {
  return {
    rowId: `row-${index + 1}`,
    scraperId: row.scraper_id ?? "",
    name: row.name ?? "",
    targetUrl: row.target_url ?? "",
    scrapingPrompt: row.scraping_prompt ?? "",
    cronSchedule: row.cron_schedule ?? "",
    repairPolicy: row.repair_policy ?? ["RETRY"],
    category: row.category ?? "",
    runTimeout: row.run_timeout ?? 300,
    agentNotes: row.agent_notes ?? "",
    containerState: row.container_state ?? "not running",
    monitoringHealth: row.monitoring?.health ?? "unknown",
    monitoringLastRun: row.monitoring?.last_run ?? "",
    monitoringTotalRuns: row.monitoring?.total_runs ?? 0,
  }
}

export async function fetchScraperData(): Promise<ScraperRow[]> {
  try {
    const response = await fetch("/conductor-api/scrapers");
    if (!response.ok) {
      throw new Error(`Request failed with ${response.status}`)
    }
    const data = await response.json();
    if (!Array.isArray(data)) {
      return []
    }
    return data.map((row, index) => toScraperRow(row as RawScraperRow, index));
  } catch (error) {
    console.error("Failed to fetch scraper data: ", error);
    return []
  }
}

export async function fetchScraperScript(scraperId: string): Promise<string> {
  const response = await fetch(`/conductor-api/scrapers/${scraperId}/script`)
  if (!response.ok) throw new Error(`Failed to fetch script (${response.status})`)
  const data = await response.json()
  return data.script
}

export async function updateScraperScript(scraperId: string, script: string): Promise<void> {
  const response = await fetch(`/conductor-api/scrapers/${scraperId}/script`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ script }),
  })
  if (!response.ok) throw new Error(`Failed to update script (${response.status})`)
}

export async function resetScraperScript(scraperId: string): Promise<void> {
  const response = await fetch(`/conductor-api/scrapers/${scraperId}/script/reset`, { method: "POST" })
  if (!response.ok) throw new Error(`Failed to reset script (${response.status})`)
}

export async function runScraper(scraperId: string): Promise<{ exit_code: number }> {
  const response = await fetch(`/conductor-api/scrapers/${scraperId}/run`, { method: "POST" })
  if (!response.ok) throw new Error(`Run failed (${response.status})`)
  return response.json()
}

export async function stopScraper(scraperId: string): Promise<void> {
  const response = await fetch(`/conductor-api/scrapers/${scraperId}/stop`, { method: "POST" })
  if (!response.ok) throw new Error(`Stop failed (${response.status})`)
}

export async function repairScraper(
  scraperId: string,
  opts: { model?: string; sockpuppet?: boolean } = {},
): Promise<void> {
  const response = await fetch(`/conductor-api/scrapers/${scraperId}/repair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lazy: false, sockpuppet: opts.sockpuppet ?? false, model: opts.model ?? "" }),
  })
  if (!response.ok) throw new Error(`Repair failed (${response.status})`)
}

export type DashboardEventRow = {
  eventType: string
  eventTime: string
}

export type DashboardTimelinePoint = {
  hour: string
  total: number
  repairs: number
  active: number
}

export type DashboardHealthCounts = Record<string, number>

type RawEventRow = {
  created_at?: string
  event_type?: string
  container_id?: string | null
}

type DashboardData = {
  healthCounts: DashboardHealthCounts
  timelineData: DashboardTimelinePoint[]
  eventRows: DashboardEventRow[]
}

const MAX_TIMELINE_MS = 12 * 60 * 60 * 1000

function classifyHealth(health: string): string {
  const value = health.toLowerCase().trim()
  if (!value) {
    return "Unknown"
  }

  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`
}

function toMinuteLabel(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })
}

export async function fetchDashboardData(): Promise<DashboardData> {
  const emptyHealthCounts: DashboardHealthCounts = {}

  const scrapers = await fetchScraperData()

  const healthCounts: DashboardHealthCounts = {}
  for (const scraper of scrapers) {
    // Derived from /scrapers -> monitoring.health
    const key = classifyHealth(scraper.monitoringHealth)
    healthCounts[key] = (healthCounts[key] ?? 0) + 1
  }

  try {
    const eventsResponse = await fetch("/api/find_events?limit=300")

    const eventRowsFromApi: RawEventRow[] = eventsResponse.ok
      ? ((await eventsResponse.json()) as RawEventRow[])
      : []

    const eventRows: DashboardEventRow[] = eventRowsFromApi.slice(0, 3).map((event) => ({
      eventType: event.event_type ?? "Unknown Event",
      eventTime: event.created_at ? new Date(event.created_at).toLocaleString() : "Unknown Time",
    }))

    const eventsAsc = [...eventRowsFromApi]
      .filter((event) => typeof event.created_at === "string")
      .sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""))

    // Build minute-level timeline from first event to now, capped at 12h
    const now = new Date()
    const earliest = eventsAsc.length > 0
      ? new Date(eventsAsc[0].created_at!)
      : now

    const startTime = new Date(Math.max(earliest.getTime(), now.getTime() - MAX_TIMELINE_MS))
    startTime.setSeconds(0, 0)

    // Generate one point per minute
    const minuteMarks: Date[] = []
    const cursor = new Date(startTime)
    while (cursor <= now) {
      minuteMarks.push(new Date(cursor))
      cursor.setMinutes(cursor.getMinutes() + 1)
    }

    let scraperCount = 0
    let activeRepairs = 0
    let activeScrapers = 0
    let eventIndex = 0

    const timelineData = minuteMarks.map((minuteStart) => {
      const minuteEnd = new Date(minuteStart)
      minuteEnd.setMinutes(minuteStart.getMinutes() + 1)

      while (eventIndex < eventsAsc.length) {
        const event = eventsAsc[eventIndex]
        const createdAt = event.created_at ? new Date(event.created_at) : null
        if (!createdAt || createdAt >= minuteEnd) break

        if (event.event_type === "scraper_created") scraperCount++
        if (event.event_type === "scraper_deleted") scraperCount = Math.max(0, scraperCount - 1)
        if (event.event_type === "scraper_launched" || event.event_type === "scraper_debug_launched") activeScrapers++
        if (event.event_type === "scraper_run_completed") {
          activeScrapers = Math.max(0, activeScrapers - 1)
        }
        if (event.event_type === "repair_launched") activeRepairs++
        if (event.event_type === "repair_cleanup") {
          activeRepairs = Math.max(0, activeRepairs - 1)
        }

        eventIndex++
      }

      return {
        hour: toMinuteLabel(minuteStart),
        total: scraperCount,
        repairs: activeRepairs,
        active: activeScrapers,
      }
    })

    return {
      healthCounts,
      timelineData,
      eventRows,
    }
  } catch (error) {
    console.error("Failed to fetch dashboard data:", error)

    const timelineData: DashboardTimelinePoint[] = [{
      hour: toMinuteLabel(new Date()),
      total: scrapers.length,
      repairs: 0,
      active: 0,
    }]

    return {
      healthCounts: scrapers.length > 0 ? healthCounts : emptyHealthCounts,
      timelineData,
      eventRows: [],
    }
  }
}

export type ScraperConfigUpdate = {
  scraper_id: string
  name?: string
  target_url?: string
  scraping_prompt?: string
  cron_schedule?: string
  repair_policy?: string[]
  category?: string
  run_timeout?: number
}

type BatchUpdateResponse = {
  updated: RawScraperRow[]
}

export async function postScraperConfig(
  input: ScraperConfigUpdate[] | string
): Promise<BatchUpdateResponse> {
  const payload =
    typeof input === "string"
      ? (JSON.parse(input) as ScraperConfigUpdate[])
      : input

  if (!Array.isArray(payload)) {
    throw new Error("Config payload must be a JSON array")
  }

  for (const row of payload) {
    if (!row?.scraper_id) {
      throw new Error("Each scraper config must include scraper_id")
    }
  }

  const response = await fetch("/conductor-api/batch-update", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`batch-update failed (${response.status}): ${errorText}`)
  }

  return (await response.json()) as BatchUpdateResponse
}

export type NewScraperInput = {
  name?: string
  target_url: string
  scraping_prompt: string
  cron_schedule?: string
  repair_policy?: string[]
  category?: string
  run_timeout?: number
}

export async function addNewScraper(input: NewScraperInput): Promise<RawScraperRow> {
  const response = await fetch("/conductor-api/scrapers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to add scraper (${response.status}): ${errorText}`)
  }

  return (await response.json()) as RawScraperRow
}

export type FeedItem = {
  id: number
  scraperId: string
  scraperName: string
  category: string
  targetUrl: string
  pageUrl: string
  title: string
  content: string
  publishedAt: string
  scrapedAt: string
}

type RawFeedItem = {
  id?: number
  scraper_id?: string
  scraper_name?: string
  category?: string
  target_url?: string
  page_url?: string
  title?: string
  content?: string
  published_at?: string
  scraped_at?: string
}

export async function fetchFeedItems(opts?: {
  scraper_id?: string
  limit?: number
  offset?: number
}): Promise<FeedItem[]> {
  try {
    const params = new URLSearchParams()
    if (opts?.scraper_id) params.set("scraper_id", opts.scraper_id)
    if (opts?.limit) params.set("limit", String(opts.limit))
    if (opts?.offset) params.set("offset", String(opts.offset))

    const qs = params.toString()
    const response = await fetch(`/api/rss_content${qs ? `?${qs}` : ""}`)
    if (!response.ok) {
      throw new Error(`Request failed with ${response.status}`)
    }
    const data = (await response.json()) as RawFeedItem[]
    if (!Array.isArray(data)) return []

    return data.map((row) => ({
      id: row.id ?? 0,
      scraperId: row.scraper_id ?? "",
      scraperName: row.scraper_name ?? "",
      category: row.category ?? "",
      targetUrl: row.target_url ?? "",
      pageUrl: row.page_url ?? "",
      title: row.title ?? "",
      content: row.content ?? "",
      publishedAt: row.published_at ? new Date(row.published_at).toLocaleString() : "",
      scrapedAt: row.scraped_at ? new Date(row.scraped_at).toLocaleString() : "",
    }))
  } catch (error) {
    console.error("Failed to fetch feed items:", error)
    return []
  }
}

