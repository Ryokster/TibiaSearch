import json
import sys
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from urllib.parse import quote, urlencode

from history import HistoryManager
from imbuements_data import IMBUEMENTS_RESOURCE

SEARCH_PAGE_URL = "https://tibia.fandom.com/wiki/Special:Search"
FANDOM_BASE_URL = IMBUEMENTS_RESOURCE.get("wiki_base", "https://tibia.fandom.com/wiki/")


def fandom_article_url(title: str) -> str:
    slug = title.strip().replace(" ", "_")
    return f"{FANDOM_BASE_URL}{quote(slug, safe='_')}"


@dataclass(frozen=True)
class Material:
    qty: int
    name: str


@dataclass(frozen=True)
class Imbuement:
    category: str
    name: str
    materials: tuple[Material, ...]

    @property
    def key(self) -> str:
        return f"{self.category}|{self.name}"


def build_imbuements(resource: dict[str, object]) -> tuple[Imbuement, ...]:
    imbuements = []
    for item in resource.get("imbuements", []):
        category = str(item.get("category", ""))
        for tier in item.get("tiers", []):
            materials = tuple(
                Material(int(source["qty"]), str(source["name"]))
                for source in tier.get("sources", [])
            )
            imbuements.append(
                Imbuement(
                    category=category,
                    name=str(tier.get("name", "")),
                    materials=materials,
                )
            )
    return tuple(imbuements)


IMBUEMENTS = build_imbuements(IMBUEMENTS_RESOURCE)


class ImbuementStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.prices: dict[str, int] = {}
        self.favorites: dict[str, bool] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            prices = data.get("prices", {})
            favorites = data.get("favorites", {})
            if isinstance(prices, dict):
                self.prices = {str(k): int(v) for k, v in prices.items()}
            if isinstance(favorites, dict):
                self.favorites = {str(k): bool(v) for k, v in favorites.items()}
        except Exception:
            self.prices = {}
            self.favorites = {}

    def _save(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                json.dump({"prices": self.prices, "favorites": self.favorites}, handle, indent=2)
        except Exception:
            pass

    def get_price(self, material_name: str) -> int:
        return int(self.prices.get(material_name, 0))

    def set_price(self, material_name: str, price: int) -> None:
        self.prices[material_name] = max(0, int(price))
        self._save()

    def is_favorite(self, key: str) -> bool:
        return bool(self.favorites.get(key, False))

    def set_favorite(self, key: str, value: bool) -> None:
        self.favorites[key] = bool(value)
        self._save()

class TibiaSearchApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tibia Search")
        self.root.resizable(True, True)
        self.root.minsize(620, 420)

        self.base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        self.history_path = self.base_dir / "history.json"
        self.state_path = self.base_dir / "imbuements_state.json"
        self.history = HistoryManager(self.history_path)
        self.store = ImbuementStore(self.state_path)

        self.always_on_top = False
        self.active_imbuement: Imbuement | None = None
        self.material_vars: dict[str, tk.StringVar] = {}
        self.material_rows: list[tuple[Material, ttk.Label]] = []

        self._build_ui()
        self._bind_events()
        self._refresh_history_list()
        self._populate_imbuements()
        self._select_first_imbuement()

        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top_frame = ttk.Frame(self.root)
        top_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        top_frame.columnconfigure(0, weight=1)

        self.search_entry = ttk.Entry(top_frame)
        self.search_entry.grid(row=0, column=0, sticky="ew")

        self.search_button = ttk.Button(top_frame, text="Search", command=self.perform_search)
        self.search_button.grid(row=0, column=1, padx=(6, 0))

        self.top_button = ttk.Button(top_frame, text="Top Off", width=8, command=self.toggle_topmost)
        self.top_button.grid(row=0, column=2, padx=(6, 0))

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        self.history_tab = ttk.Frame(self.notebook)
        self.imbuements_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.history_tab, text="History")
        self.notebook.add(self.imbuements_tab, text="Imbuements")

        self._build_history_tab()
        self._build_imbuements_tab()

    def _build_history_tab(self) -> None:
        self.history_tab.columnconfigure(0, weight=1)
        self.history_tab.rowconfigure(0, weight=1)

        self.history_list = tk.Listbox(self.history_tab, height=6)
        self.history_list.grid(row=0, column=0, sticky="nsew")

        history_scroll = ttk.Scrollbar(self.history_tab, orient="vertical", command=self.history_list.yview)
        history_scroll.grid(row=0, column=1, sticky="ns")
        self.history_list.configure(yscrollcommand=history_scroll.set)

    def _build_imbuements_tab(self) -> None:
        self.imbuements_tab.columnconfigure(0, weight=1)
        self.imbuements_tab.columnconfigure(1, weight=2)
        self.imbuements_tab.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(self.imbuements_tab)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        self.imbuement_tree = ttk.Treeview(left_frame, columns=("fav", "name", "total"), show="headings", height=12)
        self.imbuement_tree.heading("fav", text="★")
        self.imbuement_tree.heading("name", text="Imbuement")
        self.imbuement_tree.heading("total", text="Total")
        self.imbuement_tree.column("fav", width=32, anchor="center", stretch=False)
        self.imbuement_tree.column("name", width=220, anchor="w")
        self.imbuement_tree.column("total", width=110, anchor="e")
        self.imbuement_tree.grid(row=0, column=0, sticky="nsew")

        tree_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.imbuement_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.imbuement_tree.configure(yscrollcommand=tree_scroll.set)

        right_frame = ttk.Frame(self.imbuements_tab)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)

        header_frame = ttk.Frame(right_frame)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(0, weight=1)

        title_font = tkfont.Font(self.root, size=12, weight="bold")
        self.imbuement_title = ttk.Label(header_frame, text="Select an Imbuement", font=title_font)
        self.imbuement_title.grid(row=0, column=0, sticky="w")

        self.favorite_button = ttk.Button(header_frame, text="☆", width=3, command=self.toggle_selected_favorite)
        self.favorite_button.grid(row=0, column=1, padx=(6, 0))

        self.category_label = ttk.Label(header_frame, text="")
        self.category_label.grid(row=1, column=0, sticky="w", pady=(2, 8))

        action_frame = ttk.Frame(right_frame)
        action_frame.grid(row=1, column=0, sticky="w", pady=(0, 10))
        self.search_imbuement_button = ttk.Button(action_frame, text="Imbuement suchen", command=self.search_selected_imbuement)
        self.search_imbuement_button.grid(row=0, column=0, padx=(0, 6))
        self.search_materials_button = ttk.Button(action_frame, text="Alle Materialien suchen", command=self.search_all_materials)
        self.search_materials_button.grid(row=0, column=1)

        self.materials_frame = ttk.Frame(right_frame)
        self.materials_frame.grid(row=2, column=0, sticky="nsew")
        self.materials_frame.columnconfigure(1, weight=1)
        self.materials_frame.columnconfigure(3, weight=1)

        self.materials_header = ttk.Label(self.materials_frame, text="Reagenzien / Astral Sources")
        self.materials_header.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        header_qty = ttk.Label(self.materials_frame, text="Menge")
        header_item = ttk.Label(self.materials_frame, text="Item")
        header_price = ttk.Label(self.materials_frame, text="Preis/Stk")
        header_total = ttk.Label(self.materials_frame, text="Zeilenpreis")
        header_qty.grid(row=1, column=0, sticky="w")
        header_item.grid(row=1, column=1, sticky="w")
        header_price.grid(row=1, column=2, sticky="w")
        header_total.grid(row=1, column=3, sticky="e")

        self.total_label = ttk.Label(right_frame, text="Gesamt: 0 gp")
        self.total_label.grid(row=3, column=0, sticky="e", pady=(10, 0))

    def _bind_events(self) -> None:
        self.search_entry.bind("<Return>", lambda _event: self.perform_search())
        self.search_entry.bind("<Escape>", lambda _event: self.clear_entry())

        self.history_list.bind("<ButtonRelease-1>", self.load_from_history)
        self.history_list.bind("<Double-Button-1>", lambda _event: self.search_from_history())
        self.history_list.bind("<Return>", lambda _event: self.search_from_history())

        self.imbuement_tree.bind("<<TreeviewSelect>>", self.on_imbuement_select)
        self.imbuement_tree.bind("<Double-Button-1>", lambda _event: self.search_selected_imbuement())
        self.imbuement_tree.bind("<Return>", lambda _event: self.search_selected_imbuement())
        self.imbuement_tree.bind("<Button-1>", self.on_tree_click)

    def clear_entry(self) -> None:
        self.search_entry.delete(0, tk.END)

    def toggle_topmost(self) -> None:
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)
        if self.always_on_top:
            self.top_button.config(text="Top On")
        else:
            self.top_button.config(text="Top Off")

    def _refresh_history_list(self) -> None:
        self.history_list.delete(0, tk.END)
        for item in self.history.items:
            self.history_list.insert(tk.END, item)

    def load_from_history(self, _event: tk.Event) -> None:
        selection = self.history_list.curselection()
        if not selection:
            return
        value = self.history_list.get(selection[0])
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, value)

    def search_from_history(self) -> None:
        selection = self.history_list.curselection()
        if not selection:
            return
        value = self.history_list.get(selection[0])
        self.open_search(value)

    def perform_search(self) -> None:
        query = self.search_entry.get().strip()
        if not query:
            return
        self.open_search(query)

    def open_search(self, query: str) -> None:
        self.history.add(query)
        self._refresh_history_list()
        target_url = f"{SEARCH_PAGE_URL}?{urlencode({'query': query})}"
        webbrowser.open_new_tab(target_url)

    def _populate_imbuements(self) -> None:
        self.imbuement_tree.delete(*self.imbuement_tree.get_children())
        ordered = sorted(
            IMBUEMENTS,
            key=lambda item: (not self.store.is_favorite(item.key),),
        )
        for imbuement in ordered:
            self._insert_imbuement(imbuement)

    def _insert_imbuement(self, imbuement: Imbuement) -> None:
        fav = "★" if self.store.is_favorite(imbuement.key) else "☆"
        total = self._format_gp(self._calculate_total(imbuement))
        self.imbuement_tree.insert("", tk.END, iid=imbuement.key, values=(fav, imbuement.name, total))

    def _select_first_imbuement(self) -> None:
        children = self.imbuement_tree.get_children()
        if children:
            self.imbuement_tree.selection_set(children[0])

    def on_imbuement_select(self, _event: tk.Event) -> None:
        selection = self.imbuement_tree.selection()
        if not selection:
            return
        key = selection[0]
        imbuement = self._find_imbuement(key)
        if imbuement is None:
            return
        self.active_imbuement = imbuement
        self._render_imbuement_details(imbuement)

    def on_tree_click(self, event: tk.Event) -> None:
        region = self.imbuement_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self.imbuement_tree.identify_column(event.x)
        row = self.imbuement_tree.identify_row(event.y)
        if column == "#1" and row:
            self.toggle_favorite(row)

    def _find_imbuement(self, key: str) -> Imbuement | None:
        for imbuement in IMBUEMENTS:
            if imbuement.key == key:
                return imbuement
        return None

    def toggle_favorite(self, key: str) -> None:
        is_favorite = self.store.is_favorite(key)
        self.store.set_favorite(key, not is_favorite)
        self._populate_imbuements()
        if self.active_imbuement and self.active_imbuement.key == key:
            self._render_imbuement_details(self.active_imbuement)

    def toggle_selected_favorite(self) -> None:
        if not self.active_imbuement:
            return
        self.toggle_favorite(self.active_imbuement.key)

    def search_selected_imbuement(self) -> None:
        if not self.active_imbuement:
            return
        self.open_search(self.active_imbuement.name)

    def search_all_materials(self) -> None:
        if not self.active_imbuement:
            return
        for material in self.active_imbuement.materials:
            webbrowser.open_new_tab(fandom_article_url(material.name))

    def _render_imbuement_details(self, imbuement: Imbuement) -> None:
        self.imbuement_title.config(text=imbuement.name)
        self.category_label.config(text=imbuement.category)
        self.favorite_button.config(text="★" if self.store.is_favorite(imbuement.key) else "☆")

        for widget in self.materials_frame.grid_slaves():
            info = widget.grid_info()
            if info.get("row", 0) >= 2:
                widget.destroy()

        self.material_vars.clear()
        self.material_rows.clear()

        start_row = 2
        for idx, material in enumerate(imbuement.materials):
            row = start_row + idx
            ttk.Label(self.materials_frame, text=str(material.qty)).grid(row=row, column=0, sticky="w", pady=2)

            item_label = ttk.Label(self.materials_frame, text=material.name, foreground="#0a66cc", cursor="hand2")
            item_label.grid(row=row, column=1, sticky="w", pady=2)
            item_label.bind(
                "<Button-1>",
                lambda _event, name=material.name: webbrowser.open_new_tab(fandom_article_url(name)),
            )

            var = tk.StringVar(value=str(self.store.get_price(material.name)))
            self.material_vars[material.name] = var
            entry = ttk.Entry(self.materials_frame, textvariable=var, width=10, validate="key")
            entry.configure(validatecommand=(self.root.register(self._validate_price), "%P"))
            entry.grid(row=row, column=2, sticky="w", padx=(6, 6))
            var.trace_add("write", lambda _name, _index, _mode, m=material, v=var: self._on_price_change(m, v))

            row_total = ttk.Label(self.materials_frame, text=self._format_gp(material.qty * self.store.get_price(material.name)))
            row_total.grid(row=row, column=3, sticky="e", pady=2)
            self.material_rows.append((material, row_total))

        self._update_total_label(imbuement)

    def _validate_price(self, proposed: str) -> bool:
        return proposed.isdigit() or proposed == ""

    def _on_price_change(self, material: Material, var: tk.StringVar) -> None:
        value = var.get().strip()
        price = int(value) if value.isdigit() else 0
        self.store.set_price(material.name, price)
        self._update_material_totals()
        self._refresh_imbuement_totals()

    def _update_material_totals(self) -> None:
        for material, label in self.material_rows:
            line_total = material.qty * self.store.get_price(material.name)
            label.config(text=self._format_gp(line_total))
        if self.active_imbuement:
            self._update_total_label(self.active_imbuement)

    def _update_total_label(self, imbuement: Imbuement) -> None:
        total = self._calculate_total(imbuement)
        self.total_label.config(text=f"Gesamt: {self._format_gp(total)}")

    def _refresh_imbuement_totals(self) -> None:
        for child in self.imbuement_tree.get_children():
            imbuement = self._find_imbuement(child)
            if not imbuement:
                continue
            total = self._format_gp(self._calculate_total(imbuement))
            fav = "★" if self.store.is_favorite(imbuement.key) else "☆"
            self.imbuement_tree.item(child, values=(fav, imbuement.name, total))

    def _calculate_total(self, imbuement: Imbuement) -> int:
        return sum(material.qty * self.store.get_price(material.name) for material in imbuement.materials)

    def _format_gp(self, value: int) -> str:
        return f"{value:,}".replace(",", ".") + " gp"

    def exit_app(self) -> None:
        self.root.destroy()

def main() -> None:
    root = tk.Tk()
    app = TibiaSearchApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
