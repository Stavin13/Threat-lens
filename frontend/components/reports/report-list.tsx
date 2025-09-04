"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export type ReportFile = {
  filename: string
  date: string
  size_bytes: number
  events_count: number
  threats_count: number
  created_at: string
}

export function ReportList({ files }: { files: ReportFile[] }) {
  const [page, setPage] = useState(1)
  const perPage = 10
  const totalPages = Math.max(1, Math.ceil(files.length / perPage))
  const start = (page - 1) * perPage
  const current = files.slice(start, start + perPage)

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="min-w-[220px]">File</TableHead>
              <TableHead className="min-w-[120px]">Date</TableHead>
              <TableHead className="min-w-[100px]">Size</TableHead>
              <TableHead className="min-w-[100px]">Events</TableHead>
              <TableHead className="min-w-[100px]">Threats</TableHead>
              <TableHead className="min-w-[160px]">Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {current.map((f) => (
              <TableRow key={f.filename}>
                <TableCell className="font-mono text-xs">{f.filename}</TableCell>
                <TableCell>{f.date}</TableCell>
                <TableCell>{formatSize(f.size_bytes)}</TableCell>
                <TableCell>{f.events_count}</TableCell>
                <TableCell>{f.threats_count}</TableCell>
                <TableCell>{new Date(f.created_at).toLocaleString()}</TableCell>
                <TableCell className="text-right">
                  <Button asChild size="sm" variant="outline">
                    <a href="#" aria-label={`Download ${f.filename}`} download>
                      Download
                    </a>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {current.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                  No reports available.
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
          <Button size="sm" variant="outline" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
            Previous
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
