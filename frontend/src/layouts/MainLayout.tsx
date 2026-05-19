import { Outlet, Link } from "react-router-dom";

export default function MainLayout() {
  return (
    <div className="min-h-screen flex bg-gray-100">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 text-white p-5">
        <h1 className="text-2xl font-bold mb-10">OdontoNet</h1>

        <nav className="flex flex-col gap-4">
          <Link to="/dashboard" className="hover:text-blue-400 transition">
            Dashboard
          </Link>

          <Link to="/patients" className="hover:text-blue-400 transition">
            Patients
          </Link>
        </nav>
      </aside>

      {/* Content */}
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
