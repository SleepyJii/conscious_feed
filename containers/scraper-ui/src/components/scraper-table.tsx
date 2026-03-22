import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Play, Square, Wrench, Rocket } from "lucide-react"
import {
  fetchScraperData,
  runScraper,
  stopScraper,
  repairScraper,
  scraperColumns,
  type ScraperRow,
} from "@/lib/utils"

function Toast({ message, onDone }: { message: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 4000)
    return () => clearTimeout(t)
  }, [onDone])

  return createPortal(
    <div className="fixed bottom-4 right-4 z-50 rounded-lg border bg-background px-4 py-3 text-sm shadow-lg ring-1 ring-foreground/10">
      {message}
    </div>,
    document.body,
  )
}

function RepairPopover({ scraperId, onAction }: { scraperId: string; onAction: (msg: string) => void }) {
  const [open, setOpen] = useState(false)
  const [model, setModel] = useState("")
  const [sockpuppet, setSockpuppet] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (
        popoverRef.current && !popoverRef.current.contains(e.target as Node) &&
        buttonRef.current && !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [open])

  function handleOpen() {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect()
      setPos({ top: rect.bottom + 4, left: rect.right })
    }
    setOpen(!open)
  }

  async function handleLaunch() {
    setOpen(false)
    try {
      await repairScraper(scraperId, { model: sockpuppet ? undefined : (model || undefined), sockpuppet })
      onAction(sockpuppet
        ? `${scraperId}: Sockpuppet repair launched`
        : `${scraperId}: Repair launched${model ? ` (${model})` : ""}`)
    } catch (e) {
      onAction(`${scraperId}: ${e instanceof Error ? e.message : "Repair failed"}`)
    }
  }

  return (
    <>
      <button
        ref={buttonRef}
        onClick={handleOpen}
        className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
        title="Repair"
      >
        <Wrench className="h-5 w-5" />
      </button>
      {open && createPortal(
        <div
          ref={popoverRef}
          className="fixed z-50 rounded-lg border bg-background p-3 shadow-lg ring-1 ring-foreground/10"
          style={{ top: pos.top, left: pos.left, transform: "translateX(-100%)" }}
        >
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="model"
              className="w-[100px] rounded border bg-background px-2 py-1 text-xs disabled:opacity-40"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={sockpuppet}
            />
            <label className="flex items-center gap-1 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={sockpuppet}
                onChange={(e) => setSockpuppet(e.target.checked)}
                className="rounded"
              />
              sockpuppet
            </label>
            <button
              onClick={handleLaunch}
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              title="Launch repair"
            >
              <Rocket className="h-4 w-4" />
            </button>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}

export function ScraperTable() {
  const [rows, setRows] = useState<ScraperRow[]>([])
  const [toast, setToast] = useState("")

  useEffect(() => {
    let cancelled = false
    fetchScraperData().then((data) => {
      if (!cancelled) setRows(data)
    })
    return () => { cancelled = true }
  }, [])

  function showToast(msg: string) {
    setToast(msg)
  }

  async function handleRun(scraperId: string) {
    showToast(`${scraperId}: Running...`)
    try {
      const result = await runScraper(scraperId)
      showToast(`${scraperId}: Run finished (exit ${result.exit_code})`)
      fetchScraperData().then(setRows)
    } catch (e) {
      showToast(`${scraperId}: ${e instanceof Error ? e.message : "Run failed"}`)
    }
  }

  async function handleStop(scraperId: string) {
    try {
      await stopScraper(scraperId)
      showToast(`${scraperId}: Stopped`)
      fetchScraperData().then(setRows)
    } catch (e) {
      showToast(`${scraperId}: ${e instanceof Error ? e.message : "Stop failed"}`)
    }
  }

  return (
    <div className="min-h-0 rounded-xl border">
      {toast && <Toast message={toast} onDone={() => setToast("")} />}
      <Table>
        <TableHeader>
          <TableRow>
            {scraperColumns.map((col) => (
              <TableHead key={col.key}>{col.header}</TableHead>
            ))}
            <TableHead className="w-[50px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((scraper) => (
            <TableRow key={scraper.rowId}>
              {scraperColumns.map((col) => (
                <TableCell key={col.key} className={col.className}>
                  {Array.isArray(scraper[col.key]) ? (scraper[col.key] as string[]).join(", ") : scraper[col.key]}
                </TableCell>
              ))}
              <TableCell>
                <div className="flex flex-col items-center gap-0.5">
                  <button
                    onClick={() => handleRun(scraper.scraperId)}
                    className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                    title="Run now"
                  >
                    <Play className="h-5 w-5" />
                  </button>
                  <button
                    onClick={() => handleStop(scraper.scraperId)}
                    className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                    title="Stop"
                  >
                    <Square className="h-5 w-5" />
                  </button>
                  <RepairPopover scraperId={scraper.scraperId} onAction={showToast} />
                </div>
              </TableCell>
            </TableRow>
          ))}
          {rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={scraperColumns.length + 1} className="text-muted-foreground">
                No scrapers found.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
