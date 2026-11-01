import clsx from "clsx";
import { LogOut } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "../context/AuthContext";

const navItems = [
  { to: "/dashboard", label: "Inicio" },
  { to: "/patients", label: "Pacientes" },
];

export default function MainLayout() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  function handleLogout() {
    logout();
    // Evita que datos en caché de una sesión queden visibles en la siguiente
    queryClient.clear();
    navigate("/", { replace: true });
  }

  return (
    <div className="min-h-screen flex bg-gray-100">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 bg-gray-900 text-white p-5 flex flex-col">
        <h1 className="text-2xl font-bold mb-10">OdontoNet</h1>

        <nav className="flex flex-col gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  "px-3 py-2 rounded-lg transition",
                  isActive
                    ? "bg-gray-800 text-white"
                    : "text-gray-300 hover:text-white hover:bg-gray-800",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <button
          type="button"
          onClick={handleLogout}
          className="mt-auto flex items-center gap-2 px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800 transition"
        >
          <LogOut size={18} />
          Cerrar sesión
        </button>
      </aside>

      {/* Content */}
      <main className="flex-1 min-w-0 p-6">
        <Outlet />
      </main>
    </div>
  );
}
