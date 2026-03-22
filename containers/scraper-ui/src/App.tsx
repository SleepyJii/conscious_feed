import { useEffect, useState } from "react"
import { Rss, BarChart3, Info, Settings, PanelLeftClose, PanelLeftOpen } from "lucide-react"
import Markdown from "react-markdown"
import {
  AlertDialog,
  AlertDialogContent,
} from "./components/ui/alert-dialog"
import { MonitoringCharts } from "./components/monitoring-charts"
import { ScraperTable } from "./components/scraper-table"
import { ConfigModal } from "./components/config-modal"
import { Feed } from "./components/feed"

type Tab = "feed" | "fleet"

const tabs: Array<{ key: Tab; label: string; icon: typeof Rss }> = [
  { key: "feed", label: "Feed", icon: Rss },
  { key: "fleet", label: "FleetControl", icon: BarChart3 },
]

function AboutModal({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [md, setMd] = useState("")

  useEffect(() => {
    if (!open) return
    fetch("/ABOUT.md")
      .then((r) => r.text())
      .then(setMd)
      .catch(() => setMd("Failed to load ABOUT.md"))
  }, [open])

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent size="lg" className="flex max-h-[85vh] flex-col overflow-y-auto">
        <article className="prose prose-sm prose-invert max-w-none prose-headings:font-medium prose-h1:text-xl prose-h2:text-lg prose-h3:text-base prose-p:text-muted-foreground prose-li:text-muted-foreground prose-td:text-muted-foreground prose-th:text-muted-foreground prose-strong:text-foreground prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:text-xs prose-code:before:content-none prose-code:after:content-none">
          <Markdown>{md}</Markdown>
        </article>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function App() {
  const [activeTab, setActiveTab] = useState<Tab>("feed")
  const [configOpen, setConfigOpen] = useState(false)
  const [aboutOpen, setAboutOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="flex h-screen">
      {sidebarOpen ? (
        <nav className="flex w-56 flex-col border-r bg-muted/30 transition-all">
          <div className="flex items-center justify-between px-3 pt-3">
            <div />
            <button
              onClick={() => setSidebarOpen(false)}
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              title="Collapse sidebar"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>

          <div className="flex flex-col items-center px-4 py-3">
            <img src="/icon.png" alt="Conscious Feed" className="h-28 w-28 rounded-lg" />
          </div>

          <div className="flex flex-1 flex-col gap-1 px-2">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
                    activeTab === tab.key
                      ? "bg-muted font-medium text-foreground"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              )
            })}
            <button
              onClick={() => setConfigOpen(true)}
              className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
            >
              <Settings className="h-4 w-4" />
              Configure
            </button>
            <button
              onClick={() => setAboutOpen(true)}
              className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
            >
              <Info className="h-4 w-4" />
              About
            </button>
          </div>
        </nav>
      ) : (
        <div className="flex flex-col border-r bg-muted/30 px-1.5 pt-3">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            title="Expand sidebar"
          >
            <PanelLeftOpen className="h-4 w-4" />
          </button>
        </div>
      )}

      <main className="flex-1 overflow-y-auto p-6">
        {activeTab === "feed" && <Feed />}
        {activeTab === "fleet" && (
          <div className="mx-auto flex min-h-full max-w-6xl flex-col gap-8">
            <MonitoringCharts />
            <div className="flex-1">
              <ScraperTable />
            </div>
          </div>
        )}
      </main>

      <ConfigModal open={configOpen} onOpenChange={setConfigOpen} />
      <AboutModal open={aboutOpen} onOpenChange={setAboutOpen} />
    </div>
  )
}

export default App
