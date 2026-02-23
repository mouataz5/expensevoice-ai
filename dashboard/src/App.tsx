import { Link, Route, Routes } from "react-router-dom";
import Login from "./pages/Login";
import Stats from "./pages/Stats";
import Alerts from "./pages/Alerts";
import Policies from "./pages/Policies";
import { RequireAuth } from "./auth/RequireAuth";
import { useAuth } from "./auth/AuthContext";

export default function App() {
  const { token, logout } = useAuth();

  return (
    <div>
      <nav
        style={{
          padding: 12,
          borderBottom: "1px solid #ddd",
          display: "flex",
          gap: 12,
        }}
      >
        <Link to="/stats">Stats</Link>
        <Link to="/alerts">Alerts</Link>
        <Link to="/policies">Policies</Link>
        <div style={{ marginLeft: "auto" }}>
          {token ? (
            <button onClick={logout}>Logout</button>
          ) : (
            <Link to="/login">Login</Link>
          )}
        </div>
      </nav>

      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/stats"
          element={
            <RequireAuth>
              <Stats />
            </RequireAuth>
          }
        />
        <Route
          path="/alerts"
          element={
            <RequireAuth>
              <Alerts />
            </RequireAuth>
          }
        />
        <Route
          path="/policies"
          element={
            <RequireAuth>
              <Policies />
            </RequireAuth>
          }
        />
        <Route
          path="*"
          element={
            <RequireAuth>
              <Stats />
            </RequireAuth>
          }
        />
      </Routes>
    </div>
  );
}
