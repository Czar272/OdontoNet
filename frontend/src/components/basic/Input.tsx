import { useId } from "react";
import clsx from "clsx";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

const Input: React.FC<InputProps> = ({ label, id, className, ...props }) => {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div className="flex flex-col gap-2">
      {label && (
        <label htmlFor={inputId} className="font-medium text-sm">
          {label}
        </label>
      )}

      <input
        id={inputId}
        className={clsx(
          "border rounded-xl p-3 outline-none focus:ring-2 focus:ring-gray-900",
          "disabled:bg-gray-100 disabled:text-gray-500 disabled:border-gray-200 disabled:cursor-not-allowed",
          className,
        )}
        {...props}
      />
    </div>
  );
};

export default Input;
