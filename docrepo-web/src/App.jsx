import { Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/AppShell";
import ProtectedRoute from "./components/ProtectedRoute";
import Auth from "./pages/Auth";
import Search from "./pages/search";
import Upload from "./pages/Upload";
import DocumentView from "./pages/DocumentView";
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Auth />} />   {/* tabs include Sign in / Sign up */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppShell><Search /></AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/documents"
        element={
          <ProtectedRoute>
            <AppShell><Search /></AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/upload"
        element={
          <ProtectedRoute>
            <AppShell><Upload /></AppShell>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
      <Route path="/documents/:id" element={<AppShell><DocumentView /></AppShell>} />
    </Routes>
  );
}
