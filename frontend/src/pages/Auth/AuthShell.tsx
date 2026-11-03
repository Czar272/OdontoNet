interface AuthShellProps {
  title: string;
  description?: string;
  children: React.ReactNode;
}

/** Marco de las pantallas públicas: inicio de sesión y recuperación. */
export default function AuthShell({
  title,
  description,
  children,
}: AuthShellProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 p-4">
      <div className="bg-white p-10 rounded-2xl shadow-lg w-full max-w-sm flex flex-col gap-4">
        <h1 className="text-3xl font-bold mb-2 text-center">{title}</h1>

        {description && (
          <p className="text-sm text-gray-600 text-center -mt-2">
            {description}
          </p>
        )}

        {children}
      </div>
    </div>
  );
}
