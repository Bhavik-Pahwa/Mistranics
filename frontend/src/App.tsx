import { useEffect, useRef, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import type { NavItemKey } from "./components/Sidebar";
import { FloatingSearchBar } from "./components/FloatingSearchBar";
import { Part1SensorTrends } from "./components/Part1SensorTrends";
import { Part3MachineOverview } from "./components/Part3MachineOverview";
import { Part4ActiveAlerts } from "./components/Part4ActiveAlerts";
import { ChatbotView } from "./components/ChatbotView";
import { MachineAnalyticsModal } from "./components/MachineAnalyticsModal";
import { SearchDialog } from "./components/SearchDialog";
import { ModeSelection } from "./components/ModeSelection";
import { HandsOnView, TelemetryChart } from "./components/TelemetryWorkspace";
import {
  Admin,
  Investigations,
  InvestigationDetail,
  Manuals,
} from "./components/IndustrialPages";
import { SAMPLE_MACHINES, INITIAL_ACTIVE_ALERTS } from "./data/sampleData";
import type { Machine, Alert } from "./types/dashboard";
import { sensorNames, useTelemetry } from "./hooks/useTelemetry";
import "./revamp.css";

const MOTOR: Machine = {
  id: "simulation-01",
  code: "MTR-001",
  name: "Prototype motor",
  type: "ESP32 / MPU6050 + ACS712",
  location: "Simulation bench",
  priority: 1,
  healthPercentage: 100,
  healthStatus: "Healthy",
  color: "#11998c",
  telemetry: [],
  subsystems: [],
  sensors: [
    "temperature",
    "current",
    "vibration",
    "rpm",
    "ax",
    "ay",
    "az",
    "gx",
    "gy",
    "gz",
  ],
  metrics: { rpm: 1500, pressureBar: 0, runtimeHours: 0, lubeOilTemp: 28 },
};
function saved<T>(key: string, fallback: T): T {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "null");
    return Array.isArray(value) ? (value as T) : fallback;
  } catch {
    return fallback;
  }
}
function IndustrialWorkspace({ onExit }: { onExit: () => void }) {
  const [expanded, setExpanded] = useState(true);
  const [nav, setNav] = useState<NavItemKey>("dashboard");
  const [search, setSearch] = useState(false);
  const [registry, setRegistry] = useState<Machine[]>(() =>
    saved("mistranics.machines.v2", [MOTOR, ...SAMPLE_MACHINES]),
  );
  const [alerts, setAlerts] = useState<Alert[]>(() =>
    saved("mistranics.alerts.v2", INITIAL_ACTIVE_ALERTS),
  );
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [analytics, setAnalytics] = useState<Machine | null>(null);
  const [investigationId, setInvestigationId] = useState<string | null>(null);
  const [storageError, setStorageError] = useState(false);
  const processed = useRef({ session: "", sequence: 0 });
  const { state, connected } = useTelemetry("simulation");
  const latest = state?.latest;
  const motorReadings = latest?.readings;
  const motorReady = connected && state?.stream_status === "LIVE";
  const motorAnomaly = Object.values(motorReadings || {}).some(
    (r) => r.anomaly.status === "ANOMALY",
  );
  const machines = registry.map((m) =>
    m.id !== "simulation-01"
      ? m
      : {
          ...m,
          readings: Object.fromEntries(
            Object.entries(motorReadings || {}).map(([key, r]) => [
              key,
              { value: r.mean, unit: r.unit },
            ]),
          ),
          streamStatus: !motorReady
            ? "Awaiting data"
            : Object.values(motorReadings || {}).some(
                  (r) => r.anomaly.status === "WARMING_UP",
                )
              ? "Building baseline"
              : motorAnomaly
                ? "Deviation detected"
                : "No deviation",
          telemetry: (state?.history || []).map((p) => ({
            time: new Date(p.timestamp).toLocaleTimeString(),
            temperature: p.readings.temperature?.mean ?? 0,
            vibration: p.readings.vibration?.mean ?? 0,
            health: Object.values(p.readings).some(
              (r) => r.anomaly.status === "ANOMALY",
            )
              ? 50
              : 100,
          })),
          metrics: {
            ...m.metrics,
            rpm: motorReadings?.rpm?.mean ?? 0,
            lubeOilTemp: motorReadings?.temperature?.mean ?? 0,
          },
          healthPercentage: motorAnomaly ? 50 : 100,
          healthStatus: (!motorReady
            ? "Awaiting data"
            : motorAnomaly
              ? "Attention needed"
              : "Healthy") as Machine["healthStatus"],
        },
  );
  const current = machines[selectedIndex] || machines[0];
  const selectedAlert = alerts.find((a) => a.id === investigationId) || null;
  // Browser persistence is an external store; failures must be visible.
  useEffect(() => {
    try {
      localStorage.setItem("mistranics.machines.v2", JSON.stringify(registry));
      localStorage.setItem(
        "mistranics.alerts.v2",
        JSON.stringify(alerts.slice(0, 300)),
      );
      // eslint-disable-next-line react/set-state-in-effect
      setStorageError(false);
    } catch {
      // eslint-disable-next-line react/set-state-in-effect
      setStorageError(true);
    }
  }, [registry, alerts]);
  useEffect(() => {
    if (!state?.history.length) return;
    if (processed.current.session !== state.session_id)
      processed.current = { session: state.session_id, sequence: 0 };
    const unseen = state.history.filter(
      (sample) => sample.sequence > processed.current.sequence,
    );
    if (!unseen.length) return;
    processed.current.sequence = Math.max(
      ...unseen.map((sample) => sample.sequence),
    );
    const incoming: Alert[] = unseen.flatMap((sample) =>
      Object.entries(sample.readings)
        .filter(([, reading]) => reading.anomaly.status === "ANOMALY")
        .map(([key, reading]) => {
          const id = `mqtt-${sample.device_id}-${sample.sequence}-${key}`;
          const machine =
            registry.find((m) => m.id === "simulation-01") || MOTOR;
          return {
            id,
            machineId: machine.id,
            machineName: machine.name,
            machineCode: machine.code,
            title: `${sensorNames[key]} deviation`,
            description: `${reading.mean?.toFixed(2)} ${reading.unit} departed from the rolling baseline.`,
            severity: "High" as const,
            detectedTime: new Date(sample.timestamp).toLocaleTimeString(),
            detectedTimestamp: sample.timestamp,
            whatToCheckPreview:
              "Review the operating state and sensor connection.",
            detailedExplanation: `Statistical detection from the server simulator via MQTT. ${sensorNames[key]} has a z-score of ${reading.anomaly.z_score?.toFixed(2)} against a threshold of ±${reading.anomaly.threshold}. This indicates a deviation, not a confirmed mechanical diagnosis.`,
            evidence: [
              {
                metric: sensorNames[key],
                observed: `${reading.mean?.toFixed(3)} ${reading.unit}`,
                threshold: `baseline ${reading.anomaly.baseline_mean?.toFixed(3)} ${reading.unit}; z ±${reading.anomaly.threshold}`,
                timestamp: sample.timestamp,
              },
            ],
            whatToCheck: [
              "Sensor connection",
              "Operating load",
              "Recent simulator fault changes",
            ],
            troubleshootingSteps: [
              {
                step: 1,
                instruction: "Confirm the operating condition",
                detail:
                  "Check RPM, fault mode and severity in the server simulator.",
              },
              {
                step: 2,
                instruction: "Compare nearby readings",
                detail:
                  "Review temperature, current and vibration together. Confirm that the reading is not a transient.",
              },
              {
                step: 3,
                instruction: "Record the outcome",
                detail:
                  "Document the observed deviation and resolve this investigation once reviewed.",
              },
            ],
            recommendedActions: [
              "Review the simulation controls and correlate the affected sensors.",
            ],
            investigationId: id,
            investigationTitle: `${sensorNames[key]} deviation`,
            status: "active" as const,
          };
        }),
    );
    // Synchronize the external MQTT history with the persisted investigation log.
    // eslint-disable-next-line react/set-state-in-effect
    setAlerts((prev) => {
      const ids = new Set(prev.map((a) => a.id));
      const fresh = incoming.filter((a) => !ids.has(a.id));
      return fresh.length ? [...fresh.reverse(), ...prev].slice(0, 300) : prev;
    });
  }, [state, registry]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearch((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  function resolve(id: string) {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === id
          ? { ...a, status: "resolved", resolvedAt: new Date().toISOString() }
          : a,
      ),
    );
  }
  function saveMachine(machine: Machine) {
    setRegistry((prev) =>
      prev.some((m) => m.id === machine.id)
        ? prev.map((m) => (m.id === machine.id ? machine : m))
        : [...prev, machine],
    );
    setAlerts((prev) =>
      prev.map((a) =>
        a.machineId === machine.id
          ? { ...a, machineName: machine.name, machineCode: machine.code }
          : a,
      ),
    );
  }
  return (
    <div className="dashboard-ambient-bg industrial-shell flex h-screen w-screen overflow-hidden text-slate-800">
      <Sidebar
        isExpanded={expanded}
        onToggle={() => setExpanded((v) => !v)}
        activeNav={nav}
        onSelectNav={(key) => {
          setNav(key);
          setInvestigationId(null);
        }}
        onExit={onExit}
      />
      <main className="industrial-main flex min-w-0 flex-1 flex-col p-3 sm:p-4">
        <FloatingSearchBar
          onOpenSearch={() => setSearch(true)}
          totalMachines={machines.length}
          activeAlertsCount={alerts.filter((a) => a.status === "active").length}
        />
        <div className="industrial-mode-label">
          <span>INDUSTRIAL WORKSPACE</span>
          <span>
            Simulated operations ·{" "}
            {connected && state?.stream_status === "LIVE"
              ? "Motor stream connected"
              : "Motor stream waiting"}
          </span>
        </div>
        {storageError && (
          <p role="alert" className="form-error">
            Browser storage is unavailable. Changes remain in this session only.
          </p>
        )}
        {nav === "dashboard" && (
          <div className="industrial-dashboard">
            <div className="dashboard-left">
              <section className="dashboard-trends">
                <div className="industrial-sensor-select">
                  <label htmlFor="industrial-machine">Machine telemetry</label>
                  <select
                    id="industrial-machine"
                    value={current.id}
                    onChange={(e) =>
                      setSelectedIndex(
                        machines.findIndex((m) => m.id === e.target.value),
                      )
                    }
                  >
                    {machines.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                  </select>
                </div>
                {current.id === "simulation-01" ? (
                  <TelemetryChart
                    state={state}
                    connected={connected}
                    visibleSensors={current.sensors}
                    compact
                  />
                ) : (
                  <div className="sample-trends">
                    <span className="sample-label">
                      Illustrative fleet dataset
                    </span>
                    <Part1SensorTrends
                      machines={machines}
                      selectedMachineIndex={selectedIndex}
                      onSelectMachineIndex={setSelectedIndex}
                      onManualNavigate={(direction) =>
                        setSelectedIndex(
                          (i) =>
                            (i +
                              (direction === "next" ? 1 : -1) +
                              machines.length) %
                            machines.length,
                        )
                      }
                    />
                  </div>
                )}
              </section>
              <section className="dashboard-overview">
                <Part3MachineOverview
                  machines={machines}
                  onOpenMachineAnalytics={setAnalytics}
                />
              </section>
            </div>
            <section className="dashboard-alerts">
              <Part4ActiveAlerts
                alerts={alerts}
                onResolveAlert={resolve}
                onOpenInvestigation={(_, alert) => setInvestigationId(alert.id)}
              />
            </section>
          </div>
        )}
        {nav === "chatbot" && <ChatbotView machines={machines} />}
        {nav === "investigations" && (
          <Investigations
            alerts={alerts}
            selected={selectedAlert}
            onSelect={(a) => setInvestigationId(a?.id || null)}
            onResolve={resolve}
          />
        )}
        {nav === "manuals" && <Manuals machines={machines} />}
        {nav === "admin" && <Admin machines={registry} onSave={saveMachine} />}
      </main>
      <MachineAnalyticsModal
        machine={machines.find((m) => m.id === analytics?.id) || null}
        onClose={() => setAnalytics(null)}
        onOpenInvestigation={() => {
          const found = alerts.find((a) => a.machineId === analytics?.id);
          setAnalytics(null);
          setNav("investigations");
          setInvestigationId(found?.id || null);
        }}
      />
      <SearchDialog
        isOpen={search}
        onClose={() => setSearch(false)}
        machines={machines}
        alerts={alerts}
        onSelectMachine={(m) => {
          setSearch(false);
          setAnalytics(m);
        }}
        onSelectAlert={(a) => {
          setSearch(false);
          setNav("investigations");
          setInvestigationId(a.id);
        }}
      />
      {selectedAlert && nav !== "investigations" && (
        <InvestigationDetail
          alert={selectedAlert}
          onClose={() => setInvestigationId(null)}
          onResolve={resolve}
        />
      )}
    </div>
  );
}
export const App = () => {
  const [mode, setMode] = useState<"industrial" | "hands-on" | null>(null);
  return mode === "industrial" ? (
    <IndustrialWorkspace onExit={() => setMode(null)} />
  ) : mode === "hands-on" ? (
    <HandsOnView onExit={() => setMode(null)} />
  ) : (
    <ModeSelection onSelect={setMode} />
  );
};
export default App;
