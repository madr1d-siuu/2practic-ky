# Stage 2
import re
import json
import requests

DEFAULT_TIMEOUT = 10  # seconds


class FetchError(RuntimeError):
    """Общее исключение для ошибок загрузки package.json."""
    pass


# https://github.com/<owner>/<repo>[.git][/...]
_GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?(?:/|$)"
)


def _guess_github_raw_urls(repo_url: str) -> list[str]:
    """
    Из URL репозитория GitHub формирует кандидатов raw для package.json:
    - main/package.json
    - master/package.json
    """
    m = _GITHUB_REPO_RE.match(repo_url)
    if not m:
        return []
    owner = m.group("owner")
    repo = m.group("repo")
    branches = ["main", "master"]
    return [
        f"https://raw.githubusercontent.com/{owner}/{repo}/{br}/package.json"
        for br in branches
    ]


def _fetch_json(url: str) -> dict:
    try:
        r = requests.get(url, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as e:
        raise FetchError(f"Сетевой сбой при GET {url}: {e}") from e

    if r.status_code != 200:
        raise FetchError(f"GET {url} → HTTP {r.status_code}")

    # Некоторые сервера не выставляют корректный Content-Type, поэтому пробуем json() всегда.
    try:
        return r.json()
    except ValueError as e:
        snippet = r.text[:200].replace("\n", " ")
        raise FetchError(f"Некорректный JSON с {url}. Фрагмент: {snippet!r}") from e


def fetch_package_json(repo_or_url: str) -> dict:
    """
    Загружает package.json одним из способов:
      1) Если это raw-ссылка на GitHub (raw.githubusercontent.com/.../package.json) — берём как есть.
      2) Если это URL репозитория GitHub — пробуем main/master → raw package.json.
      3) Если это npm registry URL вида https://registry.npmjs.org/<name>/latest — возвращаем JSON из реестра.
      4) Если передано имя пакета (или префикс npm:<name>) — запрашиваем https://registry.npmjs.org/<name>/latest.

    Возвращает dict с содержимым package.json или npm-манифеста (у npm registry это объект метаданных, где
    нужные поля расположены на верхнем уровне, включая "name", "version", "dependencies" и пр.).
    """
    url = (repo_or_url or "").strip()
    if not url:
        raise FetchError("Пустой URL/идентификатор репозитория.")

    # 3) npm registry URL напрямую
    if url.startswith("https://registry.npmjs.org/"):
        return _fetch_json(url)

    # 1) raw link напрямую
    if "raw.githubusercontent.com" in url and url.endswith("/package.json"):
        return _fetch_json(url)

    # 2) GitHub repo URL → пробуем main/master raw
    raw_candidates = _guess_github_raw_urls(url)
    for raw_url in raw_candidates:
        try:
            return _fetch_json(raw_url)
        except FetchError:
            continue

    # 4) npm имя пакета (или префикс npm:)
    pkg = None
    if url.startswith("npm:"):
        pkg = url[4:]
    elif not url.startswith("http://") and not url.startswith("https://"):
        pkg = url

    if pkg:
        return _fetch_json(f"https://registry.npmjs.org/{pkg}/latest")

    # Если сюда дошли — ничего не сработало
    raise FetchError(
        "Не удалось получить package.json: укажите raw URL, URL GitHub-репозитория, "
        "npm registry URL или имя пакета (npm)."
    )

# ===== NPM helpers for graph building (real mode) =====

def _fetch_npm_metadata(name: str) -> dict:
    """Загружает полный npm-манифест пакета: https://registry.npmjs.org/<name>"""
    url = f"https://registry.npmjs.org/{name}"
    return _fetch_json(url)

def _is_exact_semver(spec: str) -> bool:
    # очень простая проверка на точную версию: 1.2.3 или 1.2.3-beta.1 и т.п.
    # без семантической логики — только для «есть/нет»
    return bool(re.match(r"^\d+\.\d+\.\d+([\-+].+)?$", spec or ""))

def select_version(metadata: dict, spec: str = None) -> str:
    """
    Возвращает строку версии для загрузки:
      - если spec точная и присутствует в metadata["versions"] — возвращаем её,
      - иначе возвращаем metadata["dist-tags"]["latest"].
    """
    versions = (metadata.get("versions") or {}).keys()
    dist_tags = metadata.get("dist-tags") or {}
    if spec and _is_exact_semver(spec) and spec in versions:
        return spec
    latest = dist_tags.get("latest")
    if not latest:
        # если у пакета нет latest — возьмём любую последнюю по алфавиту версию
        all_versions = sorted(versions)
        if not all_versions:
            raise FetchError("У пакета нет доступных версий.")
        return all_versions[-1]
    return latest

def fetch_npm_package_at(name: str, spec: str = None) -> dict:
    """
    Возвращает package.json конкретной версии пакета:
      - тянем метаданные пакета,
      - выбираем версию через select_version(),
      - возвращаем объект из metadata["versions"][<chosen>].
    """
    meta = _fetch_npm_metadata(name)
    ver = select_version(meta, spec)
    versions = meta.get("versions") or {}
    pkg = versions.get(ver)
    if not pkg:
        raise FetchError(f"Версия {name}@{ver} не найдена в реестре.")
    return pkg  # это полноценный package.json выбранной версии