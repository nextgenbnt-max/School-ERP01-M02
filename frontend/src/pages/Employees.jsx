import { useEffect, useState } from "react";
import api, { API_BASE, formatApiError } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Search, FileDown } from "lucide-react";

const ROLES = ["principal", "vice_principal", "teacher", "accountant", "librarian", "support_staff"];

const EMPTY = {
  name: "", contact: "", role: "teacher", picture_url: "", joining_date: "",
  monthly_salary: 0, spouse_name: "", pan: "", gender: "", experience: "",
  email: "", dob: "", education: "", address: "",
};

export default function Employees() {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("all");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);

  const load = async () => {
    const params = {};
    if (q) params.q = q;
    if (role && role !== "all") params.role = role;
    const { data } = await api.get("/employees", { params });
    setItems(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [q, role]);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (e) => { setEditing(e); setForm({ ...EMPTY, ...e }); setOpen(true); };

  const save = async () => {
    try {
      const payload = { ...form, monthly_salary: Number(form.monthly_salary || 0) };
      if (editing) await api.put(`/employees/${editing.id}`, payload);
      else await api.post("/employees", payload);
      toast.success("Saved");
      setOpen(false);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const remove = async (e) => {
    if (!confirm(`Delete employee "${e.name}"?`)) return;
    await api.delete(`/employees/${e.id}`);
    toast.success("Deleted");
    load();
  };

  return (
    <div data-testid="employees-page">
      <PageHeader
        title="Employees"
        description={`${items.length} staff member${items.length === 1 ? "" : "s"}`}
        actions={
          <Button onClick={openNew} className="bg-indigo-600 hover:bg-indigo-700" data-testid="new-employee-button">
            <Plus className="mr-1.5 h-4 w-4" /> Add employee
          </Button>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, email, contact…" className="pl-9" data-testid="employees-search-input" />
        </div>
        <Select value={role} onValueChange={setRole}>
          <SelectTrigger className="w-full sm:w-56" data-testid="employees-role-filter"><SelectValue placeholder="All roles" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            {ROLES.map((r) => <SelectItem key={r} value={r}>{r.replace(/_/g, " ")}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="surface overflow-hidden">
        <table className="w-full">
          <thead>
            <tr>
              <th className="data-table-th">Employee</th>
              <th className="data-table-th">Role</th>
              <th className="data-table-th">Email</th>
              <th className="data-table-th">Contact</th>
              <th className="data-table-th">Salary</th>
              <th className="data-table-th text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((e) => (
              <tr key={e.id} className="hover:bg-slate-50" data-testid={`employee-row-${e.id}`}>
                <td className="data-table-td">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-sm font-semibold text-emerald-700">
                      {e.name?.[0]}
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">{e.name}</div>
                      <div className="text-xs text-slate-500">{e.experience || "—"}</div>
                    </div>
                  </div>
                </td>
                <td className="data-table-td"><span className="badge-soft bg-slate-100 capitalize text-slate-700">{(e.role || "").replace(/_/g, " ")}</span></td>
                <td className="data-table-td">{e.email || "—"}</td>
                <td className="data-table-td">{e.contact || "—"}</td>
                <td className="data-table-td">${Number(e.monthly_salary || 0).toLocaleString()}</td>
                <td className="data-table-td text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button size="sm" variant="ghost" data-testid={`employee-docs-${e.id}`} title="Documents"><FileDown className="h-4 w-4" /></Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => window.open(`${API_BASE}/employees/${e.id}/job-letter.pdf`, "_blank")} data-testid={`doc-job-letter-${e.id}`}>Job letter</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => window.open(`${API_BASE}/employees/${e.id}/id-card.pdf`, "_blank")} data-testid={`doc-staff-id-${e.id}`}>Staff ID card</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button size="sm" variant="ghost" onClick={() => openEdit(e)} data-testid={`edit-employee-${e.id}`}><Pencil className="h-4 w-4" /></Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(e)} data-testid={`delete-employee-${e.id}`}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={6} className="px-6 py-16 text-center text-sm text-slate-500">No employees match your filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl" data-testid="employee-dialog">
          <DialogHeader><DialogTitle>{editing ? "Edit employee" : "New employee"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <Field label="Name"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="employee-name-input" /></Field>
            <Field label="Role">
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger data-testid="employee-role-select"><SelectValue /></SelectTrigger>
                <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r}>{r.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
            <Field label="Email"><Input value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
            <Field label="Contact"><Input value={form.contact || ""} onChange={(e) => setForm({ ...form, contact: e.target.value })} /></Field>
            <Field label="Monthly salary"><Input type="number" value={form.monthly_salary} onChange={(e) => setForm({ ...form, monthly_salary: e.target.value })} /></Field>
            <Field label="Joining date"><Input type="date" value={form.joining_date || ""} onChange={(e) => setForm({ ...form, joining_date: e.target.value })} /></Field>
            <Field label="DOB"><Input type="date" value={form.dob || ""} onChange={(e) => setForm({ ...form, dob: e.target.value })} /></Field>
            <Field label="Gender">
              <Select value={form.gender || ""} onValueChange={(v) => setForm({ ...form, gender: v })}>
                <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Male">Male</SelectItem><SelectItem value="Female">Female</SelectItem><SelectItem value="Other">Other</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field label="PAN"><Input value={form.pan || ""} onChange={(e) => setForm({ ...form, pan: e.target.value })} /></Field>
            <Field label="Education"><Input value={form.education || ""} onChange={(e) => setForm({ ...form, education: e.target.value })} /></Field>
            <Field label="Experience"><Input value={form.experience || ""} onChange={(e) => setForm({ ...form, experience: e.target.value })} /></Field>
            <Field label="Spouse name"><Input value={form.spouse_name || ""} onChange={(e) => setForm({ ...form, spouse_name: e.target.value })} /></Field>
            <Field label="Picture URL"><Input value={form.picture_url || ""} onChange={(e) => setForm({ ...form, picture_url: e.target.value })} /></Field>
            <div className="col-span-2 md:col-span-3">
              <Label className="text-xs font-medium text-slate-600">Address</Label>
              <Textarea rows={2} value={form.address || ""} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-employee-button">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <Label className="text-xs font-medium text-slate-600">{label}</Label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
