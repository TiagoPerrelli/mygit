import os
import json
import shutil
import hashlib
from datetime import datetime


# Nomes das pastas internas do nosso git
MYGIT_DIR    = ".mygit"
STAGING_DIR  = os.path.join(MYGIT_DIR, "staging")
COMMITS_DIR  = os.path.join(MYGIT_DIR, "commits")
REFS_DIR     = os.path.join(MYGIT_DIR, "refs", "heads")   # uma ref por branch
HEAD_FILE    = os.path.join(MYGIT_DIR, "HEAD")            # aponta para a branch ativa
CONFIG_FILE  = os.path.join(MYGIT_DIR, "config.json")

DEFAULT_BRANCH = "main"


# ---------------------------------------------------------------------------
# Funções auxiliares — estrutura interna
# ---------------------------------------------------------------------------

def _repo_exists() -> bool:
    """Verifica se já existe um repositório no diretório atual."""
    return os.path.isdir(MYGIT_DIR)


def _require_repo():
    """Lança um erro amigável se não houver repositório inicializado."""
    if not _repo_exists():
        raise FileNotFoundError(
            "Repositório não encontrado. Execute 'mygit init' primeiro."
        )


# --- HEAD e refs ---

def _read_current_branch() -> str:
    """
    Lê o nome da branch ativa a partir do HEAD.
    HEAD contém algo como: ref: refs/heads/main
    """
    if not os.path.exists(HEAD_FILE):
        return DEFAULT_BRANCH
    with open(HEAD_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
    # formato: "ref: refs/heads/<nome>"
    if content.startswith("ref:"):
        return content.split("/")[-1]
    return DEFAULT_BRANCH


def _write_head_branch(branch_name: str):
    """Faz HEAD apontar para uma branch (modo normal)."""
    with open(HEAD_FILE, "w", encoding="utf-8") as f:
        f.write(f"ref: refs/heads/{branch_name}")


def _ref_path(branch_name: str) -> str:
    """Retorna o caminho do arquivo de ref de uma branch."""
    return os.path.join(REFS_DIR, branch_name)


def _read_branch_commit(branch_name: str) -> str | None:
    """Retorna o hash do commit que a branch aponta, ou None."""
    path = _ref_path(branch_name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return content if content else None


def _write_branch_commit(branch_name: str, commit_hash: str):
    """Faz a branch apontar para um commit."""
    os.makedirs(REFS_DIR, exist_ok=True)
    with open(_ref_path(branch_name), "w", encoding="utf-8") as f:
        f.write(commit_hash)


def _read_head() -> str | None:
    """
    Retorna o hash do commit atual (HEAD resolvido).
    Segue a indireção branch → hash.
    """
    branch = _read_current_branch()
    return _read_branch_commit(branch)


def _write_head(commit_hash: str):
    """Avança o ponteiro da branch atual para um novo commit."""
    branch = _read_current_branch()
    _write_branch_commit(branch, commit_hash)


def _list_branches() -> list[str]:
    """Retorna todos os nomes de branches existentes."""
    if not os.path.isdir(REFS_DIR):
        return []
    return os.listdir(REFS_DIR)


# --- Hash e config ---

def _generate_hash(data: str) -> str:
    """Gera um hash SHA-1 curto (8 caracteres) para identificar o commit."""
    return hashlib.sha1(data.encode()).hexdigest()[:8]


def _read_config() -> dict:
    """Lê as configurações do repositório (autor, remote, etc.)."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_config(config: dict):
    """Salva as configurações do repositório."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _load_commit(commit_hash: str) -> dict:
    """Carrega os dados de um commit a partir do seu hash."""
    path = os.path.join(COMMITS_DIR, f"{commit_hash}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Commit '{commit_hash}' não encontrado.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _list_staging_files() -> list[str]:
    """Retorna os arquivos atualmente na área de stage."""
    if not os.path.isdir(STAGING_DIR):
        return []
    return os.listdir(STAGING_DIR)


def _ancestors(commit_hash: str | None) -> set[str]:
    """
    Retorna o conjunto de todos os hashes ancestrais de um commit
    (incluindo ele mesmo). Usado pelo merge para encontrar a base comum.
    """
    visited = set()
    stack = [commit_hash] if commit_hash else []
    while stack:
        h = stack.pop()
        if not h or h in visited:
            continue
        visited.add(h)
        try:
            data = _load_commit(h)
            stack.append(data.get("parent"))
        except FileNotFoundError:
            pass
    return visited


# ---------------------------------------------------------------------------
# Comandos principais
# ---------------------------------------------------------------------------

def init(author: str = "Anônimo") -> str:
    """
    Inicializa um novo repositório no diretório atual.

    Cria .mygit/ com staging/, commits/, refs/heads/ e o HEAD
    apontando para a branch 'main' (ainda sem commits).
    """
    if _repo_exists():
        return "Repositório já inicializado neste diretório."

    os.makedirs(STAGING_DIR)
    os.makedirs(COMMITS_DIR)
    os.makedirs(REFS_DIR)

    # HEAD aponta para 'main' (branch ainda vazia — sem arquivo de ref)
    _write_head_branch(DEFAULT_BRANCH)

    _write_config({"author": author, "remote": None})

    return (
        f"Repositório inicializado em '{os.path.abspath(MYGIT_DIR)}' "
        f"(autor: {author}, branch: {DEFAULT_BRANCH})"
    )


def add(filepath: str) -> str:
    """
    Adiciona um arquivo à área de stage.

    Copia o arquivo para .mygit/staging/, preservando seu nome.
    """
    _require_repo()

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Arquivo '{filepath}' não encontrado.")

    filename = os.path.basename(filepath)
    dest = os.path.join(STAGING_DIR, filename)
    shutil.copy2(filepath, dest)

    return f"'{filename}' adicionado ao stage."


def commit(message: str) -> str:
    """
    Cria um novo commit com os arquivos atualmente no stage.

    O commit é salvo como JSON em .mygit/commits/ e a branch ativa
    avança para apontar para ele.
    """
    _require_repo()

    staged = _list_staging_files()
    if not staged:
        return "Nada no stage para commitar. Use 'add' primeiro."

    config = _read_config()
    author = config.get("author", "Anônimo")
    parent = _read_head()
    branch = _read_current_branch()

    snapshot: dict[str, str] = {}
    for filename in staged:
        path = os.path.join(STAGING_DIR, filename)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            snapshot[filename] = f.read()

    timestamp = datetime.now().isoformat()
    raw = f"{message}{author}{timestamp}{json.dumps(snapshot)}"
    commit_hash = _generate_hash(raw)

    commit_data = {
        "hash": commit_hash,
        "message": message,
        "author": author,
        "timestamp": timestamp,
        "parent": parent,
        "branch": branch,
        "snapshot": snapshot,
    }

    commit_path = os.path.join(COMMITS_DIR, f"{commit_hash}.json")
    with open(commit_path, "w", encoding="utf-8") as f:
        json.dump(commit_data, f, indent=2, ensure_ascii=False)

    # Avança a branch atual para o novo commit e limpa o stage
    _write_head(commit_hash)
    shutil.rmtree(STAGING_DIR)
    os.makedirs(STAGING_DIR)

    return (
        f"Commit [{commit_hash}] '{message}' criado por {author} "
        f"na branch '{branch}' em {timestamp[:19]}."
    )


def log() -> list[dict]:
    """
    Retorna a lista de commits da branch ativa (mais recente primeiro),
    percorrendo a cadeia de parents a partir do HEAD.
    """
    _require_repo()

    commits = []
    current = _read_head()

    while current:
        data = _load_commit(current)
        commits.append({
            "hash":      data["hash"],
            "message":   data["message"],
            "author":    data["author"],
            "timestamp": data["timestamp"],
            "branch":    data.get("branch", "?"),
        })
        current = data.get("parent")

    return commits


def diff(filename: str) -> str:
    """
    Compara a versão do arquivo no último commit da branch ativa
    com a versão atual em disco.
    """
    _require_repo()

    head = _read_head()
    if not head:
        return "Sem commits ainda — nada para comparar."

    commit_data = _load_commit(head)
    snapshot = commit_data.get("snapshot", {})

    if filename not in snapshot:
        return f"'{filename}' não existe no último commit."

    if not os.path.isfile(filename):
        return f"'{filename}' não existe no diretório de trabalho."

    old_lines = snapshot[filename].splitlines()
    with open(filename, "r", encoding="utf-8", errors="replace") as f:
        new_lines = f.read().splitlines()

    import difflib
    result_lines = []
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in old_lines[i1:i2]:
                result_lines.append(f"  {line}")
        elif tag in ("replace", "delete"):
            for line in old_lines[i1:i2]:
                result_lines.append(f"- {line}")
            if tag == "replace":
                for line in new_lines[j1:j2]:
                    result_lines.append(f"+ {line}")
        elif tag == "insert":
            for line in new_lines[j1:j2]:
                result_lines.append(f"+ {line}")

    if not result_lines:
        return f"'{filename}' não tem diferenças em relação ao último commit."

    header = f"--- último commit [{head}]\n+++ arquivo atual\n"
    return header + "\n".join(result_lines)


def status() -> dict:
    """
    Retorna o status atual do repositório:
    branch ativa, HEAD, arquivos no stage e lista de branches.
    """
    _require_repo()

    staged  = _list_staging_files()
    branch  = _read_current_branch()
    head    = _read_head()
    head_msg = None

    if head:
        try:
            data = _load_commit(head)
            head_msg = data["message"]
        except FileNotFoundError:
            pass

    return {
        "branch":       branch,
        "staged":       staged,
        "head":         head,
        "head_message": head_msg,
        "branches":     _list_branches(),
    }
