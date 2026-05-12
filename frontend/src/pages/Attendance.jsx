import { useEffect, useState, useMemo } from "react";
import api, { formatApiError } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Save } from "lucide-react";

const STATUSES = [
  { value: "present", label: "Present", color: "bg-emerald-500 text-white" },
  { value: "absent", label: "Absent", color: "bg-red-500 text-white" },
  { value: "late", label: "Late", color: "bg-amber-500 text-white" },
  { value: "leave", label: "Leave", color: "bg-sky-500 text-white" },
];

export default function Attendance() {
  const [tab, setTab] = useState("student");
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [classes, setClasses] = useState([]);
  const [classId, setClassId] = useState("");
  const [students, setStudents] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [marks, setMarks] = useState({});

  useEffect(() => {
    api.get("/classes").then((r) => {
      setClasses(r.data);
      if (r.data[0]) setClassId(r.data[0].id);
    });
    api.get("/employees").then((r) => setEmployees(r.data));
  }, []);

  useEffect(() => {
    if (tab === "student" && classId) {
      api.get("/students", { params: { class_id: classId } }).then((r) => {
        setStudents(r.data);
        loadMarks("student", classId, r.data.map((s) => s.id));
      });
    } else if (tab === "employee") {
      loadMarks("employee", null, employees.map((e) => e.id));
    }
    // eslint-disable-next-line
  }, [tab, classId, date, employees.length]);

  const loadMarks = async (type, cid, ids) => {
    const params = { type, date };
    if (cid) params.class_id = cid;
    const { data } = await api.get("/attendance", { params });
    const m = {};
    for (const r of data) m[r.entity_id] = r.status;
    // default present for unmarked
    for (const id of ids) if (!m[id]) m[id] = "present";
    setMarks(m);
  };

  const setStatus = (id, status) => setMarks((m) => ({ ...m, [id]: status }));

  const list = tab === "student" ? students : employees;

  const summary = useMemo(() => {
    const s = { present: 0, absent: 0, late: 0, leave: 0 };
    for (const id of list.map((x) => x.id)) {
      const v = marks[id] || "present";
      s[v] = (s[v] || 0) + 1;
    }
    return s;
  }, [marks, list]);

  const save = async () => {
    try {
      const records = list.map((x) => ({ entity_id: x.id, status: marks[x.id] || "present" }));
      const payload = { type: tab, date, records, class_id: tab === "student" ? classId : null };
      await api.post("/attendance/mark", payload);
      toast.success(`Marked attendance for ${records.length} ${tab}s`);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  return (
    <div data-testid="attendance-page">
      <PageHeader
        title="Attendance"
        description="Mark daily attendance for students and employees."
        actions={
          <Button onClick={save} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-attendance-button">
            <Save className="mr-1.5 h-4 w-4" /> Save attendance
          </Button>
        }
      />

      <Tabs value={tab} onValueChange={setTab} className="mb-4">
        <TabsList>
          <TabsTrigger value="student" data-testid="att-tab-student">Students</TabsTrigger>
          <TabsTrigger value="employee" data-testid="att-tab-employee">Employees</TabsTrigger>
        </TabsList>

        <TabsContent value="student" className="mt-4">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end">
            <div>
              <Label className="text-xs">Class</Label>
              <Select value={classId} onValueChange={setClassId}>
                <SelectTrigger className="w-56" data-testid="att-class-select"><SelectValue placeholder="Select class" /></SelectTrigger>
                <SelectContent>{classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Date</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-44" data-testid="att-date-input" />
            </div>
            <SummaryStrip s={summary} />
          </div>
          <AttendanceTable list={students} marks={marks} setStatus={setStatus} type="student" />
        </TabsContent>

        <TabsContent value="employee" className="mt-4">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end">
            <div>
              <Label className="text-xs">Date</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-44" data-testid="att-date-input-emp" />
            </div>
            <SummaryStrip s={summary} />
          </div>
          <AttendanceTable list={employees} marks={marks} setStatus={setStatus} type="employee" />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SummaryStrip({ s }) {
  return (
    <div className="ml-auto flex gap-2 text-xs">
      <span className="badge-soft bg-emerald-100 text-emerald-700">Present {s.present}</span>
      <span className="badge-soft bg-red-100 text-red-700">Absent {s.absent}</span>
      <span className="badge-soft bg-amber-100 text-amber-700">Late {s.late}</span>
      <span className="badge-soft bg-sky-100 text-sky-700">Leave {s.leave}</span>
    </div>
  );
}

function AttendanceTable({ list, marks, setStatus, type }) {
  return (
    <div className="surface overflow-hidden">
      <table className="w-full">
        <thead>
          <tr>
            <th className="data-table-th">{type === "student" ? "Student" : "Employee"}</th>
            <th className="data-table-th">{type === "student" ? "Reg #" : "Role"}</th>
            <th className="data-table-th">Status</th>
          </tr>
        </thead>
        <tbody>
          {list.map((x) => (
            <tr key={x.id} data-testid={`att-row-${x.id}`}>
              <td className="data-table-td font-medium text-slate-900">{x.name}</td>
              <td className="data-table-td text-slate-600">{type === "student" ? x.registration_number : (x.role || "").replace(/_/g, " ")}</td>
              <td className="data-table-td">
                <div className="flex gap-1.5">
                  {STATUSES.map((s) => (
                    <button
                      key={s.value}
                      onClick={() => setStatus(x.id, s.value)}
                      data-testid={`att-${x.id}-${s.value}`}
                      className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                        marks[x.id] === s.value ? s.color + " shadow" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </td>
            </tr>
          ))}
          {list.length === 0 && (
            <tr><td colSpan={3} className="px-6 py-12 text-center text-sm text-slate-500">No records to mark.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
