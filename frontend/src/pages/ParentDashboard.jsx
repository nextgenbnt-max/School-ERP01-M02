import { useEffect, useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { School, LogOut, Link as LinkIcon, CalendarCheck2, CreditCard, BookOpen, Loader2 } from "lucide-react";

const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function ParentDashboard() {
  const { user, logout } = useAuth();
  const [children, setChildren] = useState([]);
  const [selected, setSelected] = useState(null);
  const [summary, setSummary] = useState(null);
  const [linkOpen, setLinkOpen] = useState(false);
  const [regNo, setRegNo] = useState("");
  const [payingInvoiceId, setPayingInvoiceId] = useState(null);
  const [polling, setPolling] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const loadChildren = async () => {
    const { data } = await api.get("/parent/children");
    setChildren(data);
    if (data[0] && !selected) setSelected(data[0]);
    if (!data.length) setSelected(null);
  };

  const refreshSummary = useCallback(async () => {
    if (!selected) { setSummary(null); return; }
    const { data } = await api.get(`/parent/children/${selected.id}/summary`);
    setSummary(data);
  }, [selected]);

  useEffect(() => { loadChildren(); }, []);
  useEffect(() => { refreshSummary(); }, [refreshSummary]);

  // Handle Stripe return: ?session_id=... — poll status
  useEffect(() => {
    const sessionId = searchParams.get("session_id");
    if (!sessionId) return;
    setPolling(true);
    let attempts = 0;
    const max = 8;
    const tick = async () => {
      attempts += 1;
      try {
        const { data } = await api.get(`/payments/checkout/status/${sessionId}`);
        if (data.payment_status === "paid") {
          toast.success("Payment successful — invoice marked as paid.");
          setPolling(false);
          // clear session_id from URL
          searchParams.delete("session_id");
          setSearchParams(searchParams, { replace: true });
          await refreshSummary();
          return;
        }
        if (data.status === "expired") {
          toast.error("Payment session expired. Please try again.");
          setPolling(false);
          searchParams.delete("session_id");
          setSearchParams(searchParams, { replace: true });
          return;
        }
        if (attempts >= max) {
          toast.message("Still processing — refresh in a moment to see latest status.");
          setPolling(false);
          searchParams.delete("session_id");
          setSearchParams(searchParams, { replace: true });
          return;
        }
        setTimeout(tick, 2000);
      } catch (e) {
        setPolling(false);
      }
    };
    tick();
    // eslint-disable-next-line
  }, []);

  const linkChild = async () => {
    try {
      await api.post("/parent/link-child", { registration_number: regNo });
      toast.success("Child linked");
      setLinkOpen(false);
      setRegNo("");
      loadChildren();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const payInvoice = async (invoice) => {
    setPayingInvoiceId(invoice.id);
    try {
      const { data } = await api.post("/parent/fees/invoices/checkout", {
        invoice_id: invoice.id,
        origin_url: window.location.origin,
      });
      window.location.href = data.url;
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
      setPayingInvoiceId(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50" data-testid="parent-dashboard">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white"><School className="h-5 w-5" /></div>
            <div>
              <div className="font-display text-lg font-bold tracking-tight text-slate-900">Parent Portal</div>
              <div className="text-xs text-slate-500">Welcome, {user?.name}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setLinkOpen(true)} data-testid="parent-link-button">
              <LinkIcon className="mr-1.5 h-4 w-4" /> Link a child
            </Button>
            <Button variant="ghost" size="sm" onClick={logout} data-testid="parent-logout-button"><LogOut className="h-4 w-4" /></Button>
          </div>
        </div>
      </header>

      {polling && (
        <div className="bg-indigo-50 text-indigo-700 text-sm" data-testid="parent-payment-polling">
          <div className="mx-auto max-w-6xl px-4 py-2.5 sm:px-6 flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" /> Checking payment status…
          </div>
        </div>
      )}

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
        {children.length === 0 ? (
          <div className="surface p-12 text-center">
            <h2 className="font-display text-xl font-bold tracking-tight text-slate-900">No children linked yet</h2>
            <p className="mt-2 text-sm text-slate-500">Use the "Link a child" button above with your child's registration number to get started.</p>
            <Button onClick={() => setLinkOpen(true)} className="mt-5 bg-indigo-600 hover:bg-indigo-700" data-testid="parent-empty-link-button">
              <LinkIcon className="mr-1.5 h-4 w-4" /> Link a child
            </Button>
          </div>
        ) : (
          <>
            <div className="mb-6 flex flex-wrap gap-2">
              {children.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelected(c)}
                  data-testid={`parent-child-${c.id}`}
                  className={`flex items-center gap-3 rounded-xl border px-4 py-2.5 text-left transition-colors ${
                    selected?.id === c.id ? "border-indigo-300 bg-indigo-50" : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">{c.name?.[0]}</div>
                  <div>
                    <div className="text-sm font-semibold text-slate-900">{c.name}</div>
                    <div className="text-xs text-slate-500">{c.class_name || "—"} · {c.registration_number}</div>
                  </div>
                </button>
              ))}
            </div>

            {summary && (
              <div className="space-y-6 animate-fade-up" data-testid="parent-summary">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <SummaryCard icon={CalendarCheck2} label="This month's attendance" color="bg-indigo-100 text-indigo-700" testid="parent-att-card">
                    <div className="mt-1 font-display text-3xl font-bold tracking-tight text-slate-900">{summary.attendance.pct}%</div>
                    <div className="mt-2 flex gap-2 text-xs">
                      <span className="badge-soft bg-emerald-100 text-emerald-700">P {summary.attendance.present}</span>
                      <span className="badge-soft bg-red-100 text-red-700">A {summary.attendance.absent}</span>
                      <span className="badge-soft bg-amber-100 text-amber-700">L {summary.attendance.late}</span>
                    </div>
                  </SummaryCard>
                  <SummaryCard icon={CreditCard} label="Fees this year" color="bg-emerald-100 text-emerald-700" testid="parent-fees-card">
                    <div className="mt-1 font-display text-3xl font-bold tracking-tight text-slate-900">${summary.fees.outstanding.toLocaleString()}</div>
                    <div className="mt-1 text-xs text-slate-500">Outstanding · Paid ${summary.fees.total_paid.toLocaleString()}</div>
                  </SummaryCard>
                  <SummaryCard icon={BookOpen} label="Upcoming homework" color="bg-amber-100 text-amber-700" testid="parent-hw-card">
                    <div className="mt-1 font-display text-3xl font-bold tracking-tight text-slate-900">{summary.upcoming_homework.length}</div>
                    <div className="mt-1 text-xs text-slate-500">Due in the next days</div>
                  </SummaryCard>
                </div>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <div className="surface p-5">
                    <h3 className="font-display text-lg font-semibold tracking-tight text-slate-900">Fee invoices</h3>
                    <div className="mt-3 space-y-2">
                      {summary.fees.invoices.map((i) => {
                        const outstanding = Number(i.amount) - Number(i.paid_amount || 0);
                        return (
                          <div key={i.id} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2.5 text-sm" data-testid={`parent-fee-row-${i.id}`}>
                            <div className="min-w-0">
                              <div className="font-medium text-slate-900">{MONTHS[i.month]} {i.year}</div>
                              <div className="text-xs text-slate-500">${Number(i.amount).toLocaleString()} · paid ${Number(i.paid_amount || 0).toLocaleString()}</div>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className={`badge-soft capitalize ${i.status === "paid" ? "bg-emerald-100 text-emerald-700" : i.status === "partial" ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>{i.status}</span>
                              {i.status !== "paid" && (
                                <Button size="sm" onClick={() => payInvoice(i)} disabled={payingInvoiceId === i.id} className="bg-indigo-600 hover:bg-indigo-700" data-testid={`parent-pay-${i.id}`}>
                                  {payingInvoiceId === i.id ? <Loader2 className="h-4 w-4 animate-spin" /> : `Pay $${outstanding.toLocaleString()}`}
                                </Button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                      {summary.fees.invoices.length === 0 && <div className="text-sm text-slate-500">No invoices yet.</div>}
                    </div>
                  </div>

                  <div className="surface p-5">
                    <h3 className="font-display text-lg font-semibold tracking-tight text-slate-900">Upcoming homework</h3>
                    <div className="mt-3 space-y-2">
                      {summary.upcoming_homework.map((h) => (
                        <div key={h.id} className="rounded-lg border border-slate-100 px-3 py-2.5" data-testid={`parent-hw-row-${h.id}`}>
                          <div className="flex items-center justify-between">
                            <div className="text-sm font-medium text-slate-900">{h.title}</div>
                            <span className="text-xs font-medium text-emerald-700">Due {h.due_date}</span>
                          </div>
                          <div className="mt-0.5 text-xs text-slate-500">{h.subject_name || ""}</div>
                          {h.description && <div className="mt-1 line-clamp-2 text-xs text-slate-600">{h.description}</div>}
                        </div>
                      ))}
                      {summary.upcoming_homework.length === 0 && <div className="text-sm text-slate-500">No upcoming homework.</div>}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>

      <Dialog open={linkOpen} onOpenChange={setLinkOpen}>
        <DialogContent data-testid="parent-link-dialog">
          <DialogHeader><DialogTitle>Link your child's account</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-500">Enter the registration number that the school issued for your child.</p>
          <div className="mt-3">
            <Label>Registration number</Label>
            <Input value={regNo} onChange={(e) => setRegNo(e.target.value)} placeholder="e.g. GW20251001" data-testid="parent-link-input" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLinkOpen(false)}>Cancel</Button>
            <Button onClick={linkChild} className="bg-indigo-600 hover:bg-indigo-700" data-testid="parent-confirm-link-button">Link</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Toaster richColors position="top-right" />
    </div>
  );
}

function SummaryCard({ icon: Icon, label, color, children, testid }) {
  return (
    <div className="kpi-card" data-testid={testid}>
      <div className="flex items-start justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
        <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${color}`}><Icon className="h-5 w-5" /></div>
      </div>
      {children}
    </div>
  );
}
