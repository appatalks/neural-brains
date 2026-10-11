"""Build the project whitepaper PDF; requires the optional ReportLab package."""

import argparse
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
INK = colors.HexColor("#162A3A")
TEAL = colors.HexColor("#087F8C")
MUTED = colors.HexColor("#526574")
LIGHT = colors.HexColor("#EEF5F7")
AMBER = colors.HexColor("#A66617")
WIDTH = A4[0] - 38 * mm
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle("PaperBody", fontName="Helvetica", fontSize=10,
                         leading=14.5, textColor=INK, spaceAfter=9))
STYLES.add(ParagraphStyle("PaperTitle", fontName="Helvetica-Bold", fontSize=34,
                         leading=39, textColor=INK, spaceAfter=18))
STYLES.add(ParagraphStyle("PaperSubtitle", fontName="Helvetica", fontSize=17,
                         leading=23, textColor=MUTED, spaceAfter=18))
STYLES.add(ParagraphStyle("PaperHeading", fontName="Helvetica-Bold", fontSize=20,
                         leading=25, textColor=INK, spaceAfter=16))
STYLES.add(ParagraphStyle("PaperSection", fontName="Helvetica-Bold", fontSize=12,
                         leading=17, textColor=TEAL, spaceBefore=9, spaceAfter=7))
STYLES.add(ParagraphStyle("PaperSmall", fontName="Helvetica", fontSize=8.5,
                         leading=12, textColor=MUTED, spaceAfter=7))
STYLES.add(ParagraphStyle("PaperTable", fontName="Helvetica", fontSize=8.6,
                         leading=11.6, textColor=INK))
STYLES.add(ParagraphStyle("PaperTableHeader", parent=STYLES["PaperTable"],
                         fontName="Helvetica-Bold", textColor=colors.white))
STYLES.add(ParagraphStyle("PaperCode", fontName="Courier", fontSize=8.2,
                         leading=12, textColor=INK, backColor=LIGHT,
                         borderPadding=10, spaceAfter=12))


def paragraph(text, style="PaperBody"):
    return Paragraph(text, STYLES[style])


def section(title, text):
    return [paragraph(title, "PaperSection"), paragraph(text)]


def table(headers, rows, widths):
    data = [[paragraph(escape(str(cell)), "PaperTableHeader") for cell in headers]]
    data += [[paragraph(escape(str(cell)).replace("\n", "<br/>"), "PaperTable") for cell in row]
             for row in rows]
    result = Table(data, colWidths=[WIDTH * width for width in widths],
                   repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT, colors.white]),
        ("LINEBELOW", (0, 0), (-1, 0), .7, TEAL),
        ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor("#D6E1E6")),
    ]))
    return result


