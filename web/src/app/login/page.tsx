"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { login, signup } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Already logged in? Skip to dashboard
  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("bse_token")) {
      router.replace("/");
    }
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await signup(email, password, name);
      }
      router.replace("/");
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg).join(", "));
      } else {
        setError(detail || err.message || "Something went wrong");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0f172a] px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 text-center">
          <span className="text-5xl">📊</span>
          <h1 className="mt-3 text-2xl font-bold text-white">BSE Result Analyser</h1>
          <p className="mt-1 text-sm text-slate-400">AI-powered financial result analysis</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-slate-700 bg-[#1e293b] p-8">
          {/* Tab toggle */}
          <div className="mb-6 flex rounded-lg bg-slate-800 p-1">
            {(["login", "signup"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => { setMode(tab); setError(""); }}
                className={`flex-1 rounded-md py-2 text-sm font-medium transition ${
                  mode === tab
                    ? "bg-[#1e293b] text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {tab === "login" ? "Sign In" : "Create Account"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "signup" && (
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="John Doe"
                  className="w-full rounded-lg border border-slate-600 bg-slate-800 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
                />
              </div>
            )}

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-400">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-400">
                Password
              </label>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-red-900/30 border border-red-800 px-4 py-2.5 text-sm text-red-400">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-500 transition disabled:opacity-50"
            >
              {loading
                ? "Please wait…"
                : mode === "login"
                ? "Sign In"
                : "Create Account"}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-slate-600">
          BSE Result Analyser · All data from BSE India
        </p>
      </div>
    </div>
  );
}
