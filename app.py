import json
import sys
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable
from urllib.parse import quote, urlencode

from history import HistoryManager
from imbuable_items_data import IMBUABLE_ITEMS_RESOURCE
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

EQUIPMENT_SLOTS = ("head", "armor", "weapon", "shield", "legs")
VOCATIONS = ("Druid", "Elder Druid")


@dataclass(frozen=True)
class EquipmentItem:
    name: str
    slot: str
    imbue_slots: int


ITEM_CATEGORY_SLOT_MAP = {
    "Helmets": "head",
    "Armors": "armor",
    "Shields": "shield",
    "Spellbooks": "shield",
    "Wands": "weapon",
    "Rods": "weapon",
    "Axe Weapons": "weapon",
    "Club Weapons": "weapon",
    "Sword Weapons": "weapon",
    "Fist Fighting Weapons": "weapon",
    "Bows": "weapon",
    "Crossbows": "weapon",
}


def build_items(resource: dict[str, object]) -> tuple[EquipmentItem, ...]:
    items: list[EquipmentItem] = []
    for category in resource.get("categories", []):
        if not isinstance(category, dict):
            continue
        category_name = str(category.get("name", ""))
        slot = ITEM_CATEGORY_SLOT_MAP.get(category_name)
        if not slot:
            continue
        for entry in category.get("items", []):
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            imbue_slots = entry.get("slots", 0)
            try:
                imbue_slots = int(imbue_slots)
            except (TypeError, ValueError):
                imbue_slots = 0
            items.append(EquipmentItem(name=name, slot=slot, imbue_slots=imbue_slots))
    items.sort(key=lambda item: (item.slot, item.name))
    return tuple(items)


ITEMS = build_items(IMBUABLE_ITEMS_RESOURCE)


DEFAULT_STATS = {
    "magic_level": 0,
    "ml_percent": 0,
    "mana_level": 0,
    "hp": 0,
    "mana": 0,
    "capacity": 0,
    "speed": 0,
    "soul_points": 0,
    "stamina": 0,
    "shielding": 0,
    "sword": 0,
    "axe": 0,
    "club": 0,
    "distance": 0,
}


class CharacterStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.characters: list[dict[str, object]] = []
        self.active_name: str | None = None
        self._load()

    def _default_character(self, name: str = "Default", vocation: str = "Druid", level: int = 1) -> dict[str, object]:
        return {
            "name": name,
            "vocation": vocation,
            "level": level,
            "stats": DEFAULT_STATS.copy(),
            "equipment": {slot: {"item": None, "imbues": []} for slot in EQUIPMENT_SLOTS},
        }

    def _load(self) -> None:
        if not self.path.exists():
            self.characters = [self._default_character()]
            self.active_name = self.characters[0]["name"]
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            data = {}
        characters = []
        for entry in data.get("characters", []):
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip() or "Unnamed"
            vocation = str(entry.get("vocation", "Druid"))
            level = entry.get("level", 1)
            try:
                level = int(level)
            except (TypeError, ValueError):
                level = 1
            stats = entry.get("stats", {})
            if not isinstance(stats, dict):
                stats = {}
            merged_stats = DEFAULT_STATS.copy()
            for key in DEFAULT_STATS:
                if key in stats:
                    try:
                        merged_stats[key] = int(stats[key])
                    except (TypeError, ValueError):
                        merged_stats[key] = 0
            equipment = entry.get("equipment", {})
            if not isinstance(equipment, dict):
                equipment = {}
            normalized_equipment = {}
            for slot in EQUIPMENT_SLOTS:
                slot_data = equipment.get(slot, {}) if isinstance(equipment.get(slot, {}), dict) else {}
                item = slot_data.get("item")
                if item is not None:
                    item = str(item)
                imbues = slot_data.get("imbues", [])
                if not isinstance(imbues, list):
                    imbues = []
                normalized_equipment[slot] = {"item": item, "imbues": [str(key) for key in imbues]}
            characters.append(
                {
                    "name": name,
                    "vocation": vocation,
                    "level": level if level >= 1 else 1,
                    "stats": merged_stats,
                    "equipment": normalized_equipment,
                }
            )
        if not characters:
            characters = [self._default_character()]
        self.characters = characters
        active_name = data.get("active_character")
        self.active_name = active_name if active_name in self.names() else self.characters[0]["name"]

    def save(self) -> None:
        payload = {"characters": self.characters, "active_character": self.active_name}
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def names(self) -> list[str]:
        return [str(entry["name"]) for entry in self.characters]

    def get_active(self) -> dict[str, object]:
        for entry in self.characters:
            if entry["name"] == self.active_name:
                return entry
        self.active_name = self.characters[0]["name"]
        return self.characters[0]

    def set_active(self, name: str) -> None:
        self.active_name = name
        self.save()

    def add_character(self, character: dict[str, object]) -> None:
        self.characters.append(character)
        self.active_name = str(character["name"])
        self.save()

    def delete_character(self, name: str) -> None:
        self.characters = [entry for entry in self.characters if entry["name"] != name]
        if not self.characters:
            self.characters = [self._default_character()]
        if self.active_name == name:
            self.active_name = self.characters[0]["name"]
        self.save()

    def is_name_unique(self, name: str, ignore: str | None = None) -> bool:
        lowered = name.casefold()
        for entry in self.characters:
            if ignore and entry["name"] == ignore:
                continue
            if str(entry["name"]).casefold() == lowered:
                return False
        return True

    def update_character(self, old_name: str, updated: dict[str, object]) -> None:
        for idx, entry in enumerate(self.characters):
            if entry["name"] == old_name:
                self.characters[idx] = updated
                break
        if self.active_name == old_name:
            self.active_name = str(updated["name"])
        self.save()


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
        self.character_path = self.base_dir / "characters_state.json"
        self.history = HistoryManager(self.history_path)
        self.store = ImbuementStore(self.state_path)
        self.character_store = CharacterStore(self.character_path)

        self.always_on_top = False
        self.active_imbuement: Imbuement | None = None
        self.material_vars: dict[str, tk.StringVar] = {}
        self.material_rows: list[tuple[Material, ttk.Label]] = []
        self.character_window: "CharacterWindow" | None = None

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

        self.character_button = ttk.Button(top_frame, text="Character Window", command=self.open_character_window)
        self.character_button.grid(row=0, column=2, padx=(6, 0))

        self.top_button = ttk.Button(top_frame, text="Top Off", width=8, command=self.toggle_topmost)
        self.top_button.grid(row=0, column=3, padx=(6, 0))

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

    def open_character_window(self) -> None:
        if self.character_window and self.character_window.window.winfo_exists():
            self.character_window.window.deiconify()
            self.character_window.window.lift()
            self.character_window.window.focus_force()
            return
        self.character_window = CharacterWindow(self.root, self.character_store, self._on_character_window_closed)

    def _on_character_window_closed(self) -> None:
        self.character_window = None


