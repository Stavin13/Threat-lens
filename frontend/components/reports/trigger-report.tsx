"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { triggerReport } from "@/lib/api"
import { useSWRConfig } from "swr"

export function TriggerReportForm() {
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<{ success: boolean; filename?: string; when?: string } | null>(null)
  const { mutate } = useSWRConfig()

  return (
    <form
      className="space-y-3"
      onSubmit={async (e) => {
        e.preventDefault()
        setSubmitting(true)
        try {
          const res = await triggerReport()
          setResult({
            success: res.success,
            filename: res.report_file,
            when: res.generated_at,
          })
          // refresh reports list
          mutate("/reports/files")
        } finally {
          setSubmitting(false)
        }
      }}
    >
      <div className="text-sm text-muted-foreground">
        Manually trigger today’s report. The backend endpoint is POST /scheduler/trigger-report.
      </div>
      <Button type="submit" disabled={submitting}>
        {submitting ? "Triggering…" : "Trigger Daily Report"}
      </Button>
      {result?.success && (
        <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
          Triggered report {result.filename} at {new Date(result.when!).toLocaleString()}.
        </p>
      )}
    </form>
  )
}
