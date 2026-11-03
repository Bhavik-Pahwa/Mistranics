"""Build reproducible, explicitly fictional manuals for Simulator.html only."""
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output" / "pdf"
VERSION = "simulation-v1"
CASES = {
    "normal": {
        "title": "Normal operation and baseline drift",
        "signature": "Healthy virtual motor: small shaft-frequency vibration and residual sensor noise. At a selected speed of 1500 rpm, modeled current settles near 1.6 A and the thermal target is 37 degC. Initial temperature is 28 degC and approaches the target gradually. A warming motor can trigger a statistical temperature deviation even with Normal selected.",
        "distinction": "A rolling z-score describes change relative to recent values. It is not a confirmed fault, an ISO vibration classification, or an approved machine limit. Constant high readings can become statistically normal as the baseline adapts.",
        "checks": ["Select Normal in the simulator and allow the temperature trend to settle.", "Compare the selected shaft speed with the recorded speed before interpreting current.", "Review the previous valid windows before interpreting a baseline deviation."],
        "recovery": "Compare repeat windows at the same selected speed and severity. Record the warm-up state and retain the initial event as a historical deviation.",
    },
    "imb": {
        "title": "Rotor imbalance",
        "signature": "Rotor imbalance increases acceleration X and Y at the shaft frequency, also called the once-per-revolution or 1x component. The imbalance contribution grows with severity and the square of effective speed. Vibration RMS rises while mean current changes only slightly. Temperature target has a small additional rise.",
        "distinction": "Dominant radial once-per-revolution motion with relatively modest current change supports an imbalance hypothesis. It differs from the twice-per-revolution axial motion used by Misalignment and the sharp impacts used by Bearing fault.",
        "checks": ["Compare acceleration X and acceleration Y with the Normal waveform at the same selected speed.", "Reduce the simulated speed and compare the change in vibration RMS.", "Return the fault selector to Normal and verify that radial vibration declines."],
        "recovery": "A declining radial waveform after removing the virtual imbalance supports the model experiment. The simulation does not prove a real rotor needs balancing.",
    },
    "mis": {
        "title": "Shaft and coupling misalignment",
        "signature": "Misalignment produces a twice-per-revolution or 2x harmonic in acceleration X and Z, an additional Y contribution, heating, and an approximate severity-dependent current rise. Axial acceleration Z must be interpreted relative to its gravity offset near 1 g, not as an absolute vibration magnitude.",
        "distinction": "Axial motion and a strong twice-per-revolution component distinguish misalignment from the radial imbalance experiment. Gyroscope channels respond to the modeled vibration but are not an independent confirmed alignment measurement.",
        "checks": ["Compare acceleration Z around its gravity offset with the Normal waveform.", "Compare the axial waveform and current trend while changing the simulated misalignment severity.", "Select Normal and verify that the extra harmonic contribution subsides."],
        "recovery": "Record the changed axial waveform and temperature trend. Temperature may remain elevated while the first-order model cools.",
    },
    "brg": {
        "title": "Bearing fault and friction impulses",
        "signature": "Bearing fault generates periodic acceleration impulses with a short ring-down, at approximately 3.57 times effective shaft frequency. Impacts enter X, Y, and Z with different amplitudes. Friction increases the thermal target and mean current; current also contains impact-related ripple.",
        "distinction": "Periodic sharp impacts and decaying high-frequency oscillations distinguish this case from the smoother imbalance waveform and the irregular Loose mount knocks. The simulator does not identify an actual bearing part number or prove a raceway defect.",
        "checks": ["Inspect the simulated acceleration waveform for repeated impacts and decaying oscillations.", "Compare current and temperature trends alongside the vibration RMS deviation.", "Reduce bearing-fault severity and compare the impact amplitudes before returning to Normal."],
        "recovery": "Verify declining impacts across repeat virtual windows. Preserve the evidence and avoid interpreting a single sampled axis mean as the complete impact waveform.",
    },
    "loose": {
        "title": "Loose mounting and irregular knocks",
        "signature": "Loose mount creates random knocks with ring-down and a half-shaft-frequency or 0.5x subharmonic. Effects appear mainly in X and Z acceleration, with small impact-related current spikes. Randomness means adjacent windows can differ substantially at identical controls.",
        "distinction": "Irregular timing and a half-frequency rattle distinguish loose mounting from the periodic Bearing fault experiment. A current spike can accompany a mechanical knock without establishing an electrical short.",
        "checks": ["Compare several simulated windows for irregular knocks instead of relying on a single point.", "Compare acceleration X and Z with the current trend during the loose-mount experiment.", "Select Normal and verify that irregular knock activity subsides over repeat windows."],
        "recovery": "Record the removed virtual fault and compare repeat windows. This guide supplies no physical mounting torque or fastener specification.",
    },
    "heat": {
        "title": "Overheating and reduced cooling",
        "signature": "Overheating raises the thermal target strongly with severity and adds a small shaft-frequency vibration contribution. Current rises modestly because the simplified model associates hot windings with a load increment. Temperature changes gradually rather than jumping immediately when controls change.",
        "distinction": "A sustained thermal rise with modest current change distinguishes Overheating from Overload, Winding short, and Stall, where the current rise is stronger. Temperature alone does not distinguish reduced cooling from every other physical cause.",
        "checks": ["Compare the temperature slope with current and selected shaft speed.", "Reduce simulated overheating severity and observe the delayed thermal response.", "Return to Normal and allow the virtual motor to cool before comparing a fresh steady period."],
        "recovery": "The cool-down button resets modeled temperature to 28 degC and can itself create a negative statistical deviation. Label this reset explicitly instead of reporting a new physical cooling fault.",
    },
    "over": {
        "title": "Overload and excess shaft torque",
        "signature": "Overload raises mean current substantially, adds torque-related ripple, increases heating, and reduces effective modeled rotation by a severity-dependent fraction. At maximum severity the current increment in the model is 1.6 times the selected-speed current term, while effective rotation loses 12 percent of selected speed.",
        "distinction": "Sustained high current with a load-related speed reduction and modest extra shaft vibration supports Overload. It differs from the fixed mains-related hum in Winding short and the near-locked rotor behavior in Stall. The published rpm is the selected setpoint, not a measured tachometer or effective rotor speed.",
        "checks": ["Compare the current trend with the Normal current at the same selected speed.", "Reduce simulated overload severity and verify that mean current falls.", "Inspect the simulated rotor motion and thermal trend before returning the fault selector to Normal."],
        "recovery": "Confirm current recovery over repeat windows and allow temperature to settle. A returned statistical NORMAL label alone is insufficient to prove that virtual overload was removed.",
    },
    "short": {
        "title": "Winding short and electrical ripple",
        "signature": "Winding short raises current and the thermal target, adds a 100 Hz current ripple, and introduces a 100 Hz hum in acceleration X, Y, and Z. The server waveform is sampled at 1 kHz. The three-second dashboard summaries sample state at a slower cadence and cannot establish a spectral frequency by themselves.",
        "distinction": "A fixed-frequency hum together with a strong current rise differentiates this modeled electrical case from smooth rotor imbalance. A temperature rise or a mean current value alone cannot confirm a physical winding short.",
        "checks": ["Inspect the server simulator waveform for the fixed-frequency current ripple and acceleration hum.", "Compare mean current and temperature with Normal at the same selected speed.", "Return the fault selector to Normal and verify that the added ripple and hum subside."],
        "recovery": "Keep waveform evidence separate from dashboard window means. This fictional guide contains no insulation-resistance procedure or authorization to test a real energized motor.",
    },
    "stall": {
        "title": "Stall and near-locked rotor",
        "signature": "Stall causes very high current, almost no effective modeled rotation, low residual shaft vibration, and rapid heating. At maximum severity effective speed loses 95 percent of the selected speed, the current increment is 4.5 times the selected-speed current term, and the thermal response time constant is 6 seconds instead of 12 seconds.",
        "distinction": "Very high current with nearly absent motion and relatively little vibration is the important combination. Low vibration does not mean a stalled motor is healthy. The displayed rpm is a control setpoint; it must not be described as actual rotor motion.",
        "checks": ["Compare high current with the nearly stationary simulated rotor and low vibration.", "Pause the simulator to record the virtual stall state and its controls.", "Select Normal and resume the simulator to compare current and motion recovery."],
        "recovery": "Observe a falling current after removing the virtual stall. Temperature retains its history unless the explicit cool-down control is used. The guide does not authorize repeated real-motor restart attempts.",
    },
}

