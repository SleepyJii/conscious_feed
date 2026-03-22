import { useEffect, useState } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { fetchScraperData, scraperColumns, type ScraperRow } from "@/lib/utils"

export function ScraperTable() {
  const [rows, setRows] = useState<ScraperRow[]>([])

  useEffect(() => {
    let cancelled = false

    fetchScraperData().then((data) => {
      if (!cancelled) setRows(data)
    })

    return () => { cancelled = true }
  }, [])

  return (
    <div className="rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            {scraperColumns.map((col) => (
              <TableHead key={col.key}>{col.header}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((scraper) => (
            <TableRow key={scraper.rowId}>
              {scraperColumns.map((col) => (
                <TableCell key={col.key} className={col.className}>
                  {scraper[col.key]}
                </TableCell>
              ))}
            </TableRow>
          ))}
          {rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={scraperColumns.length} className="text-muted-foreground">
                No scrapers found.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
