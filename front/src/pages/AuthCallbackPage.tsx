import { useEffect, useRef, useState } from "react"
import { LoaderCircle } from "lucide-react"
import { Link, useNavigate, useSearchParams } from "react-router"

import { AuthLayout } from "@/components/auth/AuthLayout"
import { completeOAuthSignIn } from "@/lib/auth"

/** Where the Cognito Hosted UI sends the browser back after Google sign-in. */
export function AuthCallbackPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const code = params.get("code")
  const state = params.get("state")
  // No code means the Hosted UI came back with an error (or the user cancelled).
  const redirectError =
    code && state ? null : (params.get("error_description") ?? "Sign-in was cancelled")
  const [exchangeError, setExchangeError] = useState<string | null>(null)
  const error = redirectError ?? exchangeError
  // The code can be exchanged only once; StrictMode runs effects twice in development.
  const started = useRef(false)

  useEffect(() => {
    if (!code || !state || started.current) return
    started.current = true
    completeOAuthSignIn(code, state)
      .then(() => navigate("/home", { replace: true }))
      .catch((err: Error) => setExchangeError(err.message))
  }, [code, state, navigate])

  return (
    <AuthLayout>
      {error ? (
        <div role="alert">
          <h1 className="text-2xl font-semibold text-foreground">Sign-in failed</h1>
          <p className="mt-2 text-sm text-muted-foreground">{error}</p>
          <Link
            to="/"
            className="mt-6 inline-block font-medium text-primary underline-offset-4 hover:underline"
          >
            Back to sign in
          </Link>
        </div>
      ) : (
        <p className="flex items-center gap-2 text-muted-foreground">
          <LoaderCircle className="size-5 animate-spin" /> Signing you in…
        </p>
      )}
    </AuthLayout>
  )
}
