/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend base URL, e.g. https://abc.lambda-url.us-east-1.on.aws (empty: same origin). */
  readonly VITE_API_URL?: string
  /** Cognito user pool settings; no client ID = auth disabled (local development). */
  readonly VITE_COGNITO_REGION?: string
  readonly VITE_COGNITO_USER_POOL_ID?: string
  readonly VITE_COGNITO_CLIENT_ID?: string
  readonly VITE_COGNITO_DOMAIN?: string
  /** OIDC Authority URL, e.g. https://cognito-idp.eu-north-1.amazonaws.com/<pool-id>. */
  readonly VITE_COGNITO_AUTHORITY?: string
  /** "true" once Google is set up as an identity provider in the user pool. */
  readonly VITE_COGNITO_GOOGLE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
