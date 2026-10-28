import { useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { Loader2, Sparkles, X } from "lucide-react"
import { toast } from "sonner"
import { z } from "zod"

import { ParticipantsMultiSelect } from "@/components/ParticipantsMultiSelect"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { useCreateMeeting, useUpdateMeeting } from "@/hooks/useMeetings"
import { api, ApiError } from "@/lib/api"
import { toDateInput, toTimeInput } from "@/lib/calendar"
import type { AiSuggestion, Meeting, MeetingCreate, ParsedAgenda } from "@/types"

const meetingSchema = z
  .object({
    title: z.string().trim().min(1, "Title is required").max(200, "Max 200 characters"),
    description: z.string().max(5000, "Max 5000 characters"),
    call_link: z.union([
      z.literal(""),
      z.url({ protocol: /^https?$/, message: "Enter a valid http(s) URL" }),
    ]),
    place: z.string().trim().max(255, "Max 255 characters"),
    date: z.string().min(1, "Date is required"),
    start_time: z.string().min(1, "Start time is required"),
    end_time: z.string().min(1, "End time is required"),
    participants: z.array(z.object({ id: z.string(), name: z.string(), email: z.string() })),
  })
  .refine((values) => values.call_link !== "" || values.place !== "", {
    message: "Provide a call link, a place, or both",
    path: ["place"],
  })
  .refine(
    (values) => !values.start_time || !values.end_time || values.end_time > values.start_time,
    {
      message: "End must be after start",
      path: ["end_time"],
    },
  )

type MeetingFormValues = z.infer<typeof meetingSchema>

/** Defaults to the next full hour, one hour long, kept within the same day. */
function emptyValues(start?: Date): MeetingFormValues {
  if (!start) {
    start = new Date()
    start.setHours(start.getHours() + 1, 0, 0, 0)
  }
  const end = new Date(start.getTime() + 60 * 60_000)
  return {
    title: "",
    description: "",
    call_link: "",
    place: "",
    date: toDateInput(start),
    start_time: toTimeInput(start),
    end_time: end.getDate() === start.getDate() ? toTimeInput(end) : "23:59",
    participants: [],
  }
}

function meetingValues(meeting: Meeting): MeetingFormValues {
  const start = new Date(meeting.starts_at)
  return {
    title: meeting.title,
    description: meeting.description ?? "",
    call_link: meeting.call_link ?? "",
    place: meeting.place ?? "",
    date: toDateInput(start),
    start_time: toTimeInput(start),
    end_time: toTimeInput(new Date(meeting.ends_at)),
    participants: meeting.participants,
  }
}

function formatAgendaToDescription(agenda: ParsedAgenda): string {
  const parts: string[] = []
  if (agenda.items && agenda.items.length > 0) {
    parts.push("Agenda:")
    agenda.items.forEach((item) => {
      const duration = item.duration_minutes ? ` (${item.duration_minutes} min)` : ""
      parts.push(`• ${item.title}${duration}`)
      if (item.description) {
        parts.push(`  ${item.description}`)
      }
    })
  }

  if (agenda.action_items && agenda.action_items.length > 0) {
    if (parts.length > 0) parts.push("")
    parts.push("Action items:")
    agenda.action_items.forEach((item) => {
      const details: string[] = []
      if (item.assignee) details.push(`assignee: ${item.assignee}`)
      if (item.due_date) details.push(`due: ${item.due_date}`)
      const extra = details.length > 0 ? ` (${details.join(", ")})` : ""
      parts.push(`- [ ] ${item.task}${extra}`)
    })
  }

  return parts.join("\n")
}

const API_FIELD_TO_FORM: Record<string, keyof MeetingFormValues> = {
  title: "title",
  description: "description",
  call_link: "call_link",
  place: "place",
  participant_ids: "participants",
  starts_at: "start_time",
  ends_at: "end_time",
}

interface MeetingFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Prefills the date and time, e.g. from a clicked calendar slot. */
  initialStart?: Date
  /** Edits this meeting instead of creating a new one. */
  meeting?: Meeting | null
}

