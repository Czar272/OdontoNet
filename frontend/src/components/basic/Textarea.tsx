import { useId } from "react";
import clsx from "clsx";

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

const Textarea: React.FC<TextareaProps> = ({
  label,
  id,
  className,
  rows = 2,
  ...props
}) => {
  const generatedId = useId();
  const textareaId = id ?? generatedId;

  return (
    <div className="flex flex-col gap-2">
      {label && (
        <label htmlFor={textareaId} className="font-medium text-sm">
          {label}
        </label>
      )}

      <textarea
        id={textareaId}
        rows={rows}
        className={clsx(
          "border rounded-xl p-3 outline-none focus:ring-2 focus:ring-gray-900 resize-y",
          "disabled:bg-gray-100 disabled:text-gray-500 disabled:border-gray-200 disabled:cursor-not-allowed",
          className,
        )}
        {...props}
      />
    </div>
  );
};

export default Textarea;