DOCUMENTS = [
    ("SIM-MTR-FAULTS", "Simulated motor - complete fault handbook", list(CASES)),
    ("SIM-MTR-MECHANICAL", "Simulated motor - mechanical troubleshooting", ["normal", "imb", "mis", "brg", "loose"]),
    ("SIM-MTR-ELECTRICAL", "Simulated motor - electrical and thermal troubleshooting", ["normal", "heat", "over", "short", "stall"]),
]


def build():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Kicker", fontSize=9, textColor=colors.HexColor("#648878"), spaceAfter=14))
    styles["Title"].fontSize = 25
    styles["Title"].leading = 30
    styles["Title"].textColor = colors.HexColor("#203e36")
    styles["BodyText"].fontSize = 11
    styles["BodyText"].leading = 16
    styles["BodyText"].spaceAfter = 12
    styles["Heading2"].textColor = colors.HexColor("#326b57")
    manifest = []
    for identity, title, modes in DOCUMENTS:
        filename = identity.lower() + ".pdf"
        story = []
        def paragraph(text, style="BodyText"):
            story.append(Paragraph(escape(text), styles[style]))
        paragraph("MISTRANICS / SIMULATION TRAINING / " + VERSION, "Kicker")
        paragraph(title, "Title")
        story.append(Spacer(1, 18))
        paragraph("FICTIONAL TRAINING MANUAL - NOT A MANUFACTURER DOCUMENT", "Heading2")
        paragraph("Applicability: Prototype motor MTR-001, asset simulation-01, Simulator.html and the Python server model. These fictional instructions apply only to virtual controls. They are not approved physical-equipment limits, maintenance specifications, or evidence of a real fault.")
        paragraph("READING THE SIGNAL", "Heading2")
        paragraph("Channels: temperature in degC; motor current in A; vibration RMS and acceleration X/Y/Z in g; gyroscope X/Y/Z in deg/s. Published rpm is the selected setpoint. Effective rotation is reduced internally for Overload and Stall. Acceleration RMS in g must not be relabeled as velocity in mm/s.")
        paragraph("The simulator publishes non-retained MQTT sensor windows. Each window includes min, mean, max and sample count. Waveforms contain the faster model samples; slow dashboard summaries do not prove a harmonic or spectral frequency.")
        paragraph("DETECTION AND ILLUSTRATIVE LABELS", "Heading2")
        paragraph("Each channel has its own rolling z-score against previous valid values. The default detector warms up over five windows, uses up to twenty baseline values, and flags an absolute score of at least three. A standard-deviation floor prevents division by zero. A statistical deviation does not identify its physical cause.")
        paragraph("Illustrative model labels use vibration above 0.15 g or temperature above 60 degC or relative current above 1.35 for WARNING, and vibration above 0.35 g or temperature above 75 degC or relative current above 1.9 for FAULT. Relative current uses the selected-speed healthy-current model. These demonstration labels are independent of the rolling detector and are not approved operating limits.")
        for mode in modes:
            case = CASES[mode]
            story.append(PageBreak())
            paragraph("SIMULATION ONLY / MODE " + mode.upper(), "Kicker")
            paragraph(case["title"], "Title")
            paragraph("EXPECTED SIMULATED SIGNATURE", "Heading2")
            paragraph(case["signature"])
            paragraph("DISTINGUISHING EVIDENCE", "Heading2")
            paragraph(case["distinction"])
            paragraph("VIRTUAL TROUBLESHOOTING CHECKS", "Heading2")
            for check in case["checks"]:
                paragraph(check)
            paragraph("RECOVERY AND LIMITATIONS", "Heading2")
            paragraph(case["recovery"])
        story.append(PageBreak())
        paragraph("ACQUISITION AND STATISTICAL EDGE CASES", "Title")
        for heading, text in [
            ("Missing or stale readings", "Check whether the server, MQTT broker and publisher are connected. A paused model, stopped publisher or disconnected broker can leave old points visible. An old point is history and must not be reported as a fresh normal observation. Resume the publisher and wait for a new valid timestamp."),
            ("Sensor error or disconnected sensor", "A sensor error has null features and zero samples. Missing data is not zero current or a cold temperature. Check the sensor status, sample count and unit before interpreting an apparent deviation."),
            ("Duplicate, overlapping or rejected windows", "QoS redelivery can repeat a sequence. The backend ignores duplicate or out-of-order identities and rejects overlapping, stale, future-dated or invalid windows. A missing graph point can indicate rejected transport data rather than a mechanical fault. Compare the publisher and backend clocks and review the received sequence."),
            ("Startup, control changes and baseline adaptation", "Warm-up, RPM changes, a changed fault severity, and the cool-down reset can all create deviations. Sustained abnormal values can enter the rolling baseline and later receive a NORMAL label. Record the selected mode and control changes alongside every anomaly."),
            ("Stopping and restarting", "Setting selected speed to zero drives modeled current toward zero and removes shaft-driven vibration. This intentional shutdown can differ from the previous rolling baseline. A restarted backend rebuilds its history and baseline. Compare like operating conditions and do not invent measurements across a gap."),
        ]:
            paragraph(heading.upper(), "Heading2")
            paragraph(text)
        def footer(canvas, doc):
            canvas.setStrokeColor(colors.HexColor("#d4e1d8"))
            canvas.line(46, 44, A4[0] - 46, 44)
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#688172"))
            canvas.drawString(46, 30, f"FICTIONAL / {identity} / {VERSION}")
            canvas.drawRightString(A4[0] - 46, 30, f"Page {doc.page}")
        doc = SimpleDocTemplate(str(OUTPUT / filename), pagesize=A4, leftMargin=46, rightMargin=46, topMargin=44, bottomMargin=62, title=title, author="Mistranics fictional training corpus", invariant=1)
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        manifest.append(dict(document_id=identity, version=VERSION, title=title, filename=filename, modes=modes, fictional=True, asset_id="simulation-01"))
    (OUTPUT / "simulation-manuals.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    build()
