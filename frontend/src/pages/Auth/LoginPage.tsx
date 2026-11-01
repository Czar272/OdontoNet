import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import Button from "../../components/basic/Button";
import FullPageLoader from "../../components/basic/FullPageLoader";
import Input from "../../components/basic/Input";
import { useAuth } from "../../context/AuthContext";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { status, login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  if (status === "loading") {
    return <FullPageLoader />;
  }

  if (status === "authenticated") {
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setIsSubmitting(true);

    const success = await login(email, password);

    setIsSubmitting(false);

    if (success) {
      navigate(from, { replace: true });
    } else {
      setPassword("");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 p-4">
      <form
        onSubmit={handleSubmit}
        className="bg-white p-10 rounded-2xl shadow-lg w-full max-w-sm flex flex-col gap-4"
      >
        <h1 className="text-3xl font-bold mb-2 text-center">OdontoNet</h1>

        <Input
          label="Correo electrónico"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <Input
          label="Contraseña"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <Button type="submit" disabled={isSubmitting} className="w-full mt-2">
          {isSubmitting ? "Ingresando..." : "Iniciar sesión"}
        </Button>
      </form>
    </div>
  );
}
