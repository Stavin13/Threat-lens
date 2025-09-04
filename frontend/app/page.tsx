"use client"

import { PageHeader } from "@/components/page-header"
import { MetricCard } from "@/components/dashboard/metric-card"
import { RecentActivityPanel, SystemStatusPanel } from "@/components/dashboard/system-panels"
import { useHighSeverityCount, useRealtimeMetrics, useRealtimeStatus, useStats } from "@/lib/api"
import { useThreatLensWS } from "@/lib/realtime"

const trend = Array.from({ length: 10 }, (_, i) => ({ x: i + 1, y: Math.round(Math.random() * 100) }))

export default function Page() {
  const { data: stats } = useStats()
  const { data: metrics } = useRealtimeMetrics()
  const { data: status } = useRealtimeStatus()
  const { data: sev } = useHighSeverityCount(7)
  const ws = useThreatLensWS()

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Real-time overview of system health, recent activity, and processing metrics."
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Events (total)"
          value={stats?.database?.total_events ?? "—"}
          data={trend}
          helpText="From /stats"
        />
        <MetricCard
          title="High Severity (≥7)"
          value={sev?.total ?? "—"}
          data={trend}
          helpText="From /events?min_severity=7"
        />
        <MetricCard
          title="Queue Depth"
          value={metrics?.queue_depth ?? "—"}
          data={trend}
          helpText="From /realtime/monitoring/metrics"
        />
        <MetricCard
          title="Events / Min"
          value={metrics?.events_per_minute?.toFixed?.(1) ?? "—"}
          data={trend}
          helpText="From /realtime/monitoring/metrics"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RecentActivityPanel />
        <SystemStatusPanel
          fileMonitorStatus={status?.components?.file_monitor?.status}
          queueSize={status?.components?.ingestion_queue?.queue_size}
          eventsProcessed={status?.components?.file_monitor?.events_processed}
          wsStatus={ws.status}
        />
      </div>
    </>
  )
}
