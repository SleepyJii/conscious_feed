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
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { buttonStyles } from "@/lib/global-styles"
import { Plus, Code, LayoutList, Trash2, FileCode } from "lucide-react"
import {
  addNewScraper,
  fetchScraperData,
  fetchScraperScript,
  updateScraperScript,
  resetScraperScript,
  postScraperConfig,
  type ScraperConfigUpdate,
} from "@/lib/utils"

interface ConfigModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type ScraperForm = {
  scraper_id: string
  name: string
  target_url: string
  scraping_prompt: string
  cron_schedule: string
  repair_policy: string
  category: string
  run_timeout: string
  isNew?: boolean
}

function scraperToForm(s: ScraperConfigUpdate): ScraperForm {
  return {
    scraper_id: s.scraper_id,
    name: s.name ?? "",
    target_url: s.target_url ?? "",
    scraping_prompt: s.scraping_prompt ?? "",
    cron_schedule: s.cron_schedule ?? "",
    category: s.category ?? "",
    repair_policy: (s.repair_policy ?? ["RETRY"]).join(", "),
    run_timeout: String(s.run_timeout ?? 300),
  }
}

function formToUpdate(f: ScraperForm): ScraperConfigUpdate {
  return {
    scraper_id: f.scraper_id,
    name: f.name,
    target_url: f.target_url,
    scraping_prompt: f.scraping_prompt,
    cron_schedule: f.cron_schedule,
    repair_policy: f.repair_policy.split(",").map((s) => s.trim()).filter(Boolean),
    category: f.category,
    run_timeout: parseInt(f.run_timeout) || 300,
  }
}

function FormField({ label, value, onChange, multiline, placeholder }: {
  label: string
  value: string
  onChange: (v: string) => void
  multiline?: boolean
  placeholder?: string
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {multiline ? (
        <Textarea
          className="min-h-[80px] text-sm"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      ) : (
        <input
          className="rounded-md border bg-background px-3 py-1.5 text-sm"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      )}
    </label>
  )
}

