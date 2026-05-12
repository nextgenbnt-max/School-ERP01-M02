import "@/index.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Classes from "@/pages/Classes";
import Subjects from "@/pages/Subjects";
import Students from "@/pages/Students";
import Employees from "@/pages/Employees";
import Fees from "@/pages/Fees";
import Salary from "@/pages/Salary";
import Accounts from "@/pages/Accounts";
import Homework from "@/pages/Homework";
import Attendance from "@/pages/Attendance";
import Timetable from "@/pages/Timetable";
import Exams from "@/pages/Exams";
import QuestionPapers from "@/pages/QuestionPapers";
import Messaging from "@/pages/Messaging";
import Reports from "@/pages/Reports";
import Settings from "@/pages/Settings";
import Users from "@/pages/Users";
import Behaviour from "@/pages/Behaviour";
import ParentDashboard from "@/pages/ParentDashboard";

function RoleRouter() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-slate-50">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === "parent") return <ParentDashboard />;
  return (
    <ProtectedRoute>
      <Layout />
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/parent" element={<RoleRouter />} />
          <Route element={<RoleRouter />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/classes" element={<Classes />} />
            <Route path="/subjects" element={<Subjects />} />
            <Route path="/students" element={<Students />} />
            <Route path="/employees" element={<Employees />} />
            <Route path="/fees" element={<Fees />} />
            <Route path="/salary" element={<Salary />} />
            <Route path="/accounts" element={<Accounts />} />
            <Route path="/homework" element={<Homework />} />
            <Route path="/attendance" element={<Attendance />} />
            <Route path="/timetable" element={<Timetable />} />
            <Route path="/exams" element={<Exams />} />
            <Route path="/question-papers" element={<QuestionPapers />} />
            <Route path="/messaging" element={<Messaging />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/users" element={<Users />} />
            <Route path="/behaviour" element={<Behaviour />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
