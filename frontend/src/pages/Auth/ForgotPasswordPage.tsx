import { useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";

import Button from "../../components/basic/Button";
import Input from "../../components/basic/Input";
import { getApiErrorMessage } from "../../services/apiError";
import { requestPasswordReset } from "../../services/authService";
import AuthShell from "./AuthShell";

/** Solicitud del enlace de recuperación (ODON-54). */
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sentMessage, setSentMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const { message } = await requestPasswordReset(email);
      setSentMessage(message);
    } catch (error) {
      toast.error(getApiErrorMessage(error, "No se pudo enviar la solicitud."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Recuperar contraseña"
      description="Te enviaremos un enlace para elegir una contraseña nueva."
    >
      {sentMessage ? (
        <>
          <p role="status" className="text-sm text-gray-700 text-center">
            {sentMessage}
          </p>
          <p className="text-sm text-gray-600 text-center">
            Si no te llega, pide a administración que te asigne una contraseña nueva.
          </p>
        </>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            label="Correo electrónico"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <Button type="submit" disabled={isSubmitting} className="w-full">
            {isSubmitting ? "Enviando..." : "Enviar enlace"}
          </Button>
        </form>
      )}

      <Link
        to="/"
        className="text-sm text-center text-gray-600 hover:text-gray-900 underline"
      >
        Volver a iniciar sesión
      </Link>
    </AuthShell>
  );
}
