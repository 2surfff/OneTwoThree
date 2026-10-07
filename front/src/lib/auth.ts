/**
 * Sign-in with Amazon Cognito, straight from the browser (no SDK): email + password through the
 * Cognito API, Google through the Hosted UI (OAuth code flow with PKCE). The ID token is sent to
 * our API, which verifies it.
 *
 * Without VITE_COGNITO_CLIENT_ID (local development without AWS) auth is disabled: any valid form
 * "signs in" and the backend treats every request as one local user.
 */

import { WebStorageStateStore } from "oidc-client-ts"
import type { AuthProviderProps } from "react-oidc-context"

export interface AuthConfig {
  region: string
  clientId: string
  domain: string
  googleEnabled: boolean
}

export function getOidcConfig(): AuthProviderProps {
  const env = import.meta.env
  const region = env.VITE_COGNITO_REGION || "eu-north-1"
  const userPoolId = env.VITE_COGNITO_USER_POOL_ID || "eu-north-1_2JHnz3607"
  const clientId = env.VITE_COGNITO_CLIENT_ID || "520q7rcdd0c5hf0ahk2adb8bm3"
  const authority =
    env.VITE_COGNITO_AUTHORITY ||
    (userPoolId ? `https://cognito-idp.${region}.amazonaws.com/${userPoolId}` : "")

  return {
    authority: authority || "https://cognito-idp.eu-north-1.amazonaws.com/placeholder",
    client_id: clientId || "placeholder",
    redirect_uri: `${window.location.origin}/auth/callback/`,
    response_type: "code",
    scope: "openid email profile",
    userStore: new WebStorageStateStore({ store: window.localStorage }),
    onSigninCallback: () => {
      window.history.replaceState({}, document.title, window.location.pathname)
    },
  }
}

export function getOidcIdToken(): string | null {
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key?.startsWith("oidc.user:")) {
        const item = localStorage.getItem(key)
        if (item) {
          const user = JSON.parse(item)
          if (user?.expires_at && user.expires_at * 1000 < Date.now()) {
            continue
          }
          if (user?.id_token) return user.id_token
        }
      }
    }
  } catch {
    // ignore
  }
  return null
}

export function getOidcEmail(): string | null {
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key?.startsWith("oidc.user:")) {
        const item = localStorage.getItem(key)
        if (item) {
          const user = JSON.parse(item)
          if (user?.expires_at && user.expires_at * 1000 < Date.now()) {
            continue
          }
          if (user?.profile?.email) return user.profile.email
          if (user?.id_token) {
            const parts = user.id_token.split(".")
            if (parts.length === 3) {
              const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")))
              if (payload?.email) return payload.email
            }
          }
        }
      }
    }
  } catch {
    // ignore
  }
  return null
}

export function getCognitoLogoutUrl(): string {
  const env = import.meta.env
  const rawDomain =
    authConfig().domain ||
    env.VITE_COGNITO_DOMAIN ||
    "anton-meetings-2026.auth.eu-north-1.amazoncognito.com"
  const domain = rawDomain.replace(/^https?:\/\//, "").replace(/\/+$/, "")
  const clientId =
    authConfig().clientId || env.VITE_COGNITO_CLIENT_ID || "520q7rcdd0c5hf0ahk2adb8bm3"
  const origin = window.location.origin
  const logoutUri = origin.includes("cloudfront.net")
    ? "https://d1y19dbl226ufk.cloudfront.net/"
    : `${origin}/`
  return `https://${domain}/logout?client_id=${encodeURIComponent(clientId)}&logout_uri=${encodeURIComponent(logoutUri)}`
}

export function authConfig(): AuthConfig {
  const env = import.meta.env
  if (env.MODE === "test" && !env.VITE_COGNITO_CLIENT_ID) {
    return {
      region: "eu-north-1",
      clientId: "",
      domain: "",
      googleEnabled: false,
    }
  }
  return {
    region: env.VITE_COGNITO_REGION || "eu-north-1",
    clientId: env.VITE_COGNITO_CLIENT_ID || "520q7rcdd0c5hf0ahk2adb8bm3",
    domain: env.VITE_COGNITO_DOMAIN || "anton-meetings-2026.auth.eu-north-1.amazoncognito.com",
    googleEnabled: true,
  }
}

export const authEnabled = () => Boolean(authConfig().clientId)
export const googleEnabled = () => authEnabled() && authConfig().googleEnabled

/** Cognito error with its exception name, e.g. NotAuthorizedException. */
export class AuthError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = "AuthError"
    this.code = code
  }
}

