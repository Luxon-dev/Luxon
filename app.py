# -*- coding: utf-8 -*-
"""
LuXon | Centro de administración
Administra productos, destacados, imágenes y banners directamente en index.html.
Mantiene la publicación automática en GitHub Pages.
No requiere dependencias externas: utiliza Python estándar + Tkinter.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import subprocess
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "index.html"
DEV_PASSWORD = os.environ.get("LUXON_DEV_PASSWORD", "luxon2026")
GITHUB_REMOTE = "origin"
GITHUB_BRANCH = "main"

BG = "#F5F1EB"
PANEL = "#FFFFFF"
DARK = "#202020"
GOLD = "#B8954B"
MUTED = "#77716A"
GREEN = "#2D7652"
RED = "#A9473F"


def read_html() -> str:
    if not HTML_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró {HTML_FILE.name}.\n"
            "Colocá app.py e index.html dentro de la misma carpeta."
        )
    return HTML_FILE.read_text(encoding="utf-8")


def find_products_array(source: str) -> tuple[str, int, int]:
    """Localiza const products=[...] respetando corchetes dentro de strings."""
    match = re.search(r"\bconst\s+products\s*=\s*", source)
    if not match:
        raise ValueError("No se encontró 'const products = [...]' en index.html.")

    start = match.end()
    while start < len(source) and source[start].isspace():
        start += 1
    if start >= len(source) or source[start] != "[":
        raise ValueError("La declaración de productos no contiene un arreglo válido.")

    depth = 0
    quote = None
    escaped = False
    for pos in range(start, len(source)):
        char = source[pos]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"', "`"):
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return source[start:pos + 1], start, pos + 1

    raise ValueError("El arreglo de productos está incompleto o tiene corchetes sin cerrar.")


def remove_trailing_commas(raw: str) -> str:
    result = []
    in_string = False
    escaped = False
    for index, char in enumerate(raw):
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            result.append(char)
        elif char == ",":
            look = index + 1
            while look < len(raw) and raw[look].isspace():
                look += 1
            if look < len(raw) and raw[look] in "}]":
                continue
            result.append(char)
        else:
            result.append(char)
    return "".join(result)


def load_catalog() -> tuple[str, list[dict[str, Any]], int, int]:
    source = read_html()
    raw, start, end = find_products_array(source)
    products = json.loads(remove_trailing_commas(raw))
    if not isinstance(products, list):
        raise ValueError("El catálogo no es una lista de productos.")

    for product in products:
        product.setdefault("featured", False)
        product.setdefault("active", True)
        product.setdefault("variants", ["Único"])
        product.setdefault("images", [])
        product.setdefault("description", "")
        product.setdefault("badge", "Selección LuXon")
        product.setdefault("category", "Otros")
        product.setdefault("numericPrice", 0)
        product.setdefault("price", "$0")
    return source, products, start, end


def format_price(value: int) -> str:
    return "$" + f"{max(0, int(value)):,}".replace(",", ".")


def parse_price(value: str) -> int:
    digits = re.sub(r"[^\d]", "", value or "")
    return int(digits or 0)


def next_product_id(products: list[dict[str, Any]]) -> str:
    highest = 0
    for product in products:
        found = re.search(r"LUX-(\d+)", str(product.get("id", "")), re.I)
        if found:
            highest = max(highest, int(found.group(1)))
    return f"LUX-{highest + 1:03d}"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="luxon_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def save_catalog(products: list[dict[str, Any]]) -> None:
    source, _, start, end = load_catalog()
    block = json.dumps(products, ensure_ascii=False, indent=8)
    updated = source[:start] + block + source[end:]
    atomic_write(HTML_FILE, updated)


def git_command(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )


def publish_to_github() -> tuple[bool, str]:
    """Publica el catálogo sin descartar cambios locales ajenos al catálogo."""
    stash_created = False
    stash_ref_before = ""
    result_message = ""
    success = False

    try:
        check = git_command(["rev-parse", "--is-inside-work-tree"])
        if check.returncode != 0:
            return False, "La carpeta no parece ser un repositorio Git.\n" + (check.stderr or check.stdout)

        project_files = [
            "index.html", "app.py", "worker.js", "wrangler.toml",
            "README_LUXON_2.txt", ".gitignore"
        ]
        existing_files = [name for name in project_files if (BASE_DIR / name).exists()]
        if not existing_files:
            return False, "No se encontraron archivos del proyecto para publicar."

        # Comprueba cambios de los archivos del proyecto respecto del último commit.
        # --only evita incluir accidentalmente otros archivos que el usuario ya
        # tuviera preparados (staged) en el repositorio.
        changed = git_command(["diff", "HEAD", "--quiet", "--", *existing_files])
        if changed.returncode not in (0, 1):
            return False, "No se pudo comprobar el estado de los archivos.\n" + (changed.stderr or changed.stdout)

        if changed.returncode == 1:
            commit = git_command([
                "commit", "--only", "-m", "Actualizacion de catalogo LuXon",
                "--", *existing_files
            ])
            if commit.returncode != 0:
                return False, "No se pudo guardar el commit del catálogo.\n\n" + (commit.stderr or commit.stdout)

        branch_result = git_command(["branch", "--show-current"])
        branch = (branch_result.stdout or "").strip() or GITHUB_BRANCH

        # Después de guardar el catálogo, aparta temporalmente cualquier otro
        # cambio pendiente (incluidos archivos no rastreados) para que rebase
        # no se bloquee por modificaciones ajenas al catálogo.
        status = git_command(["status", "--porcelain"])
        if status.returncode != 0:
            return False, "No se pudo revisar el estado del repositorio.\n" + (status.stderr or status.stdout)

        if status.stdout.strip():
            before = git_command(["rev-parse", "-q", "--verify", "refs/stash"])
            stash_ref_before = before.stdout.strip() if before.returncode == 0 else ""
            stash = git_command([
                "stash", "push", "--include-untracked",
                "-m", "LuXon: cambios locales protegidos antes de publicar"
            ])
            if stash.returncode != 0:
                return False, "No se pudieron proteger temporalmente los otros cambios locales.\n\n" + (stash.stderr or stash.stdout)
            after = git_command(["rev-parse", "-q", "--verify", "refs/stash"])
            stash_ref_after = after.stdout.strip() if after.returncode == 0 else ""
            stash_created = bool(stash_ref_after and stash_ref_after != stash_ref_before)

        fetch = git_command(["fetch", GITHUB_REMOTE, branch])
        if fetch.returncode != 0:
            result_message = "Los cambios quedaron guardados localmente, pero no se pudo consultar GitHub.\n\n" + (fetch.stderr or fetch.stdout)
        else:
            rebase = git_command(["rebase", f"{GITHUB_REMOTE}/{branch}"])
            if rebase.returncode != 0:
                details = (rebase.stderr or rebase.stdout).strip()
                git_command(["rebase", "--abort"])
                result_message = (
                    "GitHub tiene cambios que entran en conflicto con los archivos locales.\n"
                    "Tus cambios siguen guardados; no se sobrescribió GitHub.\n\n"
                    "Detalle del conflicto:\n" + details
                )
            else:
                push = git_command(["push", GITHUB_REMOTE, branch])
                if push.returncode == 0:
                    success = True
                    result_message = (
                        "¡Publicación completada!\n"
                        "Los cambios del catálogo se sincronizaron con GitHub. "
                        "GitHub Pages actualizará la tienda en unos instantes."
                    )
                else:
                    result_message = (
                        "Los cambios siguen guardados localmente, pero GitHub no confirmó el envío.\n\n"
                        + (push.stderr or push.stdout)
                    )

        # Restaura siempre los cambios que se apartaron. Si hay un conflicto al
        # restaurarlos, Git conserva la entrada del stash para recuperación.
        if stash_created:
            restore = git_command(["stash", "pop", "--index"])
            if restore.returncode != 0:
                restore_detail = (restore.stderr or restore.stdout).strip()
                result_message += (
                    "\n\nATENCIÓN: la publicación terminó, pero algunos cambios locales apartados "
                    "no pudieron restaurarse automáticamente. No se eliminaron: quedaron guardados "
                    "en el stash de Git. Detalle:\n" + restore_detail
                )
                success = False

        return success, result_message

    except FileNotFoundError:
        return False, "No se encontró Git. Instalá Git for Windows y volvé a intentarlo."
    except subprocess.TimeoutExpired:
        return False, "Git tardó demasiado en responder. Revisá la conexión e intentá nuevamente."
    except Exception as exc:
        # No se intenta borrar ni resetear ningún cambio ante un error inesperado.
        if stash_created:
            restore = git_command(["stash", "pop", "--index"])
            if restore.returncode != 0:
                return False, f"Error al publicar: {exc}\nLos cambios adicionales siguen protegidos en el stash de Git."
        return False, f"Error al publicar: {exc}"


def image_to_data_uri(file_path: str) -> str:
    extension = Path(file_path).suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(extension)
    if not mime:
        raise ValueError("Formato no admitido. Usá JPG, PNG, WEBP o GIF.")
    data = Path(file_path).read_bytes()
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def replace_element_text(source: str, element_id: str, value: str) -> str:
    safe = html.escape(value, quote=False)
    pattern = re.compile(
        rf'(<(?:h1|h2|p|span)[^>]*\bid="{re.escape(element_id)}"[^>]*>).*?(</(?:h1|h2|p|span)>)',
        re.DOTALL,
    )
    updated, count = pattern.subn(lambda m: m.group(1) + safe + m.group(2), source, count=1)
    if not count:
        raise ValueError(f"No se encontró el elemento {element_id} en index.html.")
    return updated


def replace_image_by_id(source: str, element_id: str, data_uri: str) -> str:
    pattern = re.compile(rf'<img\b(?=[^>]*\bid="{re.escape(element_id)}")[^>]*>', re.DOTALL)
    match = pattern.search(source)
    if not match:
        raise ValueError(f"No se encontró la imagen {element_id} en index.html.")
    tag = match.group(0)
    if re.search(r'\bsrc="[^"]*"', tag):
        tag = re.sub(r'\bsrc="[^"]*"', lambda _: 'src="' + data_uri + '"', tag, count=1)
    else:
        tag = tag[:-1] + ' src="' + data_uri + '">'
    return source[:match.start()] + tag + source[match.end():]


class ProductDialog(tk.Toplevel):
    def __init__(self, parent, product: dict[str, Any] | None = None, product_id: str = ""):
        super().__init__(parent)
        self.parent = parent
        self.original = product
        self.product_id = product_id or (product or {}).get("id", "")
        self.images = list((product or {}).get("images", []))
        self.result = None

        self.title("Editar producto" if product else "Nuevo producto")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        data = product or {}
        self.vars = {
            "title": tk.StringVar(value=data.get("title", "")),
            "category": tk.StringVar(value=data.get("category", "cuidado")),
            "price": tk.StringVar(value=str(data.get("numericPrice", 0) or "")),
            "badge": tk.StringVar(value=data.get("badge", "Exclusivo")),
            "variants": tk.StringVar(value=", ".join(data.get("variants", []))),
            "featured": tk.BooleanVar(value=bool(data.get("featured", False))),
            "active": tk.BooleanVar(value=data.get("active", True)),
        }

        self._build()
        self.geometry("650x690")
        self.wait_visibility()
        self.focus_force()

    def _build(self):
        header = tk.Frame(self, bg=DARK, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(header, text="LUXON  /  CATÁLOGO", bg=DARK, fg=GOLD,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(header, text="Datos del producto", bg=DARK, fg="white",
                 font=("Georgia", 20)).pack(anchor="w", pady=(5, 0))

        body = tk.Frame(self, bg=BG, padx=25, pady=18)
        body.pack(fill="both", expand=True)

        def field(label, key, row, width=52):
            tk.Label(body, text=label.upper(), bg=BG, fg=MUTED,
                     font=("Segoe UI", 8, "bold")).grid(row=row, column=0, sticky="w", pady=(9, 4))
            entry = ttk.Entry(body, textvariable=self.vars[key], width=width)
            entry.grid(row=row + 1, column=0, sticky="ew", ipady=6)
            return entry

        field("Nombre", "title", 0)
        tk.Label(body, text="CATEGORÍA", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=2, column=0, sticky="w", pady=(9, 4))
        categories = ["accesorios", "cuidado", "cuidado personal", "hogar", "hogar y decoración", "otros"]
        self.category_box = ttk.Combobox(body, textvariable=self.vars["category"], values=categories)
        self.category_box.grid(row=3, column=0, sticky="ew", ipady=4)

        field("Precio (ejemplo: 55000)", "price", 4)
        field("Etiqueta (Nuevo, Exclusivo, Más vendido…)", "badge", 6)
        field("Variantes separadas por coma", "variants", 8)

        tk.Label(body, text="DESCRIPCIÓN", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=10, column=0, sticky="w", pady=(9, 4))
        self.description = tk.Text(body, height=4, wrap="word", font=("Segoe UI", 9),
                                   relief="flat", bg="white", padx=10, pady=8)
        self.description.grid(row=11, column=0, sticky="ew")
        self.description.insert("1.0", (self.original or {}).get("description", ""))

        checks = tk.Frame(body, bg=BG)
        checks.grid(row=12, column=0, sticky="w", pady=12)
        ttk.Checkbutton(checks, text="Mostrar en destacados", variable=self.vars["featured"]).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(checks, text="Producto activo", variable=self.vars["active"]).pack(side="left")

        image_row = tk.Frame(body, bg=BG)
        image_row.grid(row=13, column=0, sticky="ew", pady=(2, 8))
        self.image_label = tk.Label(image_row, text=f"{len(self.images)} imagen(es) cargada(s)",
                                    bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.image_label.pack(side="left")
        ttk.Button(image_row, text="Seleccionar imágenes", command=self.choose_images).pack(side="right")
        ttk.Button(image_row, text="Quitar imágenes", command=self.clear_images).pack(side="right", padx=8)

        actions = tk.Frame(body, bg=BG)
        actions.grid(row=14, column=0, sticky="ew", pady=(16, 0))
        ttk.Button(actions, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(actions, text="Guardar producto", command=self.save).pack(side="right", padx=8)
        body.columnconfigure(0, weight=1)

    def choose_images(self):
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Seleccionar imágenes del producto",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp *.gif")],
        )
        if not paths:
            return
        try:
            self.images = [image_to_data_uri(path) for path in paths]
            self.image_label.config(text=f"{len(self.images)} imagen(es) seleccionada(s)")
        except Exception as exc:
            messagebox.showerror("Imágenes", str(exc), parent=self)

    def clear_images(self):
        if messagebox.askyesno("Confirmar", "¿Quitar todas las imágenes de este producto?", parent=self):
            self.images = []
            self.image_label.config(text="Sin imágenes")

    def save(self):
        title = self.vars["title"].get().strip()
        if not title:
            messagebox.showwarning("Falta información", "El nombre del producto es obligatorio.", parent=self)
            return
        try:
            price = parse_price(self.vars["price"].get())
        except ValueError:
            messagebox.showwarning("Precio inválido", "Ingresá un precio numérico.", parent=self)
            return

        variants = [item.strip() for item in self.vars["variants"].get().split(",") if item.strip()]
        if not variants:
            variants = ["Único"]

        self.result = {
            "id": self.product_id,
            "title": title,
            "category": self.vars["category"].get().strip().lower() or "otros",
            "price": format_price(price),
            "numericPrice": price,
            "badge": self.vars["badge"].get().strip() or "Selección LuXon",
            "badgeColor": "bg-gold-400 text-charcoal",
            "variants": variants,
            "images": self.images or ["https://placehold.co/600x700/EAE0D5/222222?text=LuXon"],
            "description": self.description.get("1.0", "end").strip(),
            "featured": bool(self.vars["featured"].get()),
            "active": bool(self.vars["active"].get()),
        }
        self.destroy()


class LuxonAdmin(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LuXon | Centro de Administración")
        self.geometry("1180x790")
        self.minsize(980, 680)
        self.configure(bg=BG)
        self.products: list[dict[str, Any]] = []
        self.auto_publish = tk.BooleanVar(value=True)
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Conectado al catálogo local")
        self._style()
        self._login()
        self._build_shell()
        self.reload_catalog()

    def _style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", background="white", fieldbackground="white",
                        foreground=DARK, rowheight=34, font=("Segoe UI", 9), borderwidth=0)
        style.configure("Treeview.Heading", background="#EAE3D9", foreground=DARK,
                        font=("Segoe UI", 8, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", "#E9D9B9")], foreground=[("selected", DARK)])
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=(12, 8))
        style.configure("TEntry", padding=7)
        style.configure("TCombobox", padding=6)
        style.configure("TCheckbutton", background=BG, font=("Segoe UI", 9))

    def _login(self):
        password = simpledialog.askstring(
            "Acceso de desarrollador",
            "Ingresá la clave para administrar LuXon:",
            show="•",
            parent=self,
        )
        if password != DEV_PASSWORD:
            messagebox.showerror("Acceso denegado", "La clave es incorrecta. La aplicación se cerrará.", parent=self)
            self.destroy()
            raise SystemExit(0)

    def _build_shell(self):
        sidebar = tk.Frame(self, bg=DARK, width=225)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg=DARK, padx=22, pady=25)
        brand.pack(fill="x")
        tk.Label(brand, text="LUXON", bg=DARK, fg="#E4C77F",
                 font=("Georgia", 25, "bold")).pack(anchor="w")
        tk.Label(brand, text="CENTRO DE ADMINISTRACIÓN", bg=DARK, fg="#B7B0A5",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(3, 0))
        tk.Frame(sidebar, bg="#4C463C", height=1).pack(fill="x", padx=18, pady=(5, 18))

        for label, command in [
            ("◈  Resumen", self.show_dashboard),
            ("▦  Productos", self.show_products),
            ("✧  Banners y portada", self.show_banners),
            ("✦  Asistente IA", self.show_chatbot_settings),
        ]:
            button = tk.Button(sidebar, text=label, command=command, anchor="w",
                               bg=DARK, fg="#EDE8DF", activebackground="#3B3832",
                               activeforeground="#E4C77F", relief="flat", bd=0,
                               padx=24, pady=13, font=("Segoe UI", 10, "bold"),
                               cursor="hand2")
            button.pack(fill="x")

        tk.Frame(sidebar, bg="#4C463C", height=1).pack(fill="x", padx=18, pady=18)
        ttk.Checkbutton(sidebar, text="Publicar automáticamente", variable=self.auto_publish).pack(
            anchor="w", padx=20, pady=5
        )
        tk.Label(sidebar, text="Los cambios se guardan\nen index.html y se envían\na GitHub Pages.",
                 bg=DARK, fg="#AAA39A", justify="left",
                 font=("Segoe UI", 8), padx=22).pack(anchor="w", pady=(8, 0))
        tk.Button(sidebar, text="↥  Publicar ahora", command=self.publish,
                  bg="#B8954B", fg="#202020", activebackground="#D2B46E",
                  relief="flat", bd=0, padx=14, pady=11,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(
                      side="bottom", fill="x", padx=16, pady=18
                  )

        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        header = tk.Frame(main, bg=PANEL, padx=28, pady=19)
        header.pack(fill="x")
        self.page_title = tk.Label(header, text="Resumen general", bg=PANEL, fg=DARK,
                                   font=("Georgia", 22))
        self.page_title.pack(anchor="w")
        self.page_subtitle = tk.Label(header, text="Administrá tu tienda y publicá los cambios.",
                                      bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.page_subtitle.pack(anchor="w", pady=(4, 0))
        self.content = tk.Frame(main, bg=BG, padx=25, pady=22)
        self.content.pack(fill="both", expand=True)
        footer = tk.Frame(main, bg="#EAE3D9", padx=22, pady=8)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, textvariable=self.status_var, bg="#EAE3D9", fg="#625D55",
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(footer, text="LuXon Admin  •  GitHub Pages", bg="#EAE3D9", fg="#81796F",
                 font=("Segoe UI", 8)).pack(side="right")
        self.show_dashboard()

    def set_page(self, title: str, subtitle: str):
        self.page_title.config(text=title)
        self.page_subtitle.config(text=subtitle)
        for child in self.content.winfo_children():
            child.destroy()

    def reload_catalog(self):
        try:
            _, self.products, _, _ = load_catalog()
            self.status_var.set(f"Catálogo cargado · {len(self.products)} productos")
            if hasattr(self, "tree"):
                self.refresh_tree()
        except Exception as exc:
            messagebox.showerror("Error al cargar catálogo", str(exc), parent=self)

    def persist(self, message="Cambios guardados"):
        try:
            save_catalog(self.products)
            self.status_var.set(message + " · index.html actualizado")
            if self.auto_publish.get():
                ok, detail = publish_to_github()
                self.status_var.set("Publicado en GitHub" if ok else "Guardado localmente · revisar GitHub")
                if ok:
                    messagebox.showinfo("LuXon", detail, parent=self)
                else:
                    messagebox.showwarning("Publicación pendiente", detail, parent=self)
            else:
                messagebox.showinfo("Guardado", "Los cambios quedaron guardados en index.html.\nLa publicación automática está desactivada.", parent=self)
            self.reload_catalog()
            self.show_products()
        except Exception as exc:
            messagebox.showerror("No se pudo guardar", str(exc), parent=self)

    def publish(self):
        try:
            # Asegura que el HTML tenga los datos que se ven en pantalla.
            save_catalog(self.products)
            ok, detail = publish_to_github()
            self.status_var.set("GitHub actualizado" if ok else "Publicación pendiente")
            (messagebox.showinfo if ok else messagebox.showwarning)("Publicación GitHub", detail, parent=self)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    def show_dashboard(self):
        self.set_page("Resumen general", "Estado de tu catálogo LuXon y accesos rápidos.")
        active = [p for p in self.products if p.get("active", True)]
        featured = [p for p in active if p.get("featured")]
        cards = tk.Frame(self.content, bg=BG)
        cards.pack(fill="x")
        for title, value, note in [
            ("PRODUCTOS TOTALES", len(self.products), "Inventario cargado"),
            ("PRODUCTOS ACTIVOS", len(active), "Visibles en el catálogo"),
            ("DESTACADOS", len(featured), "Aparecen en el carrusel principal"),
        ]:
            card = tk.Frame(cards, bg=PANEL, padx=20, pady=18, highlightbackground="#E7DED2", highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 12))
            tk.Label(card, text=title, bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(card, text=str(value), bg=PANEL, fg=DARK, font=("Georgia", 29)).pack(anchor="w", pady=5)
            tk.Label(card, text=note, bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")

        section = tk.Frame(self.content, bg=PANEL, padx=22, pady=20)
        section.pack(fill="both", expand=True, pady=(18, 0))
        tk.Label(section, text="Administración de la tienda", bg=PANEL, fg=DARK,
                 font=("Georgia", 17)).pack(anchor="w")
        tk.Label(section, text="Gestioná el catálogo, elegí qué productos destacar y mantené la portada actualizada.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(5, 18))
        actions = tk.Frame(section, bg=PANEL)
        actions.pack(anchor="w")
        ttk.Button(actions, text="Administrar productos", command=self.show_products).pack(side="left", padx=(0, 10))
        ttk.Button(actions, text="Editar portada y banners", command=self.show_banners).pack(side="left")
        tk.Label(section, text="Flujo de publicación", bg=PANEL, fg=DARK,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(28, 7))
        for line in ["1. Editás los datos o las imágenes desde esta aplicación.",
                     "2. El sistema actualiza el arreglo de productos dentro de index.html.",
                     "3. Si la publicación automática está activa, crea el commit y ejecuta git push.",
                     "4. GitHub Pages publica la nueva versión de la tienda."]:
            tk.Label(section, text=line, bg=PANEL, fg="#5F5A52",
                     font=("Segoe UI", 9)).pack(anchor="w", pady=3)

    def show_products(self):
        self.set_page("Productos", "Agregá, editá, ocultá y seleccioná los productos que aparecerán como destacados.")
        toolbar = tk.Frame(self.content, bg=BG)
        toolbar.pack(fill="x", pady=(0, 14))
        ttk.Entry(toolbar, textvariable=self.search_var, width=30).pack(side="left", ipady=4)
        self.search_var.trace_add("write", lambda *_: self.refresh_tree())
        ttk.Button(toolbar, text="+ Nuevo producto", command=self.add_product).pack(side="right")
        ttk.Button(toolbar, text="Editar seleccionado", command=self.edit_selected).pack(side="right", padx=8)
        ttk.Button(toolbar, text="Eliminar", command=self.delete_selected).pack(side="right", padx=8)

        table_frame = tk.Frame(self.content, bg=PANEL, padx=8, pady=8)
        table_frame.pack(fill="both", expand=True)
        columns = ("id", "title", "category", "price", "featured", "active")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        settings = [
            ("id", "Código", 90), ("title", "Producto", 270), ("category", "Categoría", 130),
            ("price", "Precio", 100), ("featured", "Destacado", 90), ("active", "Estado", 90),
        ]
        for key, label, width in settings:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w" if key in ("title", "category") else "center")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _: self.edit_selected())

        bottom = tk.Frame(self.content, bg=BG)
        bottom.pack(fill="x", pady=(12, 0))
        ttk.Button(bottom, text="Marcar / quitar destacado", command=self.toggle_featured).pack(side="left")
        ttk.Button(bottom, text="Activar / desactivar", command=self.toggle_active).pack(side="left", padx=8)
        tk.Label(bottom, text="Los destacados se muestran en el carrusel principal de la web.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="right")
        self.refresh_tree()

    def refresh_tree(self):
        if not hasattr(self, "tree") or not self.tree.winfo_exists():
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        query = self.search_var.get().strip().lower()
        for product in self.products:
            searchable = " ".join(str(product.get(k, "")) for k in ("id", "title", "category")).lower()
            if query and query not in searchable:
                continue
            self.tree.insert("", "end", iid=product["id"], values=(
                product.get("id", ""),
                product.get("title", ""),
                product.get("category", ""),
                product.get("price", ""),
                "Sí" if product.get("featured") else "No",
                "Activo" if product.get("active", True) else "Oculto",
            ))

    def selected_product(self):
        if not hasattr(self, "tree"):
            return None
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Seleccioná un producto", "Elegí un producto de la lista.", parent=self)
            return None
        product_id = selection[0]
        return next((p for p in self.products if p.get("id") == product_id), None)

    def add_product(self):
        product_id = next_product_id(self.products)
        dialog = ProductDialog(self, product_id=product_id)
        self.wait_window(dialog)
        if dialog.result:
            self.products.append(dialog.result)
            self.persist("Producto agregado")

    def edit_selected(self):
        product = self.selected_product()
        if not product:
            return
        dialog = ProductDialog(self, product=product, product_id=product["id"])
        self.wait_window(dialog)
        if dialog.result:
            index = self.products.index(product)
            self.products[index] = dialog.result
            self.persist("Producto actualizado")

    def delete_selected(self):
        product = self.selected_product()
        if not product:
            return
        if not messagebox.askyesno("Eliminar producto",
                                   f"¿Eliminar {product.get('title')} ({product.get('id')})?",
                                   parent=self):
            return
        self.products.remove(product)
        self.persist("Producto eliminado")

    def toggle_featured(self):
        product = self.selected_product()
        if not product:
            return
        product["featured"] = not bool(product.get("featured"))
        self.persist("Selección de destacados actualizada")

    def toggle_active(self):
        product = self.selected_product()
        if not product:
            return
        product["active"] = not bool(product.get("active", True))
        self.persist("Estado del producto actualizado")

    def show_banners(self):
        self.set_page("Portada y banners", "Editá los textos principales y las imágenes del carrusel de inicio.")
        try:
            source = read_html()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return

        wrapper = tk.Frame(self.content, bg=PANEL, padx=24, pady=22)
        wrapper.pack(fill="both", expand=True)
        tk.Label(wrapper, text="Carrusel principal", bg=PANEL, fg=DARK,
                 font=("Georgia", 18)).pack(anchor="w")
        tk.Label(wrapper, text="Los textos e imágenes se reemplazan directamente en index.html.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 16))

        ids = [
            ("Título del banner 1", "hero-title-1"),
            ("Subtítulo del banner 1", "hero-subtitle-1"),
            ("Título del banner 2", "hero-title-2"),
            ("Subtítulo del banner 2", "hero-subtitle-2"),
        ]
        self.banner_vars = {}
        for label, element_id in ids:
            tk.Label(wrapper, text=label.upper(), bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 4))
            var = tk.StringVar(value=self._extract_text(source, element_id))
            ttk.Entry(wrapper, textvariable=var).pack(fill="x", ipady=6)
            self.banner_vars[element_id] = var

        image_row = tk.Frame(wrapper, bg=PANEL)
        image_row.pack(fill="x", pady=20)
        ttk.Button(image_row, text="Cambiar imagen banner 1", command=lambda: self.change_banner_image("hero-image-1")).pack(side="left")
        ttk.Button(image_row, text="Cambiar imagen banner 2", command=lambda: self.change_banner_image("hero-image-2")).pack(side="left", padx=10)
        ttk.Button(wrapper, text="Guardar portada y publicar", command=self.save_banners).pack(anchor="e", pady=(12, 0))


    def show_chatbot_settings(self):
        self.set_page("Asistente IA", "Conectá el asesor virtual con el servicio seguro de IA y publicá la configuración.")
        wrapper = tk.Frame(self.content, bg=PANEL, padx=24, pady=22)
        wrapper.pack(fill="both", expand=True)
        tk.Label(wrapper, text="LuXon Assistant", bg=PANEL, fg=DARK, font=("Georgia", 20)).pack(anchor="w")
        tk.Label(wrapper, text="El navegador nunca almacena la clave de Gemini. Acá solo se configura la URL pública del intermediario seguro.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=760, justify="left").pack(anchor="w", pady=(6, 18))
        tk.Label(wrapper, text="URL DEL SERVICIO (CLOUDFLARE WORKER)", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 6))
        self.chat_api_var = tk.StringVar(value=self._read_chat_api_url())
        ttk.Entry(wrapper, textvariable=self.chat_api_var).pack(fill="x", ipady=7)
        tk.Label(wrapper, text="Ejemplo: https://luxon-assistant.tu-cuenta.workers.dev/chat  ·  Dejalo vacío para desactivar las respuestas IA.", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=760, justify="left").pack(anchor="w", pady=(7, 18))
        tk.Label(wrapper, text="PUESTA EN MARCHA", bg=PANEL, fg=DARK, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        for line in ["1. Desplegá worker.js en Cloudflare Workers.", "2. Guardá GEMINI_API_KEY como Secret en Cloudflare (nunca en GitHub).", "3. Configurá ALLOWED_ORIGIN con el dominio exacto de GitHub Pages.", "4. Pegá la URL /chat de tu Worker y guardá esta configuración."]:
            tk.Label(wrapper, text=line, bg=PANEL, fg="#5F5A52", font=("Segoe UI", 9)).pack(anchor="w", pady=3)
        ttk.Button(wrapper, text="Guardar configuración y publicar", command=self.save_chat_api_settings).pack(anchor="e", pady=(22, 0))

    @staticmethod
    def _read_chat_api_url():
        source = read_html()
        match = re.search(r'const\s+LUXON_CHAT_API_URL\s*=\s*(["\'])(.*?)\1', source)
        return match.group(2) if match else ""

    def save_chat_api_settings(self):
        try:
            value = self.chat_api_var.get().strip()
            if value and not re.match(r"^https://[^\s]+$", value):
                raise ValueError("La URL debe comenzar con https:// y no contener espacios.")
            source = read_html()
            replacement = "const LUXON_CHAT_API_URL = " + json.dumps(value, ensure_ascii=False) + ";"
            pattern = r'const\s+LUXON_CHAT_API_URL\s*=\s*(["\'])(.*?)\1\s*;'
            if re.search(pattern, source):
                source = re.sub(pattern, lambda _: replacement, source, count=1)
            else:
                raise ValueError("No se encontró la configuración LUXON_CHAT_API_URL en index.html.")
            atomic_write(HTML_FILE, source)
            if self.auto_publish.get():
                ok, detail = publish_to_github()
                self.status_var.set("Asistente configurado y publicado" if ok else "Configuración guardada · revisar GitHub")
                (messagebox.showinfo if ok else messagebox.showwarning)("LuXon Assistant", detail, parent=self)
            else:
                self.status_var.set("URL del asistente guardada localmente")
                messagebox.showinfo("LuXon Assistant", "La URL quedó guardada en index.html. Publicá cuando quieras.", parent=self)
        except Exception as exc:
            messagebox.showerror("No se pudo guardar", str(exc), parent=self)

    @staticmethod
    def _extract_text(source: str, element_id: str) -> str:
        pattern = re.compile(
            rf'<(?:h1|h2|p|span)[^>]*\bid="{re.escape(element_id)}"[^>]*>(.*?)</(?:h1|h2|p|span)>',
            re.DOTALL,
        )
        match = pattern.search(source)
        if not match:
            return ""
        return re.sub(r"<[^>]+>", "", match.group(1)).replace("&amp;", "&").strip()

    def save_banners(self):
        try:
            source = read_html()
            for element_id, variable in self.banner_vars.items():
                source = replace_element_text(source, element_id, variable.get().strip())
            atomic_write(HTML_FILE, source)
            if self.auto_publish.get():
                ok, detail = publish_to_github()
                self.status_var.set("Portada publicada" if ok else "Portada guardada localmente")
                (messagebox.showinfo if ok else messagebox.showwarning)("Portada LuXon", detail, parent=self)
            else:
                messagebox.showinfo("Portada guardada", "Los cambios quedaron guardados en index.html.", parent=self)
        except Exception as exc:
            messagebox.showerror("No se pudo guardar", str(exc), parent=self)

    def change_banner_image(self, element_id: str):
        path = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar imagen para la portada",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp")],
        )
        if not path:
            return
        try:
            source = read_html()
            source = replace_image_by_id(source, element_id, image_to_data_uri(path))
            atomic_write(HTML_FILE, source)
            if self.auto_publish.get():
                ok, detail = publish_to_github()
                self.status_var.set("Imagen publicada" if ok else "Imagen guardada localmente")
                (messagebox.showinfo if ok else messagebox.showwarning)("Imagen de portada", detail, parent=self)
            else:
                messagebox.showinfo("Imagen guardada", "La imagen quedó guardada en index.html.", parent=self)
        except Exception as exc:
            messagebox.showerror("No se pudo actualizar la imagen", str(exc), parent=self)


def main():
    app = LuxonAdmin()
    if app.winfo_exists():
        app.mainloop()


if __name__ == "__main__":
    main()
