"use client"

import type React from "react"

import { api } from "@/lib/api"
import { useState } from "react"

export function FileUploadConnected() {
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState<string>("")
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    try {
      const res = await api.ingestFile(file)
      setMessage(`Accepted: ${res.accepted}`)
    } catch (e: any) {
      setMessage(e?.message || "Upload failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2 rounded-lg border bg-background p-4">
      <div className="text-sm font-semibold">Upload Log File</div>
      <input
        type="file"
        className="block w-full text-sm"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        aria-label="Choose log file"
      />
      <button className="h-9 rounded-md border px-3 text-sm disabled:opacity-50" disabled={!file || busy}>
        {busy ? "Uploading…" : "Upload"}
      </button>
      {message && <div className="text-xs text-muted-foreground">{message}</div>}
    </form>
  )
}

export function TextIngestConnected() {
  const [text, setText] = useState("")
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    setBusy(true)
    try {
      const res = await api.ingestText(text)
      setMessage(`Accepted: ${res.accepted}`)
      setText("")
    } catch (e: any) {
      setMessage(e?.message || "Ingest failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2 rounded-lg border bg-background p-4">
      <div className="text-sm font-semibold">Paste Raw Log Text</div>
      <textarea
        className="w-full min-h-28 rounded-md border bg-background p-2 text-sm"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste log lines here…"
        aria-label="Raw log text"
      />
      <button className="h-9 rounded-md border px-3 text-sm disabled:opacity-50" disabled={!text.trim() || busy}>
        {busy ? "Submitting…" : "Ingest Text"}
      </button>
      {message && <div className="text-xs text-muted-foreground">{message}</div>}
    </form>
  )
}
