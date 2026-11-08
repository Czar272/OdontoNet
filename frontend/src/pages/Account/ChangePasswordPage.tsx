import { useState } from "react";
import toast from "react-hot-toast";

import Button from "../../components/basic/Button";
import Card from "../../components/basic/Card";
import Input from "../../components/basic/Input";
import PageHeader from "../../components/basic/PageHeader";
import { getApiErrorMessage } from "../../services/apiError";
import { changePasswordRequest } from "../../services/authService";
import { isRememberedSession, replaceToken } from "../../services/session";
import {
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
  validateNewPassword,
} from "../Auth/passwordForm";

/**
 * Cambio de la contraseña propia (ODON-54). El backend cierra las demás
 * sesiones y devuelve un token nuevo para seguir en esta.
 */
export default function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const validationError = validateNewPassword(password, confirmation);
    setError(validationError);
    if (validationError) return;

    setIsSubmitting(true);
    try {
      const { access_token } = await changePasswordRequest(
        currentPassword,
        password,
        isRememberedSession(),
      );
      replaceToken(access_token);
      setCurrentPassword("");
      setPassword("");
      setConfirmation("");
      toast.success("Contraseña actualizada. Se cerraron tus otras sesiones.");
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo cambiar la contraseña."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Cambiar contraseña"
        description="Al cambiarla se cierran tus sesiones en otros dispositivos."
      />

      <Card className="max-w-md">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            label="Contraseña actual"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />

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

          <p className="text-xs text-gray-500">
            Mínimo {MIN_PASSWORD_LENGTH} caracteres. Evita contraseñas comunes: usa una frase propia.
          </p>

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Guardando..." : "Cambiar contraseña"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
