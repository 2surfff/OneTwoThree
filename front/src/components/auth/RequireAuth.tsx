import type { ReactNode } from "react"
import { Navigate } from "react-router"

import { isSignedIn } from "@/lib/auth"

/** Renders the page only with a session; otherwise sends the user to sign in. */
export function RequireAuth({ children }: { children: ReactNode }) {
  return isSignedIn() ? children : <Navigate to="/" replace />
}

/** Sign-in and sign-up pages skip straight to the calendar when already signed in. */
export function RedirectIfSignedIn({ children }: { children: ReactNode }) {
  return isSignedIn() ? <Navigate to="/home" replace /> : children
}
