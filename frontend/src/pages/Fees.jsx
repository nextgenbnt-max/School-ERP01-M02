import { useEffect, useState } from "react";
import api, { API_BASE, formatApiError } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { CreditCard, Receipt, Wallet, FileText, Download, Mail } from "lucide-react";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export default function Fees() {
  const [invoices, setInvoices] = useState([]);
  const [report, setReport] = useState(null);
  const [classes, setClasses] = useState([]);
  const today = new Date();
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [year, setYear] = useState(today.getFullYear());
  const [status, setStatus] = useState("all");
  const [payOpen, setPayOpen] = useState(false);
  const [activeInv, setActiveInv] = useState(null);
  const [payAmount, setPayAmount] = useState(0);
  const [payMethod, setPayMethod] = useState("cash");
  const [genOpen, setGenOpen] = useState(false);
  const [genClass, setGenClass] = useState("all");
  const [emailOpen, setEmailOpen] = useState(false);
  const [emailInv, setEmailInv] = useState(null);
  const [emailTo, setEmailTo] = useState("");
  const [emailSending, setEmailSending] = useState(false);

  const load = async () => {
    const params = { month, year };
    if (status !== "all") params.status = status;
    const [invR, repR, clsR] = await Promise.all([
      api.get("/fees/invoices", { params }),
      api.get("/fees/report", { params: { year } }),
      api.get("/classes"),
    ]);
    setInvoices(invR.data);
    setReport(repR.data);
    setClasses(clsR.data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [month, year, status]);

  const openPay = (inv) => {
    setActiveInv(inv);
    setPayAmount(Math.max(0, inv.amount - (inv.paid_amount || 0)));
    setPayMethod("cash");
    setPayOpen(true);
  };

  const submitPayment = async () => {
    try {
      await api.post(`/fees/invoices/${activeInv.id}/pay`, { paid_amount: Number(payAmount), payment_method: payMethod });
      toast.success("Payment recorded");
      setPayOpen(false);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const generate = async () => {
    try {
      const params = { month, year };
      if (genClass !== "all") params.class_id = genClass;
      const { data } = await api.post("/fees/invoices/bulk-generate", null, { params });
      toast.success(`Generated ${data.created} invoices`);
      setGenOpen(false);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const openEmail = (inv) => {
    setEmailInv(inv);
    setEmailTo("");
    setEmailOpen(true);
  };

  const submitEmail = async () => {
    setEmailSending(true);
    try {
      const { data } = await api.post(`/fees/invoices/${emailInv.id}/email`, { recipient_email: emailTo });
      if (data.status === "sent") toast.success("Email sent");
      else if (data.status === "skipped") toast.message("Email skipped — RESEND_API_KEY not configured");
      else toast.error(data.error || "Email failed");
      setEmailOpen(false);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setEmailSending(false);
    }
  };

  return (
    <div data-testid="fees-page">
      <PageHeader
        title="Fees"
        description="Generate invoices, collect payments and track collections."
        actions={
          <Button onClick={() => setGenOpen(true)} className="bg-indigo-600 hover:bg-indigo-700" data-testid="generate-invoices-button">
            <Receipt className="mr-1.5 h-4 w-4" /> Generate invoices
          </Button>
        }
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard icon={CreditCard} label="Total billed" value={`$${(report?.total_billed || 0).toLocaleString()}`} color="bg-indigo-100 text-indigo-700" testid="kpi-billed" />
        <KpiCard icon={Wallet} label="Collected" value={`$${(report?.total_collected || 0).toLocaleString()}`} color="bg-emerald-100 text-emerald-700" testid="kpi-collected" />
        <KpiCard icon={FileText} label="Pending" value={`$${(report?.total_pending || 0).toLocaleString()}`} color="bg-amber-100 text-amber-700" testid="kpi-pending" />
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
          <SelectTrigger className="w-36" data-testid="fees-month-filter"><SelectValue /></SelectTrigger>
          <SelectContent>{MONTHS.map((m, i) => <SelectItem key={i} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
          <SelectTrigger className="w-32" data-testid="fees-year-filter"><SelectValue /></SelectTrigger>
          <SelectContent>{[year - 1, year, year + 1].map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-40" data-testid="fees-status-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All status</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="partial">Partial</SelectItem>
            <SelectItem value="paid">Paid</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="surface overflow-hidden">
        <table className="w-full">
          <thead>
            <tr>
              <th className="data-table-th">Student</th>
              <th className="data-table-th">Reg #</th>
              <th className="data-table-th">Period</th>
              <th className="data-table-th">Amount</th>
              <th className="data-table-th">Paid</th>
              <th className="data-table-th">Status</th>
              <th className="data-table-th text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id} className="hover:bg-slate-50" data-testid={`invoice-row-${inv.id}`}>
                <td className="data-table-td font-medium text-slate-900">{inv.student_name || "—"}</td>
                <td className="data-table-td font-mono text-xs">{inv.registration_number}</td>
                <td className="data-table-td">{MONTHS[inv.month - 1]} {inv.year}</td>
                <td className="data-table-td">${Number(inv.amount).toLocaleString()}</td>
                <td className="data-table-td">${Number(inv.paid_amount || 0).toLocaleString()}</td>
                <td className="data-table-td"><StatusBadge status={inv.status} /></td>
                <td className="data-table-td text-right">
                  {inv.status !== "paid" && (
                    <Button size="sm" onClick={() => openPay(inv)} className="bg-indigo-600 hover:bg-indigo-700 mr-1" data-testid={`collect-${inv.id}`}>Collect</Button>
                  )}
                  {inv.status === "paid" && <span className="mr-2 text-xs font-medium text-emerald-600">✓ Paid</span>}
                  <Button size="sm" variant="outline" onClick={() => window.open(`${API_BASE}/fees/invoices/${inv.id}/slip.pdf`, "_blank")} data-testid={`download-slip-${inv.id}`}><Download className="h-4 w-4" /></Button>
                  <Button size="sm" variant="outline" onClick={() => openEmail(inv)} className="ml-1" data-testid={`email-slip-${inv.id}`}><Mail className="h-4 w-4" /></Button>
                </td>
              </tr>
            ))}
            {invoices.length === 0 && (
              <tr><td colSpan={7} className="px-6 py-16 text-center text-sm text-slate-500">No invoices for this period. Generate them.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={payOpen} onOpenChange={setPayOpen}>
        <DialogContent data-testid="pay-dialog">
          <DialogHeader><DialogTitle>Collect fee</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="rounded-lg bg-slate-50 p-3 text-sm">
              <div className="font-medium text-slate-900">{activeInv?.student_name}</div>
              <div className="text-slate-500">{activeInv && `${MONTHS[activeInv.month - 1]} ${activeInv.year} · Outstanding: $${(activeInv.amount - (activeInv.paid_amount || 0)).toLocaleString()}`}</div>
            </div>
            <div>
              <Label>Amount</Label>
              <Input type="number" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} data-testid="pay-amount-input" />
            </div>
            <div>
              <Label>Method</Label>
              <Select value={payMethod} onValueChange={setPayMethod}>
                <SelectTrigger data-testid="pay-method-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="cash">Cash</SelectItem>
                  <SelectItem value="card">Card</SelectItem>
                  <SelectItem value="bank">Bank transfer</SelectItem>
                  <SelectItem value="cheque">Cheque</SelectItem>
                  <SelectItem value="upi">UPI</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPayOpen(false)}>Cancel</Button>
            <Button onClick={submitPayment} className="bg-indigo-600 hover:bg-indigo-700" data-testid="submit-payment-button">Record payment</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={genOpen} onOpenChange={setGenOpen}>
        <DialogContent data-testid="generate-dialog">
          <DialogHeader><DialogTitle>Generate monthly invoices</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-500">Generates invoices for <b>{MONTHS[month - 1]} {year}</b> for all students (skips existing).</p>
          <div className="mt-2">
            <Label>Class (optional)</Label>
            <Select value={genClass} onValueChange={setGenClass}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All classes</SelectItem>
                {classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenOpen(false)}>Cancel</Button>
            <Button onClick={generate} className="bg-indigo-600 hover:bg-indigo-700" data-testid="confirm-generate-button">Generate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={emailOpen} onOpenChange={setEmailOpen}>
        <DialogContent data-testid="email-fee-dialog">
          <DialogHeader><DialogTitle>Email fee receipt</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="rounded-lg bg-slate-50 p-3 text-sm">
              <div className="font-medium text-slate-900">{emailInv?.student_name}</div>
              <div className="text-slate-500">{emailInv && `${MONTHS[emailInv.month - 1]} ${emailInv.year} · $${emailInv.amount.toLocaleString()}`}</div>
            </div>
            <div>
              <Label>Recipient email</Label>
              <Input type="email" value={emailTo} onChange={(e) => setEmailTo(e.target.value)} placeholder="parent@example.com" data-testid="email-fee-input" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmailOpen(false)}>Cancel</Button>
            <Button onClick={submitEmail} disabled={emailSending || !emailTo} className="bg-indigo-600 hover:bg-indigo-700" data-testid="send-fee-email-button">
              <Mail className="mr-1.5 h-4 w-4" /> {emailSending ? "Sending…" : "Send"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, color, testid }) {
  return (
    <div className="kpi-card" data-testid={testid}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
          <div className="mt-2 font-display text-2xl font-bold tracking-tight text-slate-900">{value}</div>
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${color}`}><Icon className="h-5 w-5" /></div>
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    paid: "bg-emerald-100 text-emerald-700",
    partial: "bg-amber-100 text-amber-700",
    pending: "bg-red-100 text-red-700",
  };
  return <span className={`badge-soft capitalize ${map[status] || "bg-slate-100 text-slate-600"}`}>{status}</span>;
}
