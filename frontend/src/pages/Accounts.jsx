import { useEffect, useState } from "react";
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
import { Plus, Trash2, TrendingUp, TrendingDown, ArrowDownUp } from "lucide-react";

const ACCOUNT_TYPES = ["asset", "liability", "income", "expense", "equity"];

export default function Accounts() {
  const [accounts, setAccounts] = useState([]);
  const [txns, setTxns] = useState([]);
  const [statement, setStatement] = useState(null);

  const [acctOpen, setAcctOpen] = useState(false);
  const [acctForm, setAcctForm] = useState({ name: "", code: "", type: "expense", description: "" });
  const [editAcct, setEditAcct] = useState(null);

  const [txnOpen, setTxnOpen] = useState(false);
  const [txnType, setTxnType] = useState("expense");
  const today = new Date().toISOString().slice(0, 10);
  const [txnForm, setTxnForm] = useState({ account_id: "", amount: 0, date: today, description: "", category: "" });

  const [filterAcct, setFilterAcct] = useState("all");
  const [filterType, setFilterType] = useState("all");
  const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const [start, setStart] = useState(monthAgo);
  const [end, setEnd] = useState(today);

  const loadAll = async () => {
    const [a, t] = await Promise.all([api.get("/accounts"), api.get("/transactions", { params: buildFilter() })]);
    setAccounts(a.data);
    setTxns(t.data);
    const params = { start, end };
    if (filterAcct !== "all") params.account_id = filterAcct;
    const { data } = await api.get("/accounts/statement", { params });
    setStatement(data);
  };

  function buildFilter() {
    const p = { start, end };
    if (filterAcct !== "all") p.account_id = filterAcct;
    if (filterType !== "all") p.type = filterType;
    return p;
  }

  useEffect(() => { loadAll(); /* eslint-disable-next-line */ }, [filterAcct, filterType, start, end]);

  const openAddAccount = () => { setEditAcct(null); setAcctForm({ name: "", code: "", type: "expense", description: "" }); setAcctOpen(true); };
  const openEditAccount = (a) => { setEditAcct(a); setAcctForm({ name: a.name, code: a.code, type: a.type, description: a.description || "" }); setAcctOpen(true); };

  const saveAccount = async () => {
    try {
      if (editAcct) await api.put(`/accounts/${editAcct.id}`, acctForm);
      else await api.post("/accounts", acctForm);
      toast.success("Account saved");
      setAcctOpen(false);
      loadAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const deleteAccount = async (a) => {
    if (!confirm(`Delete account "${a.name}"?`)) return;
    try {
      await api.delete(`/accounts/${a.id}`);
      toast.success("Deleted");
      loadAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const openTxn = (type) => {
    setTxnType(type);
    setTxnForm({ account_id: "", amount: 0, date: today, description: "", category: "" });
    setTxnOpen(true);
  };

  const saveTxn = async () => {
    try {
      const payload = { ...txnForm, type: txnType, amount: Number(txnForm.amount) };
      await api.post("/transactions", payload);
      toast.success(`${txnType === "income" ? "Income" : "Expense"} recorded`);
      setTxnOpen(false);
      loadAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const deleteTxn = async (t) => {
    if (!confirm("Delete this transaction?")) return;
    await api.delete(`/transactions/${t.id}`);
    loadAll();
  };

  return (
    <div data-testid="accounts-page">
      <PageHeader
        title="Accounts"
        description="Chart of accounts, income & expense entries, account statement."
        actions={
          <div className="flex gap-2">
            <Button onClick={() => openTxn("income")} variant="outline" className="border-emerald-300 text-emerald-700" data-testid="add-income-button">
              <TrendingUp className="mr-1.5 h-4 w-4" /> Add income
            </Button>
            <Button onClick={() => openTxn("expense")} variant="outline" className="border-red-300 text-red-700" data-testid="add-expense-button">
              <TrendingDown className="mr-1.5 h-4 w-4" /> Add expense
            </Button>
          </div>
        }
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Kpi label="Income" value={`$${(statement?.total_income || 0).toLocaleString()}`} accent="text-emerald-600" testid="kpi-income" />
        <Kpi label="Expense" value={`$${(statement?.total_expense || 0).toLocaleString()}`} accent="text-red-600" testid="kpi-expense" />
        <Kpi label="Net" value={`$${(statement?.net || 0).toLocaleString()}`} accent={(statement?.net || 0) >= 0 ? "text-emerald-600" : "text-red-600"} testid="kpi-net" />
      </div>

      <Tabs defaultValue="ledger">
        <TabsList>
          <TabsTrigger value="ledger" data-testid="acc-tab-ledger">Ledger</TabsTrigger>
          <TabsTrigger value="chart" data-testid="acc-tab-chart">Chart of accounts</TabsTrigger>
          <TabsTrigger value="statement" data-testid="acc-tab-statement">Statement</TabsTrigger>
        </TabsList>

        <TabsContent value="ledger" className="mt-4">
          <div className="mb-3 flex flex-wrap gap-2">
            <Select value={filterAcct} onValueChange={setFilterAcct}>
              <SelectTrigger className="w-56" data-testid="ledger-acct-filter"><SelectValue placeholder="Account" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All accounts</SelectItem>
                {accounts.map((a) => <SelectItem key={a.id} value={a.id}>{a.code} · {a.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All types</SelectItem>
                <SelectItem value="income">Income</SelectItem>
                <SelectItem value="expense">Expense</SelectItem>
              </SelectContent>
            </Select>
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="w-40" />
            <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="w-40" />
          </div>

          <div className="surface overflow-hidden">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="data-table-th">Date</th>
                  <th className="data-table-th">Account</th>
                  <th className="data-table-th">Description</th>
                  <th className="data-table-th">Type</th>
                  <th className="data-table-th text-right">Amount</th>
                  <th className="data-table-th text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {txns.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50" data-testid={`txn-row-${t.id}`}>
                    <td className="data-table-td">{t.date}</td>
                    <td className="data-table-td"><span className="font-mono text-xs text-slate-500">{t.account_code}</span> {t.account_name}</td>
                    <td className="data-table-td">{t.description || "—"}</td>
                    <td className="data-table-td">
                      <span className={`badge-soft ${t.type === "income" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{t.type}</span>
                    </td>
                    <td className={`data-table-td text-right font-medium ${t.type === "income" ? "text-emerald-700" : "text-red-700"}`}>
                      {t.type === "income" ? "+" : "-"}${Number(t.amount).toLocaleString()}
                    </td>
                    <td className="data-table-td text-right">
                      <Button size="sm" variant="ghost" onClick={() => deleteTxn(t)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                    </td>
                  </tr>
                ))}
                {txns.length === 0 && (
                  <tr><td colSpan={6} className="px-6 py-14 text-center text-sm text-slate-500">No transactions in range.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="chart" className="mt-4">
          <div className="mb-3 flex justify-end">
            <Button onClick={openAddAccount} className="bg-indigo-600 hover:bg-indigo-700" data-testid="new-account-button"><Plus className="mr-1.5 h-4 w-4" /> New account</Button>
          </div>
          <div className="surface overflow-hidden">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="data-table-th">Code</th>
                  <th className="data-table-th">Name</th>
                  <th className="data-table-th">Type</th>
                  <th className="data-table-th">Description</th>
                  <th className="data-table-th text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50" data-testid={`acct-row-${a.id}`}>
                    <td className="data-table-td font-mono text-xs">{a.code}</td>
                    <td className="data-table-td font-medium text-slate-900">{a.name}</td>
                    <td className="data-table-td"><span className="badge-soft bg-slate-100 capitalize text-slate-700">{a.type}</span></td>
                    <td className="data-table-td text-slate-500">{a.description || "—"}</td>
                    <td className="data-table-td text-right">
                      <Button size="sm" variant="ghost" onClick={() => openEditAccount(a)}>Edit</Button>
                      <Button size="sm" variant="ghost" onClick={() => deleteAccount(a)} data-testid={`delete-acct-${a.id}`}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                    </td>
                  </tr>
                ))}
                {accounts.length === 0 && (
                  <tr><td colSpan={5} className="px-6 py-14 text-center text-sm text-slate-500">No accounts. Add one.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="statement" className="mt-4">
          <div className="surface overflow-hidden">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="data-table-th">Date</th>
                  <th className="data-table-th">Description</th>
                  <th className="data-table-th">Type</th>
                  <th className="data-table-th text-right">Amount</th>
                  <th className="data-table-th text-right">Running balance</th>
                </tr>
              </thead>
              <tbody>
                {(statement?.transactions || []).map((t) => (
                  <tr key={t.id}>
                    <td className="data-table-td">{t.date}</td>
                    <td className="data-table-td">{t.description}</td>
                    <td className="data-table-td"><span className="badge-soft capitalize bg-slate-100 text-slate-700">{t.type}</span></td>
                    <td className={`data-table-td text-right ${t.type === "income" ? "text-emerald-700" : "text-red-700"}`}>
                      {t.type === "income" ? "+" : "-"}${Number(t.amount).toLocaleString()}
                    </td>
                    <td className="data-table-td text-right font-semibold">${Number(t.running_balance).toLocaleString()}</td>
                  </tr>
                ))}
                {(statement?.transactions || []).length === 0 && (
                  <tr><td colSpan={5} className="px-6 py-14 text-center text-sm text-slate-500">No transactions in range.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </TabsContent>
      </Tabs>

      {/* Account dialog */}
      <Dialog open={acctOpen} onOpenChange={setAcctOpen}>
        <DialogContent data-testid="account-dialog">
          <DialogHeader><DialogTitle>{editAcct ? "Edit account" : "New account"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Code</Label><Input value={acctForm.code} onChange={(e) => setAcctForm({ ...acctForm, code: e.target.value.toUpperCase() })} data-testid="acct-code-input" /></div>
              <div>
                <Label>Type</Label>
                <Select value={acctForm.type} onValueChange={(v) => setAcctForm({ ...acctForm, type: v })}>
                  <SelectTrigger data-testid="acct-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{ACCOUNT_TYPES.map((t) => <SelectItem key={t} value={t} className="capitalize">{t}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div><Label>Name</Label><Input value={acctForm.name} onChange={(e) => setAcctForm({ ...acctForm, name: e.target.value })} data-testid="acct-name-input" /></div>
            <div><Label>Description</Label><Textarea rows={2} value={acctForm.description} onChange={(e) => setAcctForm({ ...acctForm, description: e.target.value })} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAcctOpen(false)}>Cancel</Button>
            <Button onClick={saveAccount} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-acct-button">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Transaction dialog */}
      <Dialog open={txnOpen} onOpenChange={setTxnOpen}>
        <DialogContent data-testid="txn-dialog">
          <DialogHeader><DialogTitle className="capitalize">Add {txnType}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Account</Label>
              <Select value={txnForm.account_id} onValueChange={(v) => setTxnForm({ ...txnForm, account_id: v })}>
                <SelectTrigger data-testid="txn-acct-select"><SelectValue placeholder="Select an account" /></SelectTrigger>
                <SelectContent>
                  {accounts
                    .filter((a) => txnType === "income" ? a.type === "income" : a.type === "expense")
                    .map((a) => <SelectItem key={a.id} value={a.id}>{a.code} · {a.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Amount</Label><Input type="number" value={txnForm.amount} onChange={(e) => setTxnForm({ ...txnForm, amount: e.target.value })} data-testid="txn-amount-input" /></div>
              <div><Label>Date</Label><Input type="date" value={txnForm.date} onChange={(e) => setTxnForm({ ...txnForm, date: e.target.value })} data-testid="txn-date-input" /></div>
            </div>
            <div><Label>Description</Label><Input value={txnForm.description} onChange={(e) => setTxnForm({ ...txnForm, description: e.target.value })} data-testid="txn-desc-input" /></div>
            <div><Label>Category</Label><Input value={txnForm.category} onChange={(e) => setTxnForm({ ...txnForm, category: e.target.value })} placeholder="e.g. utility, supply" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTxnOpen(false)}>Cancel</Button>
            <Button onClick={saveTxn} className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-txn-button">Record</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Kpi({ label, value, accent, testid }) {
  return (
    <div className="kpi-card" data-testid={testid}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
          <div className={`mt-2 font-display text-2xl font-bold tracking-tight ${accent}`}>{value}</div>
        </div>
        <ArrowDownUp className="h-5 w-5 text-slate-300" />
      </div>
    </div>
  );
}
