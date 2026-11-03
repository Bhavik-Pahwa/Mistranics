import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Search,
  BookOpen,
  Plus,
  Settings2,
  LockKeyhole,
  Check,
} from "lucide-react";
import type { Alert, Machine } from "../types/dashboard";
import { Modal } from "./Modal";

export function Investigations({
  alerts,
  selected,
  onSelect,
  onResolve,
}: {
  alerts: Alert[];
  selected: Alert | null;
  onSelect: (alert: Alert | null) => void;
  onResolve: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const items = alerts.filter(
    (a) =>
      `${a.title} ${a.machineName}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === "all" || a.status === filter),
  );
  return (
    <section className="industrial-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">THE RECORD BEHIND THE SIGNAL</span>
          <h1>Investigations</h1>
          <p>Logged alerts, supporting evidence, and a path forward.</p>
        </div>
        <span className="count-badge">{alerts.length} records</span>
      </div>
      <div className="page-tools">
        <label className="search-field">
          <Search size={17} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search alerts or machines"
            aria-label="Search investigations"
          />
        </label>
        <select
          aria-label="Filter investigations"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="active">Open</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>
      <div className="investigation-grid">
        {items.map((a) => (
          <button
            className="investigation-card"
            key={a.id}
            onClick={() => onSelect(a)}
          >
            <div className="card-meta">
              <span className={`severity ${a.severity.toLowerCase()}`}>
                {a.severity}
              </span>
              <span>
                {a.status === "resolved" ? "Resolved" : "Open investigation"}
              </span>
            </div>
            <h2>{a.title}</h2>
            <p>{a.description}</p>
            <div className="card-bottom">
              <div>
                <strong>{a.machineName}</strong>
                <span>
                  {a.machineCode} ·{" "}
                  {new Date(a.detectedTimestamp).toLocaleDateString()}
                </span>
              </div>
              <ArrowUpRight size={20} />
            </div>
          </button>
        ))}
      </div>
      {!items.length && (
        <div className="empty-log">No investigations match your search.</div>
      )}
      {selected && (
        <InvestigationDetail
          alert={selected}
          onClose={() => onSelect(null)}
          onResolve={onResolve}
        />
      )}
    </section>
  );
}
export function InvestigationDetail({
  alert,
  onClose,
  onResolve,
}: {
  alert: Alert;
  onClose: () => void;
  onResolve: (id: string) => void;
}) {
  return (
    <Modal title={alert.title} onClose={onClose}>
      <span className={`severity ${alert.severity.toLowerCase()}`}>
        {alert.severity} · {alert.status}
      </span>
      <p className="detail-meta">
        {alert.machineName} / {alert.machineCode} ·{" "}
        {new Date(alert.detectedTimestamp).toLocaleString()}
      </p>
      <h3>Anomaly</h3>
      <p>{alert.detailedExplanation}</p>
      <div className="evidence-grid">
        {alert.evidence.map((e, i) => (
          <div key={i}>
            <span>{e.metric}</span>
            <strong>{e.observed}</strong>
            <small>Reference: {e.threshold}</small>
          </div>
        ))}
      </div>
      <h3>Recommended troubleshooting</h3>
      <ol className="troubleshoot-list">
        {alert.troubleshootingSteps.map((s) => (
          <li key={s.step}>
            <strong>{s.instruction}</strong>
            <p>{s.detail}</p>
          </li>
        ))}
      </ol>
      <h3>Next actions</h3>
      <ul>
        {alert.recommendedActions.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
      {alert.status === "active" ? (
        <button className="primary-button" onClick={() => onResolve(alert.id)}>
          <Check size={16} /> Mark resolved
        </button>
      ) : (
        <p className="resolved-note">
          Resolved{" "}
          {alert.resolvedAt ? new Date(alert.resolvedAt).toLocaleString() : ""}
        </p>
      )}
    </Modal>
  );
}

function machineImage(machine: Machine) {
  const motor = machine.id === "simulation-01" || /motor/i.test(machine.type);
  const pump = /pump/i.test(machine.type);
  const drawing = motor
    ? '<rect x="95" y="64" width="155" height="90" rx="20"/><path d="M115 70v76m22-76v76m22-76v76m22-76v76m22-76v76m22-76v76M250 100h50v22h-50M115 154v16h110v-16"/><circle cx="95" cy="109" r="38"/>'
    : pump
      ? '<circle cx="180" cy="112" r="62"/><circle cx="180" cy="112" r="28"/><path d="M180 50V22h85v30h-55M120 102H60v30h60M150 169v12h65v-12"/>'
      : '<rect x="70" y="70" width="240" height="90" rx="38"/><path d="M100 160v20m180-20v20M130 70V42h120v28M160 42V25h60v17"/><circle cx="270" cy="112" r="24"/><path d="M85 112h130"/>';
  return `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 210"><rect width="380" height="210" fill="#eaf0ef"/><g stroke="#516f71" stroke-width="3" fill="#d5e1df">${drawing}</g><path d="M30 182h320" stroke="#b8cbc7"/></svg>`)}`;
}
type ManualResource = {
  document_id: string;
  title: string;
  version: string;
  modes: string[];
  url: string;
  chunks: number;
};
export function Manuals({ machines }: { machines: Machine[] }) {
  const [resources, setResources] = useState<ManualResource[]>([]);
  const [knowledgeStatus, setKnowledgeStatus] = useState(
    "Loading simulation manuals...",
  );
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch("/api/industrial/manuals", {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error();
        const data = await response.json();
        setResources(data.documents || []);
        setKnowledgeStatus(
          data.status === "ready"
            ? `${data.chunk_count} passages indexed for the Prototype motor`
            : data.error || "Simulation manuals are indexing.",
        );
      } catch {
        if (!controller.signal.aborted)
          setKnowledgeStatus("Simulation knowledge service is unavailable.");
      }
    }
    load();
    const timer = setInterval(load, 5000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);
  const [selected, setSelected] = useState<Machine | null>(null);
  return (
    <section className="industrial-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">KNOWLEDGE, WITHIN REACH</span>
          <h1>Knowledge manuals</h1>
          <p>Machine resources and inspection guides for your workspace.</p>
        </div>
        <BookOpen size={28} />
      </div>
      <p className="manual-index-status" role="status">
        {knowledgeStatus}
      </p>
      <div className="manual-grid simulation-manuals">
        {resources.map((resource) => (
          <a
            className="manual-card"
            key={resource.document_id}
            href={resource.url}
            target="_blank"
            rel="noreferrer"
          >
            <img
              src={machineImage(
                machines.find((m) => m.id === "simulation-01") || machines[0],
              )}
              alt="Prototype motor technical illustration"
            />
            <div>
              <span className="eyebrow">
                MTR-001 · FICTIONAL TRAINING MANUAL
              </span>
              <h2>{resource.title}</h2>
              <p>
                {resource.modes.length} modes · {resource.version} ·{" "}
                {resource.chunks} indexed passages
              </p>
              <span className="manual-link">
                Open PDF <ArrowUpRight size={17} />
              </span>
            </div>
          </a>
        ))}
      </div>
      <div className="manual-grid">
        {machines.map((m) => (
          <button
            key={m.id}
            className="manual-card"
            onClick={() => setSelected(m)}
          >
            <img
              src={machineImage(m)}
              alt={`Technical illustration of ${m.type}`}
            />
            <div>
              <span className="eyebrow">{m.code} · PROTOTYPE GUIDE</span>
              <h2>{m.name} — inspection guide</h2>
              <p>{m.type}</p>
              <span className="manual-link">
                Read resource <ArrowUpRight size={17} />
              </span>
            </div>
          </button>
        ))}
      </div>
      {selected && (
        <Modal
          title={`${selected.name} — inspection guide`}
          onClose={() => setSelected(null)}
        >
          <img
            className="manual-detail-image"
            src={machineImage(selected)}
            alt={selected.type}
          />
          <p>
            Prototype reference · {selected.code} · {selected.location}
          </p>
          <h3>Before inspection</h3>
          <p>
            Confirm the machine identity and review its approved operating
            procedures. Use the manufacturer’s manual for machine-specific
            limits and maintenance instructions.
          </p>
          <h3>Sensor inspection</h3>
          <ol className="troubleshoot-list">
            {(selected.sensors || ["temperature", "vibration", "current"]).map(
              (s) => (
                <li key={s}>
                  <strong>{s}</strong>
                  <p>
                    Check sensor mounting, connection, unit configuration, and
                    timestamp. Compare the reading with a known stable operating
                    period.
                  </p>
                </li>
              ),
            )}
          </ol>
          <h3>Document your findings</h3>
          <p>
            Record the operating load and affected sensor. Review the
            corresponding investigation before carrying out maintenance. This
            prototype guide is not an OEM manual.
          </p>
        </Modal>
      )}
    </section>
  );
}
export function Admin({
  machines,
  onSave,
}: {
  machines: Machine[];
  onSave: (machine: Machine) => void;
}) {
  const [authenticated, setAuthenticated] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Machine | "new" | null>(null);
  const [saved, setSaved] = useState("");
  if (!authenticated)
    return (
      <section className="auth-page">
        <div className="auth-card">
          <div className="auth-icon">
            <LockKeyhole size={25} />
          </div>
          <span className="eyebrow">INDUSTRIAL WORKSPACE</span>
          <h1>Admin access</h1>
          <p>Manage the machines behind your operations.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              if (
                data.get("email") === "admin@mistranics.com" &&
                data.get("password") === "admin123"
              ) {
                setAuthenticated(true);
                setError("");
              } else
                setError(
                  "Those credentials do not match. Try the prototype account below.",
                );
            }}
          >
            <label>
              Email address
              <input
                name="email"
                type="email"
                autoComplete="username"
                required
                placeholder="admin@mistranics.com"
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                placeholder="Enter password"
              />
            </label>
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
            <button className="primary-button">
              Sign in <ArrowUpRight size={17} />
            </button>
          </form>
          <div className="demo-credentials">
            Prototype account
            <br />
            <strong>admin@mistranics.com</strong> / <strong>admin123</strong>
            <small>
              Local prototype access. Machine configuration is saved in this
              browser.
            </small>
          </div>
        </div>
      </section>
    );
  return (
    <section className="industrial-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">WORKSPACE ADMINISTRATION</span>
          <h1>Machine registry</h1>
          <p>Onboard equipment and keep its sensor configuration up to date.</p>
        </div>
        <div className="admin-actions">
          <button
            className="quiet-button"
            onClick={() => setAuthenticated(false)}
          >
            Sign out
          </button>
          <button className="primary-button" onClick={() => setEditing("new")}>
            <Plus size={16} /> Onboard machine
          </button>
        </div>
      </div>
      <div className="admin-stats">
        <div>
          <span>Registered machines</span>
          <strong>{machines.length.toString().padStart(2, "0")}</strong>
        </div>
        <div>
          <span>Configured sensors</span>
          <strong>
            {machines.reduce((n, m) => n + (m.sensors?.length || 3), 0)}
          </strong>
        </div>
        <div>
          <span>Workspace</span>
          <strong>Industrial</strong>
        </div>
      </div>
      {saved && (
        <p role="status" className="resolved-note">
          {saved}
        </p>
      )}
      <div className="machine-registry">
        {machines.map((m) => (
          <article key={m.id}>
            <div className="registry-icon">
              <Settings2 size={22} />
            </div>
            <div>
              <h2>{m.name}</h2>
              <p>
                {m.code} · {m.type} · {m.location}
              </p>
              <div className="sensor-chips">
                {(m.sensors || ["temperature", "vibration", "current"]).map(
                  (s) => (
                    <span key={s}>{s}</span>
                  ),
                )}
              </div>
            </div>
            <button className="quiet-button" onClick={() => setEditing(m)}>
              Edit machine <ArrowUpRight size={15} />
            </button>
          </article>
        ))}
      </div>
      {editing && (
        <Modal
          title={editing === "new" ? "Onboard a machine" : "Edit machine"}
          onClose={() => setEditing(null)}
        >
          <form
            className="machine-form"
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              const original = editing === "new" ? null : editing;
              const code = String(data.get("code")).trim();
              if (
                machines.some(
                  (m) =>
                    m.id !== original?.id &&
                    m.code.toLowerCase() === code.toLowerCase(),
                )
              ) {
                setError("This machine code is already in use.");
                return;
              }
              const sensors = data.getAll("sensors").map(String);
              if (!sensors.length) {
                setError("Select at least one sensor.");
                return;
              }
              const machine: Machine = {
                id: original?.id || crypto.randomUUID(),
                code,
                name: String(data.get("name")).trim(),
                type: String(data.get("type")).trim(),
                location: String(data.get("location")).trim(),
                sensors,
                priority: original?.priority || machines.length + 1,
                healthPercentage: original?.healthPercentage ?? 100,
                healthStatus: original?.healthStatus || "Awaiting data",
                color: original?.color || "#11998c",
                telemetry: original?.telemetry || [],
                subsystems: original?.subsystems || [],
                metrics: original?.metrics || {
                  rpm: 0,
                  pressureBar: 0,
                  runtimeHours: 0,
                  lubeOilTemp: 0,
                },
              };
              if (
                !machine.name ||
                !machine.type ||
                !machine.code ||
                !machine.location
              ) {
                setError("Complete all machine details.");
                return;
              }
              onSave(machine);
              setEditing(null);
              setError("");
              setSaved(`${machine.name} saved.`);
            }}
          >
            <div className="form-grid">
              {(["name", "code", "type", "location"] as const).map((key) => (
                <label key={key}>
                  {key === "code" ? "Machine code" : key}
                  <input
                    name={key}
                    required
                    maxLength={80}
                    defaultValue={editing === "new" ? "" : editing[key]}
                  />
                </label>
              ))}
            </div>
            <fieldset>
              <legend>Installed sensors</legend>
              <div className="checkbox-grid">
                {[
                  "temperature",
                  "vibration",
                  "current",
                  "rpm",
                  "ax",
                  "ay",
                  "az",
                  "gx",
                  "gy",
                  "gz",
                ].map((s) => (
                  <label key={s}>
                    <input
                      type="checkbox"
                      name="sensors"
                      value={s}
                      defaultChecked={
                        editing === "new"
                          ? ["temperature", "vibration", "current"].includes(s)
                          : (
                              editing.sensors || [
                                "temperature",
                                "vibration",
                                "current",
                              ]
                            ).includes(s)
                      }
                    />
                    {s}
                  </label>
                ))}
              </div>
            </fieldset>
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
            <button className="primary-button">Save machine</button>
          </form>
        </Modal>
      )}
    </section>
  );
}
