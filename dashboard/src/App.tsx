import { Navigate, Route, Routes } from "react-router-dom";
import Stats from "./pages/Stats";
import Alerts from "./pages/Alerts";
import Policies from "./pages/Policies";
import EmployeeRecord from "./pages/EmployeeRecord";
import EmployeeScanInvoice from "./pages/EmployeeScanInvoice";
import EmployeePurchases from "./pages/EmployeePurchases";
import EmployeeAlerts from "./pages/EmployeeAlerts";
import InvoiceReview from "./pages/InvoiceReview";
import PurchaseDetails from "./pages/PurchaseDetails";
import Audit from "./pages/Audit";
import Users from "./pages/Users";
import Settings from "./pages/Settings";
import Home from "./pages/Home";
import About from "./pages/About";
import Services from "./pages/Services";
import Contact from "./pages/Contact";
import AuthLogin from "./pages/AuthLogin";
import AuthRegister from "./pages/AuthRegister";
import { RequireAuth } from "./auth/RequireAuth";
import Layout from "./components/Layout";
import { MarketingLayout } from "./components/marketing/MarketingLayout";

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
      <Route path="/" element={<MarketingLayout><Home /></MarketingLayout>} />
      <Route path="/about" element={<MarketingLayout><About /></MarketingLayout>} />
      <Route path="/services" element={<MarketingLayout><Services /></MarketingLayout>} />
      <Route path="/contact" element={<MarketingLayout><Contact /></MarketingLayout>} />
      <Route path="/auth/login" element={<AuthLogin />} />
      <Route path="/auth/register" element={<AuthRegister />} />
      <Route path="/login" element={<Navigate to="/auth/login" replace />} />
      <Route path="/stats" element={<Protected><Stats /></Protected>} />
      <Route path="/alerts" element={<Protected><Alerts /></Protected>} />
      <Route path="/invoices" element={<Protected><InvoiceReview /></Protected>} />
      <Route path="/policies" element={<Protected><Policies /></Protected>} />
      <Route path="/employee/record" element={<Protected><EmployeeRecord /></Protected>} />
      <Route path="/employee/scan-invoice" element={<Protected><EmployeeScanInvoice /></Protected>} />
      <Route path="/employee/purchases" element={<Protected><EmployeePurchases /></Protected>} />
      <Route path="/employee/alerts" element={<Protected><EmployeeAlerts /></Protected>} />
      <Route path="/purchases/:id" element={<Protected><PurchaseDetails /></Protected>} />
      <Route path="/audit" element={<Protected><Audit /></Protected>} />
      <Route path="/users" element={<Protected><Users /></Protected>} />
      <Route path="/settings" element={<Protected><Settings /></Protected>} />
      <Route path="*" element={<Protected><Stats /></Protected>} />
    </Routes>
  );
}
