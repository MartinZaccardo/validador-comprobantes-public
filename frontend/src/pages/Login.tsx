import { useState } from "react"
import type { FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { login } from "@/api/auth"

function ShieldCheckIcon() {
  return (
    <svg
      width="40"
      height="40"
      viewBox="0 0 20 20"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="text-primary"
    >
      <path
        d="M10 2L4 5.5v4.5c0 3.8 2.7 7.3 6 8.5 3.3-1.2 6-4.7 6-8.5V5.5L10 2z"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M7.5 10.5l2 2 3.5-4"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  )
}

function EyeIcon({ open }: { open: boolean }) {
  return open ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  )
}

export default function Login() {
  const [email, setEmail]                   = useState("")
  const [password, setPassword]             = useState("")
  const [mostrarPassword, setMostrarPassword] = useState(false)
  const [cargando, setCargando]             = useState(false)
  const [error, setError]                   = useState<string | null>(null)
  const navegar = useNavigate()

  async function handleSubmit(evento: FormEvent) {
    evento.preventDefault()
    setCargando(true)
    setError(null)

    try {
      await login(email, password)
      navegar("/", { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al iniciar sesión")
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="min-h-screen bg-muted flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-background rounded-xl border shadow-sm px-8 py-10 space-y-6">

        <div className="space-y-3 text-center">
          <div className="flex justify-center">
            <ShieldCheckIcon />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Validador de Comprobantes
          </h1>
          <p className="text-sm text-muted-foreground">
            Ingresá con tu cuenta de administrador
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium leading-none">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background
                         px-3 py-2 text-sm ring-offset-background
                         placeholder:text-muted-foreground
                         focus-visible:outline-none focus-visible:ring-2
                         focus-visible:ring-ring focus-visible:ring-offset-2
                         disabled:cursor-not-allowed disabled:opacity-50"
              placeholder="admin@empresa.com"
              disabled={cargando}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium leading-none">
              Contraseña
            </label>
            <div className="relative">
              <input
                id="password"
                type={mostrarPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background
                           px-3 py-2 pr-10 text-sm ring-offset-background
                           placeholder:text-muted-foreground
                           focus-visible:outline-none focus-visible:ring-2
                           focus-visible:ring-ring focus-visible:ring-offset-2
                           disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="••••••••"
                disabled={cargando}
              />
              <button
                type="button"
                onClick={() => setMostrarPassword((v) => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground hover:text-foreground"
                aria-label={mostrarPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                tabIndex={-1}
              >
                <EyeIcon open={mostrarPassword} />
              </button>
            </div>
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <Button type="submit" className="w-full" disabled={cargando}>
            {cargando ? "Ingresando..." : "Ingresar"}
          </Button>
        </form>

        <p className="text-xs text-muted-foreground text-center pt-2 border-t border-border">
          HZ Sistemas
        </p>

      </div>
    </div>
  )
}
