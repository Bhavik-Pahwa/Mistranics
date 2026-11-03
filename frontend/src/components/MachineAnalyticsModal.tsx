import type { Machine } from "../types/dashboard";
import { Modal } from "./Modal";
import { sensorNames } from "../hooks/useTelemetry";
export function MachineAnalyticsModal({
  machine,
  onClose,
  onOpenInvestigation,
}: {
  machine: Machine | null;
  onClose: () => void;
  onOpenInvestigation?: (name: string) => void;
}) {
  if (!machine) return null;
  const motor = machine.id === "simulation-01";
  return (
    <Modal title={`${machine.name} · ${machine.code}`} onClose={onClose}>
      <p>
        {machine.type} · {machine.location}
      </p>
      <p className="detail-meta">
        {motor
          ? "Server simulation received through MQTT. Vibration is acceleration RMS in g."
          : machine.telemetry.length
            ? "Illustrative fleet dataset. Values below are prototype samples."
            : "Awaiting telemetry. This machine has been registered locally."}
      </p>
      <h3>{motor ? "Current sensor window" : "Machine overview"}</h3>
      <div className="evidence-grid">
        {motor ? (
          Object.entries(machine.readings || {}).map(([key, reading]) => (
            <div key={key}>
              <span>{sensorNames[key] || key}</span>
              <strong>
                {reading.value?.toFixed(3) ?? "—"} {reading.unit}
              </strong>
            </div>
          ))
        ) : (
          <>
            <div>
              <span>Drive speed</span>
              <strong>
                {machine.telemetry.length ? machine.metrics.rpm : "—"} rpm
              </strong>
            </div>
            <div>
              <span>Discharge pressure</span>
              <strong>
                {machine.telemetry.length ? machine.metrics.pressureBar : "—"}{" "}
                bar
              </strong>
            </div>
            <div>
              <span>Lube oil temperature</span>
              <strong>
                {machine.telemetry.length ? machine.metrics.lubeOilTemp : "—"}{" "}
                °C
              </strong>
            </div>
          </>
        )}
      </div>
      {motor && (
        <p className="detail-meta">
          Stream: {machine.streamStatus || "Awaiting data"}
        </p>
      )}
      <h3>Recent telemetry</h3>
      {machine.telemetry.length ? (
        <div className="telemetry-table-wrap">
          <table className="telemetry-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Temperature · °C</th>
                <th>Vibration · {motor ? "g" : "mm/s"}</th>
              </tr>
            </thead>
            <tbody>
              {machine.telemetry
                .slice(-20)
                .reverse()
                .map((p, i) => (
                  <tr key={i}>
                    <td>{p.time}</td>
                    <td>{p.temperature.toFixed(2)}</td>
                    <td>{p.vibration.toFixed(3)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>No readings received.</p>
      )}
      <h3>Configured sensors</h3>
      <div className="sensor-chips">
        {(machine.sensors || ["temperature", "vibration", "current"]).map(
          (s) => (
            <span key={s}>{sensorNames[s] || s}</span>
          ),
        )}
      </div>
      <button
        className="primary-button"
        style={{ marginTop: 24 }}
        onClick={() => onOpenInvestigation?.(machine.name)}
      >
        View investigations
      </button>
    </Modal>
  );
}
