import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";

import LoginPage from "../pages/Auth/LoginPage";
import DashboardPage from "../pages/Dashboard/DashboardPage";
import DoctorsPage from "../pages/Doctors/DoctorsPage";
import PatientsPage from "../pages/Patients/PatientsPage";
import UsersPage from "../pages/Users/UsersPage";

import MainLayout from "../layouts/MainLayout";
import ProtectedRoute from "./ProtectedRoute";
import RequirePermission from "./RequirePermission";

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<LoginPage />} />

        {/* Protected routes */}
        <Route
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />

          <Route
            path="/patients"
            element={
              <RequirePermission permission="patients:view">
                <PatientsPage />
              </RequirePermission>
            }
          />

          <Route
            path="/doctors"
            element={
              <RequirePermission permission="doctors:view">
                <DoctorsPage />
              </RequirePermission>
            }
          />

          <Route
            path="/users"
            element={
              <RequirePermission permission="users:manage">
                <UsersPage />
              </RequirePermission>
            }
          />
        </Route>

        {/* Rutas desconocidas: login o dashboard según la sesión */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
