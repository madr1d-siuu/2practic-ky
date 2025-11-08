# npmrepo.py
from typing import Dict, List, Set, Tuple
from fetch import fetch_npm_package_at

Node = str  # формат "name@version"
Graph = Dict[Node, List[Node]]

def _node(name: str, version: str) -> Node:
    return f"{name}@{version}"

def build_npm_graph(root_name: str, root_spec: str = None, filter_substr: str = "") -> Tuple[Graph, Node]:
    """
    Строит граф зависимостей npm-пакета, рекурсивно вытягивая package.json из npm registry.
    Упрощённый резолвер версий:
      - точная версия -> берётся она;
      - иначе -> dist-tags.latest.
    Фильтр: игнорирует узлы, чьё ИМЯ (до @) содержит подстроку (кроме корня).
    Возвращает (graph, root_node), где node = "name@version".
    """
    graph: Graph = {}
    visited: Set[Node] = set()
    rec_stack: Set[Node] = set()
    flt = (filter_substr or "").strip()

    def dfs(name: str, spec: str = None) -> Node:
        pkg = fetch_npm_package_at(name, spec)
        ver = str(pkg.get("version") or "")
        node = _node(name, ver)

        if node in rec_stack:
            return node
        if node in visited:
            return node
        if flt and name != root_name and flt in name:
            # игнорируем целиком этот узел (не добавляем рёбра)
            visited.add(node)
            graph.setdefault(node, [])
            return node

        visited.add(node)
        rec_stack.add(node)

        deps = (pkg.get("dependencies") or {})
        children: List[Node] = []
        for dep_name, dep_spec in deps.items():
            if flt and flt in dep_name:
                continue
            child_node = dfs(dep_name, str(dep_spec))
            children.append(child_node)

        graph[node] = children
        rec_stack.remove(node)
        return node

    root_node = dfs(root_name, root_spec)
    return graph, root_node