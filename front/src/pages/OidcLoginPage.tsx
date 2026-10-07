import { useEffect, useRef } from "react"
import { LoaderCircle } from "lucide-react"
import { useAuth } from "react-oidc-context"
import { useNavigate } from "react-router"

import { AuthLayout } from "@/components/auth/AuthLayout"
import { getOidcEmail } from "@/lib/auth"

export function OidcLoginPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const redirectTriggered = useRef(false)
  const userEmail = (auth.user?.profile?.email as string | undefined) ?? getOidcEmail()

  useEffect(() => {
    if (auth.isAuthenticated || userEmail) {
      navigate("/home", { replace: true })
      return
    }

    if (!auth.isLoading && !redirectTriggered.current) {
      redirectTriggered.current = true
      auth.signinRedirect().catch((err: unknown) => {
        console.error("Failed to redirect to Cognito login:", err)
      })
    }
  }, [auth.isAuthenticated, auth.isLoading, auth, userEmail, navigate])

  return (
    <AuthLayout>
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <LoaderCircle className="mb-4 size-8 animate-spin text-primary" />
        <h2 className="text-xl font-semibold text-foreground">Redirecting to login…</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Taking you to the secure authentication page.
        </p>
        <button
          type="button"
          onClick={() => {
            redirectTriggered.current = true
            auth.signinRedirect().catch((err: unknown) => {
              console.error("Failed to redirect to Cognito login:", err)
            })
          }}
          className="mt-6 text-sm text-primary underline underline-offset-4 hover:text-primary/80"
        >
          Click here if you are not redirected automatically
        </button>
      </div>
    </AuthLayout>
  )
}
