"""Synthetic project model + defect injection.

The model is built once (Rev A), deep-copied, and the Rev B changes are applied to the copy.
Each injected defect records the finding signatures that count as a correct detection, so the
evaluator can compute precision/recall without hand labelling.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from ..units import format_feet_inches

PROJECT_NAME = "RIVERSIDE COMMUNITY CLINIC"
FIRM_NAME = "NORTHWIND DESIGN STUDIO"   # fictional
PROJECT_NO = "2026-014"

DOOR_TYPES = {
    "D1": dict(material="WD", frame="HM", spec="08 14 16", width="3'-0\"", height="7'-0\"",
               desc="FLUSH WOOD, SOLID CORE"),
    "D2": dict(material="HM", frame="HM", spec="08 11 13", width="3'-0\"", height="7'-0\"",
               desc="HOLLOW METAL, FLUSH"),
    "D3": dict(material="ALUM", frame="ALUM", spec="08 41 13", width="6'-0\"", height="7'-0\"",
               desc="ALUM. STOREFRONT PAIR"),
}
WOOD_FIRE_ALLOWED = ["20 MIN", "45 MIN", "60 MIN"]
HW_SETS = ["HW-1", "HW-2", "HW-3", "HW-4"]
SPEC_REFRIGERANT = "R-454B"

NORTH_ROOMS = [("LOBBY", "D1"), ("OFFICE", "D1"), ("OFFICE", "D1"), ("CONFERENCE", "D1")]
SOUTH_ROOMS = [("EXAM", "D1"), ("EXAM", "D1"), ("TOILET", "D2"), ("STORAGE", "D2"),
               ("MECH.", "D2"), ("STAFF", "D1")]


@dataclass
class Room:
    number: str
    name: str
    x0: float
    x1: float
    y0: float
    y1: float
    side: str  # N or S of the corridor


@dataclass
class Door:
    mark: str
    type: str
    width: str
    height: str
    material: str
    frame: str
    fire: str
    hw: str
    spec: str
    remarks: str = ""
    room: str = ""
    x: float | None = None       # plan position (ft); None -> not drawn
    side: str = "N"              # N: door on corridor top wall, S: bottom wall, W/E: exterior end walls
    on_plan: bool = True
    in_schedule: bool = True
    plan_label: str | None = None
    rev: str = "A"               # revision in which the door was introduced


@dataclass
class Circuit:
    panel: str
    ckt: str
    volts: str
    poles: int
    bkr: int


@dataclass
class Equip:
    tag: str
    desc: str
    qty: int
    capacity: str
    volts: str
    mca: int | None
    weight: int
    spec: str
    remarks: str = ""
    nic: bool = False
    plan: list[tuple[float, float, str]] = field(default_factory=list)   # (x_ft, y_ft, qualifier)
    in_schedule: bool = True
    circuit: Circuit | None = None
    boq_qty: int | None = None   # None -> derive from qty (0 for NIC)


@dataclass
class BoqLine:
    item: str
    desc: str
    spec: str
    unit: str
    qty: int
    rate: float
    key: str = ""    # DOORTYPE:D1 / EQUIP:RTU-1 / HW


@dataclass
class Defect:
    id: str
    kind: str
    description: str
    accept: list[dict]                 # [{"type":..., "entities":[...], "sheets":[...]}]
    gt: list[dict] = field(default_factory=list)   # ground-truth locations [{"sheet":..,"element":..}] resolved at render
    severity: str = "medium"


@dataclass
class Project:
    seed: int
    clean: bool
    rev: str
    bays_x: list[float]
    bays_y: list[float]
    corridor_half: float
    rooms: list[Room]
    doors: list[Door]
    equips: list[Equip]
    rtu_design_max: dict[str, int]
    spec_sections: list[str]
    hw_sets: list[str]
    boq: list[BoqLine]
    sheet_index: list[tuple[str, str]]
    callouts: list[tuple[str, str]]              # (detail no, sheet) placed on A-101
    dim_override: dict[tuple[str, int], str]     # (sheet, bay index) -> label text that differs from geometry
    room_name_override: dict[str, str] = field(default_factory=dict)
    revisions: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)  # sheet -> [(rev, date, desc)]
    clouds: dict[str, list[tuple]] = field(default_factory=dict)   # sheet -> element ids to cloud
    defects: list[Defect] = field(default_factory=list)
    traps: list[dict] = field(default_factory=list)

    @property
    def width(self) -> float:
        return sum(self.bays_x)

    @property
    def depth(self) -> float:
        return sum(self.bays_y)

    @property
    def corridor_y(self) -> float:
        return self.bays_y[0]

    def door(self, mark: str) -> Door:
        return next(d for d in self.doors if d.mark == mark)

    def equip(self, tag: str) -> Equip:
        return next(e for e in self.equips if e.tag == tag)


SHEETS = [
    ("G-001", "COVER SHEET AND SHEET INDEX"),
    ("A-101", "FIRST FLOOR PLAN"),
    ("A-601", "DOOR SCHEDULE AND DOOR TYPES"),
    ("S-101", "ROOF FRAMING PLAN"),
    ("M-101", "MECHANICAL FLOOR PLAN"),
    ("M-601", "MECHANICAL EQUIPMENT SCHEDULE"),
    ("E-601", "ELECTRICAL PANEL SCHEDULES"),
]
REV_A = ("A", "2026-08-14", "ISSUED FOR BID")
REV_B = ("B", "2026-09-18", "ADDENDUM 1")

ALL_DEFECT_KINDS = [
    "door_tag_undefined", "door_row_orphan", "door_tag_duplicate", "door_field_blank",
    "door_hw_undefined", "door_spec_material", "door_spec_fire", "spec_section_missing",
    "boq_door_qty", "sheet_ref_missing", "sheet_not_indexed", "dim_chain", "dim_xdisc",
    "equip_tag_undefined", "equip_voltage", "equip_no_circuit", "equip_breaker_small",
    "equip_weight", "boq_nic_item", "boq_equip_qty", "spec_refrigerant",
    "rev_unclouded", "rev_not_issued", "boq_not_updated",
]


def _snap(v: float, step: float = 0.5) -> float:
    return round(v / step) * step


def build_base(seed: int, clean: bool = False) -> Project:
    rng = random.Random(seed)
    floor = rng.choice([1, 1, 2]) if seed else 1
    if seed == 0:
        bays_x, bays_y = [25.0, 30.0, 25.0], [25.0, 25.0]
    else:
        bays_x = [_snap(rng.uniform(20, 31)) for _ in range(3)]
        bays_y = [_snap(rng.uniform(20, 28)) for _ in range(2)]
    width, depth = sum(bays_x), sum(bays_y)
    corridor_half = 3.0
    cy = bays_y[0]

    def split(total: float, n: int) -> list[float]:
        if seed == 0:
            return [total / n] * n
        cuts = sorted(rng.uniform(0.15, 0.85) * total for _ in range(n - 1))
        widths, prev = [], 0.0
        for c in cuts + [total]:
            widths.append(c - prev)
            prev = c
        # enforce a minimum room width of 10 ft
        widths = [max(10.0, w) for w in widths]
        scale = total / sum(widths)
        return [w * scale for w in widths]

    rooms: list[Room] = []
    doors: list[Door] = []
    num = floor * 100 + 1
    fire_cycle = ["-", "20 MIN", "-", "20 MIN"]
    for side, names, y0, y1 in (("N", NORTH_ROOMS, 0.0, cy - corridor_half),
                                ("S", SOUTH_ROOMS, cy + corridor_half, depth)):
        x = 0.0
        for i, ((name, dtype), w) in enumerate(zip(names, split(width, len(names)))):
            r = Room(str(num), name, x, x + w, y0, y1, side)
            rooms.append(r)
            t = DOOR_TYPES[dtype]
            fire = fire_cycle[i % 4] if dtype == "D1" else ("60 MIN" if name == "MECH." else "45 MIN" if name == "STORAGE" else "-")
            hw = {"D1": "HW-1", "D2": "HW-2"}[dtype]
            if name == "TOILET":
                hw = "HW-3"
            doors.append(Door(mark=str(num), type=dtype, width=t["width"], height=t["height"],
                              material=t["material"], frame=t["frame"], fire=fire, hw=hw, spec=t["spec"],
                              room=r.number, x=_snap(x + w / 2), side=side))
            num += 1
            x += w
    rooms.append(Room(str(num), "CORRIDOR", 0.0, width, cy - corridor_half, cy + corridor_half, "C"))
    corridor_no = num
    for suffix, side in (("A", "W"), ("B", "E")):
        t = DOOR_TYPES["D3"]
        doors.append(Door(mark=f"{corridor_no}{suffix}", type="D3", width=t["width"], height=t["height"],
                          material="ALUM", frame="ALUM", fire="-", hw="HW-4", spec=t["spec"],
                          room=str(corridor_no), x=0.0 if side == "W" else width, side=side))

    # --- mechanical equipment -------------------------------------------------------------
    n_rtu = 3 if seed == 0 else rng.choice([2, 3])
    equips: list[Equip] = []
    rtu_caps = [("10 TON", 45, 2450), ("7.5 TON", 35, 1980), ("6 TON", 30, 1650)]
    for i in range(n_rtu):
        cap, mca, wt = rtu_caps[i]
        ex = width * (i + 1) / (n_rtu + 1)
        equips.append(Equip(tag=f"RTU-{i + 1}", desc="ROOFTOP UNIT, GAS/ELEC", qty=1, capacity=cap,
                            volts="460/3", mca=mca, weight=wt, spec="23 74 13",
                            remarks=f"{SPEC_REFRIGERANT}, ECONOMIZER",
                            plan=[(ex, cy * 0.45, "")],
                            circuit=Circuit("HA", f"{6 * i + 1},{6 * i + 3},{6 * i + 5}", "460/3", 3, mca + 10)))
    n_ef = 2 if seed == 0 else rng.choice([2, 3])
    for i in range(n_ef):
        ex = width * (0.2 + 0.6 * i / max(1, n_ef - 1))
        equips.append(Equip(tag=f"EF-{i + 1}", desc="EXHAUST FAN, CEILING", qty=1, capacity=f"{[300, 500, 400][i]} CFM",
                            volts="120/1", mca=None, weight=[45, 85, 60][i], spec="23 34 16",
                            plan=[(ex, depth - 6.0, "")],
                            circuit=Circuit("LA", str(2 * i + 1), "120/1", 1, 20)))
    nic_tag = f"EF-{n_ef + 1}"
    equips.append(Equip(tag=nic_tag, desc="KITCHEN HOOD FAN", qty=1, capacity="250 CFM", volts="120/1", mca=None,
                        weight=40, spec="23 34 16", remarks="NIC - BY OWNER", nic=True,
                        plan=[(width * 0.9, depth - 6.0, "(NIC)")],
                        circuit=Circuit("LA", str(2 * n_ef + 1), "120/1", 1, 20)))
    equips.append(Equip(tag="VAV-1", desc="VAV TERMINAL, 8 IN.", qty=4, capacity="450 CFM", volts="-", mca=None,
                        weight=35, spec="23 36 00", plan=[(width * 0.3, cy, "(TYP. OF 4)")]))
    equips.append(Equip(tag="VAV-2", desc="VAV TERMINAL, 6 IN.", qty=3, capacity="250 CFM", volts="-", mca=None,
                        weight=30, spec="23 36 00", plan=[(width * 0.7, cy, "TYP.")]))
    rtu_design_max = {e.tag: e.weight + 300 for e in equips if e.tag.startswith("RTU")}

    spec_sections = ["08 11 13", "08 14 16", "08 41 13", "08 71 00", "23 34 16", "23 36 00", "23 74 13"]

    p = Project(seed=seed, clean=clean, rev="A", bays_x=bays_x, bays_y=bays_y, corridor_half=corridor_half,
                rooms=rooms, doors=doors, equips=equips, rtu_design_max=rtu_design_max,
                spec_sections=spec_sections, hw_sets=list(HW_SETS), boq=[],
                sheet_index=[s for s in SHEETS], callouts=[("4", "A-601")], dim_override={})
    p.traps = [
        {"kind": "typ_of_n", "entity": "EQUIP:VAV-1",
         "note": "One plan tag marked (TYP. OF 4); schedule and BOQ say 4. A naive tag count reports 1."},
        {"kind": "typ_no_count", "entity": "EQUIP:VAV-2",
         "note": "Plan tag marked TYP. without a count; plan quantity is unknowable from the sheet. "
                 "Only a needs_review item is acceptable, never a confirmed mismatch."},
        {"kind": "nic_excluded", "entity": f"EQUIP:{nic_tag}",
         "note": "NIC item on plan with no BOQ line is correct, not a quantity mismatch."},
        {"kind": "do_not_scale", "entity": "NOTE",
         "note": "Sheet notes say DO NOT SCALE DRAWINGS; scale-based checks must stay probable, never confirmed."},
    ]
    return p


def build_boq(p: Project, door_counts_from: Project | None = None) -> list[BoqLine]:
    src = door_counts_from or p
    lines: list[BoqLine] = []
    counts = {t: 0 for t in DOOR_TYPES}
    for d in src.doors:
        if d.in_schedule:
            counts[d.type] += 1
    rates = {"D1": 1450.0, "D2": 1180.0, "D3": 6800.0}
    for i, t in enumerate(DOOR_TYPES):
        info = DOOR_TYPES[t]
        lines.append(BoqLine(item=f"08-{100 + 10 * i}", desc=f"Door type {t}: {info['desc'].lower()}, {info['width']} x {info['height']}",
                             spec=info["spec"], unit="EA", qty=counts[t], rate=rates[t], key=f"DOORTYPE:{t}"))
    lines.append(BoqLine(item="08-700", desc="Door hardware, complete sets per 08 71 00", spec="08 71 00", unit="SET",
                         qty=sum(counts.values()), rate=640.0, key="HW"))
    rates_e = {"RTU": 21500.0, "EF": 900.0, "VAV": 1350.0}
    for j, e in enumerate(p.equips):
        if not e.in_schedule or (e.nic and e.boq_qty is None):
            continue
        qty = e.boq_qty if e.boq_qty is not None else e.qty
        prefix = e.tag.split("-")[0]
        lines.append(BoqLine(item=f"23-{100 + 10 * j}", desc=f"{e.tag} {e.desc.lower()}, {e.capacity}", spec=e.spec,
                             unit="EA", qty=qty, rate=rates_e[prefix], key=f"EQUIP:{e.tag}"))
    return lines


def _pick(rng: random.Random, seq, used: set):
    """Pick an unused element so each defect of a finding type hits a distinct entity (None if exhausted)."""
    choices = [x for x in seq if x not in used]
    if not choices:
        return None
    c = rng.choice(choices)
    used.add(c)
    return c


def make_project(seed: int, clean: bool = False) -> tuple[Project, Project]:
    """Return (rev_a, rev_b) projects with defects injected (unless clean)."""
    rng = random.Random(1000 + seed)
    a = build_base(seed, clean)
    if clean:
        active: list[str] = []
    elif seed == 0:
        active = list(ALL_DEFECT_KINDS)
    else:
        active = [k for k in ALL_DEFECT_KINDS if rng.random() < 0.5]

    used_doors: set[str] = set()
    used_equip: set[str] = set()
    interior = [d.mark for d in a.doors if d.type in ("D1", "D2")]
    wood = [d.mark for d in a.doors if d.type == "D1"]
    defects: list[Defect] = []
    did = 0

    def add(kind, desc, accept, gt, severity="medium"):
        nonlocal did
        did += 1
        defects.append(Defect(id=f"S{seed:02d}-{did:02d}", kind=kind, description=desc, accept=accept, gt=gt,
                              severity=severity))

    floor_prefix = a.doors[0].mark[0]

    # ---- door / schedule defects (present in both revisions) ------------------------------
    if "door_tag_undefined" in active:
        mark = f"{floor_prefix}{len(a.rooms) + 10:02d}"
        storage = next(r for r in a.rooms if r.name == "STORAGE")
        a.doors.append(Door(mark=mark, type="D2", width="3'-0\"", height="7'-0\"", material="HM", frame="HM",
                            fire="-", hw="HW-2", spec="08 11 13", room=storage.number,
                            x=_snap(storage.x0 + 3.5), side="S", in_schedule=False))
        add("door_tag_undefined", f"Door tag {mark} on A-101 has no row in the door schedule.",
            [{"type": "missing_info", "entities": [f"DOOR:{mark}"], "sheets": ["A-101", "A-601"]}],
            [{"sheet": "A-101", "element": ("door_tag", mark)}], "medium")
    if "door_row_orphan" in active:
        mark = f"{floor_prefix}{len(a.rooms) + 11:02d}"
        a.doors.append(Door(mark=mark, type="D1", width="3'-0\"", height="7'-0\"", material="WD", frame="HM",
                            fire="-", hw="HW-1", spec="08 14 16", room="", x=None, on_plan=False))
        add("door_row_orphan", f"Door schedule row {mark} does not appear on any plan.",
            [{"type": "missing_info", "entities": [f"DOOR:{mark}"], "sheets": ["A-601", "A-101"]}],
            [{"sheet": "A-601", "element": ("sched_row", mark)}], "low")
    if "door_tag_duplicate" in active:
        m1 = _pick(rng, interior[:-1], used_doors)
        idx = interior.index(m1)
        m2 = interior[idx + 1] if interior[idx + 1] not in used_doors else interior[idx - 1]
        used_doors.add(m2)
        a.door(m2).plan_label = m1
        add("door_tag_duplicate", f"Door tag {m1} appears twice on A-101; door {m2} is tagged {m1}.",
            [{"type": "tag_conflict", "entities": [f"DOOR:{m1}"], "sheets": ["A-101"]},
             {"type": "missing_info", "entities": [f"DOOR:{m2}"], "sheets": ["A-601", "A-101"]}],
            [{"sheet": "A-101", "element": ("door_tag", m2)}], "medium")
    if "door_field_blank" in active:
        mark = _pick(rng, interior, used_doors)
        field_name = rng.choice(["hw", "fire"]) if seed else "hw"
        setattr(a.door(mark), field_name, "")
        col = {"hw": "HDW SET", "fire": "FIRE RATING"}[field_name]
        add("door_field_blank", f"Door {mark}: {col} is blank in the door schedule.",
            [{"type": "missing_info", "entities": [f"DOOR:{mark}"], "sheets": ["A-601"]}],
            [{"sheet": "A-601", "element": ("sched_row", mark)}], "medium")
    if "door_hw_undefined" in active:
        mark = _pick(rng, interior, used_doors)
        a.door(mark).hw = "HW-9"
        add("door_hw_undefined", f"Door {mark} references hardware set HW-9, not defined in 08 71 00.",
            [{"type": "missing_info", "entities": [f"DOOR:{mark}", "HW:HW-9"], "sheets": ["A-601"]}],
            [{"sheet": "A-601", "element": ("sched_row", mark)}], "medium")
    if "door_spec_material" in active:
        mark = _pick(rng, wood, used_doors)
        a.door(mark).material = "HM"
        add("door_spec_material", f"Door {mark} is type D1 / spec 08 14 16 (flush wood) but scheduled material is HM.",
            [{"type": "spec_conflict", "entities": [f"DOOR:{mark}"], "sheets": ["A-601"]}],
            [{"sheet": "A-601", "element": ("sched_row", mark)}], "high")
    if "door_spec_fire" in active:
        mark = _pick(rng, wood, used_doors)
        a.door(mark).fire = "90 MIN"
        add("door_spec_fire", f"Wood door {mark} scheduled 90 MIN; 08 14 16 allows 20, 45 and 60 minute wood doors.",
            [{"type": "spec_conflict", "entities": [f"DOOR:{mark}"], "sheets": ["A-601"]}],
            [{"sheet": "A-601", "element": ("sched_row", mark)}], "high")
    if "spec_section_missing" in active:
        a.spec_sections.remove("08 41 13")
        add("spec_section_missing", "Section 08 41 13 is referenced by the door schedule and BOQ but is not in the project manual.",
            [{"type": "missing_info", "entities": ["SPEC:08 41 13"], "sheets": ["A-601"]}],
            [{"sheet": "A-601", "element": ("sched_row", next(d.mark for d in a.doors if d.type == "D3"))}], "medium")
    if "sheet_ref_missing" in active:
        a.callouts.append(("3", "A-501"))
        a.sheet_index.insert(2, ("A-501", "DOOR AND STOREFRONT DETAILS"))
        add("sheet_ref_missing", "A-101 references detail 3/A-501; A-501 is listed in the index but is not in the set.",
            [{"type": "missing_info", "entities": ["SHEET:A-501"], "sheets": ["A-101", "G-001"]}],
            [{"sheet": "A-101", "element": ("callout", "A-501")}], "medium")
    if "sheet_not_indexed" in active:
        a.sheet_index = [s for s in a.sheet_index if s[0] != "S-101"]
        add("sheet_not_indexed", "S-101 is in the set but missing from the G-001 sheet index.",
            [{"type": "missing_info", "entities": ["SHEET:S-101"], "sheets": ["G-001", "S-101"]}],
            [{"sheet": "G-001", "element": ("index_table", "")}], "low")
    if "dim_chain" in active:
        bay = 0 if seed == 0 else rng.randrange(len(a.bays_x))
        true = a.bays_x[bay]
        a.dim_override[("A-101", bay)] = format_feet_inches(true - 0.5)
        g = f"GRID:{bay + 1}-{bay + 2}"
        add("dim_chain", f"A-101: bay {bay + 1}-{bay + 2} labelled {format_feet_inches(true - 0.5)}; chain no longer sums to overall dimension.",
            [{"type": "dimension_conflict", "entities": [g, "GRID:1-4"], "sheets": ["A-101"]}],
            [{"sheet": "A-101", "element": ("dim", f"x{bay}")}], "high")
    if "dim_xdisc" in active:
        choices = [i for i in range(len(a.bays_x)) if ("A-101", i) not in a.dim_override]
        bay = 1 if seed == 0 else rng.choice(choices)
        true = a.bays_x[bay]
        a.dim_override[("S-101", bay)] = format_feet_inches(true + 2.0)
        g = f"GRID:{bay + 1}-{bay + 2}"
        add("dim_xdisc", f"Grid {bay + 1}-{bay + 2}: A-101 = {format_feet_inches(true)}, S-101 = {format_feet_inches(true + 2)}.",
            [{"type": "dimension_conflict", "entities": [g], "sheets": ["S-101", "A-101"]},
             {"type": "dimension_conflict", "entities": ["GRID:1-4"], "sheets": ["S-101"]}],
            [{"sheet": "S-101", "element": ("dim", f"x{bay}")}], "high")

    # ---- mechanical / electrical / structural -------------------------------------------
    rtus = [e.tag for e in a.equips if e.tag.startswith("RTU")]
    efs = [e.tag for e in a.equips if e.tag.startswith("EF") and not e.nic]
    nic = next(e.tag for e in a.equips if e.nic)
    if "equip_tag_undefined" in active:
        tag = f"EF-{len(efs) + 2}"
        a.equips.append(Equip(tag=tag, desc="", qty=1, capacity="", volts="", mca=None, weight=0, spec="",
                              plan=[(a.width * 0.55, a.depth - 6.0, "")], in_schedule=False))
        add("equip_tag_undefined", f"Equipment tag {tag} on M-101 is not in the M-601 schedule.",
            [{"type": "missing_info", "entities": [f"EQUIP:{tag}"], "sheets": ["M-101", "M-601"]}],
            [{"sheet": "M-101", "element": ("equip_tag", tag)}], "medium")
    if "equip_voltage" in active and (tag := _pick(rng, rtus, used_equip)):
        a.equip(tag).circuit.volts = "208/3"
        a.equip(tag).circuit.panel = "LA"
        add("equip_voltage", f"{tag}: M-601 says 460/3, E-601 feeds it from a 208/3 circuit.",
            [{"type": "cross_discipline_conflict", "entities": [f"EQUIP:{tag}"], "sheets": ["M-601", "E-601"]}],
            [{"sheet": "E-601", "element": ("panel_row", tag)}], "high")
    if "equip_no_circuit" in active and (tag := _pick(rng, efs, used_equip)):
        a.equip(tag).circuit = None
        add("equip_no_circuit", f"{tag} needs 120/1 power (M-601) but has no circuit on E-601.",
            [{"type": "cross_discipline_conflict", "entities": [f"EQUIP:{tag}"], "sheets": ["M-601", "E-601"]}],
            [{"sheet": "M-601", "element": ("sched_row", tag)}], "high")
    if "equip_breaker_small" in active and (tag := _pick(rng, rtus, used_equip)):
        e = a.equip(tag)
        e.circuit.bkr = e.mca - 15
        add("equip_breaker_small", f"{tag}: breaker {e.mca - 15} A on E-601 is below MCA {e.mca} A on M-601.",
            [{"type": "cross_discipline_conflict", "entities": [f"EQUIP:{tag}"], "sheets": ["M-601", "E-601"]}],
            [{"sheet": "E-601", "element": ("panel_row", tag)}], "high")
    if "equip_weight" in active and (tag := _pick(rng, rtus, used_equip)):
        a.rtu_design_max[tag] = a.equip(tag).weight - 450
        add("equip_weight", f"{tag}: M-601 weight {a.equip(tag).weight} LB exceeds S-101 design max {a.rtu_design_max[tag]} LB.",
            [{"type": "cross_discipline_conflict", "entities": [f"EQUIP:{tag}"], "sheets": ["M-601", "S-101"]}],
            [{"sheet": "S-101", "element": ("rtu_note", tag)}], "high")
    if "spec_refrigerant" in active and (tag := _pick(rng, rtus, set())):
        a.equip(tag).remarks = "R-410A, ECONOMIZER"
        add("spec_refrigerant", f"{tag} remarks R-410A; 23 74 13 requires {SPEC_REFRIGERANT}.",
            [{"type": "spec_conflict", "entities": [f"EQUIP:{tag}"], "sheets": ["M-601"]}],
            [{"sheet": "M-601", "element": ("sched_row", tag)}], "high")
    if "boq_nic_item" in active:
        a.equip(nic).boq_qty = 1
        add("boq_nic_item", f"{nic} is NIC (by owner) but is priced in the BOQ.",
            [{"type": "quantity_mismatch", "entities": [f"EQUIP:{nic}"], "sheets": ["BOQ", "M-601"]}],
            [{"sheet": "BOQ", "element": ("boq", f"EQUIP:{nic}")}], "medium")
    if "boq_equip_qty" in active and (tag := _pick(rng, efs, set())):
        a.equip(tag).boq_qty = 2
        add("boq_equip_qty", f"BOQ prices 2 EA of {tag}; plan and schedule show 1.",
            [{"type": "quantity_mismatch", "entities": [f"EQUIP:{tag}"], "sheets": ["BOQ", "M-601"]}],
            [{"sheet": "BOQ", "element": ("boq", f"EQUIP:{tag}")}], "medium")

    # ---- Rev B (copy, apply legitimate clouded changes + revision defects) ---------------
    b = copy.deepcopy(a)
    b.rev = "B"
    for s, _ in SHEETS:
        a.revisions[s] = [REV_A]
        b.revisions[s] = [REV_A]
    # legit change 1: new door into the largest south room, clouded on A-101 and A-601
    big = max((r for r in b.rooms if r.side == "S" and r.name not in ("MECH.", "TOILET")), key=lambda r: r.x1 - r.x0)
    new_mark = f"{big.number}A"
    t = DOOR_TYPES["D1"]
    b.doors.append(Door(mark=new_mark, type="D1", width=t["width"], height=t["height"], material="WD", frame="HM",
                        fire="20 MIN", hw="HW-1", spec="08 14 16", room=big.number, x=_snap(big.x1 - 3.0), side="S",
                        rev="B"))
    b.clouds.setdefault("A-101", []).append(("door_group", new_mark))
    b.clouds.setdefault("A-601", []).append(("sched_row", new_mark))
    b.revisions["A-101"].append(REV_B)
    b.revisions["A-601"].append(REV_B)
    # legit change 2: RTU-1 capacity revised on M-601, clouded
    rtu1 = b.equip("RTU-1")
    rtu1.capacity = {"10 TON": "12.5 TON"}.get(rtu1.capacity, rtu1.capacity)
    b.clouds.setdefault("M-601", []).append(("sched_cell", "RTU-1", "CAPACITY"))
    if "rev_not_issued" in active:
        add("rev_not_issued", "M-601 content changed in Rev B but its title block still shows Rev A.",
            [{"type": "revision_issue", "entities": ["SHEET:M-601"], "sheets": ["M-601"]}],
            [{"sheet": "M-601", "element": ("title_block", "")}], "medium")
    else:
        b.revisions["M-601"].append(REV_B)
    if "rev_unclouded" in active:
        variant = 0 if seed == 0 else rng.randrange(3)
        if variant == 0:
            cands = [d.mark for d in b.doors if d.type in ("D1", "D2") and d.in_schedule and d.rev == "A"
                     and d.mark not in used_doors]
            mark = rng.choice(cands)
            b.door(mark).width = "3'-6\""
            add("rev_unclouded", f"A-601 door {mark} width changed 3'-0\" -> 3'-6\" in Rev B without a revision cloud.",
                [{"type": "revision_issue", "entities": [f"DOOR:{mark}"], "sheets": ["A-601"]}],
                [{"sheet": "A-601", "element": ("sched_cell", mark, "WIDTH")}], "high")
        elif variant == 1:
            tag = rng.choice([e.tag for e in b.equips if e.tag.startswith("EF") and e.in_schedule and not e.nic])
            b.equip(tag).weight += 15
            add("rev_unclouded", f"M-601 {tag} weight changed in Rev B without a revision cloud.",
                [{"type": "revision_issue", "entities": [f"EQUIP:{tag}"], "sheets": ["M-601"]}],
                [{"sheet": "M-601", "element": ("sched_cell", tag, "WEIGHT")}], "high")
        else:
            room = rng.choice([r for r in b.rooms if r.name == "OFFICE" or r.name == "STAFF"])
            b.room_name_override[room.number] = "WORKROOM"
            add("rev_unclouded", f"A-101 room {room.number} renamed to WORKROOM in Rev B without a revision cloud.",
                [{"type": "revision_issue", "entities": [f"ROOM:{room.number}"], "sheets": ["A-101"]}],
                [{"sheet": "A-101", "element": ("room_name", room.number)}], "high")
    # BOQ is re-issued with Rev B (counts from the Rev B schedule) unless the defect says otherwise
    if "boq_not_updated" in active:
        b.boq = build_boq(b, door_counts_from=a)
        add("boq_not_updated", f"Door {new_mark} (D1) added in Rev B; BOQ D1 quantity not updated.",
            [{"type": "quantity_mismatch", "entities": ["DOORTYPE:D1"], "sheets": ["BOQ", "A-601"]}],
            [{"sheet": "BOQ", "element": ("boq", "DOORTYPE:D1")}], "high")
    else:
        b.boq = build_boq(b)
    if "boq_door_qty" in active:
        dtype = "D2"
        line = next(l for l in b.boq if l.key == f"DOORTYPE:{dtype}")
        line.qty += rng.choice([-1, 1, 2]) if seed else -1
        add("boq_door_qty", f"BOQ door type {dtype} quantity {line.qty} does not match the door schedule.",
            [{"type": "quantity_mismatch", "entities": [f"DOORTYPE:{dtype}"], "sheets": ["BOQ", "A-601"]}],
            [{"sheet": "BOQ", "element": ("boq", f"DOORTYPE:{dtype}")}], "high")
    a.boq = build_boq(a)
    a.defects = [d for d in defects if not d.kind.startswith("rev_") and d.kind != "boq_not_updated"]
    b.defects = defects
    b.traps = a.traps
    return a, b