class CharacterWindow:
    def __init__(self, root: tk.Tk, store: CharacterStore, on_close: Callable[[], None]) -> None:
        self.root = root
        self.store = store
        self.on_close = on_close
        self.window = tk.Toplevel(root)
        self.window.title("Character Window")
        self.window.resizable(True, True)
        self.window.minsize(980, 640)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self.active_slot: str = EQUIPMENT_SLOTS[0]
        self.current_character_name: str = str(self.store.get_active()["name"])

        self.item_map = {item.name: item for item in ITEMS}
        self.imbuement_map = {imbuement.key: imbuement for imbuement in IMBUEMENTS}

        self.character_var = tk.StringVar(value=self.current_character_name)
        self.stats_vars: dict[str, tk.StringVar] = {}
        self.stats_entries: dict[str, ttk.Entry] = {}
        self.stats_widgets: dict[str, tk.Widget] = {}
        self.equipment_frames: dict[str, tk.Frame] = {}
        self.equipment_labels: dict[str, dict[str, tk.Label]] = {}
        self.imbue_remove_buttons: dict[str, list[ttk.Button]] = {}

        self._build_ui()
        self._bind_events()
        self._load_character(self.current_character_name)
        self._refresh_summary()

    def _build_ui(self) -> None:
        self.window.columnconfigure(0, weight=1)
        self.window.columnconfigure(1, weight=2)
        self.window.rowconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=0)

        main_frame = ttk.Frame(self.window)
        main_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1)

        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.columnconfigure(1, weight=1)
        right_frame.columnconfigure(2, weight=1)
        right_frame.rowconfigure(0, weight=1)

        summary_frame = ttk.Frame(self.window)
        summary_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        summary_frame.columnconfigure(0, weight=1)

        self._build_character_panel(left_frame)
        self._build_equipment_panel(right_frame)
        self._build_summary_panel(summary_frame)

    def _build_character_panel(self, parent: ttk.Frame) -> None:
        selection_frame = ttk.LabelFrame(parent, text="Character")
        selection_frame.grid(row=0, column=0, sticky="ew")
        selection_frame.columnconfigure(1, weight=1)

        ttk.Label(selection_frame, text="Select").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.character_combo = ttk.Combobox(
            selection_frame,
            textvariable=self.character_var,
            values=self.store.names(),
            state="readonly",
        )
        self.character_combo.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        button_frame = ttk.Frame(selection_frame)
        button_frame.grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6))
        ttk.Button(button_frame, text="New", command=self._open_new_dialog).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(button_frame, text="Delete", command=self._delete_character).grid(row=0, column=1)

        stats_frame = ttk.LabelFrame(parent, text="Stats")
        stats_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        stats_frame.columnconfigure(1, weight=1)

        fields = [
            ("Name", "name"),
            ("Vocation", "vocation"),
            ("Level", "level"),
            ("Magic Level", "magic_level"),
            ("ML %", "ml_percent"),
            ("Mana Level", "mana_level"),
            ("HP", "hp"),
            ("Mana", "mana"),
            ("Capacity", "capacity"),
            ("Speed", "speed"),
            ("Soul Points", "soul_points"),
            ("Stamina (min)", "stamina"),
            ("Shielding", "shielding"),
            ("Sword Fighting", "sword"),
            ("Axe Fighting", "axe"),
            ("Club Fighting", "club"),
            ("Distance Fighting", "distance"),
        ]

        for row, (label, key) in enumerate(fields):
            ttk.Label(stats_frame, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=2)
            if key == "vocation":
                var = tk.StringVar()
                entry = ttk.Combobox(stats_frame, textvariable=var, values=VOCATIONS, state="readonly")
                entry.grid(row=row, column=1, sticky="ew", padx=6, pady=2)
                self.stats_widgets[key] = entry
            else:
                var = tk.StringVar()
                entry = ttk.Entry(stats_frame, textvariable=var)
                entry.grid(row=row, column=1, sticky="ew", padx=6, pady=2)
                self.stats_entries[key] = entry
                self.stats_widgets[key] = entry
            self.stats_vars[key] = var

        self.invalid_style = ttk.Style(self.window)
        self.invalid_style.configure("Invalid.TEntry", foreground="#b00020")

    def _build_equipment_panel(self, parent: ttk.Frame) -> None:
        equipment_frame = ttk.LabelFrame(parent, text="Equipment")
        equipment_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        equipment_frame.columnconfigure(0, weight=1)

        for idx, slot in enumerate(EQUIPMENT_SLOTS):
            slot_frame = tk.Frame(equipment_frame, bd=2, relief="groove")
            slot_frame.grid(row=idx, column=0, sticky="ew", padx=6, pady=4)
            slot_frame.columnconfigure(1, weight=1)
            slot_frame.bind("<Button-1>", lambda _event, s=slot: self._set_active_slot(s))
            header = tk.Label(slot_frame, text=slot.title(), font=("TkDefaultFont", 10, "bold"))
            header.grid(row=0, column=0, sticky="w", padx=4, pady=2)
            item_label = tk.Label(slot_frame, text="— leer —")
            item_label.grid(row=0, column=1, sticky="w", padx=4, pady=2)

            imbue_info = tk.Label(slot_frame, text="Imbues: 0/0")
            imbue_info.grid(row=1, column=0, columnspan=2, sticky="w", padx=4)

            imbue_labels = []
            remove_buttons = []
            for slot_idx in range(3):
                label = tk.Label(slot_frame, text=f"Slot {slot_idx + 1}: —")
                label.grid(row=2 + slot_idx, column=0, sticky="w", padx=4)
                button = ttk.Button(
                    slot_frame,
                    text="Remove",
                    width=7,
                    command=lambda s=slot, i=slot_idx: self._remove_imbue(s, i),
                )
                button.grid(row=2 + slot_idx, column=1, sticky="e", padx=4, pady=1)
                imbue_labels.append(label)
                remove_buttons.append(button)

            clear_button = ttk.Button(slot_frame, text="Clear Item", command=lambda s=slot: self._clear_item(s))
            clear_button.grid(row=5, column=0, columnspan=2, sticky="e", padx=4, pady=(2, 4))

            self.equipment_frames[slot] = slot_frame
            self.equipment_labels[slot] = {
                "item": item_label,
                "imbue_info": imbue_info,
                "slot_1": imbue_labels[0],
                "slot_2": imbue_labels[1],
                "slot_3": imbue_labels[2],
            }
            self.imbue_remove_buttons[slot] = remove_buttons

        items_frame = ttk.LabelFrame(parent, text="Items")
        items_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        items_frame.columnconfigure(0, weight=1)
        items_frame.rowconfigure(0, weight=1)

        self.items_tree = ttk.Treeview(items_frame, columns=("name", "slot", "imbues"), show="headings", height=12)
        self.items_tree.heading("name", text="Item")
        self.items_tree.heading("slot", text="Slot")
        self.items_tree.heading("imbues", text="Imbue Slots")
        self.items_tree.column("name", width=160, anchor="w")
        self.items_tree.column("slot", width=80, anchor="w")
        self.items_tree.column("imbues", width=90, anchor="center")
        self.items_tree.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        items_scroll = ttk.Scrollbar(items_frame, orient="vertical", command=self.items_tree.yview)
        items_scroll.grid(row=0, column=1, sticky="ns")
        self.items_tree.configure(yscrollcommand=items_scroll.set)

        for item in ITEMS:
            self.items_tree.insert("", tk.END, iid=item.name, values=(item.name, item.slot, item.imbue_slots))

        self.items_tree.bind("<Double-Button-1>", lambda _event: self._equip_selected_item())
        ttk.Button(items_frame, text="Equip", command=self._equip_selected_item).grid(row=1, column=0, sticky="e", padx=4, pady=(0, 4))

        imbues_frame = ttk.LabelFrame(parent, text="Imbuements")
        imbues_frame.grid(row=0, column=2, sticky="nsew")
        imbues_frame.columnconfigure(0, weight=1)
        imbues_frame.rowconfigure(0, weight=1)

        self.imbues_tree = ttk.Treeview(imbues_frame, columns=("name", "category"), show="headings", height=12)
        self.imbues_tree.heading("name", text="Imbuement")
        self.imbues_tree.heading("category", text="Category")
        self.imbues_tree.column("name", width=160, anchor="w")
        self.imbues_tree.column("category", width=120, anchor="w")
        self.imbues_tree.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        imbues_scroll = ttk.Scrollbar(imbues_frame, orient="vertical", command=self.imbues_tree.yview)
        imbues_scroll.grid(row=0, column=1, sticky="ns")
        self.imbues_tree.configure(yscrollcommand=imbues_scroll.set)

        for imbuement in IMBUEMENTS:
            self.imbues_tree.insert("", tk.END, iid=imbuement.key, values=(imbuement.name, imbuement.category))

        self.imbues_tree.bind("<Double-Button-1>", lambda _event: self._apply_selected_imbue())
        ttk.Button(imbues_frame, text="Apply", command=self._apply_selected_imbue).grid(row=1, column=0, sticky="e", padx=4, pady=(0, 4))

    def _build_summary_panel(self, parent: ttk.Frame) -> None:
        summary_label = ttk.Label(parent, text="Material Summary")
        summary_label.grid(row=0, column=0, sticky="w")

        text_frame = ttk.Frame(parent)
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)

        self.summary_text = tk.Text(text_frame, height=8, wrap="word", state="disabled")
        self.summary_text.grid(row=0, column=0, sticky="nsew")
        summary_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.summary_text.yview)
        summary_scroll.grid(row=0, column=1, sticky="ns")
        self.summary_text.configure(yscrollcommand=summary_scroll.set)

    def _bind_events(self) -> None:
        self.character_combo.bind("<<ComboboxSelected>>", self._on_character_change)
        for key, widget in self.stats_widgets.items():
            widget.bind("<FocusOut>", lambda _event, k=key: self._save_stats(k))

    def _set_active_slot(self, slot: str) -> None:
        self.active_slot = slot
        for name, frame in self.equipment_frames.items():
            if name == slot:
                frame.configure(bg="#d6e9ff")
            else:
                frame.configure(bg=self.window.cget("bg"))
            for child in frame.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=frame.cget("bg"))

    def _refresh_character_list(self) -> None:
        self.character_combo.configure(values=self.store.names())
        self.character_var.set(self.store.active_name)

    def _load_character(self, name: str) -> None:
        self.store.set_active(name)
        character = self.store.get_active()
        self.current_character_name = str(character["name"])
        self.character_var.set(self.current_character_name)

        self.stats_vars["name"].set(str(character["name"]))
        self.stats_vars["vocation"].set(str(character.get("vocation", VOCATIONS[0])))
        self.stats_vars["level"].set(str(character.get("level", 1)))

        stats = character.get("stats", {})
        for key in DEFAULT_STATS:
            value = stats.get(key, 0) if isinstance(stats, dict) else 0
            self.stats_vars[key].set(str(value))

        self._set_active_slot(self.active_slot)
        self._refresh_equipment()
        self._refresh_summary()

    def _save_stats(self, changed_key: str) -> None:
        character = self.store.get_active()
        old_name = str(character["name"])
        name_value = self.stats_vars["name"].get().strip()
        vocation_value = self.stats_vars["vocation"].get().strip() or VOCATIONS[0]
        level_value = self._parse_int(self.stats_vars["level"].get(), minimum=1)

        if not name_value:
            self._mark_invalid("name", old_name)
            return
        if not self.store.is_name_unique(name_value, ignore=old_name):
            messagebox.showwarning("Name exists", "Character name must be unique.")
            self._mark_invalid("name", old_name)
            return

        if level_value is None:
            self._mark_invalid("level", character.get("level", 1))
            return

        stats = character.get("stats", {})
        if not isinstance(stats, dict):
            stats = {}
        updated_stats = DEFAULT_STATS.copy()
        updated_stats.update(stats)

        for key in DEFAULT_STATS:
            raw = self.stats_vars[key].get()
            if key == "ml_percent":
                value = self._parse_int(raw, minimum=0, maximum=99)
            else:
                value = self._parse_int(raw, minimum=0)
            if value is None:
                self._mark_invalid(key, updated_stats.get(key, 0))
                return
            updated_stats[key] = value
            self._clear_invalid(key)

        updated_character = {
            "name": name_value,
            "vocation": vocation_value,
            "level": level_value,
            "stats": updated_stats,
            "equipment": character.get("equipment", {}),
        }

        self.store.update_character(old_name, updated_character)
        if old_name != name_value:
            self.current_character_name = name_value
            self._refresh_character_list()
        self._clear_invalid("name")
        self._clear_invalid("level")

    def _mark_invalid(self, key: str, fallback: object) -> None:
        widget = self.stats_widgets.get(key)
        if isinstance(widget, ttk.Entry):
            widget.configure(style="Invalid.TEntry")
        if key in self.stats_vars:
            self.stats_vars[key].set(str(fallback))

    def _clear_invalid(self, key: str) -> None:
        widget = self.stats_widgets.get(key)
        if isinstance(widget, ttk.Entry):
            widget.configure(style="TEntry")

    def _parse_int(self, value: str, minimum: int = 0, maximum: int | None = None) -> int | None:
        value = value.strip()
        if not value.isdigit():
            return None
        parsed = int(value)
        if parsed < minimum:
            return None
        if maximum is not None and parsed > maximum:
            return None
        return parsed

    def _on_character_change(self, _event: tk.Event) -> None:
        self._save_stats("name")
        new_name = self.character_var.get()
        self._load_character(new_name)

    def _open_new_dialog(self) -> None:
        dialog = tk.Toplevel(self.window)
        dialog.title("New Character")
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.resizable(False, False)

        ttk.Label(dialog, text="Name").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var)
        name_entry.grid(row=0, column=1, padx=6, pady=6)

        ttk.Label(dialog, text="Vocation").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        vocation_var = tk.StringVar(value=VOCATIONS[0])
        vocation_combo = ttk.Combobox(dialog, textvariable=vocation_var, values=VOCATIONS, state="readonly")
        vocation_combo.grid(row=1, column=1, padx=6, pady=6)

        ttk.Label(dialog, text="Level").grid(row=2, column=0, padx=6, pady=6, sticky="w")
        level_var = tk.StringVar(value="1")
        level_entry = ttk.Entry(dialog, textvariable=level_var)
        level_entry.grid(row=2, column=1, padx=6, pady=6)

        def submit() -> None:
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Missing name", "Name is required.")
                return
            if not self.store.is_name_unique(name):
                messagebox.showwarning("Name exists", "Character name must be unique.")
                return
            level = self._parse_int(level_var.get(), minimum=1)
            if level is None:
                messagebox.showwarning("Invalid level", "Level must be a number >= 1.")
                return
            character = self.store._default_character(name=name, vocation=vocation_var.get(), level=level)
            self.store.add_character(character)
            self._refresh_character_list()
            self._load_character(name)
            dialog.destroy()

        ttk.Button(dialog, text="Create", command=submit).grid(row=3, column=0, padx=6, pady=6)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=3, column=1, padx=6, pady=6)
        name_entry.focus_set()

    def _delete_character(self) -> None:
        name = self.character_var.get()
        if not name:
            return
        if not messagebox.askyesno("Delete Character", f"Delete {name}?"):
            return
        self.store.delete_character(name)
        self._refresh_character_list()
        self._load_character(self.store.active_name)

    def _equip_selected_item(self) -> None:
        selection = self.items_tree.selection()
        if not selection:
            return
        item_name = selection[0]
        item = self.item_map.get(item_name)
        if not item:
            return
        if item.slot != self.active_slot:
            messagebox.showinfo("Slot mismatch", "Item passt nicht in diesen Slot.")
            return
        character = self.store.get_active()
        equipment = character.get("equipment", {})
        if not isinstance(equipment, dict):
            equipment = {}
        equipment[self.active_slot] = {"item": item.name, "imbues": []}
        character["equipment"] = equipment
        self.store.update_character(self.current_character_name, character)
        self._refresh_equipment()
        self._refresh_summary()

    def _apply_selected_imbue(self) -> None:
        selection = self.imbues_tree.selection()
        if not selection:
            return
        imbue_key = selection[0]
        character = self.store.get_active()
        equipment = character.get("equipment", {})
        slot_data = equipment.get(self.active_slot, {}) if isinstance(equipment, dict) else {}
        item_name = slot_data.get("item")
        if not item_name:
            messagebox.showinfo("No item", "Kein Item im aktiven Slot.")
            return
        item = self.item_map.get(item_name)
        if not item or item.imbue_slots <= 0:
            messagebox.showinfo("No slots", "Keine freien Imbue-Slots.")
            return
        imbues = slot_data.get("imbues", [])
        if not isinstance(imbues, list):
            imbues = []
        if len(imbues) >= item.imbue_slots:
            messagebox.showinfo("No slots", "Keine freien Imbue-Slots.")
            return
        imbues.append(imbue_key)
        slot_data["imbues"] = imbues
        equipment[self.active_slot] = slot_data
        character["equipment"] = equipment
        self.store.update_character(self.current_character_name, character)
        self._refresh_equipment()
        self._refresh_summary()

    def _remove_imbue(self, slot: str, index: int) -> None:
        character = self.store.get_active()
        equipment = character.get("equipment", {})
        slot_data = equipment.get(slot, {}) if isinstance(equipment, dict) else {}
        imbues = slot_data.get("imbues", [])
        if not isinstance(imbues, list):
            return
        if index >= len(imbues):
            return
        imbues.pop(index)
        slot_data["imbues"] = imbues
        equipment[slot] = slot_data
        character["equipment"] = equipment
        self.store.update_character(self.current_character_name, character)
        self._refresh_equipment()
        self._refresh_summary()

    def _clear_item(self, slot: str) -> None:
        character = self.store.get_active()
        equipment = character.get("equipment", {})
        equipment[slot] = {"item": None, "imbues": []}
        character["equipment"] = equipment
        self.store.update_character(self.current_character_name, character)
        self._refresh_equipment()
        self._refresh_summary()

    def _refresh_equipment(self) -> None:
        character = self.store.get_active()
        equipment = character.get("equipment", {})
        for slot in EQUIPMENT_SLOTS:
            slot_data = equipment.get(slot, {"item": None, "imbues": []})
            item_name = slot_data.get("item")
            imbues = slot_data.get("imbues", []) if isinstance(slot_data.get("imbues", []), list) else []
            item_label = self.equipment_labels[slot]["item"]
            imbue_info = self.equipment_labels[slot]["imbue_info"]

            item_label.config(text=item_name or "— leer —")
            item = self.item_map.get(item_name) if item_name else None
            max_slots = item.imbue_slots if item else 0
            imbue_info.config(text=f"Imbues: {len(imbues)}/{max_slots}")

            for idx in range(3):
                label_key = f"slot_{idx + 1}"
                label = self.equipment_labels[slot][label_key]
                if idx < max_slots:
                    name = "—"
                    if idx < len(imbues):
                        imbuement = self.imbuement_map.get(imbues[idx])
                        name = imbuement.name if imbuement else imbues[idx]
                    label.config(text=f"Slot {idx + 1}: {name}")
                else:
                    label.config(text=f"Slot {idx + 1}: n/a")

                remove_button = self.imbue_remove_buttons[slot][idx]
                if idx < len(imbues):
                    remove_button.state(["!disabled"])
                else:
                    remove_button.state(["disabled"])

        self._set_active_slot(self.active_slot)

    def _refresh_summary(self) -> None:
        character = self.store.get_active()
        equipment = character.get("equipment", {})
        imbue_counts: dict[str, int] = {}
        for slot in EQUIPMENT_SLOTS:
            slot_data = equipment.get(slot, {})
            imbues = slot_data.get("imbues", []) if isinstance(slot_data, dict) else []
            for key in imbues:
                imbue_counts[key] = imbue_counts.get(key, 0) + 1

        lines = []
        if not imbue_counts:
            lines.append("No imbuements applied.")
        else:
            for key in sorted(imbue_counts, key=lambda k: self.imbuement_map.get(k).name if self.imbuement_map.get(k) else k):
                count = imbue_counts[key]
                imbuement = self.imbuement_map.get(key)
                name = imbuement.name if imbuement else key
                lines.append(f"{name} (x{count})")
                if imbuement:
                    for material in imbuement.materials:
                        total_qty = material.qty * count
                        lines.append(f"  {total_qty} × {material.name}")
                lines.append("")

            totals: dict[str, int] = {}
            for key, count in imbue_counts.items():
                imbuement = self.imbuement_map.get(key)
                if not imbuement:
                    continue
                for material in imbuement.materials:
                    totals[material.name] = totals.get(material.name, 0) + material.qty * count
            if totals:
                lines.append("Grand Totals")
                for name in sorted(totals):
                    lines.append(f"  {totals[name]} × {name}")

        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert(tk.END, "\n".join(lines).strip())
        self.summary_text.configure(state="disabled")

    def _on_close(self) -> None:
        self.window.destroy()
        self.on_close()

def main() -> None:
    root = tk.Tk()
    app = TibiaSearchApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
