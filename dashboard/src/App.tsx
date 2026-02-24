import { Route, Routes } from "react-router-dom";
import Login from "./pages/Login";
import Stats from "./pages/Stats";
import Alerts from "./pages/Alerts";
import Policies from "./pages/Policies";
import { RequireAuth } from "./auth/RequireAuth";
import Layout from "./components/Layout";

function Protected({ children }: { children: JSX.Element }) {
  return (
    <RequireAuth>
      <Layout>{children}</Layout>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/stats" element={<Protected><Stats /></Protected>} />
      <Route path="/alerts" element={<Protected><Alerts /></Protected>} />
      <Route path="/policies" element={<Protected><Policies /></Protected>} />
      <Route path="*" element={<Protected><Stats /></Protected>} />
    </Routes>
  );
}
