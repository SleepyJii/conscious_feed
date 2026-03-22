import { useEffect, useState } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  fetchDashboardData,
  type DashboardEventRow,
  type DashboardTimelinePoint,
} from "@/lib/utils"
import { CartesianGrid, Label, Line, LineChart, Pie, PieChart, XAxis, YAxis } from "recharts"

const healthChartConfig = {
  healthy: { label: "Healthy", color: "#16a34a" },
  degraded: { label: "Degraded", color: "#f59e0b" },
  failing: { label: "Failing", color: "#ef4444" },
  pending: { label: "Pending", color: "#60a5fa" },
  unknown: { label: "Unknown", color: "#9ca3af" },
} satisfies ChartConfig

const timelineChartConfig = {
  total: { label: "Total Scrapers", color: "#3b82f6" },
} satisfies ChartConfig

export function MonitoringCharts() {
  const [chartData, setChartData] = useState<Array<{ bucket: string; count: number; fill: string }>>([])
  const [timelineData, setTimelineData] = useState<DashboardTimelinePoint[]>([])
  const [eventRows, setEventRows] = useState<DashboardEventRow[]>([])

  useEffect(() => {
    let cancelled = false

    fetchDashboardData().then((data) => {
      if (cancelled) return

      const healthColors: Record<string, string> = {
        healthy: "#16a34a",
        degraded: "#f59e0b",
        failing: "#ef4444",
        pending: "#60a5fa",
        unknown: "#9ca3af",
      }

      setChartData(
        Object.entries(data.healthCounts).map(([bucket, count]) => ({
          bucket,
          count,
          fill: healthColors[bucket.toLowerCase()] ?? "#9ca3af",
        }))
      )
      setTimelineData(data.timelineData)
      setEventRows(data.eventRows)
    })

    return () => { cancelled = true }
  }, [])

  const totalScrapers = chartData.reduce((sum, item) => sum + item.count, 0)

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="rounded-xl border p-6">
        <h2 className="mb-4 text-sm font-medium">Scraper Health</h2>
        <ChartContainer config={healthChartConfig} className="mx-auto max-h-[280px] w-full">
          <PieChart>
            <ChartTooltip content={<ChartTooltipContent hideLabel />} />
            <Pie data={chartData} dataKey="count" nameKey="bucket" innerRadius={60}>
              <Label
                content={({ viewBox }) => {
                  if (!viewBox || !("cx" in viewBox) || !("cy" in viewBox)) return null
                  const cx = Number(viewBox.cx)
                  const cy = Number(viewBox.cy)
                  return (
                    <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle">
                      <tspan x={cx} y={cy} className="fill-foreground text-2xl font-semibold">
                        {totalScrapers}
                      </tspan>
                      <tspan x={cx} y={cy + 22} className="fill-muted-foreground text-xs">
                        Total
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
        <h2 className="mb-4 text-sm font-medium">Scrapers Timeline</h2>
        <ChartContainer config={timelineChartConfig} className="mx-auto max-h-[280px] w-full">
          <LineChart data={timelineData} margin={{ left: 12, right: 12 }}>
            <CartesianGrid vertical={false} />
            <XAxis type="category" dataKey="hour" tickLine={false} axisLine={false} />
            <YAxis type="number" dataKey="total" tickLine={false} axisLine={false} width={40} />
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
                <TableHead>Event</TableHead>
                <TableHead>Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {eventRows.map((event) => (
                <TableRow key={`${event.eventType}-${event.eventTime}`}>
                  <TableCell>{event.eventType}</TableCell>
                  <TableCell>{event.eventTime}</TableCell>
                </TableRow>
              ))}
              {eventRows.length === 0 && (
                <TableRow>
                  <TableCell className="text-muted-foreground" colSpan={2}>No recent events.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
