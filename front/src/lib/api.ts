import { getIdToken, signOut } from "@/lib/auth"
import type {
  Meeting,
  MeetingCreate,
  ParsedAgenda,
  Participant,
  ParticipantCreate,
  SaveAgendaRequest,
  User,
  ValidationIssue,
} from "@/types"

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.detail = detail
  }

  get issues(): ValidationIssue[] {
    return Array.isArray(this.detail) ? (this.detail as ValidationIssue[]) : []
  }
}

function messageFrom(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) return detail.map((issue: ValidationIssue) => issue.msg).join("; ")
  return `Request failed (${status})`
}

// Backend origin, set at build time (the Lambda function URL on AWS). Empty = same origin,
// where nginx (Docker Compose) or the Vite dev server proxies /api to the backend.
const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "")
const PARSER_URL = (import.meta.env.VITE_AGENDA_PARSER_URL ?? "").replace(/\/+$/, "")

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getIdToken()
  const response = await fetch(`${API_URL}/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  // Session gone or rejected: back to the sign-in page.
  if (response.status === 401) {
    signOut()
    if (window.location.pathname !== "/" && window.location.pathname !== "/login/") {
      window.location.assign("/")
    }
  }

  if (!response.ok) {
    let detail: unknown = response.statusText
    try {
      detail = (await response.json()).detail
    } catch {
      // Non-JSON error body: keep the status text.
    }
    throw new ApiError(messageFrom(detail, response.status), response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  getMe: () => request<User>("/me"),

  listMeetings: () => request<Meeting[]>("/meetings"),
  createMeeting: (data: MeetingCreate) =>
    request<Meeting>("/meetings", { method: "POST", body: JSON.stringify(data) }),
  updateMeeting: ({ id, data }: { id: string; data: MeetingCreate }) =>
    request<Meeting>(`/meetings/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteMeeting: (id: string) => request<void>(`/meetings/${id}`, { method: "DELETE" }),

  saveAgenda: ({ id, data }: { id: string; data: SaveAgendaRequest }) =>
    request<Meeting>(`/meetings/${id}/agenda`, { method: "POST", body: JSON.stringify(data) }),

  parseAgenda: async (
    text: string,
    options?: { signal?: AbortSignal },
  ): Promise<{ agenda: ParsedAgenda; model: string; prompt_version: string }> => {
    const token = await getIdToken()
    // Prefer direct Lambda Function URL if configured; otherwise use backend endpoint
    const endpoint = PARSER_URL || `${API_URL}/api/meetings/parse-agenda`
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        text,
        tz: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Kyiv",
      }),
      signal: options?.signal,
    })

    if (!response.ok) {
      let detail = response.statusText
      try {
        const textResp = await response.text()
        try {
          const data = JSON.parse(textResp)
          detail = data.error || data.detail || detail
        } catch {
          if (textResp) detail = textResp
        }
      } catch {
        // non-text error
      }
      throw new Error(detail || `Parsing failed (${response.status})`)
    }

    const raw = await response.text()
    try {
      return JSON.parse(raw)
    } catch {
      throw new Error(`Invalid response from parser: ${raw.slice(0, 200)}`)
    }
  },

  listParticipants: (q = "") =>
    request<Participant[]>(`/participants${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  createParticipant: (data: ParticipantCreate) =>
    request<Participant>("/participants", { method: "POST", body: JSON.stringify(data) }),
}
