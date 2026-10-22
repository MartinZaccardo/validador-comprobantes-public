import { Link } from "react-router-dom"

function ShieldCheckIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 20 20"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="text-primary shrink-0"
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

interface AppHeaderProps {
  children?: React.ReactNode
}

export default function AppHeader({ children }: AppHeaderProps) {
  return (
    <header className="border-b bg-background px-6 py-4 flex items-center justify-between shadow-sm">
      <Link
        to="/"
        className="flex items-center gap-2.5 hover:opacity-75 transition-opacity"
      >
        <ShieldCheckIcon />
        <div className="flex flex-col leading-tight">
          <span className="text-lg font-semibold">Validador de Comprobantes</span>
          <span className="text-xs text-muted-foreground">HZ Sistemas</span>
        </div>
      </Link>
      {children && (
        <nav className="flex items-center gap-6">{children}</nav>
      )}
    </header>
  )
}