def callout(title, text):
    result = Table([[paragraph(title, "PaperSection")], [paragraph(text)]],
                   colWidths=[WIDTH], hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("LINEBEFORE", (0, 0), (0, -1), 3, TEAL),
        ("LEFTPADDING", (0, 0), (-1, -1), 13),
        ("RIGHTPADDING", (0, 0), (-1, -1), 13),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return KeepTogether([result, Spacer(1, 12)])


class LoopDiagram(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = WIDTH, 147

    def draw(self):
        canvas = self.canv
        boxes = [
            ("01  PHYSICAL WORLD", "Geometry, contact, eye pose", False),
            ("02  SENSORY ENCODER", "Declared input approximations", True),
            ("03  FLYWIRE BRAIN", "Actual chemical-network spikes", False),
            ("04  DESCENDING SIGNAL", "Verified GF / DNp10 identities", False),
            ("05  MOTOR BOUNDARY", "Reduced / learned / assisted", True),
            ("06  BODY PHYSICS", "Actuators, forces, joint motion", False),
        ]
        cell_width = (WIDTH - 22) / 3
        for index, (title, subtitle, assumed) in enumerate(boxes):
            row, column = divmod(index, 3)
            x, y = column * (cell_width + 11), 90 - row * 70
            canvas.setFillColor(LIGHT)
            canvas.roundRect(x, y, cell_width, 52, 5, fill=1, stroke=0)
            canvas.setFillColor(AMBER if assumed else TEAL)
            canvas.rect(x, y, 3, 52, fill=1, stroke=0)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawString(x + 9, y + 32, title)
            canvas.setFont("Helvetica", 7.1)
            canvas.drawString(x + 9, y + 16, subtitle)
        canvas.setStrokeColor(TEAL)
        canvas.setLineWidth(1)
        for x in (cell_width + 1, 2 * cell_width + 12):
            canvas.line(x, 116, x + 9, 116)
            canvas.line(x, 46, x + 9, 46)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(0, 4, "Physics updates the next sensory sample; this is not yet a fully biological motor loop.")


def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D6E1E6"))
    canvas.line(19 * mm, 17 * mm, A4[0] - 19 * mm, 17 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(19 * mm, 11.5 * mm, "NEURAL-BRAINS  |  DEVELOPMENT WHITEPAPER  |  11 OCT 2026")
    canvas.drawRightString(A4[0] - 19 * mm, 11.5 * mm, str(document.page))
    if document.page > 1:
        canvas.setFont("Helvetica", 8)
        canvas.drawString(19 * mm, A4[1] - 13 * mm,
                          "CONNECTOME-INFORMED SIMULATION AND EMBODIED CAUSALITY")
    canvas.restoreState()


def build(output):
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    story = []
    story += [Spacer(1, 28 * mm),
              paragraph("NEURAL-BRAINS", "PaperSection"),
              paragraph("From connectivity<br/>to embodied causality", "PaperTitle"),
              paragraph("A connectome-informed fruit-fly simulation<br/>and reproducible research platform", "PaperSubtitle"),
              paragraph("PROJECT WHITEPAPER<br/>Version 1.0  |  11 October 2026", "PaperSmall"),
              Spacer(1, 13 * mm),
              table(["BRAIN SNAPSHOT", "EMBODIMENT", "RESEARCH STANDARD"], [
                  ["127,400 neurons\n14,687,178 chemical edges",
                   "One articulated body\nOne browser application",
                   "Traceable inputs\nCausal controls\nPreserved failures"],
              ], [.35, .31, .34]),
              Spacer(1, 13 * mm),
              paragraph("Developed in the <b>appatalks/neural-brains</b> project.<br/>"
                        '<link href="https://github.com/appatalks/neural-brains" color="#087F8C">'
                        "github.com/appatalks/neural-brains</link>"),
              callout("Claim boundary",
                      "A development-stage hybrid research system, not a complete biological fly. "
                      "Actual neural causation is demonstrated in bounded experiments; learned motor policies, "
                      "approximate sensory encoding and assisted transitions remain explicitly identified."),
              paragraph("This document is a project whitepaper, not a peer-reviewed publication or independent "
                        "biological validation. Measurements describe named experiments, not universal performance.",
                        "PaperSmall"),
              PageBreak()]

    story += [paragraph("01  Executive summary", "PaperHeading"),
              paragraph("neural-brains investigates how verified nervous-system connectivity can constrain "
                        "a physically embodied computational model. The active research track is "
                        "<i>Drosophila melanogaster</i>, supported by a broader catalog of seven species "
                        "and eleven dataset entries. The project emphasizes reproducibility and causal "
                        "interventions rather than interpreting animation or loaded connectivity as animal fidelity."),
              paragraph("The implemented brain is a persistent FlyWire630 chemical-network model. A single "
                        "browser application brings the physical habitat, rendered eye views, exact sparse "
                        "spike counts and chemical-connection inspection together. The body uses FlyBody "
                        "and MuJoCo, with published learned policies for walking and wing control."),
              callout("Central research question",
                      "Can a traceable sensory stimulus propagate through a version-matched connectome, "
                      "change physical actuation, and return through a measured sensory-feedback interface "
                      "without hidden resets, fabricated firing or a direct stimulus-to-motion bypass?"),
              *section("Demonstrated capabilities",
                       "The project reproduces a bounded sugar-to-MN9 result, uses actual giant-fiber (GF) "
                       "spikes for takeoff initiation, and links verified DNp10 responses to physical "
                       "leg-extension experiments. Additional engineering comparisons support curved "
                       "flight, movable-seed contact and an explicitly assisted, neural-initiated landing "
                       "transition with post-assistance walking."),
              *section("What is not established",
                       "Walking and wing actions are not generated by a reconstructed VNC-to-muscle "
                       "circuit. Sensory input curves, neuromodulatory state, proprioception and material "
                       "parameters are not fully calibrated. Spontaneous takeoff, organic directional "
                       "flight, robust terrain-aware landing and long-duration natural behavior remain open."),
              *section("How to read the evidence",
                       "A software test validates a contract. A neural intervention validates propagation "
                       "inside a specified model. A physical trial validates its measured kinematics. "
                       "None of these alone establishes equivalence to a living animal. This separation "
                       "is the organizing principle of the project."),
              paragraph("Document map: architecture (p. 3), provenance and methods (p. 4), neural/feedback "
                        "results (p. 5), physical results (p. 6), limitations (p. 7), reproducibility "
                        "and roadmap (p. 8), references (p. 9).", "PaperSmall"),
              PageBreak()]

    story += [paragraph("02  System architecture", "PaperHeading"),
              LoopDiagram(), Spacer(1, 8),
              table(["LAYER", "IMPLEMENTATION", "EVIDENCE BOUNDARY"], [
                  ["Brain", "Persistent Brian2 model; exact FlyWire630 IDs and chemical connections.",
                   "Connectivity is measured data; homogeneous dynamics, weights and signs follow model assumptions."],
                  ["Sensory", "Geometric sugar exposure; visible spherical expansion; optional graded and landing-surface input.",
                   "Approximations, not calibrated receptor physiology or a full retinal motion model."],
                  ["Descending", "GF initiation; DNp10 count-based leg response and reduced landing request.",
                   "Verified brain identities; no direct male-VNC/female-brain ID merge."],
                  ["Motor", "Published learned walking/flight policies; reduced activation and explicit assistance.",
                   "Not reconstructed natural muscle recruitment or calibrated force physiology."],
                  ["Physics", "One body with legs and wings, contact dynamics, wing-fluid interaction and loose objects.",
                   "Physical actuation is real model dynamics; material and object parameters remain assumptions."],
                  ["Observatory", "Authoritative world/eyes, sparse interval counts and bounded connection queries.",
                   "The neuron map is schematic index space, not anatomical spatial layout."],
              ], [.16, .42, .42]),
              *section("Clock and process boundaries",
                       "The neural model advances at a 0.1 ms timestep; the usual coupled neural interval "
                       "is 10 ms. Body control advances every 0.2 ms with 0.05 ms physics steps. Counts "
                       "arrive at an interval boundary and affect only subsequent physical steps; the "
                       "system does not invent sub-interval spike times or apply motion retroactively."),
              paragraph("The brain worker, biomechanics launcher and FlyBody/policy backend use separate "
                        "pinned environments. An independent observer renderer consumes physical "
                        "snapshots without stepping or modifying the source body. Interactive application "
                        "traffic is restricted to one local port: <b>127.0.0.1:8840</b>."),
              PageBreak()]

    story += [paragraph("03  Provenance and validation method", "PaperHeading"),
              *section("Version-matched data",
                       "The active model uses the historical FlyWire630 processed inputs associated with "
                       "the pinned Shiu-model source [1, 2]. It does not silently substitute the newer "
                       "FlyWire783 release. Historical annotation identities are retained as decimal "
                       "strings, with exact membership checks against the model."),
              paragraph("The model contains <b>127,400 neurons</b> and <b>14,687,178 aggregated chemical "
                        "connections</b>. These are not counts of individually simulated synaptic "
                        "contacts, electrical junctions or end-organ connections. Chemical counts and "
                        "assigned sign proxies are not measured conductances."),
              *section("Cross-specimen correspondence",
                       "Female FlyWire root IDs and male MANC body IDs occupy separate namespaces. "
                       "Published light-level type correspondence is recorded with its reported confidence, "
                       "not treated as neuron identity equality. DNa04/DNa05 cell-type pairs remain distinct "
                       "from DNae004/DNae006 pairs carrying those historical hemibrain names [5, 6]."),
              table(["VALIDATION LAYER", "REQUIRED OBSERVATION"], [
                  ["Software", "Strict schemas, units, ID precision, clock agreement, reset/pause behavior and explicit failure."],
                  ["Neural reproduction", "Actual count conservation; baseline and chunked parity; silent no-input controls."],
                  ["Causal intervention", "Intact versus sham, output disconnection or spike silencing; exact reset replay."],
                  ["Embodied behavior", "Recorded forces/actions, contact sequence, trajectories and physical state continuity."],
                  ["Claim acceptance", "Predeclared thresholds; held-out cases; failed bundles preserved without relabeling."],
              ], [.29, .71]),
              *section("Intervention semantics",
                       "Source-output disconnection zeros selected recurrent chemical weights but keeps "
                       "source input and spikes. DNp10 model spike silencing clamps selected voltage and "
                       "synaptic state before threshold evaluation. Neither intervention is asserted to "
                       "be equivalent to a particular animal silencing technique."),
              paragraph("Assets and derived results remain outside Git. Receipts preserve source URLs, "
                        "sizes, hashes and available licensing metadata. Unverified asset rights are not "
                        "silently converted into redistribution permission. Experiments distinguish "
                        "untouched controls from runs receiving user edits, pushes or resets.",
                        "PaperSmall"),
              PageBreak()]

    story += [paragraph("04  Neural and feedback evidence", "PaperHeading"),
              table(["EXPERIMENT", "MEASURED RESULT", "INTERPRETATION"], [
                  ["Sugar baseline", "MN9 activation in 30/30 stimulated trials; resting control silent.",
                   "Bounded reproduction of the intact sugar-to-MN9 model condition, not physical feeding."],
                  ["Visual chemical causality", "Seed 420 intact/sham: 58,750 network spikes and 326 GF spikes. Both-source disconnection: 31,083 spikes and zero GF.",
                   "Disconnected-source spikes remain; downstream responses require model chemical propagation."],
                  ["Reduced DNp10 leg pathway", "48 physical trials; 102/102 declared checks. Peak mean front-tibia differences: 0.184-0.353 rad.",
                   "Actual neural counts cause a physical effect through an explicitly assumed actuator surrogate."],
                  ["Graded sensory feedback", "44 trials; 100/100 declared checks with stable source hashes. Source/DN/motor and sensory replay/cut controls.",
                   "A continuously encoded feedback interface, not proof of biological closed-loop stabilization."],
              ], [.22, .43, .35]),
              *section("What the feedback experiment resolves",
                       "The graded comparison uses separate LC4 expansion-velocity and LPLC2 size-dependent "
                       "input curves. Its exact populations contain 104 LC4 and 210 LPLC2 inputs. "
                       "Maximum-rate input reproduces the binary baseline exactly at the tested seed. "
                       "The feature distinction has primary support [3]; the numerical saturating curves "
                       "are declared model assumptions, not fitted physiology."),
              paragraph("Cutting a second physical visual presentation reduced its network response "
                        "from 5,055-5,219 spikes to zero and altered later front-tibia trajectories by "
                        "0.173-0.273 rad. The initial sensory/neural/motor sequence remained intact."),
              callout("Critical negative result",
                      "Motor-dependent geometry changed encoded rates by only 0.00070-0.00209 Hz. "
                      "Replaying the motor-disconnected rates produced identical neural and physical "
                      "hashes in the tested comparisons. Small geometric feedback differences therefore "
                      "did not change finite-duration spikes or motion. Neural stabilization is unproven."),
              paragraph("Evidence bundles: visual-causality-001, dnp10-extension-004, graded-feedback-002 "
                        "and graded-parity-001. Parameters, seeds, hashes, interventions and failure "
                        "status are documented alongside their external result files.", "PaperSmall"),
              PageBreak()]

    story += [paragraph("05  Physical embodiment results", "PaperHeading"),
              *section("Flight and contact are measured, not animated",
                       "FlyBody [7, 8] supplies an articulated body and wing-fluid model. Learned motor "
                       "policies drive physical actuators. Engineered predictive references use "
                       "privileged geometry for avoidance; genuine neural GF responses govern takeoff "
                       "initiation but do not generate continuous flight direction."),
              table(["NAMED RESULT", "MEASUREMENT", "SCOPE"], [
                  ["Flight avoidance", "20 s; minimum arena clearance 16.27 mm; zero floor contacts.",
                   "150 mm half-size comparison; no steering assistance after launch; not universal robustness."],
                  ["Compact grassland", "225 x 225 mm; 70 fixed objects, 48 grass blades, 14 materials and three free-body objects.",
                   "Rigid stylized environment; physically interactive, not photorealistic or flexible vegetation."],
                  ["Seed interaction", "Seeds moved 6.46 / 16.34 mm; 542 / 329 fly-contact steps; upright cosine >=0.9929.",
                   "0.8 s learned-gait trial; off-path controls stayed still; exact physical replay."],
                  ["Compact flight", "15 s; minimum clearance 12.88 mm; zero fly-floor contacts.",
                   "15 cm/s engineering reference; explicit heading and physical wing phase."],
                  ["Off-center launch", "Four 3 s motor cases; no floor contacts; corner clearances >=15.17 mm.",
                   "Measured-heading reference and explicit launch-speed guard; not new neural biology."],
              ], [.23, .4, .37]),
              *section("Neural-linked assisted landing",
                       "A recorded scene-driven cycle used actual DNp10 spikes to request landing at "
                       "1.68 s, reached stable touchdown at 3.68 s and removed landing assistance at "
                       "4.68 s. It recorded 11,601 consecutive stable unassisted walking steps. "
                       "DNp10 silencing prevented the request while takeoff and flight still worked [4]."),
              paragraph("This result concerns the earlier, explicitly assisted transition. Its braking, "
                        "descent, policy blending and support forces are not measured VNC-to-muscle "
                        "dynamics. The newer shorter descent adds sustained physical-readiness gating; "
                        "targeted intact and held-out tests pass, while broader scene/perturbation "
                        "validation remains unfinished."),
              paragraph("Loose-object floor contacts are filtered out of fly landing measurements. "
                        "World-space thorax velocity is read by body identity rather than assuming the "
                        "fly occupies the first global degrees of freedom.", "PaperSmall"),
              PageBreak()]

    story += [paragraph("06  Limitations and failure evidence", "PaperHeading"),
              callout("Connectivity is a constraint, not a complete animal",
                      "Loading a large graph, displaying spikes or moving a learned-policy body "
                      "does not establish natural sensory-motor behavior. The missing interfaces "
                      "must be identified, modeled transparently and validated independently."),
              *section("Physiology and motor control",
                       "The current brain lacks a complete calibrated account of spontaneous activity, "
                       "neuromodulation, heterogeneous cellular dynamics and electrical transmission. "
                       "No integrated natural VNC-to-muscle force decoder controls walking or wings. "
                       "DNp07's state dependence is not replaced with an invented uniform flight gate."),
              *section("Perception and action selection",
                       "Geometric source exposure is not calibrated taste. Sphere/surface expansion is "
                       "not full retinal optic flow. LC4/LPLC2 propagation is not silently relabeled "
                       "as the natural LPLC3/LPLC4-associated landing pathway. The flight controller "
                       "uses privileged geometry; spontaneous takeoff and natural navigation are open."),
              *section("Landing and robustness",
                       "Stable contact plus walking is more stringent than reaching a low body height, "
                       "but still does not establish arbitrary landing-site selection, friction tolerance, "
                       "recovery from large roll/yaw or natural touchdown timing. Descending into clutter "
                       "can fail. Shorter descent revisions must be revalidated rather than inheriting "
                       "success from earlier controller settings."),
              *section("Representative failures retained",
                       "Earlier landing cycles contacted ground but tumbled after assistance removal; "
                       "one aggressive variant produced invalid physics. Smaller-arena tight turns "
                       "passed airborne checks yet failed takeoff transitions. Graded scene input "
                       "caused over-eager GF takeoff. A live corner launch exposed a world-heading/"
                       "velocity mismatch. Transient uprightness allowed premature descent in a newer "
                       "held-out landing case. None of these failures is erased by a later passing trial."),
              *section("Performance and interpretation",
                       "GPU rendering does not imply GPU neural computation or real-time coupled physics. "
                       "The original walking backend was measured below real time. A reported 1.26x gait-loop "
                       "optimization is local throughput, not a whole-app speed guarantee. The recent "
                       "repository suite reported 240 tests, with seven opt-in/environment skips; "
                       "test quantity is not biological fidelity."),
              paragraph("Emergency safety pauses remain explicit. Removing the pause without a safe "
                        "physical response would hide a failure, not repair it. User interventions "
                        "during tests are logged and invalidate untouched-trial claims.", "PaperSmall"),
              PageBreak()]

    story += [paragraph("07  Reproducibility and development path", "PaperHeading"),
              *section("Prepared-workstation launch",
                       "Use the separately pinned neural, biomechanics and flight environments. "
                       "Verify selected assets, choose an external data/results directory and launch "
                       "from the repository root. This conservative command leaves experimental full "
                       "landing disabled."),
              paragraph('export FLY_DATA_DIR="/path/to/neural-brains-data"<br/>'
                        "MUJOCO_GL=egl .venv-biomechanics/bin/python \\<br/>"
                        "&nbsp; scripts/fly_habitat.py --backend unified \\<br/>"
                        "&nbsp; --flight-avoidance --neural-leg-extension \\<br/>"
                        '&nbsp; --data-dir "$FLY_DATA_DIR" \\<br/>'
                        '&nbsp; --output-dir "$FLY_DATA_DIR/results/fly-unified/new-session"',
                        "PaperCode"),
              paragraph("Open <b>http://127.0.0.1:8840/</b>. Output directories must be new. Only one "
                        "interactive app is permitted on the fixed port; there is no alternate-port "
                        "fallback. Environment controls and resets are logged. Before replacing a "
                        "live session, preserve edits and obtain approval."),
              table(["NEXT GATE", "ACCEPTANCE DIRECTION"], [
                  ["Sensory calibration", "Accessible quantitative visual/state data, correct units and explicit held-out response fits."],
                  ["Descending/VNC correspondence", "Version/specimen-aware type mapping; distinct chemical, electrical and end-organ mechanisms."],
                  ["Motor recruitment", "Supported muscle/actuator mapping; activation, force and phase response tested independently."],
                  ["Behavioral robustness", "Physical timing, contact and recovery thresholds across heading, phase, friction and perturbations."],
                  ["Closed-loop neural control", "Motor-dependent sensory feedback must change actual neural computation and appropriate physical outcomes."],
              ], [.31, .69]),
              *section("A defensible release principle",
                       "Every advertised behavior should retain a traceable chain: source data, "
                       "encoder assumptions, neural computation, decoder assumptions, physical "
                       "actuation, measured outcome and causal controls. A result should be promoted "
                       "only within the scope its tests actually support."),
              paragraph("Implementation and acquisition details: <b>readme-2.md</b>. Evidence guides: "
                        "<b>docs/neural-fly-checklist.md</b> and the behavior-specific documents. "
                        "Biological data and result bundles remain external. A project-wide license "
                        "has not been selected; upstream software/data terms remain distinct.",
                        "PaperSmall"),
              PageBreak()]

    story += [paragraph("08  References and evidence registry", "PaperHeading")]
    references = [
        ("1", "Shiu et al. (2024). A Drosophila computational whole-brain model reveals sensorimotor processing.",
         "https://doi.org/10.1038/s41586-024-07763-9"),
        ("2", "Pinned computational model source, philshiu/Drosophila_brain_model, revision 91bdd1e7dcf193f3e7ca5a8933497fcef63b7960.",
         "https://github.com/philshiu/Drosophila_brain_model/tree/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"),
        ("3", "Ache et al. (2019). Primary study of angular-size/velocity contributions to giant-fiber escape responses.",
         "https://doi.org/10.1016/j.cub.2019.01.079"),
        ("4", "Ache et al. (2019). State-dependent decoupling of sensory and motor circuits underlies behavioral flexibility in Drosophila.",
         "https://doi.org/10.1038/s41593-019-0413-4"),
        ("5", "Cheong et al. Organization of circuits linking descending input to motor output in the Drosophila Male Adult Nerve Cord connectome.",
         "https://pmc.ncbi.nlm.nih.gov/articles/PMC13384506/"),
        ("6", "Primary MANC DN typing, tracts and light-level matching table, publisher version 2.",
         "https://cdn.elifesciences.org/articles/96084/elife-96084-supp1-v2.csv"),
        ("7", "FlyBody framework, TuragaLab; pinned revision d015e9bfe441bd90ae431bac24c55cb74bdbce26.",
         "https://github.com/TuragaLab/flybody/tree/d015e9bfe441bd90ae431bac24c55cb74bdbce26"),
        ("8", "FlyBody supplementary datasets and policy assets. Provider DOI.",
         "https://doi.org/10.25378/janelia.25309105"),
        ("9", "Namiki et al. (2022). A population of descending neurons that regulates the flight motor of Drosophila.",
         "https://pmc.ncbi.nlm.nih.gov/articles/PMC9206711/"),
    ]
    for number, label, url in references:
        story.append(paragraph(
            f"<b>[{number}]</b> {escape(label)} "
            f'<link href="{url}" color="#087F8C">Source</link>', "PaperSmall"))
    story += [Spacer(1, 7),
              *section("Project evidence registry",
                       "Catalog: research/sources.json. Neural reproduction: experiments/flywire-sugar/. "
                       "Causal evidence: docs/visual-causality.md, docs/neural-leg-extension.md and "
                       "docs/graded-visual-feedback.md. Physical evidence: docs/flight-avoidance.md, "
                       "docs/grassland-habitat.md and docs/brain-linked-landing.md."),
              paragraph("Named result bundles in this paper are stored under the approved external "
                        "data root's results/flight-steering/ or results/fly-unified/ directories. "
                        "They include trial parameters, interventions, sparse neural responses, "
                        "physical trajectories and outcome status. The paper summarizes project "
                        "measurements; primary publications support specific biological constraints, "
                        "not all implementation choices or performance claims.", "PaperSmall"),
              paragraph("Editorial snapshot: 11 October 2026. Repository development was uncommitted "
                        "at preparation time; this document is not tied to a released commit. "
                        "Latest sustained-readiness landing changes have targeted passing tests "
                        "but are not presented as a broadly validated release.", "PaperSmall")]

    document = SimpleDocTemplate(
        str(output), pagesize=A4, rightMargin=19*mm, leftMargin=19*mm,
        topMargin=23*mm, bottomMargin=23*mm,
        title="Neural-brains: From Connectivity to Embodied Causality",
        author="appatalks/neural-brains project",
        subject="Development whitepaper on connectome-informed simulation, causal validation and embodied fly behavior",
        creator="neural-brains whitepaper builder / ReportLab",
        pageCompression=1,
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT/"docs/neural-brains-whitepaper.pdf")
    args = parser.parse_args()
    print(build(args.output))
