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
  autorepair: boolean
  containerState: string
  monitoringHealth: string
  monitoringLastRun: string
  monitoringTotalRuns: number
}

type ColumnDefinition = {
  key: keyof ScraperRow
  header: string
  className?: string
}

export const scraperColumns: ColumnDefinition[] = [
  { key: "scraperId", header: "Scraper ID", className: "whitespace-normal break-words" },
  { key: "name", header: "Name", className: "whitespace-normal break-words" },
  { key: "targetUrl", header: "Target URL", className: "whitespace-normal break-words" },
  { key: "scrapingPrompt", header: "Scraping Prompt", className: "whitespace-normal break-words" },
  { key: "cronSchedule", header: "Cron Schedule", className: "whitespace-normal break-words" },
  { key: "autorepair", header: "Autorepair", className: "whitespace-normal break-words" },
  { key: "containerState", header: "Container State", className: "whitespace-normal break-words" },
  { key: "monitoringHealth", header: "Health", className: "whitespace-normal break-words" },
  { key: "monitoringLastRun", header: "Last Run", className: "whitespace-normal break-words" },
  { key: "monitoringTotalRuns", header: "Total Runs", className: "whitespace-normal break-words" },
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
  autorepair?: boolean
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
    autorepair: row.autorepair ?? false,
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

export type DashboardEventRow = {
  eventType: string
  eventTime: string
}

export type DashboardTimelinePoint = {
  hour: string
  total: number
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

const TIMELINE_HOURS = 12

function classifyHealth(health: string): string {
  const value = health.toLowerCase().trim()
  if (!value) {
    return "Unknown"
  }

  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`
}

function toHourLabel(date: Date): string {
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

    const now = new Date()
    now.setMinutes(0, 0, 0)
    const hourlyMarks = Array.from({ length: TIMELINE_HOURS }, (_, index) => {
      const hourDate = new Date(now)
      hourDate.setHours(now.getHours() - (TIMELINE_HOURS - 1 - index))
      return hourDate
    })

    const scraperSeen = new Set<string>()
    const eventsAsc = [...eventRowsFromApi]
      .filter((event) => typeof event.created_at === "string")
      .sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""))

    let eventIndex = 0
    const timelineData = hourlyMarks.map((hourStart) => {
      const hourEnd = new Date(hourStart)
      hourEnd.setHours(hourStart.getHours() + 1)

      while (eventIndex < eventsAsc.length) {
        const event = eventsAsc[eventIndex]
        const createdAt = event.created_at ? new Date(event.created_at) : null
        if (!createdAt || createdAt >= hourEnd) {
          break
        }
        if (event.container_id) {
          scraperSeen.add(event.container_id)
        }
        eventIndex += 1
      }

      return {
        hour: toHourLabel(hourStart),
        total: scraperSeen.size > 0 ? scraperSeen.size : scrapers.length,
      }
    })

    return {
      healthCounts,
      timelineData,
      eventRows,
    }
  } catch (error) {
    console.error("Failed to fetch dashboard data:", error)

    const now = new Date()
    now.setMinutes(0, 0, 0)
    const timelineData = Array.from({ length: TIMELINE_HOURS }, (_, index) => {
      const hourDate = new Date(now)
      hourDate.setHours(now.getHours() - (TIMELINE_HOURS - 1 - index))
      return {
        hour: toHourLabel(hourDate),
        total: scrapers.length,
      }
    })

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
  autorepair?: boolean
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

