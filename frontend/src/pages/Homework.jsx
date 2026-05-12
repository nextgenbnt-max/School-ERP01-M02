import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, BookOpen, Calendar, Paperclip } from "lucide-react";

const EMPTY = {
  class_id: "", subject_id: "", title: "", description: "",
  assigned_date: new Date().toISOString().slice(0, 10),
  due_date: new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
  attachment_url: "",
};

export default function Homework() {
  const [items, setItems] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [classFilter, setClassFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);

  const load = async () => {
    const params = {};
    if (classFilter !== "all") params.class_id = classFilter;
    const [h, c, s] = await Promise.all([
      api.get("/homework", { params }),
      api.get("/classes"),
      api.get("/subjects"),
    ]);
    setItems(h.data);
    setClasses(c.data);
    setSubjects(s.data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [classFilter]);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (h) => { setEditing(h); setForm({ ...EMPTY, ...h, subject_id: h.subject_id || "" }); setOpen(true); };

  const save = async () => {
    try {
      const payload = { ...form, subject_id: form.subject_id || null };
      if (editing) await api.put(`/homework/${editing.id}`, payload);
      else await api.post("/homework", payload);
      toast.success("Saved");
      setOpen(false);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const remove = async (h) => {
    if (!confirm(`Delete homework "${h.title}"?`)) return;
    await api.delete(`/homework/${h.id}`);
    toast.success("Deleted");
    load();
  };

  const today = new Date().toISOString().slice(0, 10);

  return (
    <div data-testid="homework-page">
      <PageHeader
        title="Homework"
        description="Assign and track homework by class and subject."
        actions={
          <Button onClick={openNew} className="bg-indigo-600 hover:bg-indigo-700" data-testid="new-homework-button">
            <Plus className="mr-1.5 h-4 w-4" /> Assign homework
          </Button>
        }
      />

      <div className="mb-4 flex gap-3">
        <Select value={classFilter} onValueChange={setClassFilter}>
          <SelectTrigger className="w-56" data-testid="homework-class-filter"><SelectValue placeholder="All classes" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All classes</SelectItem>
            {classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((h) => {
          const overdue = h.due_date < today;
          return (
            <div key={h.id} className="surface p-5" data-testid={`homework-card-${h.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-indigo-600" />
                  <span className="badge-soft bg-indigo-50 text-indigo-700">{h.class_name || "—"}</span>
                  {h.subject_name && <span className="badge-soft bg-slate-100 text-slate-600">{h.subject_name}</span>}
                </div>
                <div className="flex">
                  <Button size="sm" variant="ghost" onClick={() => openEdit(h)}><Pencil className="h-4 w-4" /></Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(h)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                </div>
              </div>
              <h3 className="mt-3 font-display text-lg font-semibold tracking-tight text-slate-900">{h.title}</h3>
              <p className="mt-1 line-clamp-3 text-sm text-slate-600">{h.description}</p>
              <div className="mt-4 flex items-center gap-3 text-xs">
                <span className="inline-flex items-center gap-1 text-slate-500"><Calendar className="h-3.5 w-3.5" /> Assigned {h.assigned_date}</span>
                <span className={`inline-flex items-center gap-1 font-medium ${overdue ? "text-red-600" : "text-emerald-600"}`}>
                  Due {h.due_date}{overdue ? " · Overdue" : ""}
                </span>
              </div>
              {h.attachment_url && (
                <a href={h.attachment_url} target="_blank" rel="noopener" className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700">
                  <Paperclip className="h-3.5 w-3.5" /> Attachment
                </a>
              )}
            </div>
          );
        })}
        {items.length === 0 && (
          <div className="surface col-span-full p-12 text-center text-sm text-slate-500">No homework assigned yet.</div>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-xl" data-testid="homework-dialog">
          <DialogHeader><DialogTitle>{editing ? "Edit homework" : "Assign homework"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Class</Label>
                <Select value={form.class_id} onValueChange={(v) => setForm({ ...form, class_id: v })}>
                  <SelectTrigger data-testid="hw-class-select"><SelectValue placeholder="Select" /></SelectTrigger>
                  <SelectContent>{classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label>Subject (optional)</Label>
                <Select value={form.subject_id || "none"} onValueChange={(v) => setForm({ ...form, subject_id: v === "none" ? "" : v })}>
                  <SelectTrigger data-testid="hw-subject-select"><SelectValue placeholder="Select" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">— None —</SelectItem>
                    {subjects.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div><Label>Title</Label><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="hw-title-input" /></div>
            <div><Label>Description</Label><Textarea rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="hw-desc-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Assigned date</Label><Input type="date" value={form.assigned_date} onChange={(e) => setForm({ ...form, assigned_date: e.target.value })} /></div>
              <div><Label>Due date</Label><Input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} data-testid="hw-due-input" /></div>
            </div>
            <div><Label>Attachment URL (optional)</Label><Input value={form.attachment_url} onChange={(e) => setForm({ ...form, attachment_url: e.target.value })} placeholder="https://…" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-homework-button">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
