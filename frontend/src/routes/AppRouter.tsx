import { BrowserRouter, Routes, Route } from "react-router-dom";

import LoginPage from "../pages/Auth/LoginPage";
import DashboardPage from "../pages/Dashboard/DashboardPage";
import PatientsPage from "../pages/Patients/PatientsPage";

import MainLayout from "../layouts/MainLayout";

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<LoginPage />} />

        {/* Protected routes */}
        <Route element={<MainLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />

          <Route path="/patients" element={<PatientsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
