import LoadingSpinner from "./LoadingSpinner";

/** Pantalla completa mientras se verifica la sesión: evita mostrar login o contenido protegido por error. */
const FullPageLoader = () => {
  return (
    <div
      role="status"
      aria-label="Cargando sesión"
      className="min-h-screen flex items-center justify-center bg-gray-100"
    >
      <LoadingSpinner />
    </div>
  );
};

export default FullPageLoader;
