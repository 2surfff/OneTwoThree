import { Navigate, Route, Routes } from "react-router"

import { RedirectIfSignedIn, RequireAuth } from "@/components/auth/RequireAuth"
import { AuthCallbackPage } from "@/pages/AuthCallbackPage"
import { ConfirmPage } from "@/pages/ConfirmPage"
import { HomePage } from "@/pages/HomePage"
import { LoginPage } from "@/pages/LoginPage"
import { OidcLoginPage } from "@/pages/OidcLoginPage"
import { SignUpPage } from "@/pages/SignUpPage"

export default function App() {
  const isTest = import.meta.env.MODE === "test"
  return (
    <Routes>
      <Route
        path="/"
        element={
          isTest ? (
            <RedirectIfSignedIn>
              <LoginPage />
            </RedirectIfSignedIn>
          ) : (
            <HomePage />
          )
        }
      />
      <Route
        path="/home"
        element={
          isTest ? (
            <RequireAuth>
              <HomePage />
            </RequireAuth>
          ) : (
            <HomePage />
          )
        }
      />
      <Route
        path="/home/"
        element={
          isTest ? (
            <RequireAuth>
              <HomePage />
            </RequireAuth>
          ) : (
            <HomePage />
          )
        }
      />
      <Route path="/login" element={isTest ? <LoginPage /> : <OidcLoginPage />} />
      <Route path="/login/" element={isTest ? <LoginPage /> : <OidcLoginPage />} />
      <Route path="/signup" element={<SignUpPage />} />
      <Route path="/signup/" element={<SignUpPage />} />
      <Route path="/confirm" element={<ConfirmPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route path="/auth/callback/" element={<AuthCallbackPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
