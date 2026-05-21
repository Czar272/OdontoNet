interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

const Input: React.FC<InputProps> = ({ label, ...props }) => {
  return (
    <div className="flex flex-col gap-2">
      {label && <label className="font-medium text-sm">{label}</label>}

      <input
        className="
          border
          rounded-xl
          p-3
          outline-none
          focus:ring-2
          focus:ring-gray-900
        "
        {...props}
      />
    </div>
  );
};

export default Input;
