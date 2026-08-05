import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/store/auth";

// 页面级按需加载：新增业务页面不会继续推高终端首屏包体。
const Home = lazy(() => import("@/pages/Home"));
const Login = lazy(() => import("@/pages/Login"));
const Billing = lazy(() => import("@/pages/Billing"));
const Admin = lazy(() => import("@/pages/Admin"));
const Hall = lazy(() => import("@/pages/Hall"));

function PageLoader() {
  return (
    <div className="flex min-h-dvh items-center justify-center">
      <Loader2 size={22} className="animate-spin" style={{ color: "var(--accent)" }} />
    </div>
  );
}

// 路由守卫:未登录 → 跳登录页;bootstrap 未完成 → 显示加载态(避免闪烁)。
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 size={22} className="animate-spin" style={{ color: "var(--accent)" }} />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

// 管理员守卫:非 admin(或未登录)一律跳回首页。
function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 size={22} className="animate-spin" style={{ color: "var(--accent)" }} />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_admin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  const bootstrap = useAuth((s) => s.bootstrap);
  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return (
    <Router>
      <Suspense fallback={<PageLoader />}>
        <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Home />
            </RequireAuth>
          }
        />
        <Route
          path="/billing"
          element={
            <RequireAuth>
              <Billing />
            </RequireAuth>
          }
        />
        <Route
          path="/hall"
          element={
            <RequireAuth>
              <Hall />
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <Admin />
            </RequireAdmin>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Router>
  );
}
