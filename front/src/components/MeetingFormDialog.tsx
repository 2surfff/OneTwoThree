import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { toast } from "sonner"
import { z } from "zod"

import { ParticipantsMultiSelect } from "@/components/ParticipantsMultiSelect"
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
import { ApiError } from "@/lib/api"
import { toDateInput, toTimeInput } from "@/lib/calendar"
import type { Meeting, MeetingCreate } from "@/types"

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

export function MeetingFormDialog({
  open,
  onOpenChange,
  initialStart,
  meeting,
}: MeetingFormDialogProps) {
  const createMeeting = useCreateMeeting()
  const updateMeeting = useUpdateMeeting()
  const saving = createMeeting.isPending || updateMeeting.isPending
  const form = useForm<MeetingFormValues>({
    resolver: zodResolver(meetingSchema),
    defaultValues: meeting ? meetingValues(meeting) : emptyValues(initialStart),
  })

  useEffect(() => {
    if (open) form.reset(meeting ? meetingValues(meeting) : emptyValues(initialStart))
  }, [open, initialStart, meeting, form])

  const onSubmit = async (values: MeetingFormValues) => {
    const data: MeetingCreate = {
      title: values.title,
      description: values.description.trim() || null,
      call_link: values.call_link || null,
      place: values.place || null,
      starts_at: new Date(`${values.date}T${values.start_time}`).toISOString(),
      ends_at: new Date(`${values.date}T${values.end_time}`).toISOString(),
      participant_ids: values.participants.map((p) => p.id),
    }
    try {
      if (meeting) {
        await updateMeeting.mutateAsync({ id: meeting.id, data })
        toast.success("Meeting updated")
      } else {
        await createMeeting.mutateAsync(data)
        toast.success("Meeting created")
      }
      onOpenChange(false)
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{meeting ? "Edit meeting" : "New meeting"}</DialogTitle>
          <DialogDescription>
            Add a call link, a place, or both so people know where to go.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Title</FormLabel>
                  <FormControl>
                    <Input placeholder="Sprint planning" {...field} />
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
                    <FormLabel>Date</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
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
                    <FormLabel>Start</FormLabel>
                    <FormControl>
                      <Input type="time" {...field} />
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
                    <FormLabel>End</FormLabel>
                    <FormControl>
                      <Input type="time" {...field} />
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
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea placeholder="What is this meeting about?" rows={3} {...field} />
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
                      <Input type="url" placeholder="https://meet.google.com/…" {...field} />
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
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
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
    </Dialog>
  )
}
