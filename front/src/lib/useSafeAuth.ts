import { useContext } from "react"
import { AuthContext, type AuthContextProps } from "react-oidc-context"

export function useSafeAuth(): AuthContextProps | undefined {
  return useContext(AuthContext)
}
