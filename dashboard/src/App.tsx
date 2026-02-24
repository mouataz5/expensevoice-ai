import { Route, Routes } from "react-router-dom";
import Login from "./pages/Login";
import Stats from "./pages/Stats";
import Alerts from "./pages/Alerts";
import Policies from "./pages/Policies";
import EmployeeRecord from "./pages/EmployeeRecord";
import EmployeePurchases from "./pages/EmployeePurchases";
import EmployeeAlerts from "./pages/EmployeeAlerts";
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
      <Route path="/employee/record" element={<Protected><EmployeeRecord /></Protected>} />
      <Route path="/employee/purchases" element={<Protected><EmployeePurchases /></Protected>} />
      <Route path="/employee/alerts" element={<Protected><EmployeeAlerts /></Protected>} />
      <Route path="*" element={<Protected><Stats /></Protected>} />
    </Routes>
  );
}
