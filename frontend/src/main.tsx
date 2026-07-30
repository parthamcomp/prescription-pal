import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import App from "./App";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import Register from "./pages/Register";
import "./index.css";

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="app-loading">Loading…</div>;
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

// Keep App mounted (rather than swapping routes) while /profile is open, so
// chat history and other in-progress state (upload draft, records list)
// survive the round trip instead of resetting on remount.
function Shell() {
  const onProfile = useLocation().pathname === "/profile";
  return (
    <>
      <div style={{ display: onProfile ? "none" : "contents" }}>
        <App />
      </div>
      {onProfile && <Profile />}
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/*"
            element={
              <Protected>
                <Shell />
              </Protected>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>
);
