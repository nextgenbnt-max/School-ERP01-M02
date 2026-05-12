import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Pencil, Trash2 } from "lucide-react";

export default function Classes() {
  const [items, setItems] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", monthly_fee: 0, class_teacher_id: "", section: "A" });

  const load = async () => {
    const [c, e] = await Promise.all([api.get("/classes"), api.get("/employees", { params: { role: "teacher" } })]);
    setItems(c.data);
    setTeachers(e.data);
  };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ name: "", monthly_fee: 0, class_teacher_id: "", section: "A" });
    setOpen(true);
  };

  const openEdit = (c) => {
    setEditing(c);
    setForm({
      name: c.name || "",
      monthly_fee: c.monthly_fee || 0,
      class_teacher_id: c.class_teacher_id || "",
      section: c.section || "A",
    });
    setOpen(true);
  };

  const save = async () => {
    try {
      const payload = {
        ...form,
        monthly_fee: Number(form.monthly_fee),
        class_teacher_id: form.class_teacher_id || null,
      };
      if (editing) {
        await api.put(`/classes/${editing.id}`, payload);
        toast.success("Class updated");
      } else {
        await api.post("/classes", payload);
        toast.success("Class created");
      }
      setOpen(false);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const remove = async (c) => {
    if (!confirm(`Delete class "${c.name}"?`)) return;
    await api.delete(`/classes/${c.id}`);
    toast.success("Deleted");
    load();
  };

  return (
    <div data-testid="classes-page">
      <PageHeader
        title="Classes"
        description="Organise grades, assign class teachers and set monthly tuition."
        actions={
          <Button onClick={openNew} className="bg-indigo-600 hover:bg-indigo-700" data-testid="new-class-button">
            <Plus className="mr-1.5 h-4 w-4" /> New class
          </Button>
        }
      />

      <div className="surface overflow-hidden">
        <table className="w-full">
          <thead>
            <tr>
              <th className="data-table-th">Class</th>
              <th className="data-table-th">Section</th>
              <th className="data-table-th">Class teacher</th>
              <th className="data-table-th">Monthly fee</th>
              <th className="data-table-th">Students</th>
              <th className="data-table-th text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50" data-testid={`class-row-${c.id}`}>
                <td className="data-table-td font-medium text-slate-900">{c.name}</td>
                <td className="data-table-td">{c.section || "—"}</td>
                <td className="data-table-td">{c.class_teacher_name || <span className="text-slate-400">Unassigned</span>}</td>
                <td className="data-table-td">${Number(c.monthly_fee || 0).toLocaleString()}</td>
                <td className="data-table-td">{c.student_count}</td>
                <td className="data-table-td text-right">
                  <Button size="sm" variant="ghost" onClick={() => openEdit(c)} data-testid={`edit-class-${c.id}`}><Pencil className="h-4 w-4" /></Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(c)} data-testid={`delete-class-${c.id}`}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={6} className="px-6 py-12 text-center text-sm text-slate-500">No classes yet. Create your first one.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="class-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit class" : "New class"}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Label>Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Grade 6" data-testid="class-name-input" />
            </div>
            <div>
              <Label>Section</Label>
              <Input value={form.section} onChange={(e) => setForm({ ...form, section: e.target.value })} data-testid="class-section-input" />
            </div>
            <div>
              <Label>Monthly fee</Label>
              <Input type="number" value={form.monthly_fee} onChange={(e) => setForm({ ...form, monthly_fee: e.target.value })} data-testid="class-fee-input" />
            </div>
            <div className="col-span-2">
              <Label>Class teacher</Label>
              <Select value={form.class_teacher_id || "none"} onValueChange={(v) => setForm({ ...form, class_teacher_id: v === "none" ? "" : v })}>
                <SelectTrigger data-testid="class-teacher-select"><SelectValue placeholder="Select a teacher" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Unassigned</SelectItem>
                  {teachers.map((t) => (
                    <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-class-button">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
