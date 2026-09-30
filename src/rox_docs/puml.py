"""Page model -> PlantUML text, and PlantUML text -> inline SVG."""

import re
import subprocess
import tempfile
from pathlib import Path

from rox_docs.model import BlockDiagram, DataModel, Sequence, StateMachine
from rox_docs.schema import Table

HEADER = """@startuml
!pragma layout smetana
skinparam backgroundColor #FFFFFF
skinparam defaultFontName Helvetica
skinparam shadowing false
skinparam roundCorner 8
skinparam ArrowColor #333333
skinparam componentStyle uml2
"""
FOOTER = "@enduml\n"

STORE_STEREOTYPE = {
    "redis": "redis",
    "mongo": "mongo",
    "dynamo": "dynamo",
    "kv": "kv store",
    "s3": "s3",
    "opensearch": "opensearch",
    "snowflake": "snowflake",
    "databricks": "databricks",
    "sqs": "sqs",
    "other": "store",
}


def _q(text: str) -> str:
    return text.replace('"', "'")


def _link(href: str | None) -> str:
    return f" [[{href}]]" if href else ""


def block_puml(block: BlockDiagram, hrefs: dict[str, str]) -> str:
    """`hrefs` maps node id -> link target (child page or source)."""
    lines = [
        f'{n.kind} "{_q(n.label)}" as {n.id}{_link(hrefs.get(n.id))}'
        for n in block.nodes
    ]
    lines += [f"{e.src} --> {e.dst} : {_q(e.label)}" for e in block.edges]
    return HEADER + "\n".join(lines) + "\n" + FOOTER


def schema_puml(
    tables: list[Table], data: DataModel, max_columns: int, hrefs: dict[str, str]
) -> str:
    shown = {t.name for t in tables}
    lines = []
    for t in tables:
        lines.append(
            f'entity "{t.name}" as {_alias(t.name)} <<postgres>>{_link(hrefs.get(t.name))} {{'
        )
        keys = [c for c in t.columns if c.primary_key]
        rest = [c for c in t.columns if not c.primary_key]
        rest.sort(key=lambda c: c.foreign_key is None)
        lines += [f"  * {c.name} : {c.type_name}" for c in keys]
        lines.append("  --")
        visible = rest[: max(0, max_columns - len(keys))]
        lines += [
            f"  {c.name} : {c.type_name}{' <<FK>>' if c.foreign_key else ''}"
            for c in visible
        ]
        if len(rest) > len(visible):
            lines.append(f"  .. {len(rest) - len(visible)} more ..")
        lines.append("}")
    for s in data.stores:
        lines.append(
            f'class "{_q(s.name)}" as {_alias(s.name)} <<{STORE_STEREOTYPE[s.kind]}>>{_link(hrefs.get(s.name))} {{'
        )
        lines += [f"  {_q(f)}" for f in s.fields]
        lines.append("}")
    for t in tables:
        for c in t.columns:
            target = c.foreign_key.split(".")[0] if c.foreign_key else None
            if target in shown and target != t.name:
                lines.append(f"{_alias(t.name)} }}o--|| {_alias(target)} : {c.name}")
    lines.append("hide circle" if not data.stores else "hide entity circle")
    return HEADER + "\n".join(lines) + "\n" + FOOTER


def sequence_puml(seq: Sequence, hrefs: dict[str, str]) -> str:
    lines = ["autonumber"]
    lines += [
        f'{p.kind} "{_q(p.label)}" as {p.id}{_link(hrefs.get(p.id))}'
        for p in seq.participants
    ]
    lines += [
        f"{s.src} {'-->' if s.reply else '->'} {s.dst} : {_q(s.label)}"
        for s in seq.steps
    ]
    return HEADER + "\n".join(lines) + "\n" + FOOTER


def state_puml(sm: StateMachine, hrefs: dict[str, str]) -> str:
    lines = [
        f'state "{_q(s.label)}" as {s.id}{_link(hrefs.get(s.id))}' for s in sm.states
    ]
    lines.append(f"[*] --> {sm.initial}")
    lines += [f"{t.src} --> {t.dst} : {_q(t.label)}" for t in sm.transitions]
    lines += [f"{s} --> [*]" for s in sm.final]
    return HEADER + "\n".join(lines) + "\n" + FOOTER


def _alias(name: str) -> str:
    return "t_" + re.sub(r"\W", "_", name)


def render_svgs(diagrams: dict[str, str], jar: Path) -> dict[str, str]:
    """Renders every diagram in one JVM start; raises naming the first diagram PlantUML rejects."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for name, text in diagrams.items():
            (work / f"{name}.puml").write_text(text)
        subprocess.run(
            [
                "java",
                "-Djava.awt.headless=true",
                "-jar",
                str(jar),
                "-tsvg",
                "-charset",
                "UTF-8",
                "-nometadata",
                str(work),
            ],
            check=False,
            capture_output=True,
        )
        svgs = {}
        for name, text in diagrams.items():
            svg_path = work / f"{name}.svg"
            if not svg_path.exists():
                raise RuntimeError(f"PlantUML produced no SVG for {name}:\n{text}")
            svg = svg_path.read_text()
            if "Syntax Error" in svg or ">Error line" in svg:
                raise RuntimeError(f"PlantUML syntax error in {name}:\n{text}")
            svgs[name] = re.sub(r"^<\?xml[^>]*>", "", svg)
    return svgs
