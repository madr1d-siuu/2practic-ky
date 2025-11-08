import argparse
import os
import sys

from testrepo import (
    load_test_repo,
    build_full_graph,
    get_load_order,
    print_ascii_tree,
    generate_dot,
)
from npmrepo import build_npm_graph
from fetch import fetch_package_json, FetchError
from parser import extract_dependencies


def print_user_config(args: argparse.Namespace) -> None:
    """Этап 1: печать всех настраиваемых параметров в формате ключ=значение."""
    user_config = {
        "package": args.package,
        "repo": args.repo,
        "test": args.test,
        "filter": args.filter,
        "load_order": args.load_order,
        "ascii_tree": args.ascii_tree,
    }
    print("Параметры запуска:")
    for k, v in user_config.items():
        print(f"{k}={v}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dependency graph tool")
    parser.add_argument(
        "--package",
        required=True,
        help="Имя анализируемого пакета",
    )
    parser.add_argument(
        "--repo",
        required=True,
        help=(
            "URL репозитория (для этапа 2) ИЛИ путь к файлу тестового репозитория (при --test)"
        ),
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Включить тестовый режим (работа с файлом описания графа)",
    )
    parser.add_argument(
        "--filter",
        default="",
        help="Подстрока для фильтрации пакетов (игнорировать узлы, содержащие её)",
    )
    parser.add_argument(
        "--load-order",
        action="store_true",
        help="(Этап 4) Вывести порядок загрузки зависимостей (снизу-вверх)",
    )
    parser.add_argument(
        "--ascii-tree",
        action="store_true",
        help="(Этап 5) Вывести зависимости в виде ASCII-дерева",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="depgraph 0.1.0",
    )

    args = parser.parse_args()

    # Этап 1: печать всех параметров в формате ключ=значение
    print_user_config(args)

    # Базовые проверки параметров
    if not args.package.strip():
        print("Ошибка: --package не должен быть пустым.", file=sys.stderr)
        return 2

    if args.test:
        # Тестовый режим (Этапы 3–5)
        if not os.path.isfile(args.repo):
            print(
                f"Ошибка: в тестовом режиме --repo должен быть путём к существующему файлу. Не найдено: {args.repo}",
                file=sys.stderr)
            return 2
        try:
            repo_data = load_test_repo(args.repo)
        except Exception as e:
            print(f"Ошибка чтения тестового репозитория: {e}", file=sys.stderr)
            return 2

        # Построение полного графа с учётом фильтра и обработкой циклов
        try:
            graph = build_full_graph(args.package, repo_data, args.filter)
        except KeyError as e:
            print(f"Ошибка: пакет не найден в тестовом репозитории: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"Ошибка построения графа: {e}", file=sys.stderr)
            return 2

        # Этап 5: вывод Graphviz DOT
        print("\nGraphviz DOT описание:")
        print(generate_dot(graph))

        # Этап 5: ASCII-дерево (по флагу)
        if args.ascii_tree:
            print("\nASCII дерево зависимостей:")
            print_ascii_tree(graph, args.package)

        # Этап 4: порядок загрузки (по флагу)
        if args.load_order:
            order = get_load_order(graph, args.package)
            print("\nПорядок загрузки (снизу-вверх):")
            for p in order:
                print(p)

        return 0

   # Реальный режим (Этап 2 + визуализация для npm)
    try:
        # для этапа 2 печатаем прямые зависимости текущего пакета (latest/точная версия)
        pkg_json = fetch_package_json(args.repo)
    except FetchError as e:
        print(f"Ошибка загрузки package.json: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Непредвиденная ошибка загрузки: {e}", file=sys.stderr)
        return 2

    deps = extract_dependencies(pkg_json)

    # (только для этапа 2) — выводим все прямые зависимости
    if not deps:
        print("Прямые зависимости не найдены.")
    else:
        print("Прямые зависимости:")
        for name, ver in sorted(deps.items()):
            print(f"{name}@{ver}")

    # Дополнительно: если запрошена визуализация/порядок — строим весь граф из npm registry
    if args.ascii_tree or args.load_order:
        try:
            from npmrepo import build_npm_graph
            npm_graph, npm_root = build_npm_graph(args.package, None, args.filter)
        except Exception as e:
            print(f"Ошибка построения npm-графа: {e}", file=sys.stderr)
            return 2

        # DOT (полезно видеть всегда для npm-графа, как в тестовом режиме)
        print("\nGraphviz DOT описание:")
        print(generate_dot(npm_graph))

        if args.ascii_tree:
            print("\nASCII дерево зависимостей:")
            print_ascii_tree(npm_graph, npm_root)

        if args.load_order:
            order = get_load_order(npm_graph, npm_root)
            print("\nПорядок загрузки (снизу-вверх):")
            for p in order:
                print(p)

    return 0


if __name__ == "__main__":
    sys.exit(main())