#!/usr/bin/env python3
"""
mygit — Um git simplificado para fins didáticos.

Uso:
    python mygit.py init [--author "Nome"]
    python mygit.py add <arquivo|.>
    python mygit.py commit -m "mensagem"
    python mygit.py log
    python mygit.py diff <arquivo>
    python mygit.py status
    python mygit.py remote <caminho>
    python mygit.py push
    python mygit.py pull
    python mygit.py branch [--list | --new <nome> | --checkout <nome>]
    python mygit.py merge <branch>
    python mygit.py gdrive-push
    python mygit.py gdrive-pull
    python mygit.py gdrive-status
    python mygit.py gdrive-setup
    python mygit.py gui
"""

import sys
import argparse
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import repository as repo
from core import remote as rem
from core import branches as br


# ---------------------------------------------------------------------------
# Handlers dos comandos
# ---------------------------------------------------------------------------

def cmd_init(args):
    print(repo.init(author=args.author))


def cmd_add(args):
    try:
        print(repo.add(args.file))
    except FileNotFoundError as e:
        print(f"Erro: {e}")


def cmd_commit(args):
    print(repo.commit(message=args.message))


def cmd_log(args):
    try:
        commits = repo.log()
    except FileNotFoundError as e:
        print(f"Erro: {e}")
        return

    if not commits:
        print("Sem commits ainda.")
        return

    for c in commits:
        branch_tag = f" ({c['branch']})" if c.get("branch") else ""
        print(f"commit {c['hash']}{branch_tag}")
        print(f"Autor:  {c['author']}")
        print(f"Data:   {c['timestamp'][:19]}")
        print(f"\n    {c['message']}\n")
        print("-" * 40)


def cmd_diff(args):
    try:
        print(repo.diff(args.file))
    except FileNotFoundError as e:
        print(f"Erro: {e}")


def cmd_status(args):
    try:
        s = repo.status()
    except FileNotFoundError as e:
        print(f"Erro: {e}")
        return

    print(f"=== Status do repositório (branch: {s['branch']}) ===")
    head_info = f"[{s['head']}] {s['head_message']}" if s["head"] else "sem commits"
    print(f"HEAD: {head_info}")

    other = [b for b in s["branches"] if b != s["branch"]]
    if other:
        print(f"Outras branches: {', '.join(other)}")

    if s["staged"]:
        print("\nArquivos no stage:")
        for f in s["staged"]:
            print(f"  + {f}")
    else:
        print("\nNenhum arquivo no stage.")


def cmd_remote(args):
    try:
        print(rem.set_remote(args.path))
    except FileNotFoundError as e:
        print(f"Erro: {e}")


def cmd_push(args):
    try:
        print(rem.push())
    except (ValueError, FileNotFoundError) as e:
        print(f"Erro: {e}")


def cmd_pull(args):
    try:
        print(rem.pull())
    except (ValueError, FileNotFoundError) as e:
        print(f"Erro: {e}")


def cmd_branch(args):
    try:
        if args.new:
            print(br.branch_create(args.new))
        elif args.checkout:
            print(br.checkout(args.checkout))
        else:
            branches = br.branch_list()
            if not branches:
                print("Nenhuma branch encontrada.")
                return
            for b in branches:
                marker = "* " if b["current"] else "  "
                print(f"{marker}{b['name']}  [{b['head'] or 'vazia'}]")
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Erro: {e}")


def cmd_merge(args):
    try:
        print(br.merge(args.source))
    except (FileNotFoundError, ValueError) as e:
        print(f"Erro: {e}")


def cmd_gdrive_push(args):
    try:
        from core import gdrive
        print(gdrive.gdrive_push())
    except (ImportError, FileNotFoundError, ValueError) as e:
        print(f"Erro: {e}")


def cmd_gdrive_pull(args):
    try:
        from core import gdrive
        target = getattr(args, "hash", None)
        print(gdrive.gdrive_pull(target_hash=target))
    except (ImportError, FileNotFoundError, ValueError) as e:
        print(f"Erro: {e}")


def cmd_gdrive_log(args):
    try:
        from core import gdrive
        commits = gdrive.gdrive_log()
    except (ImportError, FileNotFoundError, ValueError) as e:
        print(f"Erro: {e}")
        return

    if not commits:
        print("Nenhum commit encontrado no Google Drive.")
        return

    print("=== Commits no Google Drive ===\n")
    for c in commits:
        branch_tag = f" ({c['branch']})" if c.get("branch") else ""
        print(f"commit {c['hash']}{branch_tag}")
        print(f"Autor:  {c['author']}")
        print(f"Data:   {c['timestamp'][:19]}")
        print(f"\n    {c['message']}\n")
        print("-" * 40)


def cmd_gdrive_status(args):
    try:
        from core import gdrive
        print(gdrive.gdrive_status())
    except (ImportError, FileNotFoundError, ValueError) as e:
        print(f"Erro: {e}")


