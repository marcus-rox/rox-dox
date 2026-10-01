from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Collection
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Literal

from rox_dox.features import _git_blobs, _git_tree
from rox_dox.model import Model


class Endpoint(Model):
    method: str
    path: str
    handler: str
    line: int


class Worker(Model):
    name: str
    kind: Literal["task_executor", "temporal_workflow", "temporal_activity"]
    line: int


class ExternalCall(Model):
    service: str
    module: str
    line: int


class FileFacts(Model):
    path: str
    api_group: str | None
    endpoints: list[Endpoint]
    workers: list[Worker]
    externals: list[ExternalCall]


EXTERNAL_SERVICES = {
    "slack_sdk": "Slack",
    "twilio": "Twilio",
    "googleapiclient": "Google APIs",
    "google.auth": "Google APIs",
    "google.oauth2": "Google APIs",
    "google.cloud": "Google APIs",
    "google.api_core": "Google APIs",
    "simple_salesforce": "Salesforce",
    "hubspot": "HubSpot",
    "stripe": "Stripe",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "litellm": "LiteLLM",
    "boto3": "AWS",
    "msal": "Microsoft identity",
}
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})


def _expression_parts(expression: ast.expr) -> list[str] | None:
    if isinstance(expression, ast.Subscript):
        expression = expression.value
    parts = []
    while isinstance(expression, ast.Attribute):
        parts.append(expression.attr)
        expression = expression.value
    if not isinstance(expression, ast.Name):
        return None
    return [expression.id, *reversed(parts)]


def _call_name(expression: ast.expr) -> str | None:
    parts = _expression_parts(expression)
    return parts[-1] if parts else None


def _constant_string(expression: ast.expr | None) -> str | None:
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return expression.value
    return None


def _keyword_string(call: ast.Call, name: str) -> str | None:
    return next(
        (
            value
            for keyword in call.keywords
            if keyword.arg == name
            and (value := _constant_string(keyword.value)) is not None
        ),
        None,
    )


def _assignment_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for item in target.elts for name in _assignment_names(item)]
    return []


def _module_assignments(tree: ast.Module) -> list[tuple[str, ast.expr]]:
    assignments = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
            value = statement.value
        else:
            continue
        if value is None:
            continue
        assignments.extend(
            (name, value) for target in targets for name in _assignment_names(target)
        )
    return assignments


def _namespace_names(tree: ast.Module) -> dict[str, str]:
    namespaces = {}
    for variable, value in _module_assignments(tree):
        if not isinstance(value, ast.Call):
            continue
        call_name = _call_name(value.func)
        if call_name is None or not call_name.endswith("Namespace"):
            continue
        namespace = _keyword_string(value, "name")
        if namespace is None and value.args:
            namespace = _constant_string(value.args[0])
        if namespace is not None:
            namespaces[variable] = namespace
    return namespaces


def _registered_paths(tree: ast.Module) -> dict[str, set[str]]:
    paths: defaultdict[str, set[str]] = defaultdict(set)
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Call)
            or _call_name(node.func) != "add_namespace"
            or not node.args
            or not isinstance(node.args[0], ast.Name)
        ):
            continue
        path = _keyword_string(node, "path")
        if path is not None:
            paths[node.args[0].id].add(path)
    return dict(paths)


def _namespace_prefixes(repo: Path, commit: str) -> dict[str, frozenset[str]]:
    python_paths = [
        (path, object_id)
        for path, object_id in _git_tree(repo, commit)
        if path.startswith("backend/src/") and path.endswith(".py")
    ]
    sources = _git_blobs(repo, python_paths)
    registrations: defaultdict[str, set[str]] = defaultdict(set)
    for path in sorted(sources):
        source = sources[path]
        if "add_namespace" not in source:
            continue
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            continue
        for variable, paths in _registered_paths(tree).items():
            registrations[variable].update(paths)
    return {name: frozenset(paths) for name, paths in registrations.items()}


@lru_cache(maxsize=16)
def _cached_namespace_prefixes(repo: Path, commit: str) -> dict[str, frozenset[str]]:
    return _namespace_prefixes(repo, commit)


def _join_path(prefix: str, path: str) -> str:
    parts = [value.strip("/") for value in (prefix, path) if value.strip("/")]
    return "/" + "/".join(parts) if parts else "/"


def _decorator_call(decorator: ast.expr) -> tuple[list[str], ast.Call | None]:
    if isinstance(decorator, ast.Call):
        return _expression_parts(decorator.func) or [], decorator
    return _expression_parts(decorator) or [], None


def _flask_endpoints(
    tree: ast.Module,
    path: str,
    prefixes: dict[str, frozenset[str]],
) -> list[tuple[str, Endpoint]]:
    namespaces = _namespace_names(tree)
    endpoints = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            parts, call = _decorator_call(decorator)
            if len(parts) < 2 or parts[-1] != "route" or call is None:
                continue
            namespace_variable = parts[-2]
            namespace = namespaces.get(namespace_variable)
            if namespace is None:
                continue
            route_path = _constant_string(call.args[0]) if call.args else ""
            if route_path is None:
                continue
            registered = prefixes.get(namespace_variable, frozenset())
            prefix = (
                next(iter(registered))
                if len(registered) == 1
                else "/" + namespace.strip("/")
            )
            for method in node.body:
                if (
                    isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and method.name in HTTP_METHODS
                ):
                    endpoints.append(
                        (
                            namespace,
                            Endpoint(
                                method=method.name.upper(),
                                path=_join_path(prefix, route_path),
                                handler=node.name,
                                line=decorator.lineno,
                            ),
                        )
                    )
    return endpoints


