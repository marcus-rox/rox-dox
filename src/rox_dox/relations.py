from __future__ import annotations

import ast
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rox_dox.schema import extract_tables

COMMENTED_FOREIGN_KEY = re.compile(r"""#\s*ForeignKey\s*\(\s*["']([^"']+)["']\s*\)""")


@dataclass(frozen=True)
class RelationCandidate:
    src: str
    dst: str
    signal: str
    path: str
    line: int

    def to_tsv(self) -> str:
        return f"{self.src}\t{self.dst}\t{self.signal}\t{self.path}:{self.line}"


def _git_output(repo: Path, arguments: Sequence[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def _candidate_paths(repo: Path, commit: str) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "grep",
            "--full-name",
            "-I",
            "-l",
            "-E",
            "-e",
            "==|primaryjoin|ForeignKey",
            commit,
            "--",
            "backend/src",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError(result.stderr.strip() or "git grep failed")
    paths = [
        line.partition(":")[2] for line in result.stdout.splitlines() if ":" in line
    ]
    return sorted(
        path
        for path in paths
        if path.startswith("backend/src/") and path.endswith(".py")
    )


def _call_name(expression: ast.expr) -> str | None:
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        return expression.attr
    return None


def _column_reference(expression: ast.expr) -> tuple[str, str] | None:
    while (
        isinstance(expression, ast.Call)
        and _call_name(expression.func) in {"foreign", "remote"}
        and expression.args
    ):
        expression = expression.args[0]
    if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
        return expression.value.id, expression.attr
    return None


def _column_assignment(statement: ast.stmt) -> str | None:
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        name = statement.target.id
        value = statement.value
    elif isinstance(statement, ast.Assign) and isinstance(
        statement.targets[0], ast.Name
    ):
        name = statement.targets[0].id
        value = statement.value
    else:
        return None
    if isinstance(value, ast.Call) and _call_name(value.func) in {
        "Column",
        "mapped_column",
    }:
        return name
    return None


def _candidate_for_columns(
    left: tuple[str, str],
    right: tuple[str, str],
    *,
    class_to_table: dict[str, str],
    selected_tables: set[str],
    signal: str,
    path: str,
    line: int,
) -> RelationCandidate | None:
    src_table = class_to_table.get(left[0])
    dst_table = class_to_table.get(right[0])
    if (
        src_table is None
        or dst_table is None
        or src_table not in selected_tables
        or dst_table not in selected_tables
    ):
        return None
    return RelationCandidate(
        src=f"{src_table}.{left[1]}",
        dst=f"{dst_table}.{right[1]}",
        signal=signal,
        path=path,
        line=line,
    )


def _comparison_candidate(
    expression: ast.expr,
    *,
    class_to_table: dict[str, str],
    selected_tables: set[str],
    signal: str,
    path: str,
    line: int,
) -> RelationCandidate | None:
    if (
        not isinstance(expression, ast.Compare)
        or len(expression.ops) != 1
        or not isinstance(expression.ops[0], ast.Eq)
        or len(expression.comparators) != 1
    ):
        return None
    left = _column_reference(expression.left)
    right = _column_reference(expression.comparators[0])
    if left is None or right is None:
        return None
    return _candidate_for_columns(
        left,
        right,
        class_to_table=class_to_table,
        selected_tables=selected_tables,
        signal=signal,
        path=path,
        line=line,
    )


def _commented_foreign_key_candidates(
    module: ast.Module,
    source_lines: list[str],
    *,
    path: str,
    class_to_table: dict[str, str],
    selected_tables: set[str],
) -> list[RelationCandidate]:
    candidates = []
    for class_node in ast.walk(module):
        if not isinstance(class_node, ast.ClassDef):
            continue
        table_name = class_to_table.get(class_node.name)
        if table_name not in selected_tables:
            continue
        for statement in class_node.body:
            column_name = _column_assignment(statement)
            if column_name is None:
                continue
            end_line = getattr(statement, "end_lineno", statement.lineno)
            for line_number in range(statement.lineno, end_line + 1):
                for match in COMMENTED_FOREIGN_KEY.finditer(
                    source_lines[line_number - 1]
                ):
                    target = match.group(1)
                    if "." not in target:
                        continue
                    target_table, target_column = target.rsplit(".", 1)
                    if target_table not in selected_tables:
                        continue
                    candidates.append(
                        RelationCandidate(
                            src=f"{table_name}.{column_name}",
                            dst=f"{target_table}.{target_column}",
                            signal="commented_fk",
                            path=path,
                            line=line_number,
                        )
                    )
    return candidates


def _primaryjoin_candidates(
    module: ast.Module,
    *,
    path: str,
    class_to_table: dict[str, str],
    selected_tables: set[str],
) -> list[RelationCandidate]:
    candidates = []
    for call in ast.walk(module):
        if not isinstance(call, ast.Call):
            continue
        for keyword in call.keywords:
            if (
                keyword.arg != "primaryjoin"
                or not isinstance(keyword.value, ast.Constant)
                or not isinstance(keyword.value.value, str)
            ):
                continue
            try:
                expression = ast.parse(keyword.value.value, mode="eval")
            except SyntaxError:
                continue
            for node in ast.walk(expression):
                candidate = _comparison_candidate(
                    node,
                    class_to_table=class_to_table,
                    selected_tables=selected_tables,
                    signal="primaryjoin",
                    path=path,
                    line=keyword.value.lineno,
                )
                if candidate is not None:
                    candidates.append(candidate)
    return candidates


def _comparison_candidates(
    module: ast.Module,
    *,
    path: str,
    class_to_table: dict[str, str],
    selected_tables: set[str],
) -> list[RelationCandidate]:
    candidates = []
    for node in ast.walk(module):
        candidate = _comparison_candidate(
            node,
            class_to_table=class_to_table,
            selected_tables=selected_tables,
            signal="comparison",
            path=path,
            line=getattr(node, "lineno", 1),
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _file_candidates(
    path: str,
    source: str,
    *,
    class_to_table: dict[str, str],
    selected_tables: set[str],
) -> list[RelationCandidate]:
    try:
        module = ast.parse(source, filename=path)
    except SyntaxError as error:
        raise RuntimeError(
            f"could not parse {path}: line {error.lineno}: {error.msg}"
        ) from error
    source_lines = source.splitlines()
    return [
        *_commented_foreign_key_candidates(
            module,
            source_lines,
            path=path,
            class_to_table=class_to_table,
            selected_tables=selected_tables,
        ),
        *_primaryjoin_candidates(
            module,
            path=path,
            class_to_table=class_to_table,
            selected_tables=selected_tables,
        ),
        *_comparison_candidates(
            module,
            path=path,
            class_to_table=class_to_table,
            selected_tables=selected_tables,
        ),
    ]


def find_relation_candidates(
    repo: Path,
    commit: str,
    tables: Sequence[str],
) -> list[RelationCandidate]:
    extracted_tables = extract_tables(repo, commit)
    class_to_table = {
        table.class_name: table.name for table in extracted_tables.values()
    }
    selected_tables = set(tables)
    candidates = []
    for path in _candidate_paths(repo, commit):
        source = _git_output(repo, ["show", f"{commit}:{path}"])
        candidates.extend(
            _file_candidates(
                path,
                source,
                class_to_table=class_to_table,
                selected_tables=selected_tables,
            )
        )

    candidates.sort(key=lambda candidate: (candidate.path, candidate.line))
    deduplicated: dict[tuple[str, str, str], RelationCandidate] = {}
    for candidate in candidates:
        deduplicated.setdefault(
            (candidate.src, candidate.dst, candidate.signal),
            candidate,
        )
    return sorted(
        deduplicated.values(),
        key=lambda candidate: (
            candidate.src,
            candidate.dst,
            candidate.signal,
            candidate.path,
            candidate.line,
        ),
    )
