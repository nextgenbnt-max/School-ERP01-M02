import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  LayoutDashboard, Settings, GraduationCap, BookOpenText, Users, UserCog,
  CreditCard, CalendarCheck2, MessageSquare, BarChart3, LogOut, School,
  Banknote, BookOpen, Calculator, Clock, ClipboardCheck, FileQuestion,
  Smile, ShieldCheck,
} from "lucide-react";

const NAV = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard", testid: "nav-dashboard", end: true },
  { to: "/classes", icon: GraduationCap, label: "Classes", testid: "nav-classes" },
  { to: "/subjects", icon: BookOpenText, label: "Subjects", testid: "nav-subjects" },
  { to: "/students", icon: Users, label: "Students", testid: "nav-students" },
  { to: "/employees", icon: UserCog, label: "Employees", testid: "nav-employees" },
  { to: "/timetable", icon: Clock, label: "Timetable", testid: "nav-timetable" },
  { to: "/attendance", icon: CalendarCheck2, label: "Attendance", testid: "nav-attendance" },
  { to: "/homework", icon: BookOpen, label: "Homework", testid: "nav-homework" },
  { to: "/behaviour", icon: Smile, label: "Behaviour & Skills", testid: "nav-behaviour" },
  { to: "/exams", icon: ClipboardCheck, label: "Exams", testid: "nav-exams" },
  { to: "/question-papers", icon: FileQuestion, label: "Question Papers", testid: "nav-qp" },
  { to: "/fees", icon: CreditCard, label: "Fees", testid: "nav-fees" },
  { to: "/salary", icon: Banknote, label: "Salary", testid: "nav-salary" },
  { to: "/accounts", icon: Calculator, label: "Accounts", testid: "nav-accounts" },
  { to: "/messaging", icon: MessageSquare, label: "Messaging", testid: "nav-messaging" },
  { to: "/reports", icon: BarChart3, label: "Reports", testid: "nav-reports" },
  { to: "/users", icon: ShieldCheck, label: "Users", testid: "nav-users" },
  { to: "/settings", icon: Settings, label: "Settings", testid: "nav-settings" },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <aside className="fixed left-0 top-0 z-40 hidden h-screen w-64 flex-col border-r border-slate-200 bg-white lg:flex" data-testid="sidebar">
      <div className="flex items-center gap-2.5 border-b border-slate-200 px-5 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white">
          <School className="h-5 w-5" />
        </div>
        <div>
          <div className="font-display text-lg font-bold leading-none tracking-tight text-slate-900">Greenwood</div>
          <div className="mt-0.5 text-[11px] font-medium uppercase tracking-widest text-slate-400">School ERP</div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            data-testid={item.testid}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? "sidebar-link-active" : ""}`
            }
          >
            <item.icon className="h-4 w-4" />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-slate-200 p-3">
        <div className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 font-semibold text-indigo-700">
            {user?.name?.[0]?.toUpperCase() || "A"}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-slate-900" data-testid="sidebar-user-name">{user?.name}</div>
            <div className="truncate text-xs capitalize text-slate-500">{user?.role}</div>
          </div>
          <button
            onClick={logout}
            data-testid="logout-button"
            title="Sign out"
            className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-white hover:text-red-600"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
