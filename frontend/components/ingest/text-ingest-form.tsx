"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ingestText } from "@/lib/api"

export function TextIngestForm() {
  const [source, setSource] = useState("")
  const [content, setContent] = useState("")
  const [status, setStatus] = useState<"idle" | "success" | "error" | "submitting">("idle")
  const [message, setMessage] = useState<string | null>(null)

  const canSubmit = Boolean(source.trim() && content.trim())

  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault()
        try {
          setStatus("submitting")
          const res = await ingestText({ content, source })
          setMessage(`Submitted: ${res?.message ?? "OK"}`)
          setStatus("success")
        } catch (err: any) {
          setMessage(err?.message || "Submit failed")
          setStatus("error")
        }
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="txt-source">Source</Label>
        <Input
          id="txt-source"
          placeholder="e.g. console, server1"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="content">Log content</Label>
        <Textarea
          id="content"
          rows={8}
          placeholder="Paste log lines here..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          Text content will be sent to /ingest-log endpoint as form data.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <Button type="submit" disabled={!canSubmit || status === "submitting"}>
          {status === "submitting" ? "Sending…" : "Send"}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            setSource("")
            setContent("")
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
