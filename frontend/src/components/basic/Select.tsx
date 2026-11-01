import { useId } from "react";
import clsx from "clsx";

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
}

const Select: React.FC<SelectProps> = ({
  label,
  id,
  className,
  children,
  ...props
}) => {
  const generatedId = useId();
  const selectId = id ?? generatedId;

  return (
    <div className="flex flex-col gap-2">
      {label && (
        <label htmlFor={selectId} className="font-medium text-sm">
          {label}
        </label>
      )}

      <select
        id={selectId}
        className={clsx(
          "border rounded-xl p-3 bg-white outline-none focus:ring-2 focus:ring-gray-900",
          className,
        )}
        {...props}
      >
        {children}
      </select>
    </div>
  );
};

export default Select;
