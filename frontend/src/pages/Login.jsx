import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { School } from "lucide-react";

const LOGIN_BG = "https://static.prod-images.emergentagent.com/jobs/2cc00928-cb3f-41d8-ad15-0a128cb4c443/images/cff8753364e1280eae17f8fa4fb031627663f77b89762344ce8617e1815bbc94.png";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("admin@school.com");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2" data-testid="login-page">
      <div className="flex items-center justify-center bg-white px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-10 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-600 text-white">
              <School className="h-5 w-5" />
            </div>
            <div>
              <div className="font-display text-xl font-bold tracking-tight text-slate-900">Greenwood</div>
              <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">School ERP</div>
            </div>
          </div>

          <h1 className="font-display text-3xl font-bold tracking-tight text-slate-900">Welcome back</h1>
          <p className="mt-2 text-sm text-slate-500">Sign in to manage your institute.</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            <div>
              <Label htmlFor="email" className="text-xs font-semibold uppercase tracking-wider text-slate-600">Email</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="login-email-input"
                className="mt-1.5 h-11"
                placeholder="you@school.com"
              />
            </div>
            <div>
              <Label htmlFor="password" className="text-xs font-semibold uppercase tracking-wider text-slate-600">Password</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                data-testid="login-password-input"
                className="mt-1.5 h-11"
              />
            </div>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" data-testid="login-error">
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={submitting}
              data-testid="login-submit-button"
              className="h-11 w-full bg-indigo-600 hover:bg-indigo-700"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs leading-relaxed text-slate-600">
            <div className="font-semibold text-slate-700">Demo credentials</div>
            <div className="mt-1">Admin · <code className="text-slate-800">admin@school.com</code> / <code>admin123</code></div>
            <div>Teacher · <code className="text-slate-800">teacher@school.com</code> / <code>teacher123</code></div>
          </div>
        </div>
      </div>

      <div className="relative hidden overflow-hidden bg-indigo-600 lg:block">
        <img src={LOGIN_BG} alt="Education" className="absolute inset-0 h-full w-full object-cover opacity-90" />
        <div className="absolute inset-0 bg-gradient-to-tr from-indigo-700/70 via-indigo-600/30 to-transparent" />
        <div className="absolute bottom-12 left-12 right-12 text-white">
          <div className="text-xs font-semibold uppercase tracking-widest text-indigo-200">A modern school OS</div>
          <h2 className="mt-3 font-display text-4xl font-bold leading-tight tracking-tight">
            Run admissions, fees, attendance and parent comms from one place.
          </h2>
          <p className="mt-3 max-w-md text-sm text-indigo-100">
            Greenwood gives administrators, teachers and parents a clean, unified view of everything that matters.
          </p>
        </div>
      </div>
    </div>
  );
}
