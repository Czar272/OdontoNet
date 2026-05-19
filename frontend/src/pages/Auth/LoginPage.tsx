export default function LoginPage() {
  return (
    <div className="h-screen flex items-center justify-center bg-gray-900">
      <div className="bg-white p-10 rounded-2xl shadow-lg w-96">
        <h1 className="text-3xl font-bold mb-6 text-center">OdontoNet</h1>

        <input
          type="email"
          placeholder="Email"
          className="w-full border p-3 rounded-lg mb-4"
        />

        <input
          type="password"
          placeholder="Password"
          className="w-full border p-3 rounded-lg mb-6"
        />

        <button className="w-full bg-gray-900 text-white p-3 rounded-lg hover:bg-gray-800">
          Login
        </button>
      </div>
    </div>
  );
}
