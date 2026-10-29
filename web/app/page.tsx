export const dynamic = "force-dynamic";

const API = process.env.API_URL ?? "http://localhost:8000";

type Bucket = { calls: number; avg_cost_usd: number | null; booked_rate: number | null; savings_pct: number | null };
type Latency = { p50: number | null; p95: number | null };
type Metrics = {
  live: Bucket;
  simulated: Bucket;
  human_cost_per_call: number;
  tool_latency_ms: { live: Latency; simulated: Latency };
  whatsapp_conversations: number;
};
type Call = {
  created_at: string;
  channel: string;
  duration_s: number | null;
  cost_usd: number | null;
  outcome: string;
  summary: string | null;
  simulated: boolean;
  phone_last4: string | null;
  score: number | null;
};

// Server-only (no NEXT_PUBLIC_ prefix), so the token never reaches the browser.
const TOKEN = process.env.DASHBOARD_TOKEN;

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    cache: "no-store",
    headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {},
  });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

const usd = (n: number | null) => (n == null ? "—" : `$${Number(n).toFixed(2)}`);
const pct = (n: number | null) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);
const ms = (n: number | null) => (n == null ? "—" : `${Math.round(n)}ms`);

export default async function Dashboard() {
  const [m, calls] = await Promise.all([get<Metrics>("/metrics"), get<Call[]>("/calls")]);
  const tiles: [string, string | number, boolean?][] = [
    ["Avg cost / live call", usd(m.live.avg_cost_usd), true],
    ["Human SDR / call", usd(m.human_cost_per_call)],
    ["Cost reduction", m.live.savings_pct == null ? "—" : `${m.live.savings_pct}%`, true],
    ["Live calls", m.live.calls],
    ["Booked rate (live)", pct(m.live.booked_rate)],
    ["Tool p50 / p95 (live)", `${ms(m.tool_latency_ms.live.p50)} / ${ms(m.tool_latency_ms.live.p95)}`],
    ["WhatsApp convos", m.whatsapp_conversations],
    ["Load-test calls", m.simulated.calls],
    ["Tool p50 / p95 (load test)", `${ms(m.tool_latency_ms.simulated.p50)} / ${ms(m.tool_latency_ms.simulated.p95)}`],
  ];

  return (
    <main>
      <h1>AI Voice Operator</h1>
      <p className="sub">Inbound calls and WhatsApp, qualified and booked automatically. Load-test data is kept separate.</p>

      <section className="tiles">
        {tiles.map(([label, value, hero]) => (
          <div key={label} className={`tile${hero ? " hero" : ""}`}>
            <div className="label">{label}</div>
            <div className="value">{value}</div>
          </div>
        ))}
      </section>

      <div className="scroll">
        <table>
          <thead>
            <tr><th>When</th><th>Channel</th><th>Caller</th><th>Score</th><th>Outcome</th><th>Duration</th><th>Cost</th><th>Summary</th></tr>
          </thead>
          <tbody>
            {calls.map((c, i) => (
              <tr key={i}>
                <td>{new Date(c.created_at).toLocaleString()}</td>
                <td>{c.channel} {c.simulated && <span className="pill sim">sim</span>}</td>
                <td>···{c.phone_last4 ?? "----"}</td>
                <td className="num">{c.score ?? "—"}</td>
                <td><span className={`pill ${c.outcome === "booked" ? "booked" : ""}`}>{c.outcome}</span></td>
                <td className="num">{c.duration_s == null ? "—" : `${Math.round(Number(c.duration_s))}s`}</td>
                <td className="num">{usd(c.cost_usd)}</td>
                <td>{c.summary ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
