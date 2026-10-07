import type { ReactNode } from "react"
import { LoaderCircle } from "lucide-react"
import { useAuth } from "react-oidc-context"
import { Navigate } from "react-router"

import { authEnabled, isSignedIn } from "@/lib/auth"

/** Renders the page only with a session; otherwise sends the user to sign in. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const auth = useAuth()

  if (!authEnabled()) {
    return <>{children}</>
  }

  if (auth.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoaderCircle className="size-8 animate-spin text-primary" />
      </div>
    )
  }

  const authenticated = auth.isAuthenticated || isSignedIn()
  return authenticated ? <>{children}</> : <Navigate to="/login/" replace />
}

/** Sign-in and sign-up pages skip straight to the calendar when already signed in. */
export function RedirectIfSignedIn({ children }: { children: ReactNode }) {
  const auth = useAuth()

  if (!authEnabled()) {
    return <Navigate to="/home" replace />
  }

  if (auth.isLoading) {
    return null
  }

  const authenticated = auth.isAuthenticated || isSignedIn()
  return authenticated ? <Navigate to="/home" replace /> : <>{children}</>
}
