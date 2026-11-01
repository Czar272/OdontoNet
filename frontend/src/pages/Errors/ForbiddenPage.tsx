import { ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

export default function ForbiddenPage() {
  return (
    <div className="flex flex-col items-center justify-center text-center py-20 gap-4">
      <ShieldAlert size={48} className="text-gray-400" aria-hidden="true" />

      <h1 className="text-3xl font-bold">Acceso denegado</h1>

      <p className="text-gray-500 max-w-md">
        Tu rol no tiene permiso para ver esta sección. Si crees que es un error,
        contacta a la administración de tu clínica.
      </p>

      <Link
        to="/dashboard"
        className="px-5 py-3 rounded-xl font-medium bg-gray-900 text-white hover:bg-gray-800 transition"
      >
        Volver al inicio
      </Link>
    </div>
  );
}
