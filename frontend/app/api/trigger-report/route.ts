import { type NextRequest, NextResponse } from "next/server"

export async function POST(req: NextRequest) {
  const body = await req.text()
  const apiBase = process.env.NEXT_PUBLIC_THREATLENS_API_BASE || "http://localhost:8000"
  const res = await fetch(`${apiBase}/scheduler/trigger-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body,
  })
  const data = await res.json().catch(() => ({}))
  return NextResponse.json(data, { status: res.status })
}