def cmd_gdrive_setup(args):
    print("""
╔══════════════════════════════════════════════════════╗
║         Guia de configuração — Google Drive          ║
╚══════════════════════════════════════════════════════╝

PASSO 1 — Instalar as bibliotecas necessárias:
  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

PASSO 2 — Criar o projeto no Google Cloud Console:
  1. Acesse: https://console.cloud.google.com/
  2. Clique em "Novo Projeto" e dê um nome (ex: mygit)
  3. No menu lateral: APIs e Serviços > Biblioteca
  4. Pesquise "Google Drive API" e clique em Ativar

PASSO 3 — Criar as credenciais OAuth:
  1. APIs e Serviços > Credenciais > Criar Credencial
  2. Escolha "ID do cliente OAuth 2.0"
  3. Tipo de aplicativo: "Aplicativo para computador"
  4. Clique em Criar e depois em "Baixar JSON"
  5. Renomeie o arquivo baixado para: credentials.json
  6. Coloque o credentials.json na mesma pasta que o mygit.py

PASSO 4 — Primeiro uso (login):
  Execute qualquer comando gdrive, ex:
    python mygit.py gdrive-push
  O navegador abrirá para você autorizar o acesso.
  Após autorizar, o token é salvo em .mygit/gdrive_token.json
  e você não precisa fazer login novamente.

ESTRUTURA no Drive:
  Meu Drive/
  └── mygit-remote/
      └── <nome-do-seu-projeto>/
          ├── HEAD.txt        ← aponta para o commit mais recente
          └── commits/
              ├── abc12345.json
              └── def67890.json
""")


def cmd_gui(args):
    try:
        from gui import launch_gui
        launch_gui()
    except ImportError as e:
        print(f"Erro ao carregar GUI: {e}")


# ---------------------------------------------------------------------------
# Parser de argumentos
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mygit",
        description="Um git simplificado para fins didáticos.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Inicializa um repositório")
    p_init.add_argument("--author", default="Anônimo", help="Nome do autor")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="Adiciona arquivo(s) ao stage ('.' para todos)")
    p_add.add_argument("file", help="Caminho do arquivo ou '.' para todos")
    p_add.set_defaults(func=cmd_add)

    p_commit = sub.add_parser("commit", help="Cria um commit")
    p_commit.add_argument("-m", dest="message", required=True, help="Mensagem do commit")
    p_commit.set_defaults(func=cmd_commit)

    p_log = sub.add_parser("log", help="Exibe histórico de commits")
    p_log.set_defaults(func=cmd_log)

    p_diff = sub.add_parser("diff", help="Compara arquivo com último commit")
    p_diff.add_argument("file", help="Nome do arquivo")
    p_diff.set_defaults(func=cmd_diff)

    p_status = sub.add_parser("status", help="Exibe status do repositório")
    p_status.set_defaults(func=cmd_status)

    p_remote = sub.add_parser("remote", help="Define o repositório remoto local")
    p_remote.add_argument("path", help="Caminho para a pasta do remoto")
    p_remote.set_defaults(func=cmd_remote)

    p_push = sub.add_parser("push", help="Envia commits para o remoto local")
    p_push.set_defaults(func=cmd_push)

    p_pull = sub.add_parser("pull", help="Baixa commits do remoto local")
    p_pull.set_defaults(func=cmd_pull)

    p_branch = sub.add_parser("branch", help="Gerencia branches")
    p_branch_group = p_branch.add_mutually_exclusive_group()
    p_branch_group.add_argument("--new", metavar="NOME", help="Cria nova branch")
    p_branch_group.add_argument("--checkout", metavar="NOME", help="Troca para a branch")
    p_branch.set_defaults(func=cmd_branch)

    p_merge = sub.add_parser("merge", help="Faz merge de uma branch na atual")
    p_merge.add_argument("source", help="Nome da branch a ser mergeada")
    p_merge.set_defaults(func=cmd_merge)

    p_gp = sub.add_parser("gdrive-push", help="Envia commits para o Google Drive")
    p_gp.set_defaults(func=cmd_gdrive_push)

    p_gpl = sub.add_parser("gdrive-pull", help="Baixa commits do Google Drive")
    p_gpl.add_argument(
        "--hash", metavar="HASH", default=None,
        help="Hash (ou prefixo) do commit específico a restaurar"
    )
    p_gpl.set_defaults(func=cmd_gdrive_pull)

    p_glog = sub.add_parser("gdrive-log", help="Lista commits salvos no Google Drive")
    p_glog.set_defaults(func=cmd_gdrive_log)

    p_gs = sub.add_parser("gdrive-status", help="Mostra sincronização com o Drive")
    p_gs.set_defaults(func=cmd_gdrive_status)

    p_gsetup = sub.add_parser("gdrive-setup", help="Exibe o guia de configuração do Drive")
    p_gsetup.set_defaults(func=cmd_gdrive_setup)

    p_gui = sub.add_parser("gui", help="Abre a interface gráfica")
    p_gui.set_defaults(func=cmd_gui)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
