"use client"

import { useState } from "react"
import { useEvents, type EventItem } from "@/lib/api"
import { cn } from "@/lib/utils"

export default function EventsListConnected() {
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [category, setCategory] = useState<string>("")
  const [source, setSource] = useState<string>("")
  const [severityMin, setSeverityMin] = useState<number | undefined>()
  const [severityMax, setSeverityMax] = useState<number | undefined>()
  const { data, error, isLoading } = useEvents({
    page,
    pageSize,
    category: category || undefined,
    source: source || undefined,
    severityMin,
    severityMax,
    sort: "-timestamp",
  })

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <input
          className="h-9 rounded-md border bg-background px-3 text-sm"
          placeholder="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          aria-label="Filter by category"
        />
        <input
          className="h-9 rounded-md border bg-background px-3 text-sm"
          placeholder="Source"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          aria-label="Filter by source"
        />
        <input
          className="h-9 rounded-md border bg-background px-3 text-sm"
          placeholder="Severity min"
          type="number"
          value={severityMin ?? ""}
          onChange={(e) => setSeverityMin(e.target.value ? Number(e.target.value) : undefined)}
          aria-label="Severity min"
        />
        <input
          className="h-9 rounded-md border bg-background px-3 text-sm"
          placeholder="Severity max"
          type="number"
          value={severityMax ?? ""}
          onChange={(e) => setSeverityMax(e.target.value ? Number(e.target.value) : undefined)}
          aria-label="Severity max"
        />
      </div>

      <div className="rounded-lg border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-3 py-2 font-medium">Time</th>
              <th className="text-left px-3 py-2 font-medium">Source</th>
              <th className="text-left px-3 py-2 font-medium">Category</th>
              <th className="text-left px-3 py-2 font-medium">Severity</th>
              <th className="text-left px-3 py-2 font-medium">Message</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                  Loading…
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-destructive">
                  Failed to load events
                </td>
              </tr>
            ) : data?.items.length ? (
              data.items.map((ev: EventItem) => (
                <tr key={ev.id} className="border-t">
                  <td className="px-3 py-2">{new Date(ev.timestamp).toLocaleString()}</td>
                  <td className="px-3 py-2">{ev.source}</td>
                  <td className="px-3 py-2">{ev.category ?? "—"}</td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        "inline-flex items-center rounded px-2 py-0.5 text-xs",
                        (ev.severity ?? 0) >= 8
                          ? "bg-red-100 text-red-700"
                          : (ev.severity ?? 0) >= 5
                            ? "bg-amber-100 text-amber-700"
                            : "bg-emerald-100 text-emerald-700",
                      )}
                    >
                      {ev.severity ?? "—"}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <a className="text-primary underline-offset-2 hover:underline" href={`/events/${ev.id}`}>
                      {ev.message.slice(0, 80)}
                      {ev.message.length > 80 ? "…" : ""}
                    </a>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                  No events
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Page {data?.page ?? page} of {data ? Math.ceil(data.total / data.pageSize) : "—"}
        </div>
        <div className="flex items-center gap-2">
          <button
            className="h-9 rounded-md border px-3 text-sm disabled:opacity-50"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            Previous
          </button>
          <button
            className="h-9 rounded-md border px-3 text-sm disabled:opacity-50"
            onClick={() => setPage((p) => p + 1)}
            disabled={!!data && data.page * data.pageSize >= data.total}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
