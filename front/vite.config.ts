/// <reference types="vitest/config" />
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")

  return {
    plugins: [react(), tailwindcss()],
    define: {
      "import.meta.env.VITE_COGNITO_REGION": JSON.stringify(
        env.VITE_COGNITO_REGION || process.env.VITE_COGNITO_REGION || "eu-north-1",
      ),
      "import.meta.env.VITE_COGNITO_USER_POOL_ID": JSON.stringify(
        env.VITE_COGNITO_USER_POOL_ID || process.env.VITE_COGNITO_USER_POOL_ID || "eu-north-1_2JHnz3607",
      ),
      "import.meta.env.VITE_COGNITO_CLIENT_ID": JSON.stringify(
        env.VITE_COGNITO_CLIENT_ID || process.env.VITE_COGNITO_CLIENT_ID || "520q7rcdd0c5hf0ahk2adb8bm3",
      ),
      "import.meta.env.VITE_COGNITO_DOMAIN": JSON.stringify(
        env.VITE_COGNITO_DOMAIN || process.env.VITE_COGNITO_DOMAIN || "anton-meetings-2026.auth.eu-north-1.amazoncognito.com",
      ),
      "import.meta.env.VITE_COGNITO_AUTHORITY": JSON.stringify(
        env.VITE_COGNITO_AUTHORITY || process.env.VITE_COGNITO_AUTHORITY || "https://cognito-idp.eu-north-1.amazonaws.com/eu-north-1_2JHnz3607",
      ),
      "import.meta.env.VITE_COGNITO_GOOGLE": JSON.stringify("true"),
      "import.meta.env.VITE_API_URL": JSON.stringify(
        env.VITE_API_URL || process.env.VITE_API_URL || "",
      ),
    },
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "./src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": process.env.VITE_API_PROXY ?? "http://localhost:8000",
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
    },
  }
})
