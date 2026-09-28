import type { ReactElement } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render } from "@testing-library/react"
import { vi } from "vitest"

import type { Meeting } from "@/types"

export function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

type Handler = (url: string, init?: RequestInit) => { status?: number; body?: unknown }

/** Replaces global fetch; returns the mock so tests can inspect calls. */
export function mockFetch(handler: Handler) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const { status = 200, body } = handler(String(input), init)
    return new Response(status === 204 ? null : JSON.stringify(body ?? null), {
      status,
      headers: { "Content-Type": "application/json" },
    })
  })
}

/** Today at the given local hour, so the sample shows up in the current week and day. */
export function todayAt(hour: number): Date {
  const date = new Date()
  date.setHours(hour, 0, 0, 0)
  return date
}

export const sampleMeeting: Meeting = {
  id: "9a8b7c6d-1e2f-4a3b-9c4d-5e6f7a8b9c03",
  title: "Sprint planning",
  description: "Plan sprint 12 scope",
  call_link: "https://meet.google.com/abc-defg-hij",
  place: "Room 204",
  starts_at: todayAt(10).toISOString(),
  ends_at: todayAt(11).toISOString(),
  created_at: "2026-09-21T10:00:00Z",
  participants: [
    { id: "3f1c2a9e-8b4d-4c1e-9a7f-2d5b6e8c1a01", name: "Anna", email: "anna@example.com" },
    { id: "b7e4d2c1-5a6f-4e3b-8c9d-1f2a3b4c5d02", name: "Oleh", email: "oleh@example.com" },
  ],
}
