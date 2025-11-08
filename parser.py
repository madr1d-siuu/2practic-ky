# Stage 2

from typing import Dict, Tuple, Any


def get_package_name_version(package_json: Dict[str, Any]) -> Tuple[str, str]:
    """
    Возвращает (name, version) из package.json или npm registry (/latest).
    Если полей нет — подставляет пустые строки.
    """
    name = str(package_json.get("name", "") or "")
    version = str(package_json.get("version", "") or "")
    return name, version


def extract_dependencies(package_json: Dict[str, Any]) -> Dict[str, str]:
    """
    Извлекает прямые зависимости из package.json.
    Возвращает словарь {имя_пакета: версия}.

    Примечания:
    - Берём только поле "dependencies" (прямые зависимости).
    - Игнорируем optional/peer/dev — по ТЗ нужны прямые зависимости.
    - Гарантируем типы ключей/значений как строки.
    """
    deps = package_json.get("dependencies", {}) or {}
    if not isinstance(deps, dict):
        return {}

    result: Dict[str, str] = {}
    for k, v in deps.items():
        # пропускаем нестроковые ключи
        if not isinstance(k, str):
            continue
        # версия может быть нестрокой — нормализуем
        result[k] = str(v)
    return result