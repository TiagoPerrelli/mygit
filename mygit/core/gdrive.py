"""
gdrive.py — Integração do mygit com o Google Drive.

Como funciona:
  - Usa a API oficial do Google Drive via OAuth 2.0
  - Na primeira execução, abre o navegador para você autorizar o acesso
  - O token fica salvo em .mygit/gdrive_token.json (não precisa logar de novo)
  - Os commits ficam numa pasta "mygit-remote/<nome-do-projeto>" no seu Drive

Pré-requisitos (instalar uma vez):
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Configuração (fazer uma vez):
    1. Acesse: https://console.cloud.google.com/
    2. Crie um projeto > APIs e Serviços > Ativar "Google Drive API"
    3. Credenciais > Criar credencial > ID do cliente OAuth 2.0
       Tipo: "Aplicativo para computador"
    4. Baixe o JSON e salve como "credentials.json" na pasta do mygit
    5. Execute: python mygit.py gdrive-setup
"""

import os
import json

# Diretório onde o mygit.py está instalado — funciona independente de onde
# o usuário roda o comando (ex: dentro de C:\Projetos\MeuApp\)
_MYGIT_INSTALL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from core.repository import (
    MYGIT_DIR,
    COMMITS_DIR,
    _require_repo,
    _read_config,
    _write_config,
    _read_head,
    _write_head,
    _load_commit,
)

# Arquivos de autenticação
# credentials.json fica na mesma pasta do mygit.py (instalação),
# não no projeto — assim funciona de qualquer diretório.
CREDENTIALS_FILE = os.path.join(_MYGIT_INSTALL_DIR, "credentials.json")
TOKEN_FILE       = os.path.join(_MYGIT_INSTALL_DIR, "gdrive_token.json")

# Permissão mínima: acesso apenas a arquivos criados por este app
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Pasta raiz no Drive onde os repositórios ficam
DRIVE_ROOT_NAME = "mygit-remote"


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def _get_service():
    """
    Retorna um objeto autenticado da API do Drive.

    - Se já existe token salvo e válido, usa direto.
    - Se o token expirou, tenta renovar automaticamente.
    - Se não há token, abre o navegador para login (primeira vez).
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Bibliotecas do Google não encontradas.\n"
            "Instale com: pip install google-api-python-client "
            "google-auth-httplib2 google-auth-oauthlib"
        )

    creds = None

    # Tenta carregar token existente
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Se não há credenciais válidas, faz o fluxo de login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Arquivo 'credentials.json' não encontrado.\n"
                    f"Coloque-o aqui: {CREDENTIALS_FILE}\n"
                    "Execute 'mygit gdrive-setup' para ver o guia completo."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            # Abre o navegador para o usuário autorizar
            creds = flow.run_local_server(port=0)

        # Salva o token para usos futuros
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Helpers de navegação no Drive
# ---------------------------------------------------------------------------

def _find_or_create_folder(service, name: str, parent_id: str | None = None) -> str:
    """
    Procura uma pasta pelo nome (e parent opcional).
    Cria se não existir. Retorna o ID da pasta.
    """
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files   = results.get("files", [])

    if files:
        return files[0]["id"]

    # Cria a pasta
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]

    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def _get_repo_folder_id(service) -> str:
    """
    Retorna o ID da pasta do repositório atual no Drive.
    Estrutura: mygit-remote/<nome-da-pasta-do-projeto>/commits/

    Cria as pastas se não existirem.
    """
    project_name = os.path.basename(os.path.abspath("."))

    root_id    = _find_or_create_folder(service, DRIVE_ROOT_NAME)
    project_id = _find_or_create_folder(service, project_name, root_id)
    commits_id = _find_or_create_folder(service, "commits", project_id)

    return commits_id, project_id


def _list_remote_commits(service, commits_folder_id: str) -> dict[str, str]:
    """
    Retorna um dicionário {hash: file_id} de todos os commits no Drive.
    """
    results = service.files().list(
        q=f"'{commits_folder_id}' in parents and trashed=false",
        fields="files(id, name)",
    ).execute()

    return {
        f["name"].replace(".json", ""): f["id"]
        for f in results.get("files", [])
    }


def _upload_commit(service, commit_hash: str, commits_folder_id: str):
    """Faz upload de um arquivo de commit local para o Drive."""
    from googleapiclient.http import MediaFileUpload

    local_path = os.path.join(COMMITS_DIR, f"{commit_hash}.json")
    file_meta  = {
        "name":    f"{commit_hash}.json",
        "parents": [commits_folder_id],
    }
    media = MediaFileUpload(local_path, mimetype="application/json")
    service.files().create(body=file_meta, media_body=media, fields="id").execute()


def _download_commit(service, file_id: str, commit_hash: str):
    """Baixa um arquivo de commit do Drive e salva localmente."""
    import io
    from googleapiclient.http import MediaIoBaseDownload

    local_path = os.path.join(COMMITS_DIR, f"{commit_hash}.json")
    request    = service.files().get_media(fileId=file_id)
    fh         = io.FileIO(local_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()


def _read_remote_head(service, project_folder_id: str) -> str | None:
    """Lê o HEAD remoto (arquivo HEAD.txt na pasta do projeto no Drive)."""
    results = service.files().list(
        q=f"name='HEAD.txt' and '{project_folder_id}' in parents and trashed=false",
        fields="files(id)",
    ).execute()
    files = results.get("files", [])
    if not files:
        return None

    import io
    from googleapiclient.http import MediaIoBaseDownload

    fh         = io.BytesIO()
    request    = service.files().get_media(fileId=files[0]["id"])
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue().decode("utf-8").strip() or None


def _write_remote_head(service, project_folder_id: str, commit_hash: str):
    """Atualiza (ou cria) o arquivo HEAD.txt no Drive com o hash atual."""
    import io
    from googleapiclient.http import MediaIoBaseUpload

    # Verifica se já existe para atualizar em vez de criar duplicata
    results = service.files().list(
        q=f"name='HEAD.txt' and '{project_folder_id}' in parents and trashed=false",
        fields="files(id)",
    ).execute()
    files = results.get("files", [])

    content = commit_hash.encode("utf-8")
    media   = MediaIoBaseUpload(io.BytesIO(content), mimetype="text/plain")

    if files:
        service.files().update(fileId=files[0]["id"], media_body=media).execute()
    else:
        meta = {"name": "HEAD.txt", "parents": [project_folder_id]}
        service.files().create(body=meta, media_body=media, fields="id").execute()


# ---------------------------------------------------------------------------
# Comandos públicos
# ---------------------------------------------------------------------------

def gdrive_push() -> str:
    """
    Envia para o Google Drive todos os commits locais que ainda
    não estão na nuvem.

    Compara os commits locais com os que já existem no Drive
    (por nome de arquivo) e faz upload apenas dos novos.
    """
    _require_repo()

    local_head = _read_head()
    if not local_head:
        return "Sem commits locais para enviar."

    service = _get_service()
    commits_folder_id, project_folder_id = _get_repo_folder_id(service)

    remote_commits = _list_remote_commits(service, commits_folder_id)
    remote_head    = _read_remote_head(service, project_folder_id)

    if local_head == remote_head:
        return "Google Drive já está atualizado. Nada para enviar."

    # Coleta commits locais que o Drive não tem
    to_push = []
    current = local_head
    while current and current not in remote_commits:
        data = _load_commit(current)
        to_push.append(current)
        current = data.get("parent")

    if not to_push:
        return "Google Drive já está atualizado. Nada para enviar."

    # Envia do mais antigo para o mais novo
    for commit_hash in reversed(to_push):
        print(f"  Enviando [{commit_hash}]...")
        _upload_commit(service, commit_hash, commits_folder_id)

    _write_remote_head(service, project_folder_id, local_head)

    return (
        f"{len(to_push)} commit(s) enviado(s) para o Google Drive.\n"
        f"Pasta no Drive: {DRIVE_ROOT_NAME}/{os.path.basename(os.path.abspath('.'))}"
    )


def gdrive_pull(target_hash: str | None = None) -> str:
    """
    Baixa commits do Google Drive e restaura os arquivos.

    - Sem argumento: baixa até o commit mais recente do Drive (HEAD).
    - Com target_hash: baixa e restaura um commit específico pelo hash.
      O HEAD local NÃO é atualizado — funciona como um "checkout" de leitura,
      útil para recuperar uma versão anterior sem perder o histórico atual.
    """
    _require_repo()

    service = _get_service()
    commits_folder_id, project_folder_id = _get_repo_folder_id(service)
    remote_commits = _list_remote_commits(service, commits_folder_id)

    if not remote_commits:
        return "Google Drive não tem commits. Nada para baixar."

    # Define qual hash será o alvo do pull
    if target_hash:
        # Suporte a hash parcial: aceita prefixo e encontra o hash completo
        matches = [h for h in remote_commits if h.startswith(target_hash)]
        if not matches:
            available = ", ".join(sorted(remote_commits.keys()))
            return (
                f"Hash '{target_hash}' não encontrado no Drive.\n"
                f"Commits disponíveis: {available}"
            )
        if len(matches) > 1:
            return f"Hash ambíguo '{target_hash}' — corresponde a: {', '.join(matches)}"
        pull_head = matches[0]
        specific  = True
    else:
        pull_head = _read_remote_head(service, project_folder_id)
        if not pull_head:
            return "Google Drive não tem commits. Nada para baixar."
        local_head = _read_head()
        if local_head == pull_head:
            return "Repositório local já está atualizado."
        specific = False

    # Coleta hashes que já existem localmente
    local_set = set()
    if os.path.isdir(COMMITS_DIR):
        local_set = {f.replace(".json", "") for f in os.listdir(COMMITS_DIR)}

    # Baixa a cadeia de commits a partir do alvo até encontrar um já local
    visited = set()
    stack   = [pull_head]
    ordered = []

    while stack:
        h = stack.pop()
        if not h or h in visited or h in local_set:
            break
        visited.add(h)
        if h not in remote_commits:
            raise FileNotFoundError(
                f"Commit '{h}' referenciado no Drive mas arquivo não encontrado."
            )
        print(f"  Baixando [{h}]...")
        _download_commit(service, remote_commits[h], h)
        ordered.append(h)
        data = _load_commit(h)
        stack.append(data.get("parent"))

    # Restaura os arquivos do snapshot do commit alvo
    target_data = _load_commit(pull_head)
    snapshot    = target_data.get("snapshot", {})
    restored    = []
    for filepath, content in snapshot.items():
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        restored.append(filepath)

    if specific:
        # Pull específico: não mexe no HEAD — só restaura os arquivos
        msg = (
            f"Commit [{pull_head}] restaurado (modo leitura).\n"
            f"Mensagem: '{target_data.get('message', '?')}'\n"
            f"Autor:    {target_data.get('author', '?')}  |  {target_data.get('timestamp', '')[:19]}\n"
            f"Arquivos restaurados: {', '.join(restored) or 'nenhum'}.\n"
            f"Nota: HEAD local não foi alterado. Faça commit para salvar mudanças."
        )
    else:
        # Pull normal: atualiza HEAD
        _write_head(pull_head)
        msg = (
            f"{len(ordered)} commit(s) baixado(s) do Google Drive.\n"
            f"Arquivos restaurados: {', '.join(restored) or 'nenhum'}."
        )

    return msg


def gdrive_status() -> str:
    """
    Mostra o estado de sincronização entre o repositório local e o Drive:
    quantos commits locais ainda não foram enviados.
    """
    _require_repo()

    local_head = _read_head()
    if not local_head:
        return "Sem commits locais."

    service = _get_service()
    commits_folder_id, project_folder_id = _get_repo_folder_id(service)
    remote_head = _read_remote_head(service, project_folder_id)

    if local_head == remote_head:
        return f"✓ Sincronizado com o Drive. HEAD: [{local_head}]"

    # Conta quantos commits locais ainda não foram enviados
    pending = 0
    current = local_head
    remote_commits = _list_remote_commits(service, commits_folder_id)
    while current and current not in remote_commits:
        pending += 1
        data    = _load_commit(current)
        current = data.get("parent")

    return (
        f"↑ {pending} commit(s) local(is) ainda não enviado(s) ao Drive.\n"
        f"  Local HEAD:  [{local_head}]\n"
        f"  Drive HEAD:  [{remote_head or 'vazio'}]"
    )


def gdrive_log() -> list[dict]:
    """
    Lista todos os commits salvos no Google Drive em ordem cronológica
    (mais recente primeiro), percorrendo a cadeia de parents a partir
    do HEAD remoto — igual ao 'log' local, mas lendo da nuvem.

    Retorna lista de dicts com: hash, message, author, timestamp, branch.
    """
    _require_repo()

    service = _get_service()
    commits_folder_id, project_folder_id = _get_repo_folder_id(service)

    remote_head = _read_remote_head(service, project_folder_id)
    if not remote_head:
        return []

    remote_commits = _list_remote_commits(service, commits_folder_id)

    # Baixa localmente qualquer commit do Drive que ainda não existe no disco
    # (necessário para ler os parents e montar a cadeia)
    local_set = set()
    if os.path.isdir(COMMITS_DIR):
        local_set = {f.replace(".json", "") for f in os.listdir(COMMITS_DIR)}

    def _ensure_local(h: str):
        if h and h not in local_set and h in remote_commits:
            _download_commit(service, remote_commits[h], h)
            local_set.add(h)

    result  = []
    current = remote_head
    visited = set()

    while current and current not in visited:
        visited.add(current)
        _ensure_local(current)
        try:
            from core.repository import _load_commit
            data = _load_commit(current)
        except FileNotFoundError:
            break

        result.append({
            "hash":      data["hash"],
            "message":   data["message"],
            "author":    data["author"],
            "timestamp": data["timestamp"],
            "branch":    data.get("branch", "?"),
        })
        current = data.get("parent")

    return result
