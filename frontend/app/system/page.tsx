import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageHeader } from "@/components/page-header"

export default function SystemPage() {
  return (
    <>
      <PageHeader title="System" description="Health, real-time status, monitoring config, and metrics." />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Health</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Use /health and /health-simple for overall status.
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Realtime Status</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Use /realtime/status and /ws/info to populate components.
          </CardContent>
        </Card>
      </div>
    </>
  )
}
