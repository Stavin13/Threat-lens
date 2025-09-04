import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function RecentActivityPanel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        Placeholder: stream recent events. Later, combine /events with WebSocket new_event messages.
      </CardContent>
    </Card>
  )
}

export function SystemStatusPanel({
  fileMonitorStatus = "—",
  queueSize,
  eventsProcessed,
  wsStatus = "—",
}: {
  fileMonitorStatus?: string
  queueSize?: number
  eventsProcessed?: number
  wsStatus?: "connecting" | "open" | "closed" | "error" | string
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">System Status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-muted-foreground">File Monitor</dt>
            <dd className="font-medium">{fileMonitorStatus}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Queue Size</dt>
            <dd className="font-medium">{queueSize ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">WebSocket</dt>
            <dd className="font-medium capitalize">{String(wsStatus)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Events Processed</dt>
            <dd className="font-medium">{eventsProcessed ?? "—"}</dd>
          </div>
        </dl>
        <p className="text-xs text-muted-foreground">Live from /realtime/status and WebSocket.</p>
      </CardContent>
    </Card>
  )
}
