"use client"

import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageHeader } from "@/components/page-header"
import { CategoryBadge, MetaItem, SeverityBadge } from "@/components/events/event-meta"
import { AIAnalysisPanel } from "@/components/events/ai-analysis-panel"
import { useApi } from "@/lib/api"

export default function EventDetailPage({ params }: { params: { id: string } }) {
  const id = params.id
  const { data: event, error, isLoading } = useApi(`/event/${id}`)

  if (isLoading) {
    return (
      <>
        <PageHeader title="Event Detail" description="Loading event details..." />
        <div className="text-center py-8">
          <p className="text-muted-foreground">Loading event...</p>
        </div>
      </>
    )
  }

  if (error || !event) {
    return (
      <>
        <PageHeader title="Event Detail" description="Event not found" />
        <div className="text-center py-8">
          <p className="text-destructive">Event not found or failed to load.</p>
          <Link
            href="/events"
            className="text-sm text-muted-foreground underline-offset-2 hover:underline mt-4 inline-block"
          >
            ← Back to Events
          </Link>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader title="Event Detail" description="Detailed event context with AI analysis and remediation steps." />

      <div className="mb-4">
        <Link
          href="/events"
          className="text-sm text-muted-foreground underline-offset-2 hover:underline"
          prefetch={false}
        >
          ← Back to Events
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Event</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
                <MetaItem label="Event ID" value={<code className="text-xs">{event.id}</code>} />
                <MetaItem label="Raw Log ID" value={<code className="text-xs">{event.raw_log_id}</code>} />
                <MetaItem
                  label="Timestamp"
                  value={<span className="whitespace-nowrap">{new Date(event.timestamp).toLocaleString()}</span>}
                />
                <MetaItem label="Source" value={<span className="whitespace-nowrap">{event.source}</span>} />
                <MetaItem label="Category" value={<CategoryBadge category={event.category as string} />} />
                <MetaItem
                  label="Parsed At"
                  value={<span className="whitespace-nowrap">{new Date(event.parsed_at).toLocaleString()}</span>}
                />
                <MetaItem label="Severity" value={<SeverityBadge score={event.ai_analysis?.severity_score} />} />
              </div>

              <div>
                <div className="mb-1 text-xs text-muted-foreground">Message</div>
                <pre className="max-w-full overflow-auto rounded bg-muted p-3 text-xs leading-relaxed">
                  {event.message}
                </pre>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Actions</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Placeholder: trigger processing for raw log (POST /trigger-processing/{event.raw_log_id}), copy event ID,
              etc.
            </CardContent>
          </Card>
        </div>

        <div>{event.ai_analysis ? <AIAnalysisPanel analysis={event.ai_analysis} /> : null}</div>
      </div>
    </>
  )
}
