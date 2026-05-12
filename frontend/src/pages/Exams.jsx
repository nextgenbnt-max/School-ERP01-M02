import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Plus, Trash2, Save, GraduationCap } from "lucide-react";

export default function Exams() {
  const [exams, setExams] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [selectedExam, setSelectedExam] = useState(null);
  const [examSubjects, setExamSubjects] = useState([]);

  const [examOpen, setExamOpen] = useState(false);
  const [examForm, setExamForm] = useState({ name: "", class_id: "", start_date: "", end_date: "" });
  const [subOpen, setSubOpen] = useState(false);
  const [subForm, setSubForm] = useState({ subject_id: "", exam_date: "", max_marks: 100, pass_marks: 35 });

  const [students, setStudents] = useState([]);
  const [marks, setMarks] = useState({}); // {studentId: {subjectId: marks}}

  const load = async () => {
    const [e, c, s] = await Promise.all([api.get("/exams"), api.get("/classes"), api.get("/subjects")]);
    setExams(e.data);
    setClasses(c.data);
    setSubjects(s.data);
    if (!selectedExam && e.data[0]) setSelectedExam(e.data[0]);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  useEffect(() => {
    if (!selectedExam) return;
    Promise.all([
      api.get(`/exams/${selectedExam.id}/subjects`),
      api.get(`/students`, { params: { class_id: selectedExam.class_id } }),
      api.get(`/exams/${selectedExam.id}/results`),
    ]).then(([es, st, rs]) => {
      setExamSubjects(es.data);
      setStudents(st.data);
      const m = {};
      for (const r of rs.data) {
        m[r.student_id] = m[r.student_id] || {};
        m[r.student_id][r.subject_id] = r.marks;
      }
      setMarks(m);
    });
  }, [selectedExam]);

  const createExam = async () => {
    try {
      const { data } = await api.post("/exams", examForm);
      toast.success("Exam created");
      setExamOpen(false);
      setExamForm({ name: "", class_id: "", start_date: "", end_date: "" });
      const r = await api.get("/exams");
      setExams(r.data);
      setSelectedExam(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const addSubject = async () => {
    try {
      await api.post(`/exams/${selectedExam.id}/subjects`, { ...subForm, max_marks: Number(subForm.max_marks), pass_marks: Number(subForm.pass_marks) });
      toast.success("Subject added");
      setSubOpen(false);
      setSubForm({ subject_id: "", exam_date: "", max_marks: 100, pass_marks: 35 });
      const r = await api.get(`/exams/${selectedExam.id}/subjects`);
      setExamSubjects(r.data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const removeSubject = async (es) => {
    await api.delete(`/exams/${selectedExam.id}/subjects/${es.id}`);
    const r = await api.get(`/exams/${selectedExam.id}/subjects`);
    setExamSubjects(r.data);
  };

  const deleteExam = async () => {
    if (!confirm(`Delete exam "${selectedExam.name}"?`)) return;
    await api.delete(`/exams/${selectedExam.id}`);
    toast.success("Deleted");
    setSelectedExam(null);
    load();
  };

  const setMark = (sid, subId, v) => {
    setMarks((m) => ({ ...m, [sid]: { ...(m[sid] || {}), [subId]: v } }));
  };

  const saveMarks = async () => {
    const payload = [];
    for (const sid of Object.keys(marks)) {
      for (const subId of Object.keys(marks[sid])) {
        const val = marks[sid][subId];
        if (val !== "" && val !== null && val !== undefined) {
          payload.push({ student_id: sid, subject_id: subId, marks: Number(val) });
        }
      }
    }
    if (payload.length === 0) return toast.error("No marks to save");
    try {
      const { data } = await api.post(`/exams/${selectedExam.id}/results`, payload);
      toast.success(`Saved ${data.saved} marks`);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  return (
    <div data-testid="exams-page">
      <PageHeader
        title="Exams"
        description="Schedule exams, manage subjects per exam and enter marks."
        actions={
          <Button onClick={() => setExamOpen(true)} className="bg-indigo-600 hover:bg-indigo-700" data-testid="new-exam-button">
            <Plus className="mr-1.5 h-4 w-4" /> New exam
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <div className="surface p-4 lg:col-span-1" data-testid="exams-list">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-slate-500">All exams</div>
          <div className="space-y-1">
            {exams.map((e) => (
              <button
                key={e.id}
                onClick={() => setSelectedExam(e)}
                data-testid={`exam-item-${e.id}`}
                className={`flex w-full items-start gap-2 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                  selectedExam?.id === e.id ? "bg-indigo-50 text-indigo-700" : "hover:bg-slate-50"
                }`}
              >
                <GraduationCap className="h-4 w-4 shrink-0 opacity-70" />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{e.name}</div>
                  <div className="text-xs text-slate-500">{e.class_name} · {e.subject_count} subjects</div>
                </div>
              </button>
            ))}
            {exams.length === 0 && <div className="px-3 py-6 text-center text-xs text-slate-500">No exams yet.</div>}
          </div>
        </div>

        <div className="lg:col-span-3">
          {selectedExam ? (
            <Tabs defaultValue="subjects">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="font-display text-xl font-semibold tracking-tight text-slate-900">{selectedExam.name}</h2>
                  <div className="text-xs text-slate-500">{selectedExam.class_name} · {selectedExam.start_date} → {selectedExam.end_date}</div>
                </div>
                <Button onClick={deleteExam} variant="outline" size="sm" className="text-red-600"><Trash2 className="mr-1 h-4 w-4" />Delete exam</Button>
              </div>
              <TabsList>
                <TabsTrigger value="subjects" data-testid="exam-tab-subjects">Subjects</TabsTrigger>
                <TabsTrigger value="marks" data-testid="exam-tab-marks">Enter marks</TabsTrigger>
              </TabsList>

              <TabsContent value="subjects" className="mt-4">
                <div className="mb-3 flex justify-end">
                  <Button size="sm" onClick={() => setSubOpen(true)} className="bg-indigo-600 hover:bg-indigo-700" data-testid="add-exam-subject-button">
                    <Plus className="mr-1 h-4 w-4" /> Add subject
                  </Button>
                </div>
                <div className="surface overflow-hidden">
                  <table className="w-full">
                    <thead><tr>
                      <th className="data-table-th">Subject</th>
                      <th className="data-table-th">Exam date</th>
                      <th className="data-table-th">Max</th>
                      <th className="data-table-th">Pass</th>
                      <th className="data-table-th text-right">Action</th>
                    </tr></thead>
                    <tbody>
                      {examSubjects.map((es) => (
                        <tr key={es.id} data-testid={`es-row-${es.id}`}>
                          <td className="data-table-td font-medium text-slate-900">{es.subject_name}</td>
                          <td className="data-table-td">{es.exam_date}</td>
                          <td className="data-table-td">{es.max_marks}</td>
                          <td className="data-table-td">{es.pass_marks}</td>
                          <td className="data-table-td text-right">
                            <Button size="sm" variant="ghost" onClick={() => removeSubject(es)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                          </td>
                        </tr>
                      ))}
                      {examSubjects.length === 0 && (
                        <tr><td colSpan={5} className="px-6 py-10 text-center text-sm text-slate-500">No subjects added yet.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </TabsContent>

              <TabsContent value="marks" className="mt-4">
                <div className="mb-3 flex justify-end">
                  <Button onClick={saveMarks} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-marks-button">
                    <Save className="mr-1 h-4 w-4" /> Save marks
                  </Button>
                </div>
                <div className="surface overflow-x-auto">
                  <table className="w-full min-w-[700px]">
                    <thead><tr>
                      <th className="data-table-th">Student</th>
                      {examSubjects.map((es) => (
                        <th key={es.id} className="data-table-th">{es.subject_name}<div className="text-[10px] font-normal text-slate-400">/{es.max_marks}</div></th>
                      ))}
                    </tr></thead>
                    <tbody>
                      {students.map((s) => (
                        <tr key={s.id} data-testid={`marks-row-${s.id}`}>
                          <td className="data-table-td font-medium">{s.name}</td>
                          {examSubjects.map((es) => (
                            <td key={es.id} className="data-table-td">
                              <Input
                                type="number"
                                value={marks[s.id]?.[es.subject_id] ?? ""}
                                onChange={(e) => setMark(s.id, es.subject_id, e.target.value)}
                                className="h-8 w-20 text-sm"
                                data-testid={`mark-${s.id}-${es.subject_id}`}
                              />
                            </td>
                          ))}
                        </tr>
                      ))}
                      {students.length === 0 && (
                        <tr><td colSpan={examSubjects.length + 1} className="px-6 py-10 text-center text-sm text-slate-500">No students in this class.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </TabsContent>
            </Tabs>
          ) : (
            <div className="surface p-12 text-center text-sm text-slate-500">Select or create an exam to manage subjects and marks.</div>
          )}
        </div>
      </div>

      <Dialog open={examOpen} onOpenChange={setExamOpen}>
        <DialogContent data-testid="exam-dialog">
          <DialogHeader><DialogTitle>New exam</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Name</Label><Input value={examForm.name} onChange={(e) => setExamForm({ ...examForm, name: e.target.value })} data-testid="exam-name-input" /></div>
            <div>
              <Label>Class</Label>
              <Select value={examForm.class_id} onValueChange={(v) => setExamForm({ ...examForm, class_id: v })}>
                <SelectTrigger data-testid="exam-class-select"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>{classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Start</Label><Input type="date" value={examForm.start_date} onChange={(e) => setExamForm({ ...examForm, start_date: e.target.value })} /></div>
              <div><Label>End</Label><Input type="date" value={examForm.end_date} onChange={(e) => setExamForm({ ...examForm, end_date: e.target.value })} /></div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExamOpen(false)}>Cancel</Button>
            <Button onClick={createExam} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-exam-button">Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={subOpen} onOpenChange={setSubOpen}>
        <DialogContent data-testid="exam-subject-dialog">
          <DialogHeader><DialogTitle>Add subject to exam</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Subject</Label>
              <Select value={subForm.subject_id} onValueChange={(v) => setSubForm({ ...subForm, subject_id: v })}>
                <SelectTrigger data-testid="es-subject-select"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>{subjects.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Exam date</Label><Input type="date" value={subForm.exam_date} onChange={(e) => setSubForm({ ...subForm, exam_date: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Max marks</Label><Input type="number" value={subForm.max_marks} onChange={(e) => setSubForm({ ...subForm, max_marks: e.target.value })} /></div>
              <div><Label>Pass marks</Label><Input type="number" value={subForm.pass_marks} onChange={(e) => setSubForm({ ...subForm, pass_marks: e.target.value })} /></div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSubOpen(false)}>Cancel</Button>
            <Button onClick={addSubject} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-es-button">Add</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