const FRIENDLY_MESSAGES: Record<string, string> = {
  NotAuthorizedException: "Incorrect email or password",
  UserNotFoundException: "Incorrect email or password",
  UsernameExistsException: "An account with this email already exists",
  CodeMismatchException: "That code is not right, check the email and try again",
  ExpiredCodeException: "The code has expired, send a new one",
  LimitExceededException: "Too many attempts, try again in a few minutes",
  TooManyRequestsException: "Too many attempts, try again in a few minutes",
}

async function cognito<T>(action: string, body: Record<string, unknown>): Promise<T> {
  const { region, clientId } = authConfig()
  const response = await fetch(`https://cognito-idp.${region}.amazonaws.com/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": `AWSCognitoIdentityProviderService.${action}`,
    },
    body: JSON.stringify({ ClientId: clientId, ...body }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const code =
      String(data.__type ?? "")
        .split("#")
        .pop() || "UnknownError"
    throw new AuthError(code, FRIENDLY_MESSAGES[code] ?? data.message ?? "Sign-in failed")
  }
  return data as T
}

// --- Session (kept in localStorage so a reload stays signed in) ---

interface Session {
  idToken: string
  refreshToken?: string
  /** Epoch ms when the ID token expires. */
  expiresAt: number
}

const SESSION_KEY = "meetings.session"

function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

function writeSession(session: Session | null) {
  try {
    if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session))
    else localStorage.removeItem(SESSION_KEY)
  } catch {
    // Storage unavailable (private mode): the session lasts until reload.
  }
}

interface Tokens {
  IdToken: string
  RefreshToken?: string
  ExpiresIn: number
}

function saveTokens(tokens: Tokens, previousRefresh?: string) {
  writeSession({
    idToken: tokens.IdToken,
    refreshToken: tokens.RefreshToken ?? previousRefresh,
    expiresAt: Date.now() + tokens.ExpiresIn * 1000,
  })
}

const LOCAL_SESSION: Session = { idToken: "", expiresAt: Number.MAX_SAFE_INTEGER }

export const isSignedIn = () =>
  readSession() !== null || getOidcIdToken() !== null || getOidcEmail() !== null

export function clearAllAuthStorage() {
  writeSession(null)
  try {
    localStorage.clear()
  } catch {
    try {
      const keys: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i)
        if (k) keys.push(k)
      }
      keys.forEach((k) => localStorage.removeItem(k))
    } catch {
      // ignore
    }
  }

  try {
    sessionStorage.clear()
  } catch {
    try {
      const keys: string[] = []
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i)
        if (k) keys.push(k)
      }
      keys.forEach((k) => sessionStorage.removeItem(k))
    } catch {
      // ignore
    }
  }

  try {
    document.cookie.split(";").forEach((cookie) => {
      const eqPos = cookie.indexOf("=")
      const name = eqPos > -1 ? cookie.substring(0, eqPos).trim() : cookie.trim()
      if (name) {
        document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`
      }
    })
  } catch {
    // ignore
  }
}

export function signOut() {
  clearAllAuthStorage()
}

