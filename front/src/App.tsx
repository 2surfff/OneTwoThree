import { useState } from "react"
import { Plus } from "lucide-react"
import { toast } from "sonner"

import { BackToTop } from "@/components/BackToTop"
import { DeleteMeetingDialog } from "@/components/DeleteMeetingDialog"
import { MeetingFormDialog } from "@/components/MeetingFormDialog"
import { MeetingsCalendar } from "@/components/MeetingsCalendar"
import { SiteFooter } from "@/components/SiteFooter"
import { SiteHeader } from "@/components/SiteHeader"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useDeleteMeeting, useMeetings } from "@/hooks/useMeetings"
import type { Meeting } from "@/types"

export default function App() {
  const { data: meetings, isPending, isError, error, refetch } = useMeetings()
  const deleteMeeting = useDeleteMeeting()
  const [formOpen, setFormOpen] = useState(false)
  const [formStart, setFormStart] = useState<Date | undefined>()
  const [editing, setEditing] = useState<Meeting | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Meeting | null>(null)

  const openForm = (start?: Date) => {
    setEditing(null)
    setFormStart(start)
    setFormOpen(true)
  }

  const openEdit = (meeting: Meeting) => {
    setEditing(meeting)
    setFormOpen(true)
  }

  const confirmDelete = (meeting: Meeting) => {
    setPendingDelete(null)
    deleteMeeting.mutate(meeting.id, {
      onSuccess: () => toast.success("Meeting deleted"),
      onError: (err) => toast.error(`Could not delete meeting: ${err.message}`),
    })
  }

  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader onNewMeeting={() => openForm()} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
        <section className="rounded-sm border bg-card p-4 sm:p-6">
          <div className="mb-5 flex items-center justify-between gap-4">
            <h1 className="text-lg font-semibold text-foreground">Meetings</h1>
            <Button onClick={() => openForm()} className="px-5">
              <Plus /> New meeting
            </Button>
          </div>

          {isPending ? (
            <div className="space-y-2" aria-label="Loading meetings">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-[480px] w-full" />
            </div>
          ) : isError ? (
            <div
              role="alert"
              className="rounded-sm border border-destructive/50 p-4 text-destructive"
            >
              <p className="font-medium">Could not load meetings</p>
              <p className="text-sm">{error.message}</p>
              <Button variant="outline" size="sm" className="mt-3" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          ) : (
            <MeetingsCalendar
              meetings={meetings}
              onEdit={openEdit}
              onDelete={setPendingDelete}
              onCreateAt={openForm}
            />
          )}
        </section>
      </main>

      <SiteFooter />
      <BackToTop />

      <MeetingFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        initialStart={formStart}
        meeting={editing}
      />
      <DeleteMeetingDialog
        meeting={pendingDelete}
        onCancel={() => setPendingDelete(null)}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