function ScriptEditor({ scraperId, onClose }: { scraperId: string; onClose: () => void }) {
  const [script, setScript] = useState("")
  const [loading, setLoading] = useState(true)
  const [statusMsg, setStatusMsg] = useState("")
  const [wipeConfirmOpen, setWipeConfirmOpen] = useState(false)

  useEffect(() => {
    fetchScraperScript(scraperId)
      .then((s) => { setScript(s); setLoading(false) })
      .catch((e) => { setStatusMsg(e.message); setLoading(false) })
  }, [scraperId])

  async function handleUpdate() {
    try {
      await updateScraperScript(scraperId, script)
      setStatusMsg("Script updated.")
      setTimeout(() => setStatusMsg(""), 3000)
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "Update failed")
    }
  }

  async function handleWipe() {
    try {
      await resetScraperScript(scraperId)
      // Also clear agent_notes via PATCH
      await fetch(`/conductor-api/scrapers/${scraperId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_notes: "SCRAPER NOT YET IMPLEMENTED" }),
      })
      const freshScript = await fetchScraperScript(scraperId)
      setScript(freshScript)
      setWipeConfirmOpen(false)
      setStatusMsg("Script and agent notes wiped.")
      setTimeout(() => setStatusMsg(""), 3000)
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "Wipe failed")
    }
  }

  return (
    <AlertDialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <AlertDialogContent size="lg" className="flex max-h-[85vh] flex-col">
        <AlertDialogHeader>
          <AlertDialogTitle>Script — {scraperId}</AlertDialogTitle>
          <AlertDialogDescription>View and edit the scraper's Python script.</AlertDialogDescription>
        </AlertDialogHeader>

        {loading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Loading...</p>
        ) : (
          <Textarea
            className="min-h-[350px] flex-1 font-mono text-xs leading-relaxed"
            value={script}
            onChange={(e) => setScript(e.target.value)}
          />
        )}

        {statusMsg && (
          <p className="text-xs text-muted-foreground">{statusMsg}</p>
        )}

        <div className="flex justify-between">
          <div className="flex gap-2">
            <Button className={buttonStyles} onClick={handleUpdate}>UPDATE</Button>
            <button
              onClick={() => setWipeConfirmOpen(true)}
              className="rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
            >
              WIPE
            </button>
          </div>
          <Button variant="outline" className={buttonStyles} onClick={onClose}>Close</Button>
        </div>

        <AlertDialog open={wipeConfirmOpen} onOpenChange={setWipeConfirmOpen}>
          <AlertDialogContent size="sm">
            <AlertDialogHeader>
              <AlertDialogTitle>Wipe Script?</AlertDialogTitle>
              <AlertDialogDescription>
                This will clear the current script and agent notes entirely.
                Repair agents will need to rebuild the script from scratch using the scraping prompt.
              </AlertDialogDescription>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" className={buttonStyles} onClick={() => setWipeConfirmOpen(false)}>Cancel</Button>
                <button
                  onClick={handleWipe}
                  className="rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
                >
                  Wipe Everything
                </button>
              </div>
            </AlertDialogHeader>
          </AlertDialogContent>
        </AlertDialog>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function ConfigModal({ open, onOpenChange }: ConfigModalProps) {
  const [mode, setMode] = useState<"gui" | "json">("gui")
  const [forms, setForms] = useState<ScraperForm[]>([])
  const [rawJson, setRawJson] = useState("")
  const [status, setStatus] = useState("")
  const [statusTitle, setStatusTitle] = useState("")
  const [statusOpen, setStatusOpen] = useState(false)
  const [scriptEditorId, setScriptEditorId] = useState<string | null>(null)

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
        category: row.category,
        run_timeout: row.runTimeout ?? 300,
      }))
      setForms(payload.map(scraperToForm))
      setRawJson(JSON.stringify(payload, null, 2))
    })

    return () => { cancelled = true }
  }, [open])

  function updateForm(index: number, field: keyof ScraperForm, value: string) {
    setForms((prev) => prev.map((f, i) => i === index ? { ...f, [field]: value } : f))
  }

  async function removeForm(index: number) {
    const form = forms[index]
    if (form.scraper_id && !form.isNew) {
      try {
        const response = await fetch(`/conductor-api/scrapers/${form.scraper_id}`, { method: "DELETE" })
        if (!response.ok) throw new Error(`Delete failed (${response.status})`)
      } catch (e) {
        setStatusTitle("Error")
        setStatus(e instanceof Error ? e.message : "Failed to delete scraper")
        setStatusOpen(true)
        return
      }
    }
    setForms((prev) => prev.filter((_, i) => i !== index))
  }

  function addBlankForm() {
    setForms((prev) => [
      ...prev,
      {
        scraper_id: "",
        name: "",
        target_url: "",
        scraping_prompt: "",
        cron_schedule: "",
        repair_policy: "RETRY, REPAIR:haiku, STALL",
        category: "",
        run_timeout: "300",
        isNew: true,
      },
    ])
  }

  async function handleGuiSubmit() {
    try {
      setStatusTitle("Submitting")
      setStatus("Saving...")
      setStatusOpen(true)

      const newForms = forms.filter((f) => f.isNew)
      const existingForms = forms.filter((f) => !f.isNew)
      let createdCount = 0

      for (const form of newForms) {
        if (!form.target_url || !form.scraping_prompt) continue
        const policy = form.repair_policy.split(",").map((s) => s.trim()).filter(Boolean)
        await addNewScraper({
          name: form.name,
          target_url: form.target_url,
          scraping_prompt: form.scraping_prompt,
          cron_schedule: form.cron_schedule,
          repair_policy: policy.length > 0 ? policy : ["RETRY"],
          category: form.category,
          run_timeout: parseInt(form.run_timeout) || 300,
        })
        createdCount++
      }

      let updatedCount = 0
      if (existingForms.length > 0) {
        const result = await postScraperConfig(existingForms.map(formToUpdate))
        updatedCount = result.updated.length
      }

      setStatusTitle("Config Saved")
      const parts = []
      if (createdCount > 0) parts.push(`Created ${createdCount}`)
      if (updatedCount > 0) parts.push(`Updated ${updatedCount}`)
      setStatus(parts.length > 0 ? `${parts.join(", ")} scraper(s).` : "No changes.")

      // Reload to get assigned IDs for new scrapers
      const data = await fetchScraperData()
      const payload: ScraperConfigUpdate[] = data.map((row) => ({
        scraper_id: row.scraperId,
        name: row.name,
        target_url: row.targetUrl,
        scraping_prompt: row.scrapingPrompt,
        cron_schedule: row.cronSchedule,
        repair_policy: row.repairPolicy,
        category: row.category,
        run_timeout: row.runTimeout ?? 300,
      }))
      setForms(payload.map(scraperToForm))
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to submit config"
      setStatusTitle("Error")
      setStatus(message)
      setStatusOpen(true)
    }
  }

  async function handleJsonSubmit() {
    try {
      const parsed = JSON.parse(rawJson) as unknown
      if (!Array.isArray(parsed)) throw new Error("Config must be a JSON array")
      const normalised = JSON.stringify(parsed, null, 2)
      setRawJson(normalised)
      setStatusTitle("Submitting")
      setStatus("Saving...")
      setStatusOpen(true)
      const result = await postScraperConfig(normalised)
      setStatusTitle("Config Updated")
      setStatus(`Updated ${result.updated.length} scraper(s).`)
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to submit config"
      setStatusTitle("Error")
      setStatus(message)
      setStatusOpen(true)
    }
  }

  function syncToJson() {
    setRawJson(JSON.stringify(forms.filter((f) => !f.isNew).map(formToUpdate), null, 2))
  }

  function syncToGui() {
    try {
      const parsed = JSON.parse(rawJson) as ScraperConfigUpdate[]
      if (Array.isArray(parsed)) {
        setForms(parsed.map(scraperToForm))
      }
    } catch { /* ignore parse errors on switch */ }
  }

  return (
    <>
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent size="lg" className="flex max-h-[85vh] flex-col">
        <AlertDialogHeader>
          <div className="flex items-center justify-between">
            <div>
              <AlertDialogTitle>Scraper Configuration</AlertDialogTitle>
              <AlertDialogDescription>
                {mode === "gui" ? "Add, edit, or remove scraper feeds." : "Edit scraper configs as raw JSON."}
              </AlertDialogDescription>
            </div>
            <button
              onClick={() => {
                if (mode === "gui") { syncToJson(); setMode("json") }
                else { syncToGui(); setMode("gui") }
              }}
              className="flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground"
              title={mode === "gui" ? "Switch to JSON editor" : "Switch to GUI editor"}
            >
              {mode === "gui" ? <><Code className="h-3.5 w-3.5" /> JSON</> : <><LayoutList className="h-3.5 w-3.5" /> GUI</>}
            </button>
          </div>
        </AlertDialogHeader>

        {mode === "gui" ? (
          <div className="flex-1 overflow-y-auto">
            <Accordion>
              {forms.map((form, index) => (
                <AccordionItem key={form.scraper_id || `new-${index}`} value={form.scraper_id || `new-${index}`} className="rounded-lg border bg-muted/40 px-3 mb-2">
                  <AccordionTrigger>
                    <div className="flex items-center gap-2">
                      {form.isNew && <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">NEW</span>}
                      <span>{form.name || form.target_url || "New Scraper"}</span>
                      {form.scraper_id && <span className="text-xs text-muted-foreground">({form.scraper_id})</span>}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="flex flex-col gap-3 py-2">
                      <FormField label="Name" value={form.name} onChange={(v) => updateForm(index, "name", v)} placeholder="My Blog Scraper" />
                      <FormField label="Target URL" value={form.target_url} onChange={(v) => updateForm(index, "target_url", v)} placeholder="https://example.com" />
                      <FormField label="Scraping Prompt" value={form.scraping_prompt} onChange={(v) => updateForm(index, "scraping_prompt", v)} multiline placeholder="Extract blog post titles, URLs, and summaries..." />
                      <FormField label="Cron Schedule" value={form.cron_schedule} onChange={(v) => updateForm(index, "cron_schedule", v)} placeholder="*/30 * * * *" />
                      <FormField label="Category" value={form.category} onChange={(v) => updateForm(index, "category", v)} placeholder="e.g. blogs, news, tech" />
                      <FormField label="Repair Policy (comma-separated)" value={form.repair_policy} onChange={(v) => updateForm(index, "repair_policy", v)} placeholder="RETRY, REPAIR:haiku, STALL" />
                      <FormField label="Run Timeout (seconds)" value={form.run_timeout} onChange={(v) => updateForm(index, "run_timeout", v)} placeholder="300" />
                      <div className="flex items-center justify-between pt-1">
                        {form.scraper_id ? (
                          <button
                            onClick={() => setScriptEditorId(form.scraper_id)}
                            className="flex items-center gap-1.5 rounded-md border border-primary/50 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/20"
                          >
                            <FileCode className="h-3.5 w-3.5" /> SCRIPT
                          </button>
                        ) : <div />}
                        <button
                          onClick={() => removeForm(index)}
                          className="flex items-center gap-1 text-xs text-destructive hover:underline"
                        >
                          <Trash2 className="h-3 w-3" /> Remove
                        </button>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>

            {forms.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">No scrapers configured.</p>
            )}

            <button
              onClick={addBlankForm}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-md border border-dashed py-3 text-sm text-muted-foreground hover:border-foreground hover:text-foreground"
            >
              <Plus className="h-4 w-4" /> Add Scraper
            </button>
          </div>
        ) : (
          <Textarea
            className="min-h-[300px] flex-1 font-mono text-sm"
            value={rawJson}
            onChange={(e) => setRawJson(e.target.value)}
          />
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" className={buttonStyles} onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button className={buttonStyles} onClick={mode === "gui" ? handleGuiSubmit : handleJsonSubmit}>
            Save
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

    {scriptEditorId && (
      <ScriptEditor scraperId={scriptEditorId} onClose={() => setScriptEditorId(null)} />
    )}
    </>
  )
}
