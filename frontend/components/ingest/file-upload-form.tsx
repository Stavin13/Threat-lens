"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ingestFile } from "@/lib/api"

export function FileUploadForm() {
  const [source, setSource] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<"idle" | "success" | "error" | "submitting">("idle")
  const [message, setMessage] = useState<string | null>(null)

  const canSubmit = Boolean(source.trim() && file)

  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault()
        if (!file) return
        try {
          setStatus("submitting")
          const res = await ingestFile(file, source)
          setMessage(`Ingested: ${res?.message ?? "OK"}`)
          setStatus("success")
        } catch (err: any) {
          setMessage(err?.message || "Upload failed")
          setStatus("error")
        }
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="source">Source</Label>
        <Input
          id="source"
          placeholder="e.g. server1, console"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="logfile">Log file</Label>
        <Input
          id="logfile"
          type="file"
          accept=".log,text/plain"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <p className="text-xs text-muted-foreground">
            Selected: {file.name} ({Math.ceil(file.size / 1024)} KB)
          </p>
        ) : null}
      </div>

      <div className="flex items-center gap-2">
        <Button type="submit" disabled={!canSubmit || status === "submitting"}>
          {status === "submitting" ? "Uploading…" : "Upload"}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            setSource("")
            setFile(null)
            setStatus("idle")
            setMessage(null)
          }}
        >
          Reset
        </Button>
      </div>

      {message ? (
        <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
          {message}
        </p>
      ) : null}
    </form>
  )
}
