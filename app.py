import json
import sys
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from urllib.parse import urlencode

from history import HistoryManager

SEARCH_PAGE_URL = "https://tibia.fandom.com/wiki/Special:Search"


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


IMBUEMENTS: tuple[Imbuement, ...] = (
    Imbuement(
        category="Mana Leech",
        name="Basic Void",
        materials=(
            Material(25, "Rope Belt"),
            Material(25, "Silencer Claws"),
            Material(5, "Grimeleech Wings"),
        ),
    ),
    Imbuement(
        category="Mana Leech",
        name="Intricate Void",
        materials=(
            Material(25, "Rope Belt"),
            Material(25, "Silencer Claws"),
            Material(10, "Grimeleech Wings"),
        ),
    ),
    Imbuement(
        category="Mana Leech",
        name="Powerful Void",
        materials=(
            Material(50, "Rope Belt"),
            Material(50, "Silencer Claws"),
            Material(20, "Grimeleech Wings"),
        ),
    ),
    Imbuement(
        category="Life Leech",
        name="Basic Vampirism",
        materials=(
            Material(25, "Vampire Teeth"),
            Material(15, "Bloody Pincers"),
            Material(5, "Piece of Dead Brain"),
        ),
    ),
    Imbuement(
        category="Life Leech",
        name="Intricate Vampirism",
        materials=(
            Material(25, "Vampire Teeth"),
            Material(25, "Bloody Pincers"),
            Material(10, "Piece of Dead Brain"),
        ),
    ),
    Imbuement(
        category="Life Leech",
        name="Powerful Vampirism",
        materials=(
            Material(50, "Vampire Teeth"),
            Material(50, "Bloody Pincers"),
            Material(20, "Piece of Dead Brain"),
        ),
    ),
    Imbuement(
        category="Critical",
        name="Basic Strike",
        materials=(
            Material(20, "Protective Charm"),
            Material(25, "Sabretooth"),
            Material(5, "Vexclaw Talon"),
        ),
    ),
    Imbuement(
        category="Critical",
        name="Intricate Strike",
        materials=(
            Material(25, "Protective Charm"),
            Material(30, "Sabretooth"),
            Material(10, "Vexclaw Talon"),
        ),
    ),
    Imbuement(
        category="Critical",
        name="Powerful Strike",
        materials=(
            Material(50, "Protective Charm"),
            Material(50, "Sabretooth"),
            Material(20, "Vexclaw Talon"),
        ),
    ),
    Imbuement(
        category="Attack - Fire",
        name="Basic Scorch",
        materials=(
            Material(25, "Fiery Heart"),
            Material(10, "Fiery Tears"),
            Material(5, "Green Dragon Scale"),
        ),
    ),
    Imbuement(
        category="Attack - Fire",
        name="Intricate Scorch",
        materials=(
            Material(25, "Fiery Heart"),
            Material(20, "Fiery Tears"),
            Material(10, "Green Dragon Scale"),
        ),
    ),
    Imbuement(
        category="Attack - Fire",
        name="Powerful Scorch",
        materials=(
            Material(50, "Fiery Heart"),
            Material(30, "Fiery Tears"),
            Material(20, "Green Dragon Scale"),
        ),
    ),
    Imbuement(
        category="Attack - Earth",
        name="Basic Venom",
        materials=(
            Material(25, "Poisonous Slime"),
            Material(10, "Slime Heart"),
            Material(5, "Swamp Grass"),
        ),
    ),
    Imbuement(
        category="Attack - Earth",
        name="Intricate Venom",
        materials=(
            Material(25, "Poisonous Slime"),
            Material(20, "Slime Heart"),
            Material(10, "Swamp Grass"),
        ),
    ),
    Imbuement(
        category="Attack - Earth",
        name="Powerful Venom",
        materials=(
            Material(50, "Poisonous Slime"),
            Material(30, "Slime Heart"),
            Material(20, "Swamp Grass"),
        ),
    ),
    Imbuement(
        category="Attack - Ice",
        name="Basic Frost",
        materials=(
            Material(25, "Frosty Heart"),
            Material(10, "Seacrest Hair"),
            Material(5, "Polar Bear Paw"),
        ),
    ),
    Imbuement(
        category="Attack - Ice",
        name="Intricate Frost",
        materials=(
            Material(25, "Frosty Heart"),
            Material(20, "Seacrest Hair"),
            Material(10, "Polar Bear Paw"),
        ),
    ),
    Imbuement(
        category="Attack - Ice",
        name="Powerful Frost",
        materials=(
            Material(50, "Frosty Heart"),
            Material(30, "Seacrest Hair"),
            Material(20, "Polar Bear Paw"),
        ),
    ),
    Imbuement(
        category="Attack - Energy",
        name="Basic Electrify",
        materials=(
            Material(25, "Energy Vein"),
            Material(10, "Roc Feather"),
            Material(5, "Spark Sphere"),
        ),
    ),
    Imbuement(
        category="Attack - Energy",
        name="Intricate Electrify",
        materials=(
            Material(25, "Energy Vein"),
            Material(20, "Roc Feather"),
            Material(10, "Spark Sphere"),
        ),
    ),
    Imbuement(
        category="Attack - Energy",
        name="Powerful Electrify",
        materials=(
            Material(50, "Energy Vein"),
            Material(30, "Roc Feather"),
            Material(20, "Spark Sphere"),
        ),
    ),
    Imbuement(
        category="Attack - Death",
        name="Basic Reap",
        materials=(
            Material(25, "Reaper's Hood"),
            Material(10, "Petrified Scream"),
            Material(5, "Pile of Grave Earth"),
        ),
    ),
    Imbuement(
        category="Attack - Death",
        name="Intricate Reap",
        materials=(
            Material(25, "Reaper's Hood"),
            Material(20, "Petrified Scream"),
            Material(10, "Pile of Grave Earth"),
        ),
    ),
    Imbuement(
        category="Attack - Death",
        name="Powerful Reap",
        materials=(
            Material(50, "Reaper's Hood"),
            Material(30, "Petrified Scream"),
            Material(20, "Pile of Grave Earth"),
        ),
    ),
    Imbuement(
        category="Protection - Death",
        name="Basic Lich Shroud",
        materials=(
            Material(25, "Flask of Embalming Fluid"),
            Material(10, "Lich Staff"),
            Material(5, "Grave Flower"),
        ),
    ),
    Imbuement(
        category="Protection - Death",
        name="Intricate Lich Shroud",
        materials=(
            Material(25, "Flask of Embalming Fluid"),
            Material(20, "Lich Staff"),
            Material(10, "Grave Flower"),
        ),
    ),
    Imbuement(
        category="Protection - Death",
        name="Powerful Lich Shroud",
        materials=(
            Material(50, "Flask of Embalming Fluid"),
            Material(30, "Lich Staff"),
            Material(20, "Grave Flower"),
        ),
    ),
    Imbuement(
        category="Protection - Earth",
        name="Basic Snake Skin",
        materials=(
            Material(25, "Snakeskin"),
            Material(10, "Green Dragon Scale"),
            Material(5, "Terra Mantle"),
        ),
    ),
    Imbuement(
        category="Protection - Earth",
        name="Intricate Snake Skin",
        materials=(
            Material(25, "Snakeskin"),
            Material(20, "Green Dragon Scale"),
            Material(10, "Terra Mantle"),
        ),
    ),
    Imbuement(
        category="Protection - Earth",
        name="Powerful Snake Skin",
        materials=(
            Material(50, "Snakeskin"),
            Material(30, "Green Dragon Scale"),
            Material(20, "Terra Mantle"),
        ),
    ),
    Imbuement(
        category="Protection - Fire",
        name="Basic Dragon Hide",
        materials=(
            Material(25, "Red Dragon Scale"),
            Material(10, "Demonic Skeletal Hand"),
            Material(5, "Draken Sulphur"),
        ),
    ),
    Imbuement(
        category="Protection - Fire",
        name="Intricate Dragon Hide",
        materials=(
            Material(25, "Red Dragon Scale"),
            Material(20, "Demonic Skeletal Hand"),
            Material(10, "Draken Sulphur"),
        ),
    ),
    Imbuement(
        category="Protection - Fire",
        name="Powerful Dragon Hide",
        materials=(
            Material(50, "Red Dragon Scale"),
            Material(30, "Demonic Skeletal Hand"),
            Material(20, "Draken Sulphur"),
        ),
    ),
    Imbuement(
        category="Protection - Ice",
        name="Basic Quara Scale",
        materials=(
            Material(25, "Quara Tentacle"),
            Material(10, "Quara Eye"),
            Material(5, "Quara Pincers"),
        ),
    ),
    Imbuement(
        category="Protection - Ice",
        name="Intricate Quara Scale",
        materials=(
            Material(25, "Quara Tentacle"),
            Material(20, "Quara Eye"),
            Material(10, "Quara Pincers"),
        ),
    ),
    Imbuement(
        category="Protection - Ice",
        name="Powerful Quara Scale",
        materials=(
            Material(50, "Quara Tentacle"),
            Material(30, "Quara Eye"),
            Material(20, "Quara Pincers"),
        ),
    ),
    Imbuement(
        category="Protection - Energy",
        name="Basic Cloud Fabric",
        materials=(
            Material(25, "Cloud Fabric"),
            Material(10, "Energy Vein"),
            Material(5, "Wyvern Talisman"),
        ),
    ),
    Imbuement(
        category="Protection - Energy",
        name="Intricate Cloud Fabric",
        materials=(
            Material(25, "Cloud Fabric"),
            Material(20, "Energy Vein"),
            Material(10, "Wyvern Talisman"),
        ),
    ),
    Imbuement(
        category="Protection - Energy",
        name="Powerful Cloud Fabric",
        materials=(
            Material(50, "Cloud Fabric"),
            Material(30, "Energy Vein"),
            Material(20, "Wyvern Talisman"),
        ),
    ),
    Imbuement(
        category="Protection - Holy",
        name="Basic Demon Presence",
        materials=(
            Material(25, "Demon Horn"),
            Material(10, "Holy Orchid"),
            Material(5, "Demon Dust"),
        ),
    ),
    Imbuement(
        category="Protection - Holy",
        name="Intricate Demon Presence",
        materials=(
            Material(25, "Demon Horn"),
            Material(20, "Holy Orchid"),
            Material(10, "Demon Dust"),
        ),
    ),
    Imbuement(
        category="Protection - Holy",
        name="Powerful Demon Presence",
        materials=(
            Material(50, "Demon Horn"),
            Material(30, "Holy Orchid"),
            Material(20, "Demon Dust"),
        ),
    ),
    Imbuement(
        category="Support",
        name="Basic Swiftness",
        materials=(
            Material(25, "Tarantula Egg"),
            Material(10, "Compendium"),
            Material(5, "Crystallized Anger"),
        ),
    ),
    Imbuement(
        category="Support",
        name="Intricate Swiftness",
        materials=(
            Material(25, "Tarantula Egg"),
            Material(20, "Compendium"),
            Material(10, "Crystallized Anger"),
        ),
    ),
    Imbuement(
        category="Support",
        name="Powerful Swiftness",
        materials=(
            Material(50, "Tarantula Egg"),
            Material(30, "Compendium"),
            Material(20, "Crystallized Anger"),
        ),
    ),
    Imbuement(
        category="Support",
        name="Basic Featherweight",
        materials=(
            Material(25, "Falcon Feather"),
            Material(10, "Giant Shimmering Pearl"),
            Material(5, "Minotaur Leather"),
        ),
    ),
    Imbuement(
        category="Support",
        name="Intricate Featherweight",
        materials=(
            Material(25, "Falcon Feather"),
            Material(20, "Giant Shimmering Pearl"),
            Material(10, "Minotaur Leather"),
        ),
    ),
    Imbuement(
        category="Support",
        name="Powerful Featherweight",
        materials=(
            Material(50, "Falcon Feather"),
            Material(30, "Giant Shimmering Pearl"),
            Material(20, "Minotaur Leather"),
        ),
    ),
    Imbuement(
        category="Skill - Magic Level",
        name="Basic Epiphany",
        materials=(
            Material(25, "Frosty Heart"),
            Material(10, "Ectoplasm"),
            Material(5, "Seacrest Hair"),
        ),
    ),
    Imbuement(
        category="Skill - Magic Level",
        name="Intricate Epiphany",
        materials=(
            Material(25, "Frosty Heart"),
            Material(20, "Ectoplasm"),
            Material(10, "Seacrest Hair"),
        ),
    ),
    Imbuement(
        category="Skill - Magic Level",
        name="Powerful Epiphany",
        materials=(
            Material(50, "Frosty Heart"),
            Material(30, "Ectoplasm"),
            Material(20, "Seacrest Hair"),
        ),
    ),
    Imbuement(
        category="Skill - Fist",
        name="Basic Punch",
        materials=(
            Material(25, "Battle Stone"),
            Material(10, "Turtle Shell"),
            Material(5, "Cyclops Toe"),
        ),
    ),
    Imbuement(
        category="Skill - Fist",
        name="Intricate Punch",
        materials=(
            Material(25, "Battle Stone"),
            Material(20, "Turtle Shell"),
            Material(10, "Cyclops Toe"),
        ),
    ),
    Imbuement(
        category="Skill - Fist",
        name="Powerful Punch",
        materials=(
            Material(50, "Battle Stone"),
            Material(30, "Turtle Shell"),
            Material(20, "Cyclops Toe"),
        ),
    ),
    Imbuement(
        category="Skill - Club",
        name="Basic Bash",
        materials=(
            Material(25, "Rorc Feather"),
            Material(10, "Lion's Mane"),
            Material(5, "Ogre Ear Stud"),
        ),
    ),
    Imbuement(
        category="Skill - Club",
        name="Intricate Bash",
        materials=(
            Material(25, "Rorc Feather"),
            Material(20, "Lion's Mane"),
            Material(10, "Ogre Ear Stud"),
        ),
    ),
    Imbuement(
        category="Skill - Club",
        name="Powerful Bash",
        materials=(
            Material(50, "Rorc Feather"),
            Material(30, "Lion's Mane"),
            Material(20, "Ogre Ear Stud"),
        ),
    ),
    Imbuement(
        category="Skill - Sword",
        name="Basic Slash",
        materials=(
            Material(25, "Hunting Spear"),
            Material(10, "Lion's Mane"),
            Material(5, "Broken Shamanic Staff"),
        ),
    ),
    Imbuement(
        category="Skill - Sword",
        name="Intricate Slash",
        materials=(
            Material(25, "Hunting Spear"),
            Material(20, "Lion's Mane"),
            Material(10, "Broken Shamanic Staff"),
        ),
    ),
    Imbuement(
        category="Skill - Sword",
        name="Powerful Slash",
        materials=(
            Material(50, "Hunting Spear"),
            Material(30, "Lion's Mane"),
            Material(20, "Broken Shamanic Staff"),
        ),
    ),
    Imbuement(
        category="Skill - Axe",
        name="Basic Chop",
        materials=(
            Material(25, "Bronze Goblet"),
            Material(10, "Orc Tooth"),
            Material(5, "Vampire Teeth"),
        ),
    ),
    Imbuement(
        category="Skill - Axe",
        name="Intricate Chop",
        materials=(
            Material(25, "Bronze Goblet"),
            Material(20, "Orc Tooth"),
            Material(10, "Vampire Teeth"),
        ),
    ),
    Imbuement(
        category="Skill - Axe",
        name="Powerful Chop",
        materials=(
            Material(50, "Bronze Goblet"),
            Material(30, "Orc Tooth"),
            Material(20, "Vampire Teeth"),
        ),
    ),
    Imbuement(
        category="Skill - Distance",
        name="Basic Precision",
        materials=(
            Material(25, "Elven Scouting Glass"),
            Material(10, "Elven Hoof"),
            Material(5, "Piece of Steel"),
        ),
    ),
    Imbuement(
        category="Skill - Distance",
        name="Intricate Precision",
        materials=(
            Material(25, "Elven Scouting Glass"),
            Material(20, "Elven Hoof"),
            Material(10, "Piece of Steel"),
        ),
    ),
    Imbuement(
        category="Skill - Distance",
        name="Powerful Precision",
        materials=(
            Material(50, "Elven Scouting Glass"),
            Material(30, "Elven Hoof"),
            Material(20, "Piece of Steel"),
        ),
    ),
    Imbuement(
        category="Skill - Shielding",
        name="Basic Blockade",
        materials=(
            Material(25, "Griffin Feather"),
            Material(10, "Striped Fur"),
            Material(5, "Elven Bone"),
        ),
    ),
    Imbuement(
        category="Skill - Shielding",
        name="Intricate Blockade",
        materials=(
            Material(25, "Griffin Feather"),
            Material(20, "Striped Fur"),
            Material(10, "Elven Bone"),
        ),
    ),
    Imbuement(
        category="Skill - Shielding",
        name="Powerful Blockade",
        materials=(
            Material(50, "Griffin Feather"),
            Material(30, "Striped Fur"),
            Material(20, "Elven Bone"),
        ),
    ),
)


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
            self.open_search(material.name)

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
            item_label.bind("<Button-1>", lambda _event, name=material.name: self.open_search(name))

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
