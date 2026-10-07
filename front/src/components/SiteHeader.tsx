import { useQueryClient } from "@tanstack/react-query"
import { CalendarDays, LogIn, LogOut, Plus } from "lucide-react"
import { useAuth } from "react-oidc-context"
import { Link, useNavigate } from "react-router"

import { useMe } from "@/hooks/useMe"
import { getCognitoLogoutUrl, isSignedIn, signOut } from "@/lib/auth"

interface SiteHeaderProps {
  onNewMeeting?: () => void
}

export function SiteHeader({ onNewMeeting }: SiteHeaderProps) {
  const auth = useAuth()
  const { data: me } = useMe()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const authenticated = auth.isAuthenticated || isSignedIn()
  const userEmail = (auth.user?.profile?.email as string | undefined) ?? me?.email
  const userName = (auth.user?.profile?.name as string | undefined) ?? me?.name ?? userEmail

  const handleSignOut = async () => {
    signOut()
    queryClient.clear()
    if (auth.removeUser) {
      await auth.removeUser().catch(() => {})
    }
    const logoutUrl = getCognitoLogoutUrl()
    if (logoutUrl) {
      window.location.assign(logoutUrl)
    } else {
      navigate("/", { replace: true })
    }
  }

  return (
    <header className="sticky top-0 z-40 bg-brand text-white shadow-[0_0.8px_8px_rgba(0,0,0,0.2)]">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-8 px-4 sm:px-6">
        <Link to="/home" className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-sm border-2 border-white/90">
            <CalendarDays className="size-5" />
          </span>
          <span className="font-serif text-sm leading-tight">
            Meetings
            <br />
            <span className="text-white/80">Scheduler</span>
          </span>
        </Link>

        <nav className="hidden h-full items-stretch gap-6 text-sm sm:flex">
          <Link
            to="/home"
            className="flex items-center border-b-[3px] border-white pt-[3px] font-medium"
          >
            Meetings
          </Link>
        </nav>

        <div className="ml-auto flex items-center gap-4">
          {authenticated ? (
            <>
              {onNewMeeting && (
                <button
                  type="button"
                  onClick={onNewMeeting}
                  className="flex items-center gap-1.5 text-sm font-semibold hover:text-white/80"
                >
                  <Plus className="size-4" /> New meeting
                </button>
              )}
              <span className="h-8 w-px bg-white/30" />
              {userName && (
                <span
                  className="hidden max-w-48 truncate text-sm text-white/90 lg:inline"
                  title={userEmail}
                >
                  {userName}
                </span>
              )}
              <button
                type="button"
                onClick={handleSignOut}
                className="flex items-center gap-1.5 text-sm text-white/90 hover:text-white"
                aria-label="Sign out"
              >
                <LogOut className="size-4" />
                <span className="hidden md:inline">Sign out</span>
              </button>
            </>
          ) : (
            <Link
              to="/login/"
              className="flex items-center gap-1.5 rounded-sm bg-white/10 px-3 py-1.5 text-sm font-semibold text-white hover:bg-white/20"
            >
              <LogIn className="size-4" />
              <span>Sign in</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  )
}
