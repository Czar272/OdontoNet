import clsx from "clsx";

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

const Card: React.FC<CardProps> = ({ children, className }) => {
  return (
    <div className={clsx("bg-white rounded-2xl shadow-sm p-6", className)}>
      {children}
    </div>
  );
};

export default Card;
