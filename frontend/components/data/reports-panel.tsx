"use client"

import { useReports } from "@/lib/api"
import { useState } from "react"

export default function ReportsPanelConnected() {
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const { data, error, isLoading, mutate } = useReports({ page, pageSize })

  async function trigger(kind: "daily" | "weekly" | "custom") {
    // Use a simple client call via fetch to avoid circular imports
    await fetch("/api/trigger-report", { method: "POST", body: JSON.stringify({ type: kind }) })
    mutate()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button className="h-9 rounded-md border px-3 text-sm" onClick={() => trigger("daily")}>
          Trigger Daily
        </button>
        <button className="h-9 rounded-md border px-3 text-sm" onClick={() => trigger("weekly")}>
          Trigger Weekly
        </button>
      </div>

      <div className="rounded-lg border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-3 py-2 font-medium">Generated</th>
              <th className="text-left px-3 py-2 font-medium">Filename</th>
              <th className="text-left px-3 py-2 font-medium">Size</th>
              <th className="text-left px-3 py-2 font-medium">Download</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-muted-foreground">
                  Loading…
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-destructive">
                  Failed to load reports
                </td>
              </tr>
            ) : data?.items.length ? (
              data.items.map((f) => (
                <tr key={f.id} className="border-t">
                  <td className="px-3 py-2">{new Date(f.generatedAt).toLocaleString()}</td>
                  <td className="px-3 py-2">{f.filename}</td>
                  <td className="px-3 py-2">{(f.sizeBytes / 1024).toFixed(1)} KB</td>
                  <td className="px-3 py-2">
                    {f.downloadUrl ? (
                      <a className="text-primary underline-offset-2 hover:underline" href={f.downloadUrl}>
                        Download
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-muted-foreground">
                  No report files
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
            onClick={() => setPage((p) => p + 1))}\
            disabled={!!data && data.page * data.pageSize >= data.total}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
