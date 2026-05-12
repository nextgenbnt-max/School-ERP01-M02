import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { Send, MessageCircle, MessageSquare } from "lucide-react";

const TEMPLATES = {
  fee_reminder: "Hi {parent}, this is a friendly reminder that {student}'s school fee is due. Please pay at your earliest convenience. — Greenwood School",
  absence_alert: "Hi {parent}, this is to inform you that {student} was marked absent today. Please contact us if you have any concerns. — Greenwood School",
  event_invite: "Dear parent, you are cordially invited to our upcoming event. Details to follow. — Greenwood School",
};

export default function Messaging() {
  const [channel, setChannel] = useState("sms");
  const [body, setBody] = useState("");
  const [students, setStudents] = useState([]);
  const [selected, setSelected] = useState({});
  const [history, setHistory] = useState([]);
  const [classes, setClasses] = useState([]);
  const [classFilter, setClassFilter] = useState("all");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api.get("/classes").then((r) => setClasses(r.data));
    refreshHistory();
  }, []);
  useEffect(() => {
    const params = classFilter !== "all" ? { class_id: classFilter } : {};
    api.get("/students", { params }).then((r) => setStudents(r.data));
  }, [classFilter]);

  const refreshHistory = () => api.get("/messages").then((r) => setHistory(r.data));

  const toggle = (id) => setSelected((s) => ({ ...s, [id]: !s[id] }));
  const toggleAll = () => {
    if (Object.values(selected).filter(Boolean).length === students.length) setSelected({});
    else {
      const all = {};
      students.forEach((s) => (all[s.id] = true));
      setSelected(all);
    }
  };

  const applyTemplate = (key) => setBody(TEMPLATES[key]);

  const send = async () => {
    const chosen = students.filter((s) => selected[s.id]);
    if (chosen.length === 0) return toast.error("Pick at least one recipient");
    if (!body.trim()) return toast.error("Message cannot be empty");
    setSending(true);
    try {
      const recipients = chosen
        .map((s) => s.father_contact || s.mother_contact || s.mobile)
        .filter(Boolean);
      const messages = chosen.map((s) => ({
        recipient: s.father_contact || s.mother_contact || s.mobile,
        body: body
          .replace(/{parent}/g, s.father_name || s.mother_name || "Parent")
          .replace(/{student}/g, s.name),
      }));
      // send individually so each gets templated text
      let sent = 0, failed = 0, skipped = 0;
      for (const m of messages) {
        if (!m.recipient) { skipped++; continue; }
        const { data } = await api.post("/messages/send", { channel, recipients: [m.recipient], body: m.body });
        const r = data.results[0];
        if (r.status === "sent") sent++;
        else if (r.status === "skipped") skipped++;
        else failed++;
      }
      toast.success(`Sent ${sent} · Skipped ${skipped} · Failed ${failed}`);
      refreshHistory();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setSending(false);
    }
  };

  return (
    <div data-testid="messaging-page">
      <PageHeader
        title="Messaging"
        description="Send SMS or WhatsApp messages to parents via Twilio."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="surface p-6 lg:col-span-2">
          <Tabs value={channel} onValueChange={setChannel}>
            <TabsList>
              <TabsTrigger value="sms" data-testid="msg-channel-sms"><MessageSquare className="mr-1.5 h-4 w-4" />SMS</TabsTrigger>
              <TabsTrigger value="whatsapp" data-testid="msg-channel-whatsapp"><MessageCircle className="mr-1.5 h-4 w-4" />WhatsApp</TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="mt-5">
            <Label>Quick templates</Label>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => applyTemplate("fee_reminder")} data-testid="tpl-fee-reminder">Fee reminder</Button>
              <Button size="sm" variant="outline" onClick={() => applyTemplate("absence_alert")} data-testid="tpl-absence">Absence alert</Button>
              <Button size="sm" variant="outline" onClick={() => applyTemplate("event_invite")} data-testid="tpl-event">Event invite</Button>
            </div>
          </div>

          <div className="mt-4">
            <Label>Message</Label>
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={6}
              placeholder="Hi {parent}, …"
              data-testid="msg-body-input"
            />
            <p className="mt-1 text-xs text-slate-500">Tokens: <code>{"{parent}"}</code>, <code>{"{student}"}</code></p>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1 text-sm text-slate-500">
              {Object.values(selected).filter(Boolean).length} of {students.length} recipients selected
            </div>
            <Button onClick={send} disabled={sending} className="bg-indigo-600 hover:bg-indigo-700" data-testid="send-message-button">
              <Send className="mr-1.5 h-4 w-4" /> {sending ? "Sending…" : `Send ${channel.toUpperCase()}`}
            </Button>
          </div>
        </div>

        <div className="surface p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-display text-lg font-semibold tracking-tight text-slate-900">Recipients</h3>
            <Select value={classFilter} onValueChange={setClassFilter}>
              <SelectTrigger className="w-32" data-testid="msg-class-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                {classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <button onClick={toggleAll} className="mb-2 text-xs font-medium text-indigo-600 hover:text-indigo-700" data-testid="msg-select-all">
            Select / clear all
          </button>
          <div className="max-h-80 space-y-1 overflow-y-auto pr-1">
            {students.map((s) => (
              <label key={s.id} className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm hover:bg-slate-50">
                <Checkbox checked={!!selected[s.id]} onCheckedChange={() => toggle(s.id)} data-testid={`msg-recipient-${s.id}`} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-slate-800">{s.name}</div>
                  <div className="truncate text-xs text-slate-500">{s.father_contact || s.mother_contact || s.mobile || "no number"}</div>
                </div>
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-6 surface p-5">
        <h3 className="mb-3 font-display text-lg font-semibold tracking-tight text-slate-900">Message history</h3>
        <div className="overflow-hidden rounded-xl border border-slate-100">
          <table className="w-full">
            <thead>
              <tr>
                <th className="data-table-th">Channel</th>
                <th className="data-table-th">Recipient</th>
                <th className="data-table-th">Message</th>
                <th className="data-table-th">Status</th>
                <th className="data-table-th">Sent</th>
              </tr>
            </thead>
            <tbody>
              {history.map((m) => (
                <tr key={m.id}>
                  <td className="data-table-td capitalize">{m.channel}</td>
                  <td className="data-table-td font-mono text-xs">{m.recipient}</td>
                  <td className="data-table-td max-w-md truncate">{m.body}</td>
                  <td className="data-table-td">
                    <span className={`badge-soft ${m.status === "sent" ? "bg-emerald-100 text-emerald-700" : m.status === "failed" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>{m.status}</span>
                  </td>
                  <td className="data-table-td text-xs text-slate-500">{m.sent_at?.slice(0, 16).replace("T", " ")}</td>
                </tr>
              ))}
              {history.length === 0 && (
                <tr><td colSpan={5} className="px-6 py-10 text-center text-sm text-slate-500">No messages sent yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
