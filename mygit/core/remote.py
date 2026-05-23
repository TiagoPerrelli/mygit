import os
import json
import shutil

from core.repository import (
    COMMITS_DIR,
    HEAD_FILE,
    CONFIG_FILE,
    _require_repo,
    _read_head,
    _write_head,
    _read_config,
    _write_config,
    _load_commit,
    STAGING_DIR,
)

# ---------------------------------------------------------------------------
# O "remoto" é simplesmente outra pasta no seu sistema de arquivos.
# Ela tem a mesma estrutura de .mygit/: uma pasta commits/ e um arquivo HEAD.
# ---------------------------------------------------------------------------

REMOTE_COMMITS_SUBDIR = "commits"
REMOTE_HEAD_FILE = "HEAD"


def _get_remote_path() -> str:
    """Lê o caminho do remoto a partir da configuração do repositório."""
    config = _read_config()
    remote = config.get("remote")
    if not remote:
        raise ValueError(
            "Nenhum remoto configurado. "
            "Use 'set_remote(<caminho>)' para definir um."
        )
    return remote


def set_remote(remote_path: str) -> str:
    """
    Define (ou atualiza) o caminho do repositório remoto.

    O remoto é criado automaticamente se não existir ainda.
    """
    _require_repo()

    remote_path = os.path.abspath(remote_path)
    commits_dir = os.path.join(remote_path, REMOTE_COMMITS_SUBDIR)
    head_file = os.path.join(remote_path, REMOTE_HEAD_FILE)

    os.makedirs(commits_dir, exist_ok=True)

    # Cria o HEAD do remoto se ainda não existir
    if not os.path.exists(head_file):
        open(head_file, "w", encoding="utf-8").close()

    config = _read_config()
    config["remote"] = remote_path
    _write_config(config)

    return f"Remoto configurado em: {remote_path}"


def push() -> str:
    """
    Envia os commits locais que o remoto ainda não tem.

    Percorre a cadeia de commits a partir do HEAD local e copia
    para o remoto todos os que estiverem faltando.
    """
    _require_repo()
    remote_path = _get_remote_path()

    local_head = _read_head()
    if not local_head:
        return "Sem commits locais para enviar."

    remote_commits_dir = os.path.join(remote_path, REMOTE_COMMITS_SUBDIR)
    remote_head_file = os.path.join(remote_path, REMOTE_HEAD_FILE)

    # Lê o HEAD do remoto
    with open(remote_head_file, "r", encoding="utf-8") as f:
        remote_head = f.read().strip() or None

    if local_head == remote_head:
        return "Remoto já está atualizado. Nada para enviar."

    # Coleta commits locais que o remoto não tem
    # Percorre do HEAD local até encontrar um commit que o remoto já conhece
    to_push = []
    current = local_head

    while current and current != remote_head:
        commit_data = _load_commit(current)
        to_push.append(commit_data)
        current = commit_data.get("parent")

    if not to_push:
        return "Remoto já está atualizado. Nada para enviar."

    # Envia do mais antigo para o mais novo (inverte a lista)
    for commit_data in reversed(to_push):
        dest = os.path.join(remote_commits_dir, f"{commit_data['hash']}.json")
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(commit_data, f, indent=2, ensure_ascii=False)

    # Atualiza o HEAD do remoto
    with open(remote_head_file, "w", encoding="utf-8") as f:
        f.write(local_head)

    count = len(to_push)
    return f"{count} commit(s) enviado(s) para o remoto em '{remote_path}'."


def pull() -> str:
    """
    Baixa os commits do remoto que o repositório local ainda não tem
    e restaura os arquivos do snapshot mais recente no diretório de trabalho.
    """
    _require_repo()
    remote_path = _get_remote_path()

    remote_head_file = os.path.join(remote_path, REMOTE_HEAD_FILE)
    remote_commits_dir = os.path.join(remote_path, REMOTE_COMMITS_SUBDIR)

    with open(remote_head_file, "r", encoding="utf-8") as f:
        remote_head = f.read().strip() or None

    if not remote_head:
        return "Remoto não tem commits. Nada para baixar."

    local_head = _read_head()

    if local_head == remote_head:
        return "Repositório local já está atualizado."

    # Coleta commits do remoto que o local não tem
    to_pull = []
    current = remote_head

    while current and current != local_head:
        commit_file = os.path.join(remote_commits_dir, f"{current}.json")
        if not os.path.exists(commit_file):
            raise FileNotFoundError(
                f"Commit '{current}' não encontrado no remoto. "
                "O histórico pode estar corrompido."
            )
        with open(commit_file, "r", encoding="utf-8") as f:
            commit_data = json.load(f)
        to_pull.append(commit_data)
        current = commit_data.get("parent")

    if not to_pull:
        return "Repositório local já está atualizado."

    # Copia os commits do remoto para o local (do mais antigo para o mais novo)
    for commit_data in reversed(to_pull):
        dest = os.path.join(COMMITS_DIR, f"{commit_data['hash']}.json")
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(commit_data, f, indent=2, ensure_ascii=False)

    # Atualiza o HEAD local
    _write_head(remote_head)

    # Restaura os arquivos do snapshot mais recente no diretório de trabalho
    latest = to_pull[0]  # o primeiro da lista é o mais recente
    snapshot = latest.get("snapshot", {})
    restored = []

    for filename, content in snapshot.items():
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        restored.append(filename)

    count = len(to_pull)
    files_info = ", ".join(restored) if restored else "nenhum arquivo restaurado"
    return (
        f"{count} commit(s) baixado(s) do remoto.\n"
        f"Arquivos restaurados: {files_info}."
    )
