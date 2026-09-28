import type { Meeting } from "@/types"

export type CalendarView = "week" | "day"

export const MINUTES_PER_DAY = 24 * 60

export function startOfDay(date: Date): Date {
  const day = new Date(date)
  day.setHours(0, 0, 0, 0)
  return day
}

export function addDays(date: Date, days: number): Date {
  const result = new Date(date)
  result.setDate(result.getDate() + days)
  return result
}

/** Weeks start on Monday. */
export function startOfWeek(date: Date): Date {
  const day = startOfDay(date)
  return addDays(day, -((day.getDay() + 6) % 7))
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

export function visibleDays(view: CalendarView, anchor: Date): Date[] {
  if (view === "day") return [startOfDay(anchor)]
  const monday = startOfWeek(anchor)
  return Array.from({ length: 7 }, (_, i) => addDays(monday, i))
}

export function shiftAnchor(view: CalendarView, anchor: Date, direction: 1 | -1): Date {
  return addDays(anchor, direction * (view === "week" ? 7 : 1))
}

export function minutesSinceMidnight(date: Date): number {
  return date.getHours() * 60 + date.getMinutes()
}

export interface DaySegment {
  meeting: Meeting
  /** Minutes from midnight, clipped to the day. */
  startMin: number
  endMin: number
  /** Side-by-side slot among overlapping meetings. */
  column: number
  columns: number
}

/** The part of each meeting that falls on `day`, with overlapping meetings placed side by side. */
export function layoutDay(meetings: Meeting[], day: Date): DaySegment[] {
  const dayStart = startOfDay(day).getTime()
  const dayEnd = addDays(startOfDay(day), 1).getTime()
  const segments = meetings
    .flatMap((meeting) => {
      const start = new Date(meeting.starts_at).getTime()
      const end = new Date(meeting.ends_at).getTime()
      if (end <= dayStart || start >= dayEnd) return []
      return [
        {
          meeting,
          startMin: Math.max(0, (start - dayStart) / 60_000),
          endMin: Math.min(MINUTES_PER_DAY, (end - dayStart) / 60_000),
          column: 0,
          columns: 1,
        },
      ]
    })
    .sort((a, b) => a.startMin - b.startMin || b.endMin - a.endMin)

  // Meetings that overlap, directly or through each other, share one cluster and split its width.
  let cluster: DaySegment[] = []
  let columnEnds: number[] = []
  let clusterEnd = -1
  const closeCluster = () => {
    for (const segment of cluster) segment.columns = columnEnds.length
    cluster = []
    columnEnds = []
  }
  for (const segment of segments) {
    if (segment.startMin >= clusterEnd) closeCluster()
    let column = columnEnds.findIndex((end) => end <= segment.startMin)
    if (column === -1) column = columnEnds.length
    columnEnds[column] = segment.endMin
    segment.column = column
    cluster.push(segment)
    clusterEnd = Math.max(clusterEnd, segment.endMin)
  }
  closeCluster()
  return segments
}

const LOCALE = "en-GB"
const timeFormat = new Intl.DateTimeFormat(LOCALE, { hour: "2-digit", minute: "2-digit" })
const longDayFormat = new Intl.DateTimeFormat(LOCALE, {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
})
const shortDayFormat = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short" })
const weekdayFormat = new Intl.DateTimeFormat(LOCALE, { weekday: "short" })

export const formatTime = (date: Date | string) => timeFormat.format(new Date(date))
export const formatLongDay = (date: Date) => longDayFormat.format(date)
export const formatWeekday = (date: Date) => weekdayFormat.format(date)

export function formatHour(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`
}

/** Toolbar title: "Monday 28 September 2026" or "28 Sept – 4 Oct 2026". */
export function formatPeriod(view: CalendarView, anchor: Date): string {
  if (view === "day") return formatLongDay(anchor)
  const [first, last] = [startOfWeek(anchor), addDays(startOfWeek(anchor), 6)]
  return `${shortDayFormat.format(first)} – ${shortDayFormat.format(last)} ${last.getFullYear()}`
}

/** Values for <input type="date"> and <input type="time">, in local time. */
export function toDateInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function toTimeInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}
