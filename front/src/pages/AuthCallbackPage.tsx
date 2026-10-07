import { useEffect } from "react"
import { LoaderCircle } from "lucide-react"
import { useAuth } from "react-oidc-context"
import { Link, useNavigate } from "react-router"

import { AuthLayout } from "@/components/auth/AuthLayout"

/** Where Cognito sends the browser back after sign-in. */
export function AuthCallbackPage() {
  const auth = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (auth.isAuthenticated) {
      navigate("/home", { replace: true })
    } else if (!auth.isLoading && !auth.error) {
      const params = new URLSearchParams(window.location.search)
      if (!params.get("code")) {
        navigate("/login/", { replace: true })
      }
    }
  }, [auth.isAuthenticated, auth.isLoading, auth.error, navigate])

  if (auth.error) {
    return (
      <AuthLayout>
        <div role="alert">
          <h1 className="text-2xl font-semibold text-foreground">Sign-in failed</h1>
          <p className="mt-2 text-sm text-muted-foreground">{auth.error.message}</p>
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
