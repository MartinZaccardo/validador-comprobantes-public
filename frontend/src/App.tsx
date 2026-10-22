import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { Toaster } from "sonner"
import Layout from "@/components/Layout"
import Dashboard from "./pages/Dashboard"
import Login from "./pages/Login"
import Perfil from "./pages/Perfil"
import Admins from "./pages/Admins"
import Historial from "./pages/Historial"
import Clientes from "./pages/Clientes"
import { estaAutenticado } from "./api/auth"

function AuthLayout() {
  if (!estaAutenticado()) return <Navigate to="/login" replace />
  return <Layout />
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="bottom-right" richColors />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<AuthLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/perfil" element={<Perfil />} />
          <Route path="/admins" element={<Admins />} />
          <Route path="/historial" element={<Historial />} />
          <Route path="/clientes" element={<Clientes />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
