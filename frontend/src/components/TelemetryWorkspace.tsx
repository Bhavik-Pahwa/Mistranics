import { useState } from "react";
import { Activity, ArrowLeft, Radio, AlertTriangle } from "lucide-react";
import { sensorNames, useTelemetry } from "../hooks/useTelemetry";
import type { Stream } from "../hooks/useTelemetry";

export function TelemetryChart({
  state,
  connected,
  compact = false,
  visibleSensors,
}: {
  state: Stream | null;
  connected: boolean;
  compact?: boolean;
  visibleSensors?: string[];
}) {
  const [selected, setSelected] = useState("temperature");
  const available = Object.keys(
    state?.latest?.readings || { temperature: null },
  );
  const keys = available.filter(
    (key) => !visibleSensors || visibleSensors.includes(key),
  );
  if (!keys.length) keys.push(visibleSensors?.[0] || "temperature");
  const metric = keys.includes(selected) ? selected : keys[0];
  const reading = state?.latest?.readings[metric];
  const history = state?.history || [];
  const values = history.flatMap((p) =>
    p.readings[metric]?.mean == null ? [] : [p.readings[metric].mean!],
  );
  const low = values.length
    ? Math.min(...values) -
      Math.max(0.5, (Math.max(...values) - Math.min(...values)) * 0.2)
    : 0;
  const high = values.length
    ? Math.max(...values) +
      Math.max(0.5, (Math.max(...values) - Math.min(...values)) * 0.2)
    : 100;
  const points = history.map((p, i) => ({
    sample: p,
    reading: p.readings[metric],
    x: 55 + (i / Math.max(history.length - 1, 1)) * 865,
  }));
  const y = (v: number) => 245 - ((v - low) / (high - low)) * 205;
  const status = !connected
    ? "Connecting to backend"
    : state?.stream_status === "LIVE"
      ? "Receiving readings"
      : state?.stream_status === "SENSOR_ERROR"
        ? "Sensor error"
        : "Waiting for sensor";
  const path = points
    .map((p, index) =>
      p.reading?.mean == null
        ? ""
        : `${index > 0 && points[index - 1].reading?.mean != null ? "L" : "M"}${p.x},${y(p.reading.mean)}`,
    )
    .join(" ");
  return (
    <section className={`telemetry-panel ${compact ? "compact" : ""}`}>
      <div className="telemetry-heading">
        <div>
          <span className="eyebrow">
            {state?.source === "simulation"
              ? "SIMULATED MOTOR · MQTT"
              : "SENSOR OBSERVATORY"}
          </span>
          <h2>{sensorNames[metric] || metric}</h2>
        </div>
        <span
          className={`connection-pill ${connected && state?.stream_status === "LIVE" ? "online" : ""}`}
        >
          <i />
          {status}
        </span>
      </div>
      <div className="sensor-tabs" aria-label="Sensor readings">
        {keys.map((key) => (
          <button
            key={key}
            aria-pressed={metric === key}
            onClick={() => setSelected(key)}
          >
            {sensorNames[key] || key}
          </button>
        ))}
      </div>
      <div className="reading-line">
        <strong>
          {reading?.mean?.toFixed(2) ?? "—"}
          <small>{reading?.unit === "degC" ? "°C" : reading?.unit}</small>
        </strong>
        <span role="status" aria-label="Sensor detection">
          {reading?.anomaly.status.replaceAll("_", " ") || "NO DATA YET"}
          <small>
            {state?.latest
              ? new Date(state.latest.timestamp).toLocaleTimeString()
              : "A new window arrives every 3 seconds"}
          </small>
        </span>
      </div>
      <div className="telemetry-plot">
        <svg
          viewBox="0 0 950 285"
          role="img"
          aria-label={`${sensorNames[metric]} readings; red points indicate detected anomalies`}
        >
          {[0, 1, 2, 3, 4].map((i) => (
            <g key={i}>
              <line
                x1="55"
                x2="920"
                y1={40 + i * 51.25}
                y2={40 + i * 51.25}
                stroke="#e7edf0"
              />
              <text
                x="43"
                y={44 + i * 51.25}
                textAnchor="end"
                fill="#7b8999"
                fontSize="10"
              >
                {(high - (i / 4) * (high - low)).toFixed(1)}
              </text>
            </g>
          ))}
          <path d={path} fill="none" stroke="#11998c" strokeWidth="2.5" />
          {points.map((p) =>
            p.reading?.mean == null ? null : (
              <circle
                key={p.sample.sequence}
                cx={p.x}
                cy={y(p.reading.mean)}
                r={p.reading.anomaly.status === "ANOMALY" ? 5 : 2.5}
                fill={
                  p.reading.anomaly.status === "ANOMALY" ? "#e34d59" : "#11998c"
                }
              >
                <title>
                  {new Date(p.sample.timestamp).toLocaleTimeString()} ·{" "}
                  {p.reading.mean.toFixed(3)} {p.reading.unit} ·{" "}
                  {p.reading.anomaly.status}
                </title>
              </circle>
            ),
          )}
          {[
            points[0],
            points.length > 1 ? points[points.length - 1] : null,
          ].map((p, i) =>
            p ? (
              <text
                key={i}
                x={p.x}
                y="272"
                textAnchor={i ? "end" : "start"}
                fontSize="10"
                fill="#7b8999"
              >
                {new Date(p.sample.timestamp).toLocaleTimeString()}
              </text>
            ) : null,
          )}
        </svg>
        {!values.length && (
          <div className="chart-empty">
            <Radio size={28} />
            <strong>Ready when your sensor is.</strong>
            <span>
              {connected
                ? "No readings received for this workspace yet."
                : "Connecting to the telemetry service…"}
            </span>
          </div>
        )}
      </div>
      <div className="chart-foot">
        <span>
          <i /> Observed reading <i className="red" /> Anomaly
        </span>
        <span>
          {history.length} / 60 windows ·{" "}
          {state?.latest?.device_id || "Awaiting device"}
        </span>
      </div>
    </section>
  );
}
export function HandsOnView({ onExit }: { onExit: () => void }) {
  const { state, connected } = useTelemetry("physical");
  const events = (state?.history || [])
    .flatMap((sample) =>
      Object.entries(sample.readings)
        .filter(
          ([, r]) => r.anomaly.status === "ANOMALY" || r.status !== "valid",
        )
        .map(([key, reading]) => ({ sample, key, reading })),
    )
    .reverse();
  return (
    <main className="hands-workspace">
      <header className="workspace-top">
        <button onClick={onExit}>
          <ArrowLeft size={17} /> Workspaces
        </button>
        <span className="wordmark">
          mistranics<span> / hands-on</span>
        </span>
        <span className="workspace-badge">
          <Radio size={14} /> CONNECTED HARDWARE
        </span>
      </header>
      <div className="hands-content">
        <div className="page-intro">
          <span className="eyebrow">REAL READINGS. CLEAR SIGNALS.</span>
          <h1>
            Your machine, <em>in the moment.</em>
          </h1>
          <p>A direct view of your sensor. Every reading, every deviation.</p>
        </div>
        <TelemetryChart state={state} connected={connected} />
        <div className="event-heading">
          <h2>
            <Activity size={18} /> Detection log
          </h2>
          <span>{events.length} events in the current window</span>
        </div>
        <div className="detection-list">
          {events.length ? (
            events.map(({ sample, key, reading }) => (
              <article
                className="detection-card"
                key={`${sample.sequence}-${key}`}
              >
                <AlertTriangle size={20} />
                <div>
                  <h3>
                    {sensorNames[key]}{" "}
                    {reading.status !== "valid"
                      ? "sensor error"
                      : "anomaly detected"}
                  </h3>
                  <p>
                    {sample.device_id} ·{" "}
                    {new Date(sample.timestamp).toLocaleString()} · Window #
                    {sample.sequence}
                  </p>
                  <dl>
                    <div>
                      <dt>Observed</dt>
                      <dd>
                        {reading.mean?.toFixed(2) ?? "Unavailable"}{" "}
                        {reading.unit}
                      </dd>
                    </div>
                    <div>
                      <dt>Baseline</dt>
                      <dd>
                        {reading.anomaly.baseline_mean?.toFixed(2) ?? "—"}{" "}
                        {reading.unit}
                      </dd>
                    </div>
                    <div>
                      <dt>Z-score / threshold</dt>
                      <dd>
                        {reading.anomaly.z_score?.toFixed(2) ?? "—"} / ±
                        {reading.anomaly.threshold}
                      </dd>
                    </div>
                    <div>
                      <dt>Samples</dt>
                      <dd>{reading.sample_count}</dd>
                    </div>
                  </dl>
                </div>
              </article>
            ))
          ) : (
            <div className="empty-log">
              <Activity size={22} />
              <div>
                <h3>
                  {state?.latest
                    ? "No anomalies in this window"
                    : "Listening for the first reading"}
                </h3>
                <p>
                  {state?.latest
                    ? "Detections appear here after the statistical baseline is established."
                    : "Connect your hardware publisher to begin monitoring."}
                </p>
              </div>
            </div>
          )}
        </div>
        <footer className="hands-footer">
          Statistical anomaly detection · Baseline builds over the first 5 valid
          windows
        </footer>
      </div>
    </main>
  );
}
