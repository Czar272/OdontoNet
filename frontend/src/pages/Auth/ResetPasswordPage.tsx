import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";

import Button from "../../components/basic/Button";
import Input from "../../components/basic/Input";
import { getApiErrorMessage } from "../../services/apiError";
import { confirmPasswordReset } from "../../services/authService";
import AuthShell from "./AuthShell";
import {
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
  validateNewPassword,
} from "./passwordForm";

/** Nueva contraseña desde el enlace del correo (ODON-54). */
export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  // El token se lee una vez y se quita de la barra de direcciones.
  const [token] = useState(() => searchParams.get("token") ?? "");

  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (searchParams.has("token")) {
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const validationError = validateNewPassword(password, confirmation);
    setError(validationError);
    if (validationError) return;

    setIsSubmitting(true);
    try {
      const { message } = await confirmPasswordReset(token, password);
      toast.success(message);
      navigate("/", { replace: true });
    } catch (err) {
      setError(
        getApiErrorMessage(err, "No se pudo restablecer la contraseña."),
      );
      setIsSubmitting(false);
    }
  }

  if (!token) {
    return (
      <AuthShell title="Restablecer contraseña">
        <p role="alert" className="text-sm text-red-600 text-center">
          El enlace no es válido o ya expiró. Solicita uno nuevo.
        </p>
        <Link
          to="/forgot-password"
          className="text-sm text-center text-gray-600 hover:text-gray-900 underline"
        >
          Solicitar un enlace nuevo
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Restablecer contraseña"
      description={`Elige una contraseña nueva de al menos ${MIN_PASSWORD_LENGTH} caracteres.`}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Nueva contraseña"
          type="password"
          autoComplete="new-password"
          maxLength={MAX_PASSWORD_LENGTH}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <Input
          label="Confirmar contraseña"
          type="password"
          autoComplete="new-password"
          maxLength={MAX_PASSWORD_LENGTH}
          value={confirmation}
          onChange={(e) => setConfirmation(e.target.value)}
          required
        />

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Guardando..." : "Guardar contraseña"}
        </Button>
      </form>

      <Link
        to="/forgot-password"
        className="text-sm text-center text-gray-600 hover:text-gray-900 underline"
      >
        Solicitar un enlace nuevo
      </Link>
    </AuthShell>
  );
}
