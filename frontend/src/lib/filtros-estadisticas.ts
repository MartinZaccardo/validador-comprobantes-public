import { type EstadoValidacion, type CanalValidacion } from "@/api/validaciones";

export interface FiltrosEstadisticasValues {
  estado: EstadoValidacion | "";
  canal: CanalValidacion | "";
  fecha_desde: string;
  fecha_hasta: string;
  fecha_mod_desde: string;
  fecha_mod_hasta: string;
  codigo_cliente: string;
  numero_operacion: string;
  usuario: string;
  banco: string;
}

export const FILTROS_INICIALES: FiltrosEstadisticasValues = {
  estado: "",
  canal: "",
  fecha_desde: "",
  fecha_hasta: "",
  fecha_mod_desde: "",
  fecha_mod_hasta: "",
  codigo_cliente: "",
  numero_operacion: "",
  usuario: "",
  banco: "",
};
