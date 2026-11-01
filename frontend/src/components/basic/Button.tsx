import clsx from "clsx";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger";
}

const Button: React.FC<ButtonProps> = ({
  children,
  variant = "primary",
  type = "button",
  className,
  ...props
}) => {
  return (
    <button
      type={type}
      className={clsx(
        "px-5 py-3 rounded-xl font-medium transition disabled:opacity-60 disabled:cursor-not-allowed",

        {
          "bg-gray-900 text-white hover:bg-gray-800": variant === "primary",

          "bg-gray-200 hover:bg-gray-300": variant === "secondary",

          "bg-red-600 text-white hover:bg-red-700": variant === "danger",
        },

        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
};

export default Button;
