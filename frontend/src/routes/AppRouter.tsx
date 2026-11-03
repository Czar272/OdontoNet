import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";

import LoadingSpinner from "../components/basic/LoadingSpinner";
import ChangePasswordPage from "../pages/Account/ChangePasswordPage";
import ForgotPasswordPage from "../pages/Auth/ForgotPasswordPage";
import LoginPage from "../pages/Auth/LoginPage";
import ResetPasswordPage from "../pages/Auth/ResetPasswordPage";
import DashboardPage from "../pages/Dashboard/DashboardPage";
import ClinicPage from "../pages/Clinic/ClinicPage";
import DoctorsPage from "../pages/Doctors/DoctorsPage";
import PatientDetailPage from "../pages/Patients/PatientDetailPage";
import PatientsPage from "../pages/Patients/PatientsPage";
import UsersPage from "../pages/Users/UsersPage";

import MainLayout from "../layouts/MainLayout";
import ProtectedRoute from "./ProtectedRoute";
import RequirePermission from "./RequirePermission";

// La agenda carga el calendario (FullCalendar) en un archivo aparte:
// el resto de la aplicación no paga su peso.
const AgendaPage = lazy(() => import("../pages/Agenda/AgendaPage"));

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        {/* Protected routes */}
        <Route
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />

          <Route path="/account/password" element={<ChangePasswordPage />} />

          <Route
            path="/agenda"
            element={
              <RequirePermission permission="appointments:view">
                <Suspense fallback={<LoadingSpinner />}>
                  <AgendaPage />
                </Suspense>
              </RequirePermission>
            }
          />

          <Route
            path="/patients"
            element={
              <RequirePermission permission="patients:view">
                <PatientsPage />
              </RequirePermission>
            }
          />

          <Route
            path="/patients/:patientId"
            element={
              <RequirePermission permission="patients:view">
                <PatientDetailPage />
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
            path="/clinic"
            element={
              <RequirePermission permission="clinic:view">
                <ClinicPage />
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
