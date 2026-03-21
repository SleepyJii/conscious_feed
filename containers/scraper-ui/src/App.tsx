import { useEffect, useState } from "react"
import { HashRouter, Routes, Route, useLocation } from "react-router-dom";
import { Navbar } from "./components/navbar";
import { Textarea } from "./components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./components/ui/table";
import {
  fetchDashboardData,
  fetchScraperData,
  postScraperConfig,
  scraperColumns,
  type DashboardEventRow,
  type DashboardTimelinePoint,
  type ScraperConfigUpdate,
  type ScraperRow,
} from "@/lib/utils"
import { Button } from "./components/ui/button";
import { buttonStyles } from "./lib/global-styles";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./components/ui/alert-dialog";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "./components/ui/chart";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";
import { CartesianGrid, Label, Line, LineChart, Pie, PieChart, XAxis, YAxis } from "recharts";

const dashboardChartConfig = {
  healthy: {
    label: "Healthy",
    color: "#16a34a",
  },
  degraded: {
    label: "Degraded",
    color: "#f59e0b",
  },
  failing: {
    label: "Failing",
    color: "#ef4444",
  },
  pending: {
    label: "Pending",
    color: "#60a5fa",
  },
  unknown: {
    label: "Unknown",
    color: "#9ca3af",
  },
} satisfies ChartConfig

const dashboardTimelineConfig = {
  total: {
    label: "Total Scrapers",
    color: "#3b82f6",
  },
} satisfies ChartConfig

const ROUTE_TRANSITION_MS = 220

