"use client"

import { useState } from "react"
import { PageHeader } from "@/components/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { EventsFilters, type EventsFilters as Filters } from "@/components/events/events-filters"
import { EventsTable, type EventRow } from "@/components/events/events-table"
import { useEvents } from "@/lib/api"

export default function EventsPage() {
  const [appliedFilters, setAppliedFilters] = useState<Filters>({})
  const [sortBy, setSortBy] = useState<"timestamp" | "severity" | "source" | "category">("timestamp")
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")
  const [page, setPage] = useState(1)
  const perPage = 20

  const { data, isLoading, error } = useEvents({
    page,
    per_page: perPage,
    category: appliedFilters.category as any,
    min_severity: appliedFilters.minSeverity,
    max_severity: appliedFilters.maxSeverity,
    start_date: appliedFilters.startDate,
    end_date: appliedFilters.endDate,
    source: appliedFilters.source,
    sort_by: sortBy,
    sort_order: sortOrder,
  })

  const rows: EventRow[] =
    data?.events?.map((e) => ({
      id: e.id,
      timestamp: e.timestamp,
      source: e.source,
      message: e.message,
      category: e.category,
      severity_score: e.ai_analysis?.severity_score,
    })) ?? []

  return (
    <>
      <PageHeader
        title="Events"
        description="Browse, filter, and sort security events. Now wired to /events with backend pagination."
      />

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <EventsFilters
            onApply={(f) => {
              setAppliedFilters(f)
              setPage(1)
            }}
            onReset={() => {
              setAppliedFilters({})
              setPage(1)
            }}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between gap-4 md:flex-row">
          <CardTitle className="text-base">Events</CardTitle>
          <div className="flex items-center gap-2">
            <button
              className="text-sm text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => setSortBy("timestamp")}
            >
              Sort: Time
            </button>
            <span aria-hidden>·</span>
            <button
              className="text-sm text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => setSortBy("severity")}
            >
              Severity
            </button>
            <span aria-hidden>·</span>
            <button
              className="text-sm text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => setSortBy("source")}
            >
              Source
            </button>
            <span aria-hidden>·</span>
            <button
              className="text-sm text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => setSortBy("category")}
            >
              Category
            </button>
            <span aria-hidden>·</span>
            <button
              className="text-sm text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => setSortOrder((o) => (o === "asc" ? "desc" : "asc"))}
              aria-label="Toggle sort order"
              title="Toggle sort order"
            >
              {sortOrder === "asc" ? "Asc" : "Desc"}
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-destructive">Failed to load events.</p>
          ) : (
            <EventsTable
              rows={rows}
              total={data?.total ?? rows.length}
              perPage={perPage}
              currentPage={page}
              onPageChange={setPage}
              serverPaginated
            />
          )}
          {isLoading ? <p className="mt-2 text-sm text-muted-foreground">Loading…</p> : null}
        </CardContent>
      </Card>
    </>
  )
}
