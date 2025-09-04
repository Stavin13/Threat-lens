import { cn } from "@/lib/utils"

export function PageHeader({
  title,
  description,
  className,
}: {
  title: string
  description?: string
  className?: string
}) {
  return (
    <div className={cn("mb-6", className)}>
      <h1 className="text-pretty text-2xl font-semibold leading-tight tracking-tight md:text-3xl">{title}</h1>
      {description ? (
        <p className="mt-2 max-w-prose text-sm text-muted-foreground leading-relaxed">{description}</p>
      ) : null}
    </div>
  )
}
