import Button from "./Button";
import Modal from "./Modal";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: React.ReactNode;
  confirmLabel: string;
  variant?: "primary" | "danger";
  isPending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Confirmación accesible sin diálogos del navegador (window.confirm). */
export default function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel,
  variant = "primary",
  isPending = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal isOpen={isOpen} onClose={onCancel} title={title}>
      <div className="text-gray-700">{message}</div>

      <div className="mt-6 flex justify-end gap-3">
        <Button variant="secondary" onClick={onCancel} disabled={isPending}>
          Cancelar
        </Button>

        <Button variant={variant} onClick={onConfirm} disabled={isPending}>
          {isPending ? "Guardando..." : confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
