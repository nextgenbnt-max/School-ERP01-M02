import { useEffect, useState } from "react";
import api from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Users, GraduationCap, UserCog, CreditCard, TrendingUp, CalendarCheck2 } from "lucide-react";
import { Link } from "react-router-dom";

function fmtMoney(n) {
  return "$" + Number(n || 0).toLocaleString();
}

const KPIS = [
  { key: "students", label: "Total Students", icon: Users, color: "bg-indigo-100 text-indigo-700", testid: "kpi-students" },
  { key: "employees", label: "Total Employees", icon: UserCog, color: "bg-emerald-100 text-emerald-700", testid: "kpi-employees" },
  { key: "classes", label: "Classes", icon: GraduationCap, color: "bg-amber-100 text-amber-700", testid: "kpi-classes" },
  { key: "attendance_pct", label: "Today's Attendance", icon: CalendarCheck2, color: "bg-sky-100 text-sky-700", testid: "kpi-attendance", suffix: "%" },
];

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [institute, setInstitute] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data));
    api.get("/institute").then((r) => setInstitute(r.data));
  }, []);

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        title={institute ? `Welcome to ${institute.name}` : "Dashboard"}
        description={institute?.tagline || "Snapshot of your institute today"}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {KPIS.map((k) => (
          <div key={k.key} className="kpi-card animate-fade-up" data-testid={k.testid}>
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">{k.label}</div>
                <div className="mt-2 font-display text-3xl font-bold tracking-tight text-slate-900" data-testid={`${k.testid}-value`}>
                  {stats ? `${stats[k.key] ?? 0}${k.suffix || ""}` : "—"}
                </div>
              </div>
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${k.color}`}>
                <k.icon className="h-5 w-5" />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="surface p-6 lg:col-span-2" data-testid="fees-summary-card">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">Fees overview</div>
              <h3 className="mt-1 font-display text-xl font-semibold tracking-tight text-slate-900">Cashflow this academic year</h3>
            </div>
            <CreditCard className="h-5 w-5 text-slate-400" />
          </div>
          <div className="mt-5 grid grid-cols-3 gap-4">
            <Stat label="Billed" value={fmtMoney(stats?.total_billed)} accent="text-slate-900" />
            <Stat label="Collected" value={fmtMoney(stats?.total_collected)} accent="text-emerald-600" />
            <Stat label="Pending invoices" value={stats?.pending_invoices ?? "—"} accent="text-amber-600" />
          </div>
          <Link to="/fees" className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-700" data-testid="fees-go-link">
            Manage fees <TrendingUp className="h-4 w-4" />
          </Link>
        </div>

        <div className="surface p-6" data-testid="recent-students-card">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">Recent admissions</div>
          <h3 className="mt-1 font-display text-xl font-semibold tracking-tight text-slate-900">New students</h3>
          <ul className="mt-4 space-y-3">
            {(stats?.recent_students || []).map((s) => (
              <li key={s.id} className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">
                  {s.name?.[0]}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-slate-800">{s.name}</div>
                  <div className="text-xs text-slate-500">{s.registration_number}</div>
                </div>
              </li>
            ))}
            {(!stats?.recent_students || stats.recent_students.length === 0) && (
              <li className="text-sm text-slate-500">No students yet.</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`mt-1 font-display text-2xl font-bold tracking-tight ${accent}`}>{value}</div>
    </div>
  );
}
