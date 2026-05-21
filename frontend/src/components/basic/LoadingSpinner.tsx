const LoadingSpinner = () => {
  return (
    <div className="flex justify-center items-center py-10">
      <div
        className="
          w-10
          h-10
          border-4
          border-gray-300
          border-t-gray-900
          rounded-full
          animate-spin
        "
      />
    </div>
  );
};

export default LoadingSpinner;
