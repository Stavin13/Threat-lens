"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export type EventsFilters = {
  category?: string
  minSeverity?: number
  maxSeverity?: number
  startDate?: string
  endDate?: string
  source?: string
}

export function EventsFilters({
  defaultValues,
  onApply,
  onReset,
}: {
  defaultValues?: EventsFilters
  onApply?: (filters: EventsFilters) => void
  onReset?: () => void
}) {
  const [filters, setFilters] = useState<EventsFilters>({
    category: defaultValues?.category ?? "all",
    minSeverity: defaultValues?.minSeverity ?? undefined,
    maxSeverity: defaultValues?.maxSeverity ?? undefined,
    startDate: defaultValues?.startDate ?? "",
    endDate: defaultValues?.endDate ?? "",
    source: defaultValues?.source ?? "",
  })

  return (
    <form
      className="grid grid-cols-1 gap-4 md:grid-cols-6"
      onSubmit={(e) => {
        e.preventDefault()
        onApply?.(filters)
      }}
    >
      <div className="space-y-2 md:col-span-2">
        <Label htmlFor="category">Category</Label>
        <Select value={filters.category} onValueChange={(v) => setFilters((f) => ({ ...f, category: v }))}>
          <SelectTrigger id="category" aria-label="Category">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="auth">Auth</SelectItem>
            <SelectItem value="system">System</SelectItem>
            <SelectItem value="network">Network</SelectItem>
            <SelectItem value="security">Security</SelectItem>
            <SelectItem value="application">Application</SelectItem>
            <SelectItem value="kernel">Kernel</SelectItem>
            <SelectItem value="unknown">Unknown</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="minSeverity">Min severity</Label>
        <Input
          id="minSeverity"
          inputMode="numeric"
          type="number"
          min={1}
          max={10}
          placeholder="1"
          value={filters.minSeverity ?? ""}
          onChange={(e) =>
            setFilters((f) => ({
              ...f,
              minSeverity: e.target.value ? Number(e.target.value) : undefined,
            }))
          }
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="maxSeverity">Max severity</Label>
        <Input
          id="maxSeverity"
          inputMode="numeric"
          type="number"
          min={1}
          max={10}
          placeholder="10"
          value={filters.maxSeverity ?? ""}
          onChange={(e) =>
            setFilters((f) => ({
              ...f,
              maxSeverity: e.target.value ? Number(e.target.value) : undefined,
            }))
          }
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="startDate">Start date</Label>
        <Input
          id="startDate"
          type="datetime-local"
          value={filters.startDate}
          onChange={(e) => setFilters((f) => ({ ...f, startDate: e.target.value }))}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="endDate">End date</Label>
        <Input
          id="endDate"
          type="datetime-local"
          value={filters.endDate}
          onChange={(e) => setFilters((f) => ({ ...f, endDate: e.target.value }))}
        />
      </div>

      <div className="space-y-2 md:col-span-2">
        <Label htmlFor="source">Source</Label>
        <Input
          id="source"
          placeholder="sshd, kernel, app..."
          value={filters.source}
          onChange={(e) => setFilters((f) => ({ ...f, source: e.target.value }))}
        />
      </div>

      <div className="flex items-end gap-2 md:col-span-4">
        <Button type="submit">Apply</Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            setFilters({
              category: "all",
              minSeverity: undefined,
              maxSeverity: undefined,
              startDate: "",
              endDate: "",
              source: "",
            })
            onReset?.()
          }}
        >
          Reset
        </Button>
      </div>
    </form>
  )
}
