import { NavLink } from "react-router-dom"
import {
  CalendarIcon,
  ClientesIcon,
  HistorialIcon,
  UserIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from "@/components/icons"

const NAV_ITEMS = [
  { to: "/",          end: true,  icon: <CalendarIcon />,  label: "Gestión del día" },
  { to: "/historial", end: false, icon: <HistorialIcon />, label: "Historial" },
  { to: "/clientes",  end: false, icon: <ClientesIcon />,  label: "Clientes" },
]

const NAV_BOTTOM = [
  { to: "/perfil", end: false, icon: <UserIcon />, label: "Mi perfil" },
]

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
      <path d="M10 2L4 5.5v4.5c0 3.8 2.7 7.3 6 8.5 3.3-1.2 6-4.7 6-8.5V5.5L10 2z" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M7.5 10.5l2 2 3.5-4" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  )
}

interface Props {
  expandido: boolean
  onToggle: () => void
}

export default function Sidebar({ expandido, onToggle }: Props) {
  return (
    <aside
      className={`flex flex-col h-screen border-r bg-background transition-all duration-200 shrink-0 ${
        expandido ? "w-48" : "w-14"
      }`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 h-14 px-3 border-b shrink-0">
        <ShieldCheckIcon />
        {expandido && (
          <div className="flex flex-col leading-tight overflow-hidden">
            <span className="text-sm font-semibold truncate">Validador</span>
            <span className="text-xs text-muted-foreground">HZ Sistemas</span>
          </div>
        )}
      </div>

      {/* Navegación */}
      <nav className="flex-1 py-2 px-2 space-y-0.5">
        {NAV_ITEMS.map((item) => (
          <div key={item.to} className="relative group/nav">
            <NavLink
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 py-2 rounded-md text-sm transition-colors ${
                  expandido ? "px-3 justify-start" : "px-0 justify-center"
                } ${
                  isActive
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`
              }
            >
              {item.icon}
              {expandido && <span className="truncate">{item.label}</span>}
            </NavLink>
            {!expandido && (
              <span className="pointer-events-none absolute left-full top-1/2 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md border bg-popover px-2 py-1 text-xs text-popover-foreground shadow-md opacity-0 transition-opacity group-hover/nav:opacity-100 z-50">
                {item.label}
              </span>
            )}
          </div>
        ))}
      </nav>

      {/* Navegación inferior (perfil, configuración, etc.) */}
      <div className="py-2 px-2 space-y-0.5 border-t">
        {NAV_BOTTOM.map((item) => (
          <div key={item.to} className="relative group/nav">
            <NavLink
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 py-2 rounded-md text-sm transition-colors ${
                  expandido ? "px-3 justify-start" : "px-0 justify-center"
                } ${
                  isActive
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`
              }
            >
              {item.icon}
              {expandido && <span className="truncate">{item.label}</span>}
            </NavLink>
            {!expandido && (
              <span className="pointer-events-none absolute left-full top-1/2 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md border bg-popover px-2 py-1 text-xs text-popover-foreground shadow-md opacity-0 transition-opacity group-hover/nav:opacity-100 z-50">
                {item.label}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Botón toggle */}
      <button
        onClick={onToggle}
        aria-label={expandido ? "Colapsar menú" : "Expandir menú"}
        className="flex items-center justify-center h-10 border-t text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
      >
        {expandido ? <ChevronLeftIcon /> : <ChevronRightIcon />}
      </button>
    </aside>
  )
}
