import type { ReactNode } from "react"
import { LoaderCircle } from "lucide-react"
import { useAuth } from "react-oidc-context"
import { Navigate } from "react-router"

import { getOidcEmail, isSignedIn } from "@/lib/auth"

/** Renders the page only with a valid OIDC session; otherwise sends the user to sign in. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const auth = useAuth()
  const userEmail = (auth.user?.profile?.email as string | undefined) ?? getOidcEmail()

  if (auth.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoaderCircle className="size-8 animate-spin text-primary" />
      </div>
    )
  }

  const authenticated = Boolean(auth.isAuthenticated || userEmail || isSignedIn())
  return authenticated ? <>{children}</> : <Navigate to="/login/" replace />
}

/** Sign-in pages skip straight to the calendar when already signed in. */
export function RedirectIfSignedIn({ children }: { children: ReactNode }) {
  const auth = useAuth()
  const userEmail = (auth.user?.profile?.email as string | undefined) ?? getOidcEmail()

  if (auth.isLoading) {
    return null
  }

  const authenticated = Boolean(auth.isAuthenticated || userEmail || isSignedIn())
  return authenticated ? <Navigate to="/home" replace /> : <>{children}</>
}
