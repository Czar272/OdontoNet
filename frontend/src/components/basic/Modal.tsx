import { X } from "lucide-react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

export default function Modal({
  isOpen,
  onClose,
  title,
  children,
}: ModalProps) {
  if (!isOpen) return null;

  return (
    <div
      className="
        fixed
        inset-0
        z-50
        flex
        items-center
        justify-center
      "
    >
      {/* Overlay */}
      <div
        onClick={onClose}
        className="
          absolute
          inset-0
          bg-black/50
          backdrop-blur-sm
        "
      />

      {/* Modal */}
      <div
        className="
          relative
          bg-white
          rounded-2xl
          shadow-xl
          w-full
          max-w-2xl
          p-6
          z-10
          animate-in
          fade-in
          zoom-in
        "
      >
        {/* Header */}
        <div
          className="
            flex
            items-center
            justify-between
            mb-6
          "
        >
          {title && <h2 className="text-2xl font-bold">{title}</h2>}
          <button
            onClick={onClose}
            className="
              p-2
              rounded-lg
              hover:bg-gray-100
              transition
            "
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div>{children}</div>
      </div>
    </div>
  );
}
