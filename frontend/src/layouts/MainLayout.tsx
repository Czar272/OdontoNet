import clsx from "clsx";
import { KeyRound, LogOut } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { getNavigation } from "../config/navigation";
import { useAuth } from "../context/AuthContext";
import { ROLE_LABELS } from "../types/auth";

export default function MainLayout() {
  const { user, logout } = useAuth();
  const navItems = getNavigation(user?.role);

  return (
    <div className="min-h-screen flex bg-gray-100">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 bg-gray-900 text-white p-5 flex flex-col">
        <h1 className="text-2xl font-bold">OdontoNet</h1>

        {user && (
          <p
            className="text-sm text-gray-400 mt-1 mb-8"
            data-testid="clinic-name"
          >
            {user.clinic.name}
          </p>
        )}

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

        <div className="mt-auto flex flex-col gap-3">
          {user && (
            <div className="px-3" data-testid="current-user">
              <p className="text-sm font-medium truncate">{user.name}</p>
              <p className="text-xs text-gray-400">{ROLE_LABELS[user.role]}</p>
            </div>
          )}

          <NavLink
            to="/account/password"
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-2 px-3 py-2 rounded-lg transition",
                isActive
                  ? "bg-gray-800 text-white"
                  : "text-gray-300 hover:text-white hover:bg-gray-800",
              )
            }
          >
            <KeyRound size={18} />
            Cambiar contraseña
          </NavLink>

          <button
            type="button"
            onClick={logout}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800 transition"
          >
            <LogOut size={18} />
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 min-w-0 p-6">
        <Outlet />
      </main>
    </div>
  );
}
