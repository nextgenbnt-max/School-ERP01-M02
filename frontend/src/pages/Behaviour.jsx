import { useEffect, useMemo, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Plus, Trash2, Star, Smile, MessageSquare } from "lucide-react";

const BEHAVIOUR_CATS = ["Punctuality", "Respect", "Discipline", "Teamwork", "Honesty"];
const SKILL_CATS = ["Leadership", "Creativity", "Communication", "Problem-solving", "Initiative"];

export default function Behaviour() {
  const [students, setStudents] = useState([]);
  const [studentId, setStudentId] = useState("");
  const [classes, setClasses] = useState([]);
  const [classFilter, setClassFilter] = useState("all");
  const [behaviour, setBehaviour] = useState([]);
  const [skills, setSkills] = useState([]);
  const [obs, setObs] = useState([]);

  const [ratingOpen, setRatingOpen] = useState(false);
  const [ratingKind, setRatingKind] = useState("behaviour");
  const [ratingForm, setRatingForm] = useState({ category: "", rating: 4, remark: "" });

  const [obsOpen, setObsOpen] = useState(false);
  const [obsNote, setObsNote] = useState("");

  useEffect(() => {
    api.get("/classes").then((r) => setClasses(r.data));
  }, []);

  useEffect(() => {
    const params = {};
    if (classFilter !== "all") params.class_id = classFilter;
    api.get("/students", { params }).then((r) => {
      setStudents(r.data);
      if (r.data[0]) setStudentId(r.data[0].id);
      else setStudentId("");
    });
  }, [classFilter]);

  const loadRatings = async () => {
    if (!studentId) { setBehaviour([]); setSkills([]); setObs([]); return; }
    const [b, s, o] = await Promise.all([
      api.get("/behaviour-ratings", { params: { student_id: studentId } }),
      api.get("/skill-ratings", { params: { student_id: studentId } }),
      api.get("/observations", { params: { student_id: studentId } }),
    ]);
    setBehaviour(b.data);
    setSkills(s.data);
    setObs(o.data);
  };
  useEffect(() => { loadRatings(); }, [studentId]);

  const openRating = (kind) => {
    setRatingKind(kind);
    setRatingForm({ category: (kind === "behaviour" ? BEHAVIOUR_CATS : SKILL_CATS)[0], rating: 4, remark: "" });
    setRatingOpen(true);
  };

  const saveRating = async () => {
    try {
      const url = ratingKind === "behaviour" ? "/behaviour-ratings" : "/skill-ratings";
      await api.post(url, { student_id: studentId, ...ratingForm, rating: Number(ratingForm.rating) });
      toast.success("Rating saved");
      setRatingOpen(false);
      loadRatings();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const removeRating = async (kind, id) => {
    await api.delete(`/${kind}-ratings/${id}`);
    loadRatings();
  };

  const saveObs = async () => {
    if (!obsNote.trim()) return;
    try {
      await api.post("/observations", { student_id: studentId, note: obsNote });
      toast.success("Observation added");
      setObsOpen(false);
      setObsNote("");
      loadRatings();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const removeObs = async (id) => {
    await api.delete(`/observations/${id}`);
    loadRatings();
  };

  const avgFor = (rows, cat) => {
    const xs = rows.filter((r) => r.category === cat).map((r) => r.rating);
    if (!xs.length) return null;
    return Math.round((xs.reduce((s, x) => s + x, 0) / xs.length) * 10) / 10;
  };

  const student = useMemo(() => students.find((s) => s.id === studentId), [students, studentId]);

  return (
    <div data-testid="behaviour-page">
      <PageHeader
        title="Behaviour & Skills"
        description="Rate behaviours, skills, and record observations per student."
      />

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <Label className="text-xs">Class</Label>
          <Select value={classFilter} onValueChange={setClassFilter}>
            <SelectTrigger data-testid="beh-class-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All classes</SelectItem>
              {classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Student</Label>
          <Select value={studentId} onValueChange={setStudentId}>
            <SelectTrigger data-testid="beh-student-select"><SelectValue placeholder="Select student" /></SelectTrigger>
            <SelectContent>
              {students.map((s) => <SelectItem key={s.id} value={s.id}>{s.name} · {s.registration_number}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {student && (
        <>
          <div className="mb-4 surface p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-display text-xl font-semibold tracking-tight text-slate-900">{student.name}</h2>
                <div className="text-xs text-slate-500">{student.class_name || "—"} · {student.registration_number}</div>
              </div>
              <div className="text-xs text-slate-500">{behaviour.length + skills.length} ratings · {obs.length} observations</div>
            </div>
          </div>

          <Tabs defaultValue="behaviour">
            <TabsList>
              <TabsTrigger value="behaviour" data-testid="beh-tab-behaviour"><Smile className="mr-1.5 h-4 w-4" />Behaviours</TabsTrigger>
              <TabsTrigger value="skills" data-testid="beh-tab-skills"><Star className="mr-1.5 h-4 w-4" />Skills</TabsTrigger>
              <TabsTrigger value="observations" data-testid="beh-tab-observations"><MessageSquare className="mr-1.5 h-4 w-4" />Observations</TabsTrigger>
            </TabsList>

            <TabsContent value="behaviour" className="mt-4 space-y-4">
              <CategoryStrip cats={BEHAVIOUR_CATS} avgFor={(c) => avgFor(behaviour, c)} />
              <RatingList items={behaviour} kind="behaviour" onAdd={() => openRating("behaviour")} onDelete={(id) => removeRating("behaviour", id)} />
            </TabsContent>

            <TabsContent value="skills" className="mt-4 space-y-4">
              <CategoryStrip cats={SKILL_CATS} avgFor={(c) => avgFor(skills, c)} />
              <RatingList items={skills} kind="skill" onAdd={() => openRating("skill")} onDelete={(id) => removeRating("skill", id)} />
            </TabsContent>

            <TabsContent value="observations" className="mt-4 space-y-3">
              <div className="flex justify-end">
                <Button onClick={() => setObsOpen(true)} className="bg-indigo-600 hover:bg-indigo-700" data-testid="new-obs-button">
                  <Plus className="mr-1.5 h-4 w-4" /> Add observation
                </Button>
              </div>
              <div className="space-y-2">
                {obs.map((o) => (
                  <div key={o.id} className="surface p-4" data-testid={`obs-${o.id}`}>
                    <div className="flex items-start justify-between">
                      <div className="text-xs text-slate-500">{o.date}</div>
                      <Button size="sm" variant="ghost" onClick={() => removeObs(o.id)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                    </div>
                    <div className="mt-1 text-sm text-slate-700">{o.note}</div>
                  </div>
                ))}
                {obs.length === 0 && <div className="surface p-10 text-center text-sm text-slate-500">No observations yet.</div>}
              </div>
            </TabsContent>
          </Tabs>
        </>
      )}

      <Dialog open={ratingOpen} onOpenChange={setRatingOpen}>
        <DialogContent data-testid="rating-dialog">
          <DialogHeader><DialogTitle>Add {ratingKind} rating</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Category</Label>
              <Select value={ratingForm.category} onValueChange={(v) => setRatingForm({ ...ratingForm, category: v })}>
                <SelectTrigger data-testid="rating-cat-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(ratingKind === "behaviour" ? BEHAVIOUR_CATS : SKILL_CATS).map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Rating (1–5)</Label>
              <div className="mt-2 flex gap-1">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    onClick={() => setRatingForm({ ...ratingForm, rating: n })}
                    data-testid={`rating-star-${n}`}
                    className={`flex h-10 w-10 items-center justify-center rounded-lg border ${
                      ratingForm.rating >= n ? "border-amber-300 bg-amber-50 text-amber-600" : "border-slate-200 text-slate-300 hover:text-slate-400"
                    }`}
                  >
                    <Star className="h-5 w-5" fill={ratingForm.rating >= n ? "currentColor" : "none"} />
                  </button>
                ))}
              </div>
            </div>
            <div><Label>Remark (optional)</Label><Textarea rows={2} value={ratingForm.remark} onChange={(e) => setRatingForm({ ...ratingForm, remark: e.target.value })} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRatingOpen(false)}>Cancel</Button>
            <Button onClick={saveRating} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-rating-button">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={obsOpen} onOpenChange={setObsOpen}>
        <DialogContent data-testid="obs-dialog">
          <DialogHeader><DialogTitle>Add observation</DialogTitle></DialogHeader>
          <div><Label>Note</Label><Textarea rows={4} value={obsNote} onChange={(e) => setObsNote(e.target.value)} data-testid="obs-note-input" /></div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setObsOpen(false)}>Cancel</Button>
            <Button onClick={saveObs} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-obs-button">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CategoryStrip({ cats, avgFor }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
      {cats.map((c) => {
        const v = avgFor(c);
        return (
          <div key={c} className="surface p-3 text-center">
            <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">{c}</div>
            <div className="mt-1 font-display text-xl font-bold tracking-tight text-slate-900">{v == null ? "—" : `${v}/5`}</div>
          </div>
        );
      })}
    </div>
  );
}

function RatingList({ items, kind, onAdd, onDelete }) {
  return (
    <>
      <div className="flex justify-end">
        <Button onClick={onAdd} className="bg-indigo-600 hover:bg-indigo-700" data-testid={`add-${kind}-button`}>
          <Plus className="mr-1.5 h-4 w-4" /> Add rating
        </Button>
      </div>
      <div className="surface overflow-hidden">
        <table className="w-full">
          <thead><tr>
            <th className="data-table-th">Date</th>
            <th className="data-table-th">Category</th>
            <th className="data-table-th">Rating</th>
            <th className="data-table-th">Remark</th>
            <th className="data-table-th text-right"></th>
          </tr></thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} data-testid={`${kind}-row-${r.id}`}>
                <td className="data-table-td">{r.date}</td>
                <td className="data-table-td font-medium">{r.category}</td>
                <td className="data-table-td">
                  <div className="flex">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <Star key={n} className={`h-4 w-4 ${r.rating >= n ? "text-amber-500" : "text-slate-200"}`} fill={r.rating >= n ? "currentColor" : "none"} />
                    ))}
                  </div>
                </td>
                <td className="data-table-td text-slate-600">{r.remark || "—"}</td>
                <td className="data-table-td text-right">
                  <Button size="sm" variant="ghost" onClick={() => onDelete(r.id)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                </td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={5} className="px-6 py-10 text-center text-sm text-slate-500">No ratings yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
