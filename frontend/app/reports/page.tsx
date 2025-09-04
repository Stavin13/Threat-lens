"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageHeader } from "@/components/page-header"
import { ReportList } from "@/components/reports/report-list"
import { TriggerReportForm } from "@/components/reports/trigger-report"
import { useReports } from "@/lib/api"

export default function ReportsPage() {
  const { data, error, isLoading } = useReports()

  return (
    <>
      <PageHeader
        title="Reports"
        description="Daily reports and scheduler controls. Wired to /reports/files (list) and POST /scheduler/trigger-report."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Available Reports</CardTitle>
            </CardHeader>
            <CardContent>
              {error ? (
                <p className="text-sm text-destructive">Failed to load reports.</p>
              ) : (
                <ReportList files={data ?? []} />
              )}
              {isLoading ? <p className="mt-2 text-sm text-muted-foreground">Loading…</p> : null}
            </CardContent>
          </Card>
        </div>

        <div>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Manual Trigger</CardTitle>
            </CardHeader>
            <CardContent>
              <TriggerReportForm />
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
