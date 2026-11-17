"""Pure helpers: condense an OpenAPI document, validate a call against it, and inject source credentials."""

import os
import re
from urllib.parse import quote, urlsplit

import yaml

READ_METHODS = {"get", "head"}


def parse_url_map(text: str) -> list[tuple[str, str]]:
    """'from=to,from=to' -> prefix pairs, e.g. 'http://src-pictoaccess:8000/=http://localhost:8103/'."""
    pairs = [p.split("=", 1) for p in text.split(",") if p.strip()]
    if any(len(p) != 2 for p in pairs):
        raise ValueError("SOURCE_URL_MAP must look like 'http://from/=http://to/,…'")
    return [(a.strip(), b.strip()) for a, b in pairs]


def reachable(url: str, url_map: list[tuple[str, str]]) -> str:
    """Rewrite a registered source URL to where this connector can reach it (first matching prefix)."""
    return next((to + url[len(src):] for src, to in url_map if url.startswith(src)), url)


def load_credentials(path: str) -> dict:
    """credentials.yaml maps dataset id -> {api_key, in?, name?, prefix?}; ${VAR} is read from the environment."""
    try:
        with open(path) as f:
            text = f.read()
    except FileNotFoundError:
        return {}
    text = re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), text)
    creds = yaml.safe_load(text) or {}
    return {k: v for k, v in creds.items() if isinstance(v, dict) and v.get("api_key")}


def _resolve(spec: dict, node):
    """Follow local $ref pointers such as #/components/parameters/limit."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 10:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            return node
        node = spec
        for part in ref[2:].split("/"):
            node = node.get(part.replace("~1", "/").replace("~0", "~"), {})
        seen += 1
    return node


def operations(spec: dict) -> dict[str, dict]:
    """operation id -> {method, path, op, parameters}. Operations without operationId get 'METHOD /path'."""
    ops = {}
    for path, item in (spec.get("paths") or {}).items():
        item = _resolve(spec, item)
        shared = [_resolve(spec, p) for p in item.get("parameters", [])]
        for method, op in item.items():
            if method not in {"get", "put", "post", "delete", "patch", "head", "options"}:
                continue
            params = {(p["name"], p["in"]): p for p in shared}
            params.update({(p["name"], p["in"]): p for p in (_resolve(spec, x) for x in op.get("parameters", []))})
            op_id = op.get("operationId") or f"{method.upper()} {path}"
            ops[op_id] = {"method": method, "path": path, "op": op, "parameters": list(params.values())}
    return ops


def _enum(spec: dict, schema: dict) -> list | None:
    """Allowed values, also when nested in anyOf (optional params) or items (array params)."""
    schema = _resolve(spec, schema or {})
    if "enum" in schema:
        return schema["enum"]
    for sub in schema.get("anyOf", []) + ([schema["items"]] if "items" in schema else []):
        found = _enum(spec, sub)
        if found:
            return found
    return None


def _security_schemes(spec: dict, op: dict) -> list[dict]:
    reqs = op.get("security", spec.get("security", []))
    schemes = (spec.get("components") or {}).get("securitySchemes") or {}
    return [_resolve(spec, schemes[name]) for req in reqs for name in req if name in schemes]


def condense(spec: dict, credentials_configured: bool) -> dict:
    """A compact view of the API that fits in an agent's context."""
    info = spec.get("info", {})
    out = []
    for op_id, o in operations(spec).items():
        if o["method"] not in READ_METHODS:
            continue
        params = []
        for p in o["parameters"]:
            schema = _resolve(spec, p.get("schema", {}))
            params.append({k: v for k, v in {
                "name": p["name"], "in": p["in"], "required": p.get("required", False),
                "type": schema.get("type") or [s.get("type") for s in schema.get("anyOf", []) if s.get("type") != "null"],
                "enum": _enum(spec, schema), "default": schema.get("default"),
                "description": p.get("description") or schema.get("description"),
            }.items() if v not in (None, [], "")})
        out.append({k: v for k, v in {
            "operation_id": op_id, "method": o["method"].upper(), "path": o["path"],
            "summary": o["op"].get("summary"), "description": o["op"].get("description"),
            "parameters": params, "requires_api_key": bool(_security_schemes(spec, o["op"])),
        }.items() if v not in (None, "")})
    return {"title": info.get("title"), "description": info.get("description"),
            "credentials_configured": credentials_configured, "operations": out}


class CallError(ValueError):
    pass


def build_request(spec: dict, endpoint_url: str, operation_id: str, params: dict, cred: dict | None):
    """Validate params against the operation and return (method, url, query, headers). Raises CallError."""
    ops = operations(spec)
    if operation_id not in ops:
        raise CallError(f"unknown operation_id {operation_id!r}; known: {sorted(ops)}")
    o = ops[operation_id]
    if o["method"] not in READ_METHODS:
        raise CallError("only read operations (GET, HEAD) may be called")
    declared = {p["name"]: p for p in o["parameters"] if p["in"] in {"path", "query", "header"}}
    unknown = sorted(set(params) - set(declared))
    if unknown:
        raise CallError(f"parameters not in the OpenAPI: {unknown}; allowed: {sorted(declared)}")
    missing = sorted(n for n, p in declared.items() if p.get("required") and n not in params)
    if missing:
        raise CallError(f"missing required parameters: {missing}")
    for name, value in params.items():
        enum = _enum(spec, declared[name].get("schema", {}))
        bad = [v for v in (value if isinstance(value, list) else [value]) if enum and v not in enum]
        if bad:
            raise CallError(f"{name}={bad!r} is not one of {enum}")

    path = o["path"]
    query, headers = {}, {}
    for name, value in params.items():
        where = declared[name]["in"]
        if where == "path":
            path = path.replace("{" + name + "}", quote(str(value), safe=""))
        elif where == "query":
            query[name] = value
        else:
            headers[name] = str(value)
    url = endpoint_url.rstrip("/") + "/" + path.lstrip("/")
    if urlsplit(url).netloc != urlsplit(endpoint_url).netloc:
        raise CallError("refusing a call outside the registered endpoint host")

    schemes = _security_schemes(spec, o["op"])
    if cred:
        where, name, prefix = cred.get("in"), cred.get("name"), cred.get("prefix", "")
        if not (where and name):
            scheme = next((s for s in schemes if s.get("type") in {"apiKey", "http"}), None)
            if scheme is None:
                raise CallError("the OpenAPI declares no apiKey/http security scheme; set 'in' and 'name' in credentials.yaml")
            if scheme["type"] == "apiKey":
                where, name = scheme["in"], scheme["name"]
            else:
                where, name, prefix = "header", "Authorization", prefix or "Bearer "
        if where == "query":
            query[name] = prefix + cred["api_key"]
        elif where == "header":
            headers[name] = prefix + cred["api_key"]
        else:
            raise CallError(f"unsupported credential location {where!r}")
    # No key configured: call anyway; some sources declare a key that is optional (e.g. higher quotas only).
    return o["method"].upper(), url, query, headers
