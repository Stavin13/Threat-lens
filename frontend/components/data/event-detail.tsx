"use client"

import { useEvent } from "@/lib/api"

export default function EventDetailConnected({ id }: { id: string }) {
  const { data, error, isLoading } = useEvent(id)

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading event…</div>
  if (error) return <div className="text-sm text-destructive">Failed to load event</div>
  if (!data) return <div className="text-sm text-muted-foreground">Event not found</div>

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-background p-4">
        <div className="text-xs text-muted-foreground">Event ID</div>
        <div className="text-sm font-mono">{data.id}</div>
        <div className="mt-2 text-xs text-muted-foreground">Timestamp</div>
        <div className="text-sm">{new Date(data.timestamp).toLocaleString()}</div>
        <div className="mt-2 text-xs text-muted-foreground">Source</div>
        <div className="text-sm">{data.source}</div>
      </div>

      <div className="rounded-lg border bg-background p-4">
        <div className="text-sm font-semibold mb-1">Message</div>
        <pre className="whitespace-pre-wrap text-sm">{data.message}</pre>
      </div>

      <div className="rounded-lg border bg-background p-4">
        <div className="text-sm font-semibold mb-2">AI Analysis</div>
        {data.ai ? (
          <div className="space-y-2 text-sm">
            {data.ai.summary && <p>{data.ai.summary}</p>}
            {typeof data.ai.riskScore === "number" && (
              <div>
                <span className="text-xs text-muted-foreground">Risk Score</span>
                <div className="text-lg font-semibold">{data.ai.riskScore}</div>
              </div>
            )}
            {data.ai.recommendations?.length ? (
              <div>
                <div className="text-xs text-muted-foreground mb-1">Recommendations</div>
                <ul className="list-disc pl-5">
                  {data.ai.recommendations.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">No AI analysis for this event.</div>
        )}
      </div>
    </div>
  )
}