/** A valid ID token for the API, refreshed when about to expire; null when signed out. */
export async function getIdToken(): Promise<string | null> {
  const oidcToken = getOidcIdToken()
  if (oidcToken) return oidcToken

  const session = readSession()
  if (!session || !authEnabled()) return null
  if (session.expiresAt - 60_000 > Date.now()) return session.idToken
  if (!session.refreshToken) {
    signOut()
    return null
  }
  try {
    const { AuthenticationResult } = await cognito<{ AuthenticationResult: Tokens }>(
      "InitiateAuth",
      { AuthFlow: "REFRESH_TOKEN_AUTH", AuthParameters: { REFRESH_TOKEN: session.refreshToken } },
    )
    saveTokens(AuthenticationResult, session.refreshToken)
    return AuthenticationResult.IdToken
  } catch {
    signOut()
    return null
  }
}

// --- Email + password ---

export async function signIn(email: string, password: string): Promise<void> {
  if (!authEnabled()) {
    writeSession(LOCAL_SESSION)
    return
  }
  const result = await cognito<{ AuthenticationResult?: Tokens; ChallengeName?: string }>(
    "InitiateAuth",
    { AuthFlow: "USER_PASSWORD_AUTH", AuthParameters: { USERNAME: email, PASSWORD: password } },
  )
  if (!result.AuthenticationResult) {
    throw new AuthError(
      result.ChallengeName ?? "ChallengeRequired",
      "This account needs an extra step that the app does not support yet",
    )
  }
  saveTokens(result.AuthenticationResult)
}

/** Creates the account; Cognito then emails a code to confirm it. */
export async function signUp(name: string, email: string, password: string): Promise<void> {
  if (!authEnabled()) return
  await cognito("SignUp", {
    Username: email,
    Password: password,
    UserAttributes: [
      { Name: "email", Value: email },
      { Name: "name", Value: name },
    ],
  })
}

export async function confirmSignUp(email: string, code: string): Promise<void> {
  if (!authEnabled()) return
  await cognito("ConfirmSignUp", { Username: email, ConfirmationCode: code })
}

export async function resendCode(email: string): Promise<void> {
  if (!authEnabled()) return
  await cognito("ResendConfirmationCode", { Username: email })
}

// --- Google (Hosted UI, authorization code + PKCE) ---

const PKCE_KEY = "meetings.pkce"
export const callbackUrl = () => `${window.location.origin}/auth/callback`

function base64Url(bytes: ArrayBuffer | Uint8Array): string {
  const binary = String.fromCharCode(...new Uint8Array(bytes))
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")
}

export async function startGoogleSignIn(): Promise<void> {
  const { clientId, domain } = authConfig()
  const verifier = base64Url(crypto.getRandomValues(new Uint8Array(32)))
  const state = base64Url(crypto.getRandomValues(new Uint8Array(16)))
  const challenge = base64Url(
    await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)),
  )
  sessionStorage.setItem(PKCE_KEY, JSON.stringify({ verifier, state }))
  const params = new URLSearchParams({
    identity_provider: "Google",
    response_type: "code",
    client_id: clientId,
    redirect_uri: callbackUrl(),
    scope: "openid email profile",
    state,
    code_challenge_method: "S256",
    code_challenge: challenge,
  })
  window.location.assign(`https://${domain}/oauth2/authorize?${params}`)
}

/** Exchanges the code from the Hosted UI redirect for tokens. */
export async function completeOAuthSignIn(code: string, state: string): Promise<void> {
  const { clientId, domain } = authConfig()
  const saved = JSON.parse(sessionStorage.getItem(PKCE_KEY) ?? "null") as {
    verifier: string
    state: string
  } | null
  sessionStorage.removeItem(PKCE_KEY)
  if (!saved || saved.state !== state) {
    throw new AuthError("StateMismatch", "Sign-in expired or was started elsewhere, try again")
  }
  const response = await fetch(`https://${domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: clientId,
      code,
      redirect_uri: callbackUrl(),
      code_verifier: saved.verifier,
    }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok)
    throw new AuthError(data.error ?? "TokenError", "Google sign-in failed, try again")
  saveTokens({
    IdToken: data.id_token,
    RefreshToken: data.refresh_token,
    ExpiresIn: data.expires_in,
  })
}
