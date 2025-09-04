"use client"

import { useMemo } from "react"
import { useStats, useStatus } from "@/lib/api"
import { useThreatlensWS } from "@/lib/realtime"

export default function DashboardLivePanels() {
  const { data: stats, error: statsError, isLoading: statsLoading } = useStats()
  const { data: statusData } = useStatus()
  const { isConnected, lastMessage } = useThreatlensWS()

  const liveTotals = useMemo(() => {
    if (lastMessage?.type === "metrics" && lastMessage.data?.totals) {
      return lastMessage.data.totals
    }
    return null
  }, [lastMessage])

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="rounded-lg border bg-background p-4">
        <div className="text-sm text-muted-foreground">WebSocket</div>
        <div className="mt-2 text-2xl font-semibold">{isConnected ? "Connected" : "Disconnected"}</div>
        <div className="mt-1 text-xs text-muted-foreground">
          {statusData ? `${statusData.ws.clients} clients` : "—"}
        </div>
      </div>

      <div className="rounded-lg border bg-background p-4">
        <div className="text-sm text-muted-foreground">Total Events</div>
        <div className="mt-2 text-2xl font-semibold">
          {statsLoading ? "…" : (liveTotals?.events ?? stats?.totals.events ?? "—")}
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          Last updated: {stats?.lastUpdated ? new Date(stats.lastUpdated).toLocaleString() : "—"}
        </div>
      </div>

      <div className="rounded-lg border bg-background p-4">
        <div className="text-sm text-muted-foreground">Sources</div>
        <div className="mt-2 text-2xl font-semibold">
          {statsLoading ? "…" : (liveTotals?.sources ?? stats?.totals.sources ?? "—")}
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          Queue depth: {statusData?.processing.queueDepth ?? "—"}
        </div>
      </div>

      {statsError ? (
        <div className="md:col-span-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm">
          Failed to load stats
        </div>
      ) : null}
    </div>
  )
}
