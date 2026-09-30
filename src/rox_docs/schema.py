"""Reads SQLAlchemy table declarations out of source without importing it."""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Column:
    name: str
    type_name: str
    primary_key: bool
    foreign_key: str | None


@dataclass(frozen=True)
class Table:
    name: str
    class_name: str
    path: str
    line: int
    end_line: int
    columns: tuple[Column, ...]


def extract_tables(repo: Path, src_dir: str) -> list[Table]:
    """Every class with a `__tablename__` under `repo/src_dir`; f-string names keep their `{placeholders}`."""
    tables = []
    for file in sorted((repo / src_dir).rglob("*.py")):
        tree = ast.parse(file.read_text(), filename=str(file))
        rel = str(file.relative_to(repo))
        tables += [
            t
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and (t := _table(node, rel))
        ]
    return tables


def tables_touched(repo: Path, covers: list[str], tables: list[Table]) -> list[Table]:
    """Tables declared under `covers`, or whose model class is imported by a file under `covers`."""
    by_class: dict[str, list[Table]] = {}
    for t in tables:
        by_class.setdefault(t.class_name, []).append(t)
    touched = {t.name: t for t in tables if any(_under(t.path, c) for c in covers)}
    for cover in covers:
        root = repo / cover
        files = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for file in files:
            for module, name in _imported_names(ast.parse(file.read_text())):
                for t in _resolve(by_class.get(name, []), module):
                    touched.setdefault(t.name, t)
    return sorted(touched.values(), key=lambda t: t.name)


def _table(cls: ast.ClassDef, path: str) -> Table | None:
    name = next(
        (_tablename(s.value) for s in cls.body if _assigns(s, "__tablename__")), None
    )
    if name is None:
        return None
    columns = tuple(c for s in cls.body if (c := _column(s)))
    return Table(
        name, cls.name, path, cls.lineno, cls.end_lineno or cls.lineno, columns
    )


def _assigns(stmt: ast.stmt, target: str) -> bool:
    return isinstance(stmt, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == target for t in stmt.targets
    )


def _tablename(value: ast.expr) -> str:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.JoinedStr):
        return "".join(
            p.value if isinstance(p, ast.Constant) else "{" + ast.unparse(p.value) + "}"
            for p in value.values
        )
    return "{" + ast.unparse(value) + "}"


def _column(stmt: ast.stmt) -> Column | None:
    if not (
        isinstance(stmt, ast.AnnAssign)
        and isinstance(stmt.target, ast.Name)
        and isinstance(stmt.value, ast.Call)
    ):
        return None
    call = stmt.value
    if _call_name(call) != "mapped_column":
        return None
    primary_key = any(
        k.arg == "primary_key"
        and isinstance(k.value, ast.Constant)
        and k.value.value is True
        for k in call.keywords
    )
    foreign_key = next((fk for a in call.args if (fk := _foreign_key(a))), None)
    return Column(
        stmt.target.id, _type_name(stmt.annotation, call), primary_key, foreign_key
    )


def _call_name(call: ast.Call) -> str:
    func = call.func
    return (
        func.id
        if isinstance(func, ast.Name)
        else func.attr
        if isinstance(func, ast.Attribute)
        else ""
    )


def _foreign_key(arg: ast.expr) -> str | None:
    if isinstance(arg, ast.Call) and _call_name(arg) == "ForeignKey" and arg.args:
        target = arg.args[0]
        if isinstance(target, ast.Constant) and isinstance(target.value, str):
            return target.value
    return None


def _type_name(annotation: ast.expr, call: ast.Call) -> str:
    """The SQL type passed to mapped_column if any, else the Python type inside Mapped[...]."""
    for arg in call.args:
        if isinstance(arg, ast.Name):
            return arg.id
        if isinstance(arg, ast.Call) and _call_name(arg) != "ForeignKey":
            return _call_name(arg)
    if isinstance(annotation, ast.Subscript):
        return ast.unparse(annotation.slice)
    return ast.unparse(annotation)


def _imported_names(tree: ast.Module) -> list[tuple[str, str]]:
    return [
        (n.module or "", a.name)
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
        for a in n.names
    ]


def _resolve(candidates: list[Table], module: str) -> list[Table]:
    """Same-named model classes are disambiguated by the import's module path when it names one."""
    if len(candidates) <= 1:
        return candidates
    module_path = module.replace(".", "/")
    exact = [t for t in candidates if module_path and module_path in t.path]
    return exact or candidates


def _under(path: str, cover: str) -> bool:
    return path == cover or path.startswith(cover.rstrip("/") + "/")


if __name__ == "__main__":
    import sys

    repo_arg, src_arg = Path(sys.argv[1]), sys.argv[2]
    found = extract_tables(repo_arg, src_arg)
    print(f"{len(found)} tables, {sum(len(t.columns) for t in found)} columns")
    for t in found[:5]:
        print(t.name, t.path, [c.name for c in t.columns][:6])
    if len(sys.argv) > 3:
        hit = tables_touched(repo_arg, sys.argv[3:], found)
        print(f"{len(hit)} touched by {sys.argv[3:]}:", [t.name for t in hit][:40])
