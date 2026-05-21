import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useEffect, useState } from "react";

export default function LoginPage() {
  const navigate = useNavigate();

  const { login } = useAuth();

  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");

  async function handleLogin() {
    const succes = await login(email, password);

    if (succes) {
      navigate("/dashboard");
    } else {
      alert("Invalid credentials");
    }
  }

  useEffect(() => {
    console.warn("Email: ", email, "Password: ", password);
  }, [email, password]);

  return (
    <div className="h-screen flex items-center justify-center bg-gray-900">
      <div className="bg-white p-10 rounded-2xl shadow-lg w-96">
        <h1 className="text-3xl font-bold mb-6 text-center">OdontoNet</h1>

        <input
          type="email"
          placeholder="Email"
          className="w-full border p-3 rounded-lg mb-4"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <input
          type="password"
          placeholder="Password"
          className="w-full border p-3 rounded-lg mb-6"
          value={password}
          onChange={(p) => setPassword(p.target.value)}
        />

        <button
          className="w-full bg-gray-900 text-white p-3 rounded-lg hover:bg-gray-800"
          onClick={handleLogin}
        >
          Login
        </button>
      </div>
    </div>
  );
}
