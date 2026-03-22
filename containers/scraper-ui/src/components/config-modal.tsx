import { useEffect, useState } from "react"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { buttonStyles } from "@/lib/global-styles"
import {
  fetchScraperData,
  postScraperConfig,
  type ScraperConfigUpdate,
} from "@/lib/utils"

interface ConfigModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ConfigModal({ open, onOpenChange }: ConfigModalProps) {
  const [scrapers, setScrapers] = useState("")
  const [status, setStatus] = useState("")
  const [statusTitle, setStatusTitle] = useState("")
  const [statusOpen, setStatusOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    let cancelled = false

    fetchScraperData().then((data) => {
      if (cancelled) return
      const payload: ScraperConfigUpdate[] = data.map((row) => ({
        scraper_id: row.scraperId,
        name: row.name,
        target_url: row.targetUrl,
        scraping_prompt: row.scrapingPrompt,
        cron_schedule: row.cronSchedule,
        repair_policy: row.repairPolicy,
      }))
      setScrapers(JSON.stringify(payload, null, 2))
    })

    return () => { cancelled = true }
  }, [open])

  async function handleSubmit() {
    try {
      const parsed = JSON.parse(scrapers) as unknown
      if (!Array.isArray(parsed)) {
        throw new Error("Config must be a JSON array: [ { ... }, { ... } ]")
      }
      if (parsed.some((item) => typeof item !== "object" || item === null || Array.isArray(item))) {
        throw new Error("Each item must be a JSON object")
      }

      const normalised = JSON.stringify(parsed, null, 2)
      setScrapers(normalised)
      setStatusTitle("Submitting Config")
      setStatus("Submitting...")
      setStatusOpen(true)
      const result = await postScraperConfig(normalised)
      setStatusTitle("Config Updated")
      setStatus(`Updated ${result.updated.length} scraper(s).`)
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to submit config"
      setStatusTitle("Submission Failed")
      setStatus(message)
      setStatusOpen(true)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent size="lg" className="flex max-h-[80vh] flex-col">
        <AlertDialogHeader>
          <AlertDialogTitle>Scraper Configuration</AlertDialogTitle>
          <AlertDialogDescription>
            Edit scraper configs as JSON and submit to apply changes.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <Textarea
          className="min-h-[300px] flex-1 font-mono text-sm"
          value={scrapers}
          onChange={(e) => setScrapers(e.target.value)}
        />

        <div className="flex justify-end gap-2">
          <Button variant="outline" className={buttonStyles} onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button className={buttonStyles} onClick={handleSubmit}>
            Submit Config
          </Button>
        </div>

        <AlertDialog open={statusOpen} onOpenChange={setStatusOpen}>
          <AlertDialogContent size="sm">
            <AlertDialogHeader>
              <AlertDialogTitle>{statusTitle}</AlertDialogTitle>
              <AlertDialogDescription>{status}</AlertDialogDescription>
              <Button className={`${buttonStyles} mt-0`} onClick={() => setStatusOpen(false)}>OK</Button>
            </AlertDialogHeader>
          </AlertDialogContent>
        </AlertDialog>
      </AlertDialogContent>
    </AlertDialog>
  )
}
