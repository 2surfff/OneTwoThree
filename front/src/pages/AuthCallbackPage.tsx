import { useEffect, useRef, useState } from "react"
import { LoaderCircle } from "lucide-react"
import { Link, useNavigate, useSearchParams } from "react-router"

import { AuthLayout } from "@/components/auth/AuthLayout"
import { completeOAuthSignIn } from "@/lib/auth"
import { useSafeAuth } from "@/lib/useSafeAuth"

/** Where Cognito sends the browser back after sign-in. */
export function AuthCallbackPage() {
  const auth = useSafeAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [exchangeError, setExchangeError] = useState<string | null>(null)
  const started = useRef(false)

  const code = params.get("code")
  const state = params.get("state")
  const errorMsg = auth?.error?.message ?? exchangeError

  useEffect(() => {
    if (auth?.isAuthenticated) {
      navigate("/", { replace: true })
      return
    }

    if (code && state && !started.current) {
      started.current = true
      completeOAuthSignIn(code, state)
        .then(() => navigate("/", { replace: true }))
        .catch((err: Error) => setExchangeError(err.message))
      return
    }

    if (!auth?.isLoading && !auth?.error && !code) {
      navigate("/login/", { replace: true })
    }
  }, [auth?.isAuthenticated, auth?.isLoading, auth?.error, code, state, navigate])

  if (errorMsg) {
    return (
      <AuthLayout>
        <div role="alert">
          <h1 className="text-2xl font-semibold text-foreground">Sign-in failed</h1>
          <p className="mt-2 text-sm text-muted-foreground">{errorMsg}</p>
          <Link
            to="/login/"
            className="mt-6 inline-block font-medium text-primary underline-offset-4 hover:underline"
          >
            Back to sign in
          </Link>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <div className="flex items-center gap-2 text-muted-foreground">
        <LoaderCircle className="size-5 animate-spin" /> Signing you in…
      </div>
    </AuthLayout>
  )
}
