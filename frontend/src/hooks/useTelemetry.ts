import { useEffect, useState } from "react";

export type Source = "physical" | "simulation";
export interface Detection {
  status: string;
  method: string;
  value: number | null;
  baseline_mean: number | null;
  baseline_std: number | null;
  z_score: number | null;
  threshold: number;
  baseline_samples: number;
}
export interface Reading {
  mean: number | null;
  min: number | null;
  max: number | null;
  unit: string;
  sample_count: number;
  status: string;
  anomaly: Detection;
}
export interface Sample {
  source: Source;
  device_id: string;
  sequence: number;
  timestamp: string;
  readings: Record<string, Reading>;
}
export interface Stream {
  session_id: string;
  source: Source;
  mqtt_connected: boolean;
  stream_status: string;
  history: Sample[];
  latest: Sample | null;
}
export const sensorNames: Record<string, string> = {
  temperature: "Temperature",
  current: "Motor current",
  vibration: "Vibration RMS",
  rpm: "Shaft speed",
  ax: "Acceleration X",
  ay: "Acceleration Y",
  az: "Acceleration Z",
  gx: "Gyroscope X",
  gy: "Gyroscope Y",
  gz: "Gyroscope Z",
};
export function useTelemetry(source: Source) {
  const [state, setState] = useState<Stream | null>(null);
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    let stopped = false,
      socket: WebSocket | null = null,
      retry: ReturnType<typeof setTimeout>,
      received = Date.now();
    // Clear the external stream when subscribing to a different source.
    // eslint-disable-next-line react/set-state-in-effect
    setState(null);
    setConnected(false);
    function connect() {
      const url = new URL(`/ws/telemetry?source=${source}`, location.href);
      url.protocol = location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(url);
      received = Date.now();
      socket.onmessage = (e) => {
        if (stopped) return;
        try {
          const next = JSON.parse(e.data);
          if (next.source !== source || !Array.isArray(next.history)) return;
          setState(next);
          setConnected(true);
          received = Date.now();
        } catch {
          socket?.close();
        }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (!stopped) {
          setConnected(false);
          retry = setTimeout(connect, 1500);
        }
      };
    }
    connect();
    const heartbeat = setInterval(() => {
      if (Date.now() - received > 5000) {
        setConnected(false);
        socket?.close();
      }
    }, 1000);
    return () => {
      stopped = true;
      clearTimeout(retry);
      clearInterval(heartbeat);
      socket?.close();
    };
  }, [source]);
  return { state, connected };
}
