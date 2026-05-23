"""
gui.py — Interface gráfica do mygit usando Tkinter.

Abas:
  - Repositório  (init, status, log, branch, merge)
  - Arquivos     (add, commit, diff)
  - Remoto       (set remote, push, pull)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import repository as repo
from core import remote as rem
from core import branches as br


# ---------------------------------------------------------------------------
# Tema
# ---------------------------------------------------------------------------
DARK_BG  = "#1e1e2e"
PANEL_BG = "#2a2a3e"
ACCENT   = "#89b4fa"
GREEN    = "#a6e3a1"
RED      = "#f38ba8"
YELLOW   = "#f9e2af"
PURPLE   = "#cba6f7"
TEXT_FG  = "#cdd6f4"
MUTED    = "#6c7086"
FONT_MONO  = ("Courier New", 10)
FONT_UI    = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 12, "bold")


# ---------------------------------------------------------------------------
# Widgets auxiliares
# ---------------------------------------------------------------------------

def _output(widget, text, color=TEXT_FG):
    widget.config(state="normal")
    widget.insert("end", text + "\n", color)
    widget.tag_config(color, foreground=color)
    widget.see("end")
    widget.config(state="disabled")


def _clear(widget):
    widget.config(state="normal")
    widget.delete("1.0", "end")
    widget.config(state="disabled")


def make_output_box(parent, height=12):
    return scrolledtext.ScrolledText(
        parent, height=height,
        bg=DARK_BG, fg=TEXT_FG, font=FONT_MONO,
        insertbackground=TEXT_FG, relief="flat",
        borderwidth=0, state="disabled",
    )


def styled_button(parent, text, command, color=ACCENT):
    return tk.Button(
        parent, text=text, command=command,
        bg=color, fg=DARK_BG, font=FONT_UI,
        relief="flat", padx=12, pady=6, cursor="hand2",
        activebackground=TEXT_FG, activeforeground=DARK_BG,
    )


def styled_entry(parent, width=30):
    return tk.Entry(
        parent, width=width,
        bg=PANEL_BG, fg=TEXT_FG, font=FONT_UI,
        insertbackground=TEXT_FG, relief="flat", borderwidth=4,
    )


def styled_label(parent, text, bold=False):
    return tk.Label(
        parent, text=text, bg=PANEL_BG, fg=TEXT_FG,
        font=FONT_TITLE if bold else FONT_UI,
    )


def section_frame(parent, title):
    return tk.LabelFrame(
        parent, text=f" {title} ", bg=PANEL_BG, fg=ACCENT,
        font=FONT_TITLE, relief="groove", bd=1,
    )


# ---------------------------------------------------------------------------
# Aba 1 — Repositório
# ---------------------------------------------------------------------------

class RepoTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=PANEL_BG)
        self._build()

    def _build(self):
        # Init
        s1 = section_frame(self, "Inicializar repositório")
        s1.pack(fill="x", padx=16, pady=(16, 6))
        row1 = tk.Frame(s1, bg=PANEL_BG)
        row1.pack(padx=10, pady=10, fill="x")
        styled_label(row1, "Autor:").pack(side="left")
        self.author_entry = styled_entry(row1, 22)
        self.author_entry.insert(0, "Anônimo")
        self.author_entry.pack(side="left", padx=(8, 12))
        styled_button(row1, "Init", self._do_init).pack(side="left")

        # Status / Log
        s2 = section_frame(self, "Status & Log")
        s2.pack(fill="x", padx=16, pady=6)
        row2 = tk.Frame(s2, bg=PANEL_BG)
        row2.pack(padx=10, pady=10)
        styled_button(row2, "Status", self._do_status).pack(side="left", padx=4)
        styled_button(row2, "Log", self._do_log).pack(side="left", padx=4)
        styled_button(row2, "Limpar", self._clear_out, color=MUTED).pack(side="left", padx=4)

        # Branch
        s3 = section_frame(self, "Branches")
        s3.pack(fill="x", padx=16, pady=6)
        row3 = tk.Frame(s3, bg=PANEL_BG)
        row3.pack(padx=10, pady=8, fill="x")
        styled_label(row3, "Nome:").pack(side="left")
        self.branch_entry = styled_entry(row3, 18)
        self.branch_entry.pack(side="left", padx=(8, 10))
        styled_button(row3, "Criar branch", self._do_branch_create, color=PURPLE).pack(side="left", padx=4)
        styled_button(row3, "Checkout", self._do_checkout, color=YELLOW).pack(side="left", padx=4)
        styled_button(row3, "Listar", self._do_branch_list).pack(side="left", padx=4)

        # Merge
        s4 = section_frame(self, "Merge")
        s4.pack(fill="x", padx=16, pady=6)
        row4 = tk.Frame(s4, bg=PANEL_BG)
        row4.pack(padx=10, pady=8, fill="x")
        styled_label(row4, "Branch de origem:").pack(side="left")
        self.merge_entry = styled_entry(row4, 18)
        self.merge_entry.pack(side="left", padx=(8, 10))
        styled_button(row4, "Merge ↓", self._do_merge, color=GREEN).pack(side="left", padx=4)

        # Output
        self.out = make_output_box(self, height=10)
        self.out.pack(fill="both", expand=True, padx=16, pady=(4, 16))

    # --- handlers ---

    def _do_init(self):
        author = self.author_entry.get().strip() or "Anônimo"
        _output(self.out, repo.init(author=author), GREEN)

    def _do_status(self):
        _clear(self.out)
        try:
            s = repo.status()
        except FileNotFoundError as e:
            _output(self.out, str(e), RED); return

        _output(self.out, f"Branch ativa: {s['branch']}", ACCENT)
        head = f"[{s['head']}] {s['head_message']}" if s["head"] else "sem commits"
        _output(self.out, f"HEAD: {head}", TEXT_FG)

        _output(self.out, "\nBranches:", YELLOW)
        for b in sorted(s["branches"]):
            marker = "* " if b == s["branch"] else "  "
            _output(self.out, f"  {marker}{b}", TEXT_FG)

        if s["staged"]:
            _output(self.out, "\nStage:", YELLOW)
            for f in s["staged"]:
                _output(self.out, f"  + {f}", GREEN)
        else:
            _output(self.out, "\nStage vazio.", MUTED)

    def _do_log(self):
        _clear(self.out)
        try:
            commits = repo.log()
        except FileNotFoundError as e:
            _output(self.out, str(e), RED); return
        if not commits:
            _output(self.out, "Sem commits ainda.", MUTED); return
        for c in commits:
            _output(self.out, f"commit {c['hash']}  ({c.get('branch','?')})", YELLOW)
            _output(self.out, f"Autor: {c['author']}  |  {c['timestamp'][:19]}", MUTED)
            _output(self.out, f"  {c['message']}", TEXT_FG)
            _output(self.out, "─" * 44, MUTED)

    def _do_branch_create(self):
        name = self.branch_entry.get().strip()
        if not name:
            messagebox.showwarning("mygit", "Informe o nome da branch."); return
        try:
            _output(self.out, br.branch_create(name), GREEN)
        except (FileNotFoundError, ValueError) as e:
            _output(self.out, str(e), RED)

    def _do_checkout(self):
        name = self.branch_entry.get().strip()
        if not name:
            messagebox.showwarning("mygit", "Informe o nome da branch."); return
        try:
            _output(self.out, br.checkout(name), ACCENT)
        except (FileNotFoundError, RuntimeError) as e:
            _output(self.out, str(e), RED)

    def _do_branch_list(self):
        _clear(self.out)
        try:
            branches = br.branch_list()
        except FileNotFoundError as e:
            _output(self.out, str(e), RED); return
        if not branches:
            _output(self.out, "Nenhuma branch.", MUTED); return
        for b in branches:
            marker = "* " if b["current"] else "  "
            _output(self.out, f"{marker}{b['name']}  [{b['head'] or 'vazia'}]",
                    ACCENT if b["current"] else TEXT_FG)

    def _do_merge(self):
        source = self.merge_entry.get().strip()
        if not source:
            messagebox.showwarning("mygit", "Informe a branch de origem."); return
        try:
            result = br.merge(source)
            color = RED if "CONFLITO" in result else GREEN
            _output(self.out, result, color)
        except (FileNotFoundError, ValueError) as e:
            _output(self.out, str(e), RED)

    def _clear_out(self):
        _clear(self.out)


# ---------------------------------------------------------------------------
# Aba 2 — Arquivos
# ---------------------------------------------------------------------------

class FilesTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=PANEL_BG)
        self._build()

    def _build(self):
        # Add
        s1 = section_frame(self, "Add")
        s1.pack(fill="x", padx=16, pady=(16, 6))
        row1 = tk.Frame(s1, bg=PANEL_BG)
        row1.pack(padx=10, pady=10, fill="x")
        self.add_entry = styled_entry(row1, 28)
        self.add_entry.pack(side="left", padx=(0, 8))
        styled_button(row1, "Procurar", self._browse_add).pack(side="left", padx=4)
        styled_button(row1, "Add", self._do_add).pack(side="left", padx=4)

        # Commit
        s2 = section_frame(self, "Commit")
        s2.pack(fill="x", padx=16, pady=6)
        row2 = tk.Frame(s2, bg=PANEL_BG)
        row2.pack(padx=10, pady=10, fill="x")
        styled_label(row2, "Mensagem:").pack(side="left")
        self.msg_entry = styled_entry(row2, 28)
        self.msg_entry.pack(side="left", padx=8)
        styled_button(row2, "Commit", self._do_commit, color=GREEN).pack(side="left")

        # Diff
        s3 = section_frame(self, "Diff")
        s3.pack(fill="x", padx=16, pady=6)
        row3 = tk.Frame(s3, bg=PANEL_BG)
        row3.pack(padx=10, pady=10, fill="x")
        self.diff_entry = styled_entry(row3, 28)
        self.diff_entry.pack(side="left", padx=(0, 8))
        styled_button(row3, "Procurar", self._browse_diff).pack(side="left", padx=4)
        styled_button(row3, "Diff", self._do_diff, color=YELLOW).pack(side="left", padx=4)

        # Output
        self.out = make_output_box(self, height=12)
        self.out.pack(fill="both", expand=True, padx=16, pady=(4, 16))

    def _browse_add(self):
        p = filedialog.askopenfilename()
        if p:
            self.add_entry.delete(0, "end")
            self.add_entry.insert(0, p)

    def _browse_diff(self):
        p = filedialog.askopenfilename()
        if p:
            self.diff_entry.delete(0, "end")
            self.diff_entry.insert(0, os.path.basename(p))

    def _do_add(self):
        path = self.add_entry.get().strip()
        if not path:
            messagebox.showwarning("mygit", "Informe o arquivo."); return
        try:
            _output(self.out, repo.add(path), GREEN)
        except FileNotFoundError as e:
            _output(self.out, str(e), RED)

    def _do_commit(self):
        msg = self.msg_entry.get().strip()
        if not msg:
            messagebox.showwarning("mygit", "Informe a mensagem."); return
        result = repo.commit(msg)
        _output(self.out, result, GREEN if "criado" in result else YELLOW)
        self.msg_entry.delete(0, "end")

    def _do_diff(self):
        _clear(self.out)
        filename = self.diff_entry.get().strip()
        if not filename:
            messagebox.showwarning("mygit", "Informe o arquivo."); return
        try:
            result = repo.diff(filename)
        except FileNotFoundError as e:
            _output(self.out, str(e), RED); return
        for line in result.splitlines():
            color = GREEN if line.startswith("+") else RED if line.startswith("-") else \
                    ACCENT if line.startswith(("@", "=", "-" * 3, "+" * 3)) else MUTED
            _output(self.out, line, color)


# ---------------------------------------------------------------------------
# Aba 3 — Remoto
# ---------------------------------------------------------------------------

class RemoteTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=PANEL_BG)
        self._build()

    def _build(self):
        s1 = section_frame(self, "Configurar remoto")
        s1.pack(fill="x", padx=16, pady=(16, 6))
        row1 = tk.Frame(s1, bg=PANEL_BG)
        row1.pack(padx=10, pady=10, fill="x")
        self.remote_entry = styled_entry(row1, 28)
        self.remote_entry.pack(side="left", padx=(0, 8))
        styled_button(row1, "Procurar pasta", self._browse_remote).pack(side="left", padx=4)
        styled_button(row1, "Set Remote", self._do_set_remote).pack(side="left", padx=4)

        s2 = section_frame(self, "Push & Pull")
        s2.pack(fill="x", padx=16, pady=6)
        row2 = tk.Frame(s2, bg=PANEL_BG)
        row2.pack(padx=10, pady=10)
        styled_button(row2, "Push ↑", self._do_push, color=ACCENT).pack(side="left", padx=8)
        styled_button(row2, "Pull ↓", self._do_pull, color=GREEN).pack(side="left", padx=8)

        self.out = make_output_box(self, height=16)
        self.out.pack(fill="both", expand=True, padx=16, pady=(4, 16))

    def _browse_remote(self):
        p = filedialog.askdirectory()
        if p:
            self.remote_entry.delete(0, "end")
            self.remote_entry.insert(0, p)

    def _do_set_remote(self):
        path = self.remote_entry.get().strip()
        if not path:
            messagebox.showwarning("mygit", "Informe o caminho."); return
        try:
            _output(self.out, rem.set_remote(path), GREEN)
        except FileNotFoundError as e:
            _output(self.out, str(e), RED)

    def _do_push(self):
        try:
            _output(self.out, rem.push(), ACCENT)
        except (ValueError, FileNotFoundError) as e:
            _output(self.out, str(e), RED)

    def _do_pull(self):
        try:
            _output(self.out, rem.pull(), GREEN)
        except (ValueError, FileNotFoundError) as e:
            _output(self.out, str(e), RED)


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------

def launch_gui():
    root = tk.Tk()
    root.title("mygit — Interface Gráfica")
    root.configure(bg=DARK_BG)
    root.geometry("720x620")
    root.resizable(True, True)

    tk.Label(root, text="⬡  mygit", bg=DARK_BG, fg=ACCENT,
             font=("Courier New", 18, "bold"), pady=10).pack(fill="x")
    tk.Label(root, text="Um git simplificado para fins didáticos",
             bg=DARK_BG, fg=MUTED, font=FONT_UI).pack()

    style = ttk.Style()
    style.theme_use("default")
    style.configure("TNotebook", background=DARK_BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=PANEL_BG, foreground=TEXT_FG,
                    font=FONT_UI, padding=[14, 6])
    style.map("TNotebook.Tab",
              background=[("selected", ACCENT)],
              foreground=[("selected", DARK_BG)])

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=12, pady=12)

    nb.add(RepoTab(nb),   text="  Repositório  ")
    nb.add(FilesTab(nb),  text="  Arquivos  ")
    nb.add(RemoteTab(nb), text="  Remoto  ")

    root.mainloop()


if __name__ == "__main__":
    launch_gui()
