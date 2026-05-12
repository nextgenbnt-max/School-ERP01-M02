import { useEffect, useState } from "react";
import api, { API_BASE, formatApiError } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Trash2, Pencil, Download, FileQuestion } from "lucide-react";

const EMPTY = {
  title: "", subject_id: "", class_id: "",
  duration_minutes: 60, total_marks: 100,
  instructions: "", questions: [{ text: "", marks: 5 }],
};

export default function QuestionPapers() {
  const [items, setItems] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);

  const load = async () => {
    const [q, c, s] = await Promise.all([api.get("/question-papers"), api.get("/classes"), api.get("/subjects")]);
    setItems(q.data);
    setClasses(c.data);
    setSubjects(s.data);
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (qp) => {
    setEditing(qp);
    setForm({ ...EMPTY, ...qp, subject_id: qp.subject_id || "", class_id: qp.class_id || "", questions: qp.questions || [] });
    setOpen(true);
  };

  const save = async () => {
    try {
      const payload = {
        ...form,
        subject_id: form.subject_id || null,
        class_id: form.class_id || null,
        duration_minutes: Number(form.duration_minutes),
        total_marks: Number(form.total_marks),
        questions: form.questions.map((q) => ({ text: q.text, marks: Number(q.marks) })),
      };
      if (editing) await api.put(`/question-papers/${editing.id}`, payload);
      else await api.post("/question-papers", payload);
      toast.success("Saved");
      setOpen(false);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const remove = async (qp) => {
    if (!confirm(`Delete "${qp.title}"?`)) return;
    await api.delete(`/question-papers/${qp.id}`);
    load();
  };

  const updQ = (i, k, v) => {
    const arr = [...form.questions];
    arr[i] = { ...arr[i], [k]: v };
    setForm({ ...form, questions: arr });
  };
  const addQ = () => setForm({ ...form, questions: [...form.questions, { text: "", marks: 5 }] });
  const rmQ = (i) => setForm({ ...form, questions: form.questions.filter((_, k) => k !== i) });

  const totalQMarks = form.questions.reduce((s, q) => s + (Number(q.marks) || 0), 0);

  return (
    <div data-testid="qp-page">
      <PageHeader
        title="Question Papers"
        description="Author exam papers, export PDFs for printing."
        actions={
          <Button onClick={openNew} className="bg-indigo-600 hover:bg-indigo-700" data-testid="new-qp-button">
            <Plus className="mr-1.5 h-4 w-4" /> New paper
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((qp) => (
          <div key={qp.id} className="surface p-5" data-testid={`qp-card-${qp.id}`}>
            <div className="flex items-start justify-between">
              <FileQuestion className="h-6 w-6 text-indigo-600" />
              <div className="flex">
                <Button size="sm" variant="ghost" onClick={() => window.open(`${API_BASE}/question-papers/${qp.id}/pdf`, "_blank")} data-testid={`qp-pdf-${qp.id}`}><Download className="h-4 w-4" /></Button>
                <Button size="sm" variant="ghost" onClick={() => openEdit(qp)}><Pencil className="h-4 w-4" /></Button>
                <Button size="sm" variant="ghost" onClick={() => remove(qp)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
              </div>
            </div>
            <h3 className="mt-3 font-display text-lg font-semibold tracking-tight text-slate-900">{qp.title}</h3>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {qp.class_name && <span className="badge-soft bg-indigo-50 text-indigo-700">{qp.class_name}</span>}
              {qp.subject_name && <span className="badge-soft bg-slate-100 text-slate-600">{qp.subject_name}</span>}
              <span className="badge-soft bg-amber-50 text-amber-700">{qp.duration_minutes} min</span>
              <span className="badge-soft bg-emerald-50 text-emerald-700">{qp.total_marks} marks</span>
            </div>
            <p className="mt-3 text-xs text-slate-500">{(qp.questions || []).length} question(s)</p>
          </div>
        ))}
        {items.length === 0 && (
          <div className="surface col-span-full p-12 text-center text-sm text-slate-500">No question papers yet. Create your first.</div>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl max-h-[88vh] overflow-y-auto" data-testid="qp-dialog">
          <DialogHeader><DialogTitle>{editing ? "Edit question paper" : "New question paper"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className="md:col-span-2"><Label>Title</Label><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="qp-title-input" /></div>
              <div>
                <Label>Class</Label>
                <Select value={form.class_id || "none"} onValueChange={(v) => setForm({ ...form, class_id: v === "none" ? "" : v })}>
                  <SelectTrigger data-testid="qp-class-select"><SelectValue placeholder="Select" /></SelectTrigger>
                  <SelectContent><SelectItem value="none">— None —</SelectItem>{classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label>Subject</Label>
                <Select value={form.subject_id || "none"} onValueChange={(v) => setForm({ ...form, subject_id: v === "none" ? "" : v })}>
                  <SelectTrigger data-testid="qp-subject-select"><SelectValue placeholder="Select" /></SelectTrigger>
                  <SelectContent><SelectItem value="none">— None —</SelectItem>{subjects.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label>Duration (min)</Label><Input type="number" value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })} /></div>
              <div><Label>Total marks</Label><Input type="number" value={form.total_marks} onChange={(e) => setForm({ ...form, total_marks: e.target.value })} /></div>
              <div className="md:col-span-2"><Label>Instructions</Label><Input value={form.instructions || ""} onChange={(e) => setForm({ ...form, instructions: e.target.value })} /></div>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <Label>Questions</Label>
                <span className="text-xs text-slate-500">{form.questions.length} · {totalQMarks} marks</span>
              </div>
              <div className="space-y-2">
                {form.questions.map((q, i) => (
                  <div key={i} className="flex gap-2">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">Q{i + 1}</div>
                    <Textarea rows={2} className="flex-1" value={q.text} onChange={(e) => updQ(i, "text", e.target.value)} data-testid={`qp-q-${i}`} />
                    <Input type="number" className="w-20" value={q.marks} onChange={(e) => updQ(i, "marks", e.target.value)} />
                    <Button size="sm" variant="ghost" onClick={() => rmQ(i)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                  </div>
                ))}
                <Button size="sm" variant="outline" onClick={addQ} data-testid="qp-add-question"><Plus className="mr-1 h-3.5 w-3.5" /> Add question</Button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-qp-button">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
