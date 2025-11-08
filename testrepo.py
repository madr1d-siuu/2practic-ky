# testrepo.py

from typing import Dict, List, Set, Optional


def load_test_repo(file_path: str) -> Dict[str, List[str]]:
    """
    Загружает описание тестового репозитория из файла формата:
        A: B C
        B: D
        C: D E
        D:
        E:
    Пустые строки и строки, начинающиеся с '#', игнорируются.
    Строки без двоеточия также игнорируются.
    """
    repo: Dict[str, List[str]] = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            pkg, deps = line.split(":", 1)
            pkg = pkg.strip()
            dep_list = [d.strip() for d in deps.split() if d.strip()]
            repo[pkg] = dep_list
    return repo


def build_full_graph(root: str, repo: Dict[str, List[str]], filter_substr: str) -> Dict[str, List[str]]:
    """
    Строит полный граф зависимостей из тестового репозитория DFS-обходом с рекурсией.
    - Игнорирует узлы (кроме root), чьё имя содержит filter_substr.
    - Корректно обрабатывает циклы.
    - Если root отсутствует в repo — KeyError(root).
    Возвращает adjacency list: {узел: [его прямые зависимости]}.
    """
    if root not in repo:
        raise KeyError(root)

    graph: Dict[str, List[str]] = {}
    visited: Set[str] = set()
    rec_stack: Set[str] = set()
    flt = (filter_substr or "").strip()

    def dfs(pkg: str) -> None:
        if pkg in rec_stack:
            return
        if pkg in visited:
            return
        if flt and pkg != root and flt in pkg:
            return

        visited.add(pkg)
        rec_stack.add(pkg)

        deps = repo.get(pkg, [])
        kept_children: List[str] = []
        for d in deps:
            if flt and flt in d:
                continue
            kept_children.append(d)
            dfs(d)

        graph[pkg] = kept_children
        rec_stack.remove(pkg)

    dfs(root)
    return graph


def get_load_order(graph: Dict[str, List[str]], root: str) -> List[str]:
    """
    Возвращает порядок загрузки «снизу-вверх» (пост-обход DFS без разворота списка).
    Дубликаты не выводятся.
    Пример: для A->(B, C), B->D, C->(D, E) → D, E, B, C, A.
    """
    visited: Set[str] = set()
    order: List[str] = []

    def dfs(node: str) -> None:
        if node in visited:
            return
        visited.add(node)
        for child in graph.get(node, []):
            dfs(child)
        order.append(node)

    dfs(root)
    return order


def print_ascii_tree(
    graph: Dict[str, List[str]],
    root: str,
    prefix: str = "",
    visited: Optional[Set[str]] = None,
    is_last: bool = True,
) -> None:
    """
    Печатает дерево зависимостей в ASCII-формате с ровными отступами.
    Повторные узлы помечаются [повтор].
    """
    if visited is None:
        visited = set()

    connector = "└── " if is_last else "├── "
    print(prefix + connector + root)
    visited.add(root)

    children = graph.get(root, [])
    for i, child in enumerate(children):
        last = i == len(children) - 1
        branch_prefix = prefix + ("    " if is_last else "│   ")
        if child in visited:
            repeat_connector = "└── " if last else "├── "
            print(branch_prefix + repeat_connector + f"{child} [повтор]")
            continue
        print_ascii_tree(graph, child, branch_prefix, visited, last)


def generate_dot(graph: Dict[str, List[str]]) -> str:
    """
    Генерирует Graphviz DOT описание ориентированного графа зависимостей. Можно протестить на сайте
    graph.flyte.org 
    """
    lines = ["digraph dependencies {"]
    for node in sorted(graph.keys()):
        for dep in sorted(graph.get(node, [])):
            lines.append(f'    "{node}" -> "{dep}";')
    lines.append("}")
    return "\n".join(lines)