"""
branches.py — Gerenciamento de branches e merge.

Conceitos implementados:

  branch (criar/listar/trocar)
  ─────────────────────────────
  Uma branch é apenas um arquivo em .mygit/refs/heads/<nome>
  cujo conteúdo é o hash do commit mais recente daquela linha.
  Criar uma branch = copiar o hash atual para um novo arquivo de ref.
  Trocar de branch (checkout) = atualizar HEAD + restaurar snapshot.

  merge
  ─────
  Dado que queremos fazer merge da branch B na branch A (ativa):

  1. Encontra o ancestral comum mais recente (LCA) entre A e B
     percorrendo os parents de cada um.

  2. Para cada arquivo que aparece nos snapshots de A e/ou B:
     - só A mudou  → usa A  (já está no working dir)
     - só B mudou  → aplica B
     - ambos mudaram igual → ok
     - ambos mudaram diferente → CONFLITO → aborta e avisa

  3. Se não houver conflitos, cria um commit de merge com os
     arquivos resultantes e dois parents (A e B).
"""

import os
import json

from core.repository import (
    _require_repo,
    _read_current_branch,
    _write_head_branch,
    _read_branch_commit,
    _write_branch_commit,
    _write_head,
    _read_head,
    _load_commit,
    _list_branches,
    _ancestors,
    _generate_hash,
    COMMITS_DIR,
    STAGING_DIR,
    _read_config,
)
from datetime import datetime
import shutil


# ---------------------------------------------------------------------------
# branch
# ---------------------------------------------------------------------------

def branch_create(name: str) -> str:
    """
    Cria uma nova branch apontando para o commit atual (HEAD).

    É como tirar uma 'fotografia' do ponto atual do histórico
    e dar um nome a ela.
    """
    _require_repo()

    if not name.strip():
        raise ValueError("O nome da branch não pode ser vazio.")

    if _read_branch_commit(name) is not None:
        return f"Branch '{name}' já existe."

    head = _read_head()
    if not head:
        raise ValueError(
            "Não é possível criar uma branch sem nenhum commit. "
            "Faça pelo menos um commit primeiro."
        )

    _write_branch_commit(name, head)
    return f"Branch '{name}' criada a partir do commit [{head}]."


def branch_list() -> list[dict]:
    """
    Retorna a lista de branches com indicação de qual é a ativa.
    """
    _require_repo()

    current = _read_current_branch()
    result = []
    for b in sorted(_list_branches()):
        commit_hash = _read_branch_commit(b)
        result.append({
            "name":    b,
            "current": b == current,
            "head":    commit_hash,
        })
    return result


def checkout(name: str) -> str:
    """
    Troca para a branch indicada e restaura os arquivos do snapshot
    mais recente dela no diretório de trabalho.

    Bloqueia a troca se houver arquivos no stage (igual ao git real).
    """
    _require_repo()

    # Não permite trocar com arquivos no stage
    staged = os.listdir(STAGING_DIR) if os.path.isdir(STAGING_DIR) else []
    if staged:
        raise RuntimeError(
            "Há arquivos no stage. Faça commit antes de trocar de branch."
        )

    if _read_branch_commit(name) is None:
        raise FileNotFoundError(f"Branch '{name}' não encontrada.")

    current = _read_current_branch()
    if current == name:
        return f"Você já está na branch '{name}'."

    # Atualiza HEAD para apontar para a nova branch
    _write_head_branch(name)

    # Restaura os arquivos do snapshot do commit mais recente da branch
    commit_hash = _read_branch_commit(name)
    if commit_hash:
        data = _load_commit(commit_hash)
        for filename, content in data.get("snapshot", {}).items():
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

    return f"Mudou para a branch '{name}' [{commit_hash or 'vazia'}]."


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

def _find_lca(hash_a: str | None, hash_b: str | None) -> str | None:
    """
    Encontra o Ancestral Comum mais recente (Lowest Common Ancestor)
    entre dois commits percorrendo seus históricos.

    Estratégia: coleta todos os ancestrais de A num set e depois
    caminha pelos ancestrais de B até encontrar o primeiro que
    esteja no set de A — esse é o LCA.
    """
    ancestors_a = _ancestors(hash_a)

    stack = [hash_b]
    visited = set()
    while stack:
        h = stack.pop()
        if not h or h in visited:
            continue
        if h in ancestors_a:
            return h          # primeiro ancestral comum encontrado
        visited.add(h)
        try:
            data = _load_commit(h)
            stack.append(data.get("parent"))
            # suporte a commits de merge com dois parents
            if data.get("parent2"):
                stack.append(data["parent2"])
        except FileNotFoundError:
            pass
    return None


def _snapshot_of(commit_hash: str | None) -> dict[str, str]:
    """Retorna o snapshot de um commit, ou {} se não houver commit."""
    if not commit_hash:
        return {}
    try:
        return _load_commit(commit_hash).get("snapshot", {})
    except FileNotFoundError:
        return {}


def merge(source_branch: str) -> str:
    """
    Faz merge da branch 'source_branch' na branch ativa.

    Algoritmo de 3 vias (three-way merge):
      - base    = snapshot do ancestral comum
      - ours    = snapshot do HEAD da branch ativa
      - theirs  = snapshot do HEAD da source_branch

    Para cada arquivo:
      • só theirs mudou  → aplica theirs
      • só ours mudou    → mantém ours
      • ambos mudaram igual → ok
      • ambos mudaram diferente → CONFLITO → aborta tudo

    Se passar sem conflitos, cria um commit de merge automático.
    """
    _require_repo()

    current_branch = _read_current_branch()

    if source_branch == current_branch:
        return f"Você já está na branch '{source_branch}'. Nada a fazer."

    if _read_branch_commit(source_branch) is None:
        raise FileNotFoundError(f"Branch '{source_branch}' não encontrada.")

    head_ours   = _read_head()
    head_theirs = _read_branch_commit(source_branch)

    # Fast-forward: se a branch ativa não tem commits, só aponta para theirs
    if not head_ours:
        _write_head(head_theirs)
        return (
            f"Fast-forward: branch '{current_branch}' avançada "
            f"para [{head_theirs}] de '{source_branch}'."
        )

    # Se theirs já está nos ancestrais de ours, não há nada a fazer
    if head_theirs in _ancestors(head_ours):
        return f"Branch '{current_branch}' já contém todos os commits de '{source_branch}'."

    # Encontra o ancestral comum
    lca = _find_lca(head_ours, head_theirs)

    snap_base   = _snapshot_of(lca)
    snap_ours   = _snapshot_of(head_ours)
    snap_theirs = _snapshot_of(head_theirs)

    # Reúne todos os arquivos mencionados em qualquer um dos três snapshots
    all_files = set(snap_base) | set(snap_ours) | set(snap_theirs)

    merged: dict[str, str] = {}
    conflicts: list[str]   = []

    for filename in all_files:
        base   = snap_base.get(filename)
        ours   = snap_ours.get(filename)
        theirs = snap_theirs.get(filename)

        # --- Nenhuma das branches mudou em relação à base ---
        if ours == base and theirs == base:
            if ours is not None:
                merged[filename] = ours
            # arquivo deletado em ambos → não inclui

        # --- Só ours mudou (ou theirs não tocou) ---
        elif theirs == base:
            if ours is not None:
                merged[filename] = ours

        # --- Só theirs mudou (ou ours não tocou) ---
        elif ours == base:
            if theirs is not None:
                merged[filename] = theirs

        # --- Ambos mudaram ---
        else:
            if ours == theirs:
                # Mesma mudança nos dois lados — sem conflito
                if ours is not None:
                    merged[filename] = ours
            else:
                # Mudanças diferentes — CONFLITO
                conflicts.append(filename)

    if conflicts:
        lista = ", ".join(f"'{f}'" for f in conflicts)
        return (
            f"CONFLITO: merge abortado.\n"
            f"Os seguintes arquivos têm alterações conflitantes "
            f"entre '{current_branch}' e '{source_branch}': {lista}.\n"
            f"Resolva manualmente e tente novamente."
        )

    # --- Sem conflitos: cria o commit de merge ---
    config    = _read_config()
    author    = config.get("author", "Anônimo")
    timestamp = datetime.now().isoformat()
    message   = f"Merge branch '{source_branch}' into '{current_branch}'"
    raw       = f"{message}{author}{timestamp}{json.dumps(merged)}"
    commit_hash = _generate_hash(raw)

    commit_data = {
        "hash":      commit_hash,
        "message":   message,
        "author":    author,
        "timestamp": timestamp,
        "parent":    head_ours,    # parent principal = branch ativa
        "parent2":   head_theirs,  # segundo parent = branch mergeada
        "branch":    current_branch,
        "snapshot":  merged,
    }

    commit_path = os.path.join(COMMITS_DIR, f"{commit_hash}.json")
    with open(commit_path, "w", encoding="utf-8") as f:
        json.dump(commit_data, f, indent=2, ensure_ascii=False)

    # Avança a branch ativa para o commit de merge
    _write_branch_commit(current_branch, commit_hash)

    # Restaura os arquivos merged no diretório de trabalho
    for filename, content in merged.items():
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

    return (
        f"Merge concluído! Commit [{commit_hash}] criado.\n"
        f"'{source_branch}' → '{current_branch}' "
        f"({len(merged)} arquivo(s) no resultado)."
    )