function Home() {
  const [rows, setRows] = useState<ScraperRow[]>([])

  useEffect(() => {
    let cancelled = false

    fetchScraperData().then((data) => {
      if (!cancelled) {
        setRows(data)
      }
    })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="flex flex-1 items-start justify-center p-6">
      <div className="flex w-full min-w-0 max-w-6xl flex-col gap-4 text-sm leading-loose">
        <Table>
          <TableHeader>
            <TableRow>
              {scraperColumns.map((column) => (
                <TableHead key={column.key}>{column.header}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((scraper) => (
              <TableRow key={scraper.rowId}>
                {scraperColumns.map((column) => (
                  <TableCell key={column.key} className={column.className}>
                    {scraper[column.key]}
                  </TableCell>
                ))}
              </TableRow>
            ))}
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={scraperColumns.length} className="text-muted-foreground">
                  No rows returned by fetchScraperData.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        <div className="font-mono text-xs text-muted-foreground" />
      </div>
    </div>
  )
}

function Config() {
  const [scrapers, setScrapers] = useState("")
  const [status, setStatus] = useState("")
  const [statusTitle, setStatusTitle] = useState("Status")
  const [statusDialogOpen, setStatusDialogOpen] = useState(false)

  useEffect(() => {
    let cancelled = false

    fetchScraperData().then((data) => {
      if (!cancelled) {
        const payload: ScraperConfigUpdate[] = data.map((row) => ({
          scraper_id: row.scraperId,
          name: row.name,
          target_url: row.targetUrl,
          scraping_prompt: row.scrapingPrompt,
          cron_schedule: row.cronSchedule,
          autorepair: row.autorepair,
        }))
        setScrapers(JSON.stringify(payload, null, 2))
      }
    })

    return () => {
      cancelled = true
    }
  }, [])

  async function handleSubmitConfig() {
    try {
      const parsed = JSON.parse(scrapers) as unknown
      if (!Array.isArray(parsed)) {
        throw new Error("Config must be a JSON array: [ { ... }, { ... } ]")
      }
      if (parsed.some((item) => typeof item !== "object" || item === null || Array.isArray(item))) {
        throw new Error("Each item must be a JSON object: [ { ... }, { ... } ]")
      }

      const normalised = JSON.stringify(parsed, null, 2)
      setScrapers(normalised)
      setStatusTitle("Submitting Config")
      setStatus("Submitting...")
      setStatusDialogOpen(true)
      const result = await postScraperConfig(normalised)
      setStatusTitle("Config Updated")
      setStatus(`Updated ${result.updated.length} scraper(s).`)
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to submit config"
      setStatusTitle("Submission Failed")
      setStatus(message)
      setStatusDialogOpen(true)
    }
  }

  return (
    <div className="flex h-full flex-col gap-4 p-6">

        <AlertDialog open={statusDialogOpen} onOpenChange={setStatusDialogOpen}>
          <AlertDialogContent size="sm">
            <AlertDialogHeader>
              <AlertDialogTitle>{statusTitle}</AlertDialogTitle>
              <AlertDialogDescription>{status}</AlertDialogDescription>
              <Button className={`${buttonStyles} mt-0`} onClick={() => setStatusDialogOpen(false)}>Proceed</Button>
            </AlertDialogHeader>
          </AlertDialogContent>
        </AlertDialog>

        <div className="flex justify-center">
          <Button variant="outline" className={buttonStyles} onClick={() => handleSubmitConfig()}>Submit Config</Button>
        </div>
        <div className="flex flex-1 justify-center">
          <Textarea
            className="h-full w-1/2"
            value={scrapers}
            onChange={(e) => setScrapers(e.target.value)}
          />
        </div>
    </div>
  )
}

function Dashboard() {
  const [dashboardChartData, setDashboardChartData] = useState<Array<{ bucket: string; count: number; fill: string }>>([])
  const [dashboardTimelineData, setDashboardTimelineData] = useState<DashboardTimelinePoint[]>([])
  const [dashboardEventRows, setDashboardEventRows] = useState<DashboardEventRow[]>([])

  useEffect(() => {
    let cancelled = false

    async function loadDashboard() {
      try {
        const data = await fetchDashboardData()

        if (cancelled) {
          return
        }

        const healthColorByKey: Record<string, string> = {
          healthy: "#16a34a",
          degraded: "#f59e0b",
          failing: "#ef4444",
          pending: "#60a5fa",
          unknown: "#9ca3af",
        }

        const chartData = Object.entries(data.healthCounts).map(([bucket, count]) => {
          const key = bucket.toLowerCase()
          return {
            bucket,
            count,
            fill: healthColorByKey[key] ?? "#9ca3af",
          }
        })

        setDashboardChartData(chartData)
        setDashboardTimelineData(data.timelineData)
        setDashboardEventRows(data.eventRows)
      } catch {
        if (!cancelled) {
          setDashboardTimelineData([])
          setDashboardEventRows([])
        }
      }
    }

    loadDashboard()

    return () => {
      cancelled = true
    }
  }, [])

  const totalScrapers = dashboardChartData.reduce((sum, item) => sum + item.count, 0)

  return (
    <div className="flex flex-1 items-start justify-center p-6">
      <div className="grid w-full max-w-6xl grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border p-6">
          <h2 className="mb-4 text-sm font-medium">Scraper Health</h2>
          <ChartContainer config={dashboardChartConfig} className="mx-auto max-h-[320px] w-full">
            <PieChart>
              <ChartTooltip content={<ChartTooltipContent hideLabel />} />
              <Pie data={dashboardChartData} dataKey="count" nameKey="bucket" innerRadius={60}>
                <Label
                  content={({ viewBox }) => {
                    if (!viewBox || !("cx" in viewBox) || !("cy" in viewBox)) {
                      return null
                    }

                    const cx = Number(viewBox.cx)
                    const cy = Number(viewBox.cy)

                    return (
                      <text
                        x={cx}
                        y={cy}
                        textAnchor="middle"
                        dominantBaseline="middle"
                      >
                        <tspan x={cx} y={cy} className="fill-foreground text-2xl font-semibold">
                          {totalScrapers}
                        </tspan>
                        <tspan x={cx} y={cy + 22} className="fill-muted-foreground text-xs">
                          Total Scrapers
                        </tspan>
                      </text>
                    )
                  }}
                />
              </Pie>
            </PieChart>
          </ChartContainer>
        </div>

        <div className="rounded-xl border p-6">
          <h2 className="mb-4 text-sm font-medium">Total Scrapers Timeline</h2>
          <ChartContainer config={dashboardTimelineConfig} className="mx-auto max-h-[320px] w-full">
            <LineChart data={dashboardTimelineData} margin={{ left: 12, right: 12 }}>
              <CartesianGrid vertical={false} />
              <XAxis type="category" dataKey="hour" name="Time" tickLine={false} axisLine={false} />
              <YAxis type="number" dataKey="total" name="Total Scrapers" tickLine={false} axisLine={false} width={56} />
              <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
              <Line
                type="monotone"
                dataKey="total"
                stroke="var(--color-total)"
                strokeWidth={2}
                dot={{ r: 4, fill: "var(--color-total)" }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ChartContainer>
        </div>

        <Card className="bg-background">
          <CardHeader>
            <CardTitle>Recent Events</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Event Type</TableHead>
                  <TableHead>Time of Event</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dashboardEventRows.map((event) => (
                  <TableRow key={`${event.eventType}-${event.eventTime}`}>
                    <TableCell>{event.eventType}</TableCell>
                    <TableCell>{event.eventTime}</TableCell>
                  </TableRow>
                ))}
                {dashboardEventRows.length === 0 && (
                  <TableRow>
                    <TableCell className="text-muted-foreground" colSpan={2}>No recent events.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function AppRoutes() {
  const location = useLocation()
  const [displayLocation, setDisplayLocation] = useState(location)
  const [transitionStage, setTransitionStage] = useState<"fadeIn" | "fadeOut">("fadeIn")

  useEffect(() => {
    if (location.pathname !== displayLocation.pathname) {
      setTransitionStage("fadeOut")
    }
  }, [location, displayLocation.pathname])

  useEffect(() => {
    if (transitionStage !== "fadeOut") {
      return
    }

    const timeoutId = window.setTimeout(() => {
      setDisplayLocation(location)
      setTransitionStage("fadeIn")
    }, ROUTE_TRANSITION_MS)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [transitionStage, location])

  return (
    <div className="flex h-screen flex-col">
      <Navbar currentPath={location.pathname} />
      <div className={`flex-1 ${transitionStage === "fadeIn" ? "route-fade-in" : "route-fade-out"}`}>
        <Routes location={displayLocation}>
          <Route path="/" element={<Home />} />
          <Route path="/config" element={<Config />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </div>
    </div>
  )
}

export function App() {
  return (
    <HashRouter>
      <AppRoutes />
    </HashRouter>
  )
}


export default App
