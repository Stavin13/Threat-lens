import type React from "react"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

export function MetaItem({
  label,
  value,
  className,
}: {
  label: string
  value: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="text-sm">{value}</div>
    </div>
  )
}

export function CategoryBadge({ category }: { category: string }) {
  const variant =
    category === "security" || category === "auth"
      ? "default"
      : category === "network" || category === "system"
        ? "secondary"
        : "outline"
  return (
    <Badge variant={variant as any} className="capitalize">
      {category}
    </Badge>
  )
}

export function SeverityBadge({ score }: { score?: number }) {
  if (score === undefined || score === null) return null
  let variant: "default" | "secondary" | "outline" = "outline"
  if (score >= 9) variant = "default"
  else if (score >= 5) variant = "secondary"
  return <Badge variant={variant}>{score}</Badge>
}