function MeetingFormContent({
  onClose,
  initialStart,
  meeting,
}: {
  onClose: () => void
  initialStart?: Date
  meeting?: Meeting | null
}) {
  const createMeeting = useCreateMeeting()
  const updateMeeting = useUpdateMeeting()
  const saving = createMeeting.isPending || updateMeeting.isPending

  // AI Agenda Parsing state
  const [showAiParser, setShowAiParser] = useState(false)
  const [rawText, setRawText] = useState("")
  const [isParsing, setIsParsing] = useState(false)
  const [suggestedFields, setSuggestedFields] = useState<Set<string>>(new Set())
  const [aiSuggestion, setAiSuggestion] = useState<AiSuggestion | null>(
    meeting?.ai_suggestion ?? null,
  )
  const abortControllerRef = useRef<AbortController | null>(null)

  const form = useForm<MeetingFormValues>({
    resolver: zodResolver(meetingSchema),
    defaultValues: meeting ? meetingValues(meeting) : emptyValues(initialStart),
  })

  const handleFieldChange = (fieldName: string) => {
    if (suggestedFields.has(fieldName)) {
      setSuggestedFields((prev) => {
        const next = new Set(prev)
        next.delete(fieldName)
        return next
      })
    }
  }

  const handleCancelParse = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsParsing(false)
  }

  const handleParseAgenda = async () => {
    if (!rawText.trim()) return
    setIsParsing(true)
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    try {
      const result = await api.parseAgenda(rawText.trim(), { signal: abortController.signal })
      const agenda = result.agenda

      const newSuggested = new Set<string>()

      if (agenda.title) {
        form.setValue("title", agenda.title, { shouldValidate: true })
        newSuggested.add("title")
      }

      if (agenda.starts_at) {
        const parsedDate = new Date(agenda.starts_at)
        if (!isNaN(parsedDate.getTime())) {
          form.setValue("date", toDateInput(parsedDate), { shouldValidate: true })
          form.setValue("start_time", toTimeInput(parsedDate), { shouldValidate: true })
          newSuggested.add("date")
          newSuggested.add("start_time")

          const duration = agenda.duration_minutes || 60
          const endDate = new Date(parsedDate.getTime() + duration * 60_000)
          form.setValue("end_time", toTimeInput(endDate), { shouldValidate: true })
          newSuggested.add("end_time")
        }
      } else if (agenda.duration_minutes) {
        const currentStartTime = form.getValues("start_time")
        if (currentStartTime) {
          const [hours, minutes] = currentStartTime.split(":").map(Number)
          const totalMinutes = hours * 60 + minutes + agenda.duration_minutes
          const endHours = Math.floor(totalMinutes / 60) % 24
          const endMins = totalMinutes % 60
          const endTimeStr = `${String(endHours).padStart(2, "0")}:${String(endMins).padStart(2, "0")}`
          form.setValue("end_time", endTimeStr, { shouldValidate: true })
          newSuggested.add("end_time")
        }
      }

      const formattedDesc = formatAgendaToDescription(agenda)
      if (formattedDesc) {
        form.setValue("description", formattedDesc, { shouldValidate: true })
        newSuggested.add("description")
      }

      setSuggestedFields(newSuggested)
      setAiSuggestion({
        agenda,
        model: result.model,
        prompt_version: result.prompt_version,
        raw_text: rawText.trim(),
      })

      setShowAiParser(false)
      toast.success("Agenda parsed! Review the suggested fields below.")
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        toast.info("Parsing cancelled")
      } else {
        toast.error(error instanceof Error ? error.message : "Could not parse agenda")
      }
    } finally {
      setIsParsing(false)
      abortControllerRef.current = null
    }
  }

  const onSubmit = async (values: MeetingFormValues) => {
    const data: MeetingCreate = {
      title: values.title,
      description: values.description.trim() || null,
      call_link: values.call_link || null,
      place: values.place || null,
      starts_at: new Date(`${values.date}T${values.start_time}`).toISOString(),
      ends_at: new Date(`${values.date}T${values.end_time}`).toISOString(),
      participant_ids: values.participants.map((p) => p.id),
      ...(aiSuggestion?.agenda || meeting?.agenda
        ? { agenda: aiSuggestion?.agenda ?? meeting?.agenda }
        : {}),
      ...(aiSuggestion || meeting?.ai_suggestion
        ? { ai_suggestion: aiSuggestion ?? meeting?.ai_suggestion }
        : {}),
    }

    try {
      if (meeting) {
        await updateMeeting.mutateAsync({ id: meeting.id, data })
        if (aiSuggestion) {
          await api.saveAgenda({
            id: meeting.id,
            data: { agenda: aiSuggestion.agenda, ai_suggestion: aiSuggestion },
          })
        }
        toast.success("Meeting updated")
      } else {
        const created = await createMeeting.mutateAsync(data)
        if (aiSuggestion && created?.id) {
          try {
            await api.saveAgenda({
              id: created.id,
              data: { agenda: aiSuggestion.agenda, ai_suggestion: aiSuggestion },
            })
          } catch {
            // saved via createMeeting
          }
        }
        toast.success("Meeting created")
      }
      onClose()
    } catch (error) {
      if (error instanceof ApiError && error.status === 422 && error.issues.length > 0) {
        for (const issue of error.issues) {
          const field = API_FIELD_TO_FORM[String(issue.loc[1])]
          form.setError(field ?? "root", { message: issue.msg })
        }
        return
      }
      toast.error(
        error instanceof Error ? error.message : `Could not ${meeting ? "save" : "create"} meeting`,
      )
    }
  }

  const suggestedBadge = (fieldName: string) => {
    if (!suggestedFields.has(fieldName)) return null
    return (
      <Badge
        variant="outline"
        className="ml-2 border-amber-300 bg-amber-50 text-[10px] font-semibold tracking-wider text-amber-700 uppercase dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300"
      >
        suggested
      </Badge>
    )
  }

  return (
    <DialogContent className="sm:max-w-lg">
      <DialogHeader>
        <div className="flex items-center justify-between">
          <DialogTitle>{meeting ? "Edit meeting" : "New meeting"}</DialogTitle>
          {!showAiParser && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowAiParser(true)}
              className="h-7 gap-1 border-primary/30 text-xs text-primary hover:bg-primary/5"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Paste an agenda
            </Button>
          )}
        </div>
        <DialogDescription>
          Add a call link, a place, or both so people know where to go.
        </DialogDescription>
      </DialogHeader>

      {showAiParser && (
        <div className="mb-2 space-y-2 rounded-lg border border-primary/20 bg-primary/5 p-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Paste raw notes, chat message or email:
            </span>
            {!isParsing && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground"
                onClick={() => setShowAiParser(false)}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
          <Textarea
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            placeholder="e.g. 'Пн 10:00, синк по прайсингу на півгодини. Обговорити знижки для ентерпрайз клієнтів. Антон готує таблицю.'"
            rows={3}
            disabled={isParsing}
            className="bg-background text-xs"
          />
          <div className="flex items-center justify-between pt-1">
            {isParsing ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                <span>Parsing agenda with Claude… (2-8s)</span>
              </div>
            ) : (
              <span className="text-[11px] text-muted-foreground">
                Claude AI will pre-fill the form fields.
              </span>
            )}
            <div className="flex items-center gap-2">
              {isParsing ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleCancelParse}
                  className="h-7 text-xs"
                >
                  Cancel
                </Button>
              ) : (
                <>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowAiParser(false)}
                    className="h-7 text-xs"
                  >
                    Close
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleParseAgenda}
                    disabled={!rawText.trim()}
                    className="h-7 gap-1 text-xs"
                  >
                    <Sparkles className="h-3 w-3" />
                    Parse
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField
            control={form.control}
            name="title"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center">
                  <FormLabel>Title</FormLabel>
                  {suggestedBadge("title")}
                </div>
                <FormControl>
                  <Input
                    placeholder="Sprint planning"
                    {...field}
                    onChange={(e) => {
                      field.onChange(e)
                      handleFieldChange("title")
                    }}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="grid gap-4 sm:grid-cols-[1.4fr_1fr_1fr]">
            <FormField
              control={form.control}
              name="date"
              render={({ field }) => (
                <FormItem>
                  <div className="flex items-center">
                    <FormLabel>Date</FormLabel>
                    {suggestedBadge("date")}
                  </div>
                  <FormControl>
                    <Input
                      type="date"
                      {...field}
                      onChange={(e) => {
                        field.onChange(e)
                        handleFieldChange("date")
                      }}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="start_time"
              render={({ field }) => (
                <FormItem>
                  <div className="flex items-center">
                    <FormLabel>Start</FormLabel>
                    {suggestedBadge("start_time")}
                  </div>
                  <FormControl>
                    <Input
                      type="time"
                      {...field}
                      onChange={(e) => {
                        field.onChange(e)
                        handleFieldChange("start_time")
                      }}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="end_time"
              render={({ field }) => (
                <FormItem>
                  <div className="flex items-center">
                    <FormLabel>End</FormLabel>
                    {suggestedBadge("end_time")}
                  </div>
                  <FormControl>
                    <Input
                      type="time"
                      {...field}
                      onChange={(e) => {
                        field.onChange(e)
                        handleFieldChange("end_time")
                      }}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <FormField
            control={form.control}
            name="description"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center">
                  <FormLabel>Description</FormLabel>
                  {suggestedBadge("description")}
                </div>
                <FormControl>
                  <Textarea
                    placeholder="What is this meeting about?"
                    rows={3}
                    {...field}
                    onChange={(e) => {
                      field.onChange(e)
                      handleFieldChange("description")
                    }}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="participants"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Participants</FormLabel>
                <FormControl>
                  <ParticipantsMultiSelect value={field.value} onChange={field.onChange} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="call_link"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Call link</FormLabel>
                  <FormControl>
                    <Input placeholder="https://meet.google.com/…" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="place"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Place</FormLabel>
                  <FormControl>
                    <Input placeholder="Room 204" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          {form.formState.errors.root && (
            <p className="text-sm text-destructive">{form.formState.errors.root.message}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {meeting
                ? saving
                  ? "Saving…"
                  : "Save changes"
                : saving
                  ? "Creating…"
                  : "Create meeting"}
            </Button>
          </DialogFooter>
        </form>
      </Form>
    </DialogContent>
  )
}

export function MeetingFormDialog({
  open,
  onOpenChange,
  initialStart,
  meeting,
}: MeetingFormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open && (
        <MeetingFormContent
          onClose={() => onOpenChange(false)}
          initialStart={initialStart}
          meeting={meeting}
        />
      )}
    </Dialog>
  )
}
