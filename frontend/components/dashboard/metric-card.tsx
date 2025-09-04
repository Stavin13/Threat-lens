import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

type Point = { x: string | number; y: number }

export function MetricCard({
  title,
  value,
  helpText,
  data,
  className,
}: {
  title: string
  value: string | number
  helpText?: string
  data?: Point[]
  className?: string
}) {
  return (
    <Card className={cn(className)}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-2xl font-semibold leading-none">{value}</div>
            {helpText ? <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{helpText}</p> : null}
          </div>
          <div className="h-14 w-32">
            {data && data.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                  <defs>
                    <linearGradient id="metricGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="oklch(var(--color-chart-1))" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="oklch(var(--color-chart-1))" stopOpacity={0.1} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="x" hide />
                  <YAxis hide />
                  <Tooltip
                    cursor={{ fill: "transparent" }}
                    formatter={(v) => [v as number, title]}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="y"
                    stroke="oklch(var(--color-chart-1))"
                    fill="url(#metricGradient)"
                    strokeWidth={2}
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full w-full rounded bg-muted" aria-hidden />
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
