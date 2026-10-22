import { useState, useRef } from "react"
import { Outlet, NavLink } from "react-router-dom"
import Sidebar from "@/components/Sidebar"
import { CalendarIcon, HistorialIcon, UserIcon, ClientesIcon } from "@/components/icons"

const BOTTOM_NAV_ITEMS = [
  { to: "/",          end: true,  icon: <CalendarIcon />,  label: "Gestión del día" },
  { to: "/historial", end: false, icon: <HistorialIcon />, label: "Historial" },
  { to: "/clientes",  end: false, icon: <ClientesIcon />,  label: "Clientes" },
  { to: "/perfil",    end: false, icon: <UserIcon />,      label: "Perfil" },
]

export default function Layout() {
  const [expandido, setExpandido] = useState(false)
  const [navOculta, setNavOculta] = useState(false)
  const scrollPrevRef = useRef(0)

  function handleScroll(e: React.UIEvent<HTMLDivElement>) {
    const y = e.currentTarget.scrollTop
    if (y > 60) {
      setNavOculta(y > scrollPrevRef.current)
    } else {
      setNavOculta(false)
    }
    scrollPrevRef.current = y
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <div className="hidden md:flex">
        <Sidebar expandido={expandido} onToggle={() => setExpandido((e) => !e)} />
      </div>
      <div className="flex-1 overflow-y-auto pb-16 md:pb-0" onScroll={handleScroll}>
        <Outlet />
      </div>
      <nav className={`md:hidden fixed bottom-0 left-0 right-0 z-40 flex border-t bg-background transition-transform duration-300 ${navOculta ? "translate-y-full" : "translate-y-0"}`}>
        {BOTTOM_NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center justify-center gap-1 py-2 text-xs transition-colors ${
                isActive ? "text-primary" : "text-muted-foreground"
              }`
            }
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
