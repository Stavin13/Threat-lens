import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { SeverityBadge } from "./event-meta"

export type AIAnalysis = {
  id: string
  event_id: string
  severity_score: number
  explanation: string
  recommendations: string[]
  analyzed_at: string
}

export function AIAnalysisPanel({ analysis }: { analysis: AIAnalysis }) {
  const pct = Math.min(100, Math.max(0, (analysis.severity_score / 10) * 100))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>AI Analysis</span>
          <SeverityBadge score={analysis.severity_score} />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="mb-2 text-xs text-muted-foreground">Severity</div>
          <div className="h-2 w-full rounded bg-muted">
            <div
              className="h-2 rounded bg-primary"
              style={{ width: `${pct}%` }}
              aria-label={`Severity ${analysis.severity_score} of 10`}
            />
          </div>
        </div>

        <div>
          <div className="mb-1 text-xs text-muted-foreground">Explanation</div>
          <p className="text-sm leading-relaxed">{analysis.explanation}</p>
        </div>

        <div>
          <div className="mb-1 text-xs text-muted-foreground">Recommendations</div>
          <ul className="list-inside list-disc text-sm leading-relaxed">
            {analysis.recommendations.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-muted-foreground">Analyzed at: {new Date(analysis.analyzed_at).toLocaleString()}</p>
      </CardContent>
    </Card>
  )
}
