import { CalendarDays, Plus } from "lucide-react"

interface SiteHeaderProps {
  onNewMeeting: () => void
}

export function SiteHeader({ onNewMeeting }: SiteHeaderProps) {
  return (
    <header className="sticky top-0 z-40 bg-brand text-white shadow-[0_0.8px_8px_rgba(0,0,0,0.2)]">
      <div className="mx-auto flex h-20 max-w-7xl items-center gap-8 px-4 sm:px-6">
        <a href="/" className="flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-sm border-2 border-white/90">
            <CalendarDays className="size-6" />
          </span>
          <span className="font-serif text-[15px] leading-tight">
            Meetings
            <br />
            <span className="text-white/80">Scheduler</span>
          </span>
        </a>

        <nav className="hidden h-full items-stretch gap-6 text-sm sm:flex">
          <a
            href="/"
            className="flex items-center border-b-[3px] border-white pt-[3px] font-medium"
          >
            Meetings
          </a>
        </nav>

        <div className="ml-auto flex items-center gap-4">
          <button
            type="button"
            onClick={onNewMeeting}
            className="flex items-center gap-1.5 text-sm font-semibold hover:text-white/80"
          >
            <Plus className="size-4" /> New meeting
          </button>
        </div>
      </div>
    </header>
  )
}
