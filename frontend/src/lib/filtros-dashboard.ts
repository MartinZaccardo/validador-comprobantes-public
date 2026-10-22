import { type EstadoValidacion, type CanalValidacion } from "@/api/validaciones";

export interface FiltrosDashboardValues {
  estado: EstadoValidacion | "";
  canal: CanalValidacion | "";
  cliente: string;
  numero_operacion: string;
  usuario: string;
  banco: string;
}

export const FILTROS_INICIALES: FiltrosDashboardValues = {
  estado: "",
  canal: "",
  cliente: "",
  numero_operacion: "",
  usuario: "",
  banco: "",
};