def _router_config(
    tree: ast.Module,
    path: str,
) -> dict[str, tuple[str, str]]:
    routers = {}
    for variable, value in _module_assignments(tree):
        if not isinstance(value, ast.Call):
            continue
        call_name = _call_name(value.func)
        if call_name != "APIRouter" and variable != "app":
            continue
        prefix = _keyword_string(value, "prefix")
        tags = next(
            (
                keyword.value
                for keyword in value.keywords
                if keyword.arg == "tags"
                and isinstance(keyword.value, (ast.List, ast.Tuple))
            ),
            None,
        )
        first_tag = (
            _constant_string(tags.elts[0])
            if isinstance(tags, (ast.List, ast.Tuple)) and tags.elts
            else None
        )
        group = (
            (prefix.strip("/") if prefix is not None else "")
            or first_tag
            or (PurePosixPath(path).stem)
        )
        routers[variable] = (prefix or "", group)
    return routers


def _fastapi_endpoints(
    tree: ast.Module,
    path: str,
) -> list[tuple[str, Endpoint]]:
    routers = _router_config(tree, path)
    routers.setdefault("app", ("", PurePosixPath(path).stem))
    endpoints = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            parts, call = _decorator_call(decorator)
            if len(parts) < 2 or parts[-1] not in HTTP_METHODS or call is None:
                continue
            router = routers.get(parts[-2])
            if router is None:
                continue
            route_path = _constant_string(call.args[0]) if call.args else ""
            if route_path is None:
                continue
            prefix, group = router
            endpoints.append(
                (
                    group,
                    Endpoint(
                        method=parts[-1].upper(),
                        path=_join_path(prefix, route_path),
                        handler=node.name,
                        line=decorator.lineno,
                    ),
                )
            )
    return endpoints


def _worker_facts(tree: ast.Module) -> list[Worker]:
    workers = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if not node.name.startswith("Base") and any(
                (parts := _expression_parts(base))
                and parts[-1].endswith("TaskExecutor")
                for base in node.bases
            ):
                workers.append(
                    Worker(
                        name=node.name,
                        kind="task_executor",
                        line=node.lineno,
                    )
                )
            if any(
                _decorator_call(decorator)[0][-2:] == ["workflow", "defn"]
                for decorator in node.decorator_list
            ):
                workers.append(
                    Worker(
                        name=node.name,
                        kind="temporal_workflow",
                        line=node.lineno,
                    )
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(
                _decorator_call(decorator)[0][-2:] == ["activity", "defn"]
                for decorator in node.decorator_list
            ):
                workers.append(
                    Worker(
                        name=node.name,
                        kind="temporal_activity",
                        line=node.lineno,
                    )
                )
    return workers


def _external_facts(tree: ast.Module) -> list[ExternalCall]:
    calls = []
    service_keys = sorted(EXTERNAL_SERVICES, key=lambda key: (-len(key), key))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules = [node.module]
        else:
            continue
        for module in modules:
            service_key = next(
                (
                    key
                    for key in service_keys
                    if module == key or module.startswith(f"{key}.")
                ),
                None,
            )
            if service_key is not None:
                calls.append(
                    ExternalCall(
                        service=EXTERNAL_SERVICES[service_key],
                        module=module,
                        line=node.lineno,
                    )
                )
    unique = {(call.service, call.module, call.line): call for call in calls}
    return sorted(
        unique.values(),
        key=lambda call: (call.service, call.module, call.line),
    )


def _file_facts(
    path: str,
    source: str,
    prefixes: dict[str, frozenset[str]],
) -> FileFacts:
    endpoints: list[tuple[str, Endpoint]] = []
    if path.endswith(".py"):
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            return FileFacts(
                path=path,
                api_group=None,
                endpoints=[],
                workers=[],
                externals=[],
            )
        endpoints.extend(_flask_endpoints(tree, path, prefixes))
        endpoints.extend(_fastapi_endpoints(tree, path))
        workers = _worker_facts(tree)
        externals = _external_facts(tree)
    else:
        return FileFacts(
            path=path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[],
        )
    groups = sorted({group for group, _ in endpoints})
    return FileFacts(
        path=path,
        api_group=groups[0] if groups else None,
        endpoints=sorted(
            {
                endpoint.model_dump_json(): endpoint for _, endpoint in endpoints
            }.values(),
            key=lambda endpoint: (
                endpoint.path,
                endpoint.method,
                endpoint.handler,
                endpoint.line,
            ),
        ),
        workers=sorted(
            {worker.model_dump_json(): worker for worker in workers}.values(),
            key=lambda worker: (worker.kind, worker.name, worker.line),
        ),
        externals=externals,
    )


def extract_file_facts(
    repo: Path,
    commit: str,
    paths: Collection[str],
) -> dict[str, FileFacts]:
    requested = sorted(set(paths))
    tree = dict(_git_tree(repo, commit))
    missing = sorted(path for path in requested if path not in tree)
    if missing:
        raise ValueError(f"paths are missing at {commit}: {', '.join(missing)}")
    python_paths = [path for path in requested if path.endswith(".py")]
    sources = _git_blobs(repo, [(path, tree[path]) for path in python_paths])
    prefixes = _cached_namespace_prefixes(repo.resolve(), commit)
    return {
        path: _file_facts(path, sources.get(path, ""), prefixes) for path in requested
    }
