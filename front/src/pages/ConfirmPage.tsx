import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { MailCheck } from "lucide-react"
import { Link, useLocation, useNavigate } from "react-router"
import { toast } from "sonner"
import { z } from "zod"

import { AuthLayout } from "@/components/auth/AuthLayout"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { confirmSignUp, resendCode } from "@/lib/auth"

const confirmSchema = z.object({
  email: z.email("Enter a valid email"),
  code: z
    .string()
    .trim()
    .regex(/^\d{6}$/, "Enter the 6-digit code"),
})

type ConfirmValues = z.infer<typeof confirmSchema>

/** Second step of sign-up: the code Cognito emailed. */
export function ConfirmPage() {
  const navigate = useNavigate()
  const email = ((useLocation().state ?? {}) as { email?: string }).email ?? ""
  const form = useForm<ConfirmValues>({
    resolver: zodResolver(confirmSchema),
    defaultValues: { email, code: "" },
  })

  const onSubmit = async (values: ConfirmValues) => {
    try {
      await confirmSignUp(values.email, values.code)
      navigate("/", { replace: true, state: { email: values.email, confirmed: true } })
    } catch (error) {
      form.setError("root", {
        message: error instanceof Error ? error.message : "Could not confirm",
      })
    }
  }

  const resend = async () => {
    const valid = await form.trigger("email")
    if (!valid) return
    try {
      await resendCode(form.getValues("email"))
      toast.success("A new code is on its way")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not send a new code")
    }
  }

  return (
    <AuthLayout>
      <span className="flex size-11 items-center justify-center rounded-full bg-secondary text-brand">
        <MailCheck className="size-5" />
      </span>
      <h1 className="mt-4 text-2xl font-semibold text-foreground">Check your email</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        {email ? (
          <>
            We sent a 6-digit code to <span className="font-medium text-foreground">{email}</span>.
          </>
        ) : (
          "Enter your email and the 6-digit code we sent you."
        )}
      </p>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="mt-8 space-y-4" noValidate>
          {!email && (
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type="email" autoComplete="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}
          <FormField
            control={form.control}
            name="code"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Confirmation code</FormLabel>
                <FormControl>
                  <Input
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    placeholder="123456"
                    className="tracking-[0.3em]"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          {form.formState.errors.root && (
            <p role="alert" className="text-sm text-destructive">
              {form.formState.errors.root.message}
            </p>
          )}
          <Button type="submit" className="h-10 w-full" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Confirming…" : "Confirm account"}
          </Button>
        </form>
      </Form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Didn&apos;t get it?{" "}
        <button
          type="button"
          onClick={resend}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Send a new code
        </button>
        {" · "}
        <Link to="/" className="font-medium text-primary underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      </p>
    </AuthLayout>
  )
}
