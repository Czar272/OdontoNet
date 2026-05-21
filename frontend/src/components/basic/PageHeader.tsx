interface PageHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  action,
}) => {
  return (
    <div className="flex justify-between items-center mb-8">
      <div>
        <h1 className="text-4xl font-bold">{title}</h1>

        {description && <p className="text-gray-500 mt-2">{description}</p>}
      </div>

      {action}
    </div>
  );
};

export default PageHeader;
