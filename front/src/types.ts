export interface Participant {
  id: string
  name: string
  email: string
}

export interface User {
  id: string
  email: string
  name: string | null
}

export interface AgendaItem {
  title: string
  duration_minutes?: number | null
  description?: string | null
}

export interface ActionItem {
  task: string
  assignee?: string | null
  due_date?: string | null
}

export interface ParsedAgenda {
  title: string
  starts_at?: string | null
  duration_minutes?: number | null
  items: AgendaItem[]
  action_items: ActionItem[]
  language: string
}

export interface AiSuggestion {
  agenda?: ParsedAgenda | null
  model: string
  prompt_version: string
  raw_text?: string
}

export interface SaveAgendaRequest {
  agenda?: ParsedAgenda | Record<string, unknown> | null
  ai_suggestion?: AiSuggestion | Record<string, unknown> | null
}

export interface Meeting {
  id: string
  title: string
  description: string | null
  call_link: string | null
  place: string | null
  starts_at: string
  ends_at: string
  owner_id: string | null
  participants: Participant[]
  created_at: string
  agenda?: ParsedAgenda | null
  ai_suggestion?: AiSuggestion | null
}

export interface MeetingCreate {
  title: string
  description: string | null
  call_link: string | null
  place: string | null
  starts_at: string
  ends_at: string
  participant_ids: string[]
  agenda?: ParsedAgenda | Record<string, unknown> | null
  ai_suggestion?: AiSuggestion | Record<string, unknown> | null
}

export interface ParticipantCreate {
  name: string
  email: string
}

/** One entry of FastAPI's 422 `detail` list. */
export interface ValidationIssue {
  loc: (string | number)[]
  msg: string
  type: string
}
