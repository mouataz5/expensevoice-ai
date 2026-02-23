import { useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const [email, setEmail] = useState("admin@company.com");
  const [password, setPassword] = useState("Admin12345!");
  const [error, setError] = useState<string | null>(null);
  const { setToken } = useAuth();
  const nav = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await api.post("/api/auth/login", { email, password });
      setToken(res.data.access_token);
      nav("/stats");
    } catch (err: unknown) {
      const axErr = err as { response?: { data?: { detail?: string } } };
      setError(
        axErr?.response?.data?.detail ?? "Login failed"
      );
    }
  };

  return (
    <div
      style={{
        maxWidth: 360,
        margin: "80px auto",
        fontFamily: "system-ui",
      }}
    >
      <h2>Dashboard Login</h2>
      <form onSubmit={submit}>
        <label>Email</label>
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{ width: "100%", marginBottom: 10, display: "block" }}
        />
        <label>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{ width: "100%", marginBottom: 10, display: "block" }}
        />
        {error && (
          <div style={{ color: "crimson", marginBottom: 10 }}>{error}</div>
        )}
        <button type="submit">Login</button>
      </form>
    </div>
  );
}
