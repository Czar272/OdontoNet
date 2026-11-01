import { useAuth } from "../../context/AuthContext";

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div>
      <h1 className="text-4xl font-bold mb-4">Inicio</h1>

      <p>
        Bienvenido a OdontoNet{user ? `, ${user.name}` : ""}.
        {user && <span className="text-gray-500"> {user.clinic.name}</span>}
      </p>
    </div>
  );
}
