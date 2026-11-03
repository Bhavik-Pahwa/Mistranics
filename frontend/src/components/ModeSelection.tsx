import { ArrowUpRight, Activity, Factory, Radio } from "lucide-react";
export function ModeSelection({
  onSelect,
}: {
  onSelect: (mode: "industrial" | "hands-on") => void;
}) {
  return (
    <main className="mode-screen">
      <header className="mode-brand">
        <span className="brand-symbol">m.</span> MISTRANICS{" "}
        <span className="prototype-label">PROTOTYPE / 01</span>
      </header>
      <div className="mode-intro">
        <span className="eyebrow">ONE PLATFORM. TWO PERSPECTIVES.</span>
        <h1>
          Know what’s happening.
          <br />
          <em>Before it matters.</em>
        </h1>
        <p>Choose your workspace to get started.</p>
      </div>
      <div className="mode-choices">
        <button
          className="mode-choice industrial-choice"
          onClick={() => onSelect("industrial")}
        >
          <span className="mode-number">01 / SIMULATED OPERATIONS</span>
          <div className="mode-art">
            <Factory strokeWidth={0.8} />
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <span className="art-chip">
              FLEET INTELLIGENCE <Activity size={14} />
            </span>
          </div>
          <div className="mode-copy">
            <span className="mode-tag">The big picture</span>
            <h2>
              Industrial Mode <ArrowUpRight />
            </h2>
            <p>
              Your fleet, in focus. Explore simulated machine telemetry,
              investigate anomalies, and find the next step.
            </p>
            <span className="mode-enter">
              Enter workspace <span>↗</span>
            </span>
          </div>
        </button>
        <button
          className="mode-choice hands-choice"
          onClick={() => onSelect("hands-on")}
        >
          <span className="mode-number">02 / CONNECTED HARDWARE</span>
          <div className="mode-art">
            <Radio strokeWidth={0.8} />
            <svg viewBox="0 0 400 90" className="signal-art" aria-hidden="true">
              <path d="M0 45H70L85 30L100 62L120 10L140 80L158 45H210L225 27L240 60L260 20L280 65L295 45H400" />
            </svg>
            <span className="art-chip">
              SENSOR TO SIGNAL <Activity size={14} />
            </span>
          </div>
          <div className="mode-copy">
            <span className="mode-tag">Closer to the machine</span>
            <h2>
              Hands-on Mode <ArrowUpRight />
            </h2>
            <p>
              Connect your sensor. Watch real readings take shape and spot
              anomalies as they happen.
            </p>
            <span className="mode-enter">
              Open sensor workspace <span>↗</span>
            </span>
          </div>
        </button>
      </div>
      <footer className="mode-footer">
        <span>CONDITION MONITORING, MADE CLEAR.</span>
        <span>Built for the people behind the machines.</span>
      </footer>
    </main>
  );
}
