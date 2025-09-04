"use client"

import Link from "next/link"
import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export type EventRow = {
  id: string
  timestamp: string
  source: string
  message: string
  category: "auth" | "system" | "network" | "security" | "application" | "kernel" | "unknown"
  severity_score?: number
}

export function EventsTable({
  rows,
  total = rows.length,
  initialPage = 1,
  perPage = 20,
  currentPage,
  onPageChange,
  serverPaginated = false,
}: {
  rows: EventRow[]
  total?: number
  initialPage?: number
  perPage?: number
  currentPage?: number
  onPageChange?: (page: number) => void
  serverPaginated?: boolean
}) {
  const [internalPage, setInternalPage] = useState(initialPage)
  const page = currentPage ?? internalPage
  const totalPages = Math.max(1, Math.ceil(total / perPage))

  const startIdx = (page - 1) * perPage
  const currentRows = serverPaginated ? rows : rows.slice(startIdx, startIdx + perPage)

  const categoryVariant = (c: EventRow["category"]) => {
    switch (c) {
      case "security":
      case "auth":
        return "default" as const
      case "network":
      case "system":
        return "secondary" as const
      default:
        return "outline" as const
    }
  }

  const severityBadge = (s?: number) => {
    if (!s && s !== 0) return null
    const label = `${s}`
    let variant: "default" | "secondary" | "outline" = "outline"
    if (s >= 9) variant = "default"
    else if (s >= 5) variant = "secondary"
    return <Badge variant={variant}>{label}</Badge>
  }

  const go = (next: number) => {
    if (onPageChange) onPageChange(next)
    else setInternalPage(next)
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="min-w-[160px]">Time</TableHead>
              <TableHead className="min-w-[120px]">Source</TableHead>
              <TableHead>Message</TableHead>
              <TableHead className="min-w-[120px]">Category</TableHead>
              <TableHead className="min-w-[100px] text-right">Severity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {currentRows.map((ev) => (
              <TableRow key={ev.id}>
                <TableCell className="whitespace-nowrap text-sm">{new Date(ev.timestamp).toLocaleString()}</TableCell>
                <TableCell className="whitespace-nowrap text-sm">{ev.source}</TableCell>
                <TableCell className="text-pretty">
                  <Link href={`/events/${ev.id}`} className="underline-offset-2 hover:underline" prefetch={false}>
                    {ev.message}
                  </Link>
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  <Badge variant={categoryVariant(ev.category)} className="capitalize">
                    {ev.category}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">{severityBadge(ev.severity_score)}</TableCell>
              </TableRow>
            ))}
            {currentRows.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                  No events found. Try adjusting filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => go(Math.max(1, (page ?? 1) - 1))} disabled={page <= 1}>
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => go(Math.min(totalPages, (page ?? 1) + 1))}
            disabled={page >= totalPages}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
