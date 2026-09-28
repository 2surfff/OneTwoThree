import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { Link, useNavigate } from "react-router"
import { z } from "zod"

import { AuthLayout } from "@/components/auth/AuthLayout"
import { GoogleButton, OrDivider } from "@/components/auth/GoogleButton"
import { PasswordInput } from "@/components/auth/PasswordInput"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { authEnabled, signIn, signUp } from "@/lib/auth"

const signUpSchema = z
  .object({
    name: z.string().trim().min(1, "Name is required").max(120, "Max 120 characters"),
    email: z.email("Enter a valid email"),
    // Mirrors the user pool's password policy.
    password: z
      .string()
      .min(8, "At least 8 characters")
      .regex(/[a-z]/, "Include a lowercase letter")
      .regex(/\d/, "Include a number"),
    confirm: z.string(),
  })
  .refine((values) => values.password === values.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  })

type SignUpValues = z.infer<typeof signUpSchema>

export function SignUpPage() {
  const navigate = useNavigate()
  const form = useForm<SignUpValues>({
    resolver: zodResolver(signUpSchema),
    defaultValues: { name: "", email: "", password: "", confirm: "" },
  })

  const onSubmit = async ({ name, email, password }: SignUpValues) => {
    try {
      await signUp(name, email, password)
      if (authEnabled()) {
        // Cognito emailed a code; the account works once it is confirmed.
        navigate("/confirm", { state: { email } })
      } else {
        await signIn(email, password)
        navigate("/home", { replace: true })
      }
    } catch (error) {
      form.setError("root", { message: error instanceof Error ? error.message : "Sign-up failed" })
    }
  }

  return (
    <AuthLayout>
      <h1 className="text-2xl font-semibold text-foreground">Create an account</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">Start scheduling meetings in a minute.</p>

      <div className="mt-8">
        <GoogleButton label="Sign up with Google" />
      </div>
      <OrDivider />

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl>
                  <Input autoComplete="name" placeholder="Anna Kovalenko" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input
                    type="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <PasswordInput autoComplete="new-password" {...field} />
                </FormControl>
                <FormDescription>
                  At least 8 characters, with a lowercase letter and a number.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="confirm"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Confirm password</FormLabel>
                <FormControl>
                  <PasswordInput autoComplete="new-password" {...field} />
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
            {form.formState.isSubmitting ? "Creating account…" : "Create account"}
          </Button>
        </form>
      </Form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link to="/" className="font-medium text-primary underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}
