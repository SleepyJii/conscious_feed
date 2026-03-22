import { useState } from "react"
import { Settings } from "lucide-react"
import { Button } from "./components/ui/button"
import { buttonStyles } from "./lib/global-styles"
import { MonitoringCharts } from "./components/monitoring-charts"
import { ScraperTable } from "./components/scraper-table"
import { ConfigModal } from "./components/config-modal"
import { Feed } from "./components/feed"

type Tab = "feed" | "fleet"

const tabs: Array<{ key: Tab; label: string }> = [
  { key: "feed", label: "Feed" },
  { key: "fleet", label: "FleetControl" },
]

export function App() {
  const [activeTab, setActiveTab] = useState<Tab>("feed")
  const [configOpen, setConfigOpen] = useState(false)

  return (
    <div className="flex h-screen flex-col">
      <div className="border-b">
        <div className="flex items-center justify-between px-4 pt-4">
          <h1 className="font-medium">Conscious Feed</h1>
          <Button variant="outline" className={buttonStyles} onClick={() => setConfigOpen(true)}>
            <Settings className="mr-2 h-4 w-4" />
            Configure
          </Button>
        </div>
        <div className="flex gap-0 px-4 pt-3">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`border-b-2 px-4 pb-2 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "border-foreground text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === "feed" && <Feed />}
        {activeTab === "fleet" && (
          <div className="mx-auto max-w-6xl space-y-8">
            <MonitoringCharts />
            <ScraperTable />
          </div>
        )}
      </div>

      <ConfigModal open={configOpen} onOpenChange={setConfigOpen} />
    </div>
  )
}

export default App
