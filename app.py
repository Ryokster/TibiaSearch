import json
import re
import sys
import threading
import uuid
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable
from urllib.parse import quote, urlencode

from history import HistoryManager
from imbuable_items_data import IMBUABLE_ITEMS_RESOURCE
from imbuements_data import IMBUEMENTS_RESOURCE
from scripts.refresh_market_prices import refresh_market_prices

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
EQUIPMENT_TAGS = (
    "Normal",
    "Erdresi",
    "Feuerresi",
    "Eisresi",
    "Energiresi",
    "Todesresi",
    "Physresi",
)


@dataclass(frozen=True)
class EquipmentItem:
    name: str
    slot: str
    imbue_slots: int
    category: str


@dataclass(frozen=True)
class TibiaItem:
    name: str
    slug: str
    url: str
    weight: float
    category: str
    providers: tuple[str, ...]
    gold: int


SLOT_ALLOWED_CATEGORIES = {
    "head": {"HELMET"},
    "armor": {"ARMOR"},
    "legs": {"LEGS"},
    "shield": {"SHIELD"},
    "weapon": {"WEAPON_1H", "WEAPON_2H"},
}


def _normalize_number(value: str) -> str:
    return value.replace(",", "").strip()


def _parse_int_safe(value: str) -> int:
    cleaned = _normalize_number(value)
    if cleaned in {"", "-", "+"}:
        return 0
    try:
        return int(cleaned)
    except (TypeError, ValueError):
        return 0


def _parse_float_safe(value: str) -> float | None:
    cleaned = _normalize_number(value)
    if cleaned in {"", "-", "+"}:
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _format_number(value: float, decimals: int = 0) -> str:
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _parse_duration(value: str) -> int:
    match = re.match(r"^(\d{1,2}):(\d{2})h$", value.strip())
    if not match:
        return 0
    hours = int(match.group(1))
    minutes = int(match.group(2))
    return hours * 3600 + minutes * 60


def _parse_session_log(raw_text: str) -> dict[str, object]:
    result: dict[str, object] = {
        "start_dt": None,
        "end_dt": None,
        "duration_seconds": 0,
        "xp_total": 0,
        "xp_per_hour": None,
        "loot_total": 0,
        "supplies_total": 0,
        "balance_total": 0,
        "damage_total": 0,
        "damage_per_hour": None,
        "healing_total": 0,
        "healing_per_hour": None,
        "kills_breakdown": {},
        "kills_count": 0,
        "looted_items_breakdown": {},
    }

    text = raw_text.strip()

    session_match = re.search(
        r"Session data:\s*From\s*(\d{4}-\d{2}-\d{2}),\s*(\d{2}:\d{2}:\d{2})\s*to\s*(\d{4}-\d{2}-\d{2}),\s*(\d{2}:\d{2}:\d{2})",
        text,
        re.DOTALL,
    )
    if session_match:
        start_str = f"{session_match.group(1)}, {session_match.group(2)}"
        end_str = f"{session_match.group(3)}, {session_match.group(4)}"
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d, %H:%M:%S")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d, %H:%M:%S")
            if end_dt < start_dt:
                end_dt += timedelta(hours=24)
            result["start_dt"] = start_dt.isoformat()
            result["end_dt"] = end_dt.isoformat()
            result["duration_seconds"] = int((end_dt - start_dt).total_seconds())
        except ValueError:
            pass
    else:
        duration_match = re.search(r"Session:\s*(\d{1,2}):(\d{2})h", text, re.DOTALL)
        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2))
            result["duration_seconds"] = hours * 3600 + minutes * 60

    def _find_number(label: str) -> str | None:
        match = re.search(rf"{label}:\s*([-\d,]+)", text, re.DOTALL)
        if not match:
            return None
        return match.group(1)

    xp_total_raw = _find_number("XP Gain")
    xp_per_hour_raw = _find_number("XP/h")
    loot_raw = _find_number("Loot")
    supplies_raw = _find_number("Supplies")
    balance_raw = _find_number("Balance")
    damage_raw = _find_number("Damage")
    damage_per_hour_raw = _find_number("Damage/h")
    healing_raw = _find_number("Healing")
    healing_per_hour_raw = _find_number("Healing/h")

    result["xp_total"] = _parse_int_safe(xp_total_raw or "0")
    result["xp_per_hour"] = _parse_float_safe(xp_per_hour_raw) if xp_per_hour_raw else None
    result["loot_total"] = _parse_int_safe(loot_raw or "0")
    result["supplies_total"] = _parse_int_safe(supplies_raw or "0")
    result["balance_total"] = _parse_int_safe(balance_raw or "0")
    result["damage_total"] = _parse_int_safe(damage_raw or "0")
    result["damage_per_hour"] = _parse_float_safe(damage_per_hour_raw) if damage_per_hour_raw else None
    result["healing_total"] = _parse_int_safe(healing_raw or "0")
    result["healing_per_hour"] = _parse_float_safe(healing_per_hour_raw) if healing_per_hour_raw else None

    kills_breakdown: dict[str, int] = {}
    kills_start = text.find("Killed Monsters:")
    if kills_start != -1:
        kills_end = text.find("Looted Items:", kills_start)
        kills_segment = text[kills_start:kills_end if kills_end != -1 else len(text)]
        for count_text, name in re.findall(r"(\d+)x\s+([A-Za-z][A-Za-z '\-]+)", kills_segment):
            count = _parse_int_safe(count_text)
            key = name.strip().lower()
            if not key:
                continue
            kills_breakdown[key] = kills_breakdown.get(key, 0) + count
    result["kills_breakdown"] = kills_breakdown
    result["kills_count"] = sum(kills_breakdown.values())

    loot_breakdown: dict[str, int] = {}
    loot_start = text.find("Looted Items:")
    if loot_start != -1:
        loot_segment = text[loot_start:]
        for count_text, name in re.findall(r"(\d+)x\s+([A-Za-z][A-Za-z '\-]+)", loot_segment):
            count = _parse_int_safe(count_text)
            key = name.strip()
            if not key:
                continue
            loot_breakdown[key] = loot_breakdown.get(key, 0) + count
    result["looted_items_breakdown"] = loot_breakdown

    duration_seconds = int(result.get("duration_seconds", 0) or 0)
    duration_hours = duration_seconds / 3600 if duration_seconds else 0
    if duration_hours:
        if result["xp_per_hour"] is None:
            result["xp_per_hour"] = result["xp_total"] / duration_hours
        if result["damage_per_hour"] is None:
            result["damage_per_hour"] = result["damage_total"] / duration_hours
        if result["healing_per_hour"] is None:
            result["healing_per_hour"] = result["healing_total"] / duration_hours
    return result


def _build_category_slot_map() -> dict[str, str]:
    category_map: dict[str, str] = {}
    for slot, categories in SLOT_ALLOWED_CATEGORIES.items():
        for category in categories:
            category_map[category] = slot
    return category_map


def build_items(resource: dict[str, object]) -> tuple[EquipmentItem, ...]:
    items: list[EquipmentItem] = []
    category_slot_map = _build_category_slot_map()
    for category in resource.get("categories", []):
        if not isinstance(category, dict):
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
            item_category = str(entry.get("category", "")).strip()
            slot = category_slot_map.get(item_category)
            if not slot:
                continue
            items.append(
                EquipmentItem(
                    name=name,
                    slot=slot,
                    imbue_slots=imbue_slots,
                    category=item_category,
                )
            )
    items.sort(key=lambda item: (item.slot, item.name))
    return tuple(items)


ITEMS = build_items(IMBUABLE_ITEMS_RESOURCE)


def load_json_resource(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def build_tibia_items(resource: dict[str, object]) -> tuple[TibiaItem, ...]:
    items: list[TibiaItem] = []
    for entry in resource.get("items", []):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        slug = str(entry.get("slug", "")).strip()
        url = str(entry.get("url", "")).strip()
        category = str(entry.get("category", "")).strip()
        gold = entry.get("gold", 0)
        try:
            gold_value = int(gold)
        except (TypeError, ValueError):
            gold_value = 0
        weight = entry.get("weight", 0)
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = 0.0
        providers = entry.get("providers", [])
        if not isinstance(providers, list):
            providers = []
        providers_tuple = tuple(str(provider).strip() for provider in providers if str(provider).strip())
        items.append(
            TibiaItem(
                name=name,
                slug=slug,
                url=url,
                weight=weight,
                category=category,
                providers=providers_tuple,
                gold=gold_value,
            )
        )
    items.sort(key=lambda item: item.name.lower())
    return tuple(items)


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


class ItemPriceStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.prices: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            prices = data.get("prices", {})
            if isinstance(prices, dict):
                self.prices = {str(k): int(v) for k, v in prices.items()}
        except Exception:
            self.prices = {}

    def _save(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                json.dump({"prices": self.prices}, handle, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_price(self, item_name: str) -> int:
        return int(self.prices.get(item_name, 0))

    def set_price(self, item_name: str, price: int) -> None:
        self.prices[item_name] = max(0, int(price))
        self._save()


class HuntStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.hunts: list[dict[str, object]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            data = {}
        hunts = []
        for entry in data.get("hunts", []):
            if not isinstance(entry, dict):
                continue
            hunts.append(self._normalize_entry(entry))
        self.hunts = hunts

    def _normalize_entry(self, entry: dict[str, object]) -> dict[str, object]:
        hunt_id = str(entry.get("id") or uuid.uuid4())
        name = str(entry.get("name", "")).strip() or "Unnamed"
        equipment_tag = str(entry.get("equipment_tag", "Normal"))
        if equipment_tag not in EQUIPMENT_TAGS:
            equipment_tag = "Normal"
        character_id = str(entry.get("character_id") or "Default").strip() or "Default"
        raw_log_text = str(entry.get("raw_log_text", "")).strip()
        created_at = str(entry.get("created_at") or datetime.now().isoformat(timespec="seconds"))
        updated_at = str(entry.get("updated_at") or created_at)
        parsed = _parse_session_log(raw_log_text)
        normalized: dict[str, object] = {
            "id": hunt_id,
            "name": name,
            "character_id": character_id,
            "equipment_tag": equipment_tag,
            "raw_log_text": raw_log_text,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        normalized.update(parsed)
        return normalized

    def _save(self) -> None:
        payload = {"hunts": self.hunts}
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_hunt(self, name: str, character_id: str, equipment_tag: str, raw_log_text: str) -> str:
        now = datetime.now().isoformat(timespec="seconds")
        hunt_id = str(uuid.uuid4())
        parsed = _parse_session_log(raw_log_text)
        entry: dict[str, object] = {
            "id": hunt_id,
            "name": name,
            "character_id": character_id,
            "equipment_tag": equipment_tag,
            "raw_log_text": raw_log_text,
            "created_at": now,
            "updated_at": now,
        }
        entry.update(parsed)
        self.hunts.append(entry)
        self._save()
        return hunt_id

    def update_hunt(self, hunt_id: str, updates: dict[str, object]) -> None:
        for entry in self.hunts:
            if entry.get("id") == hunt_id:
                entry.update(updates)
                entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
                self._save()
                return

    def update_hunt_log(self, hunt_id: str, raw_log_text: str) -> None:
        parsed = _parse_session_log(raw_log_text)
        updates = {"raw_log_text": raw_log_text}
        updates.update(parsed)
        self.update_hunt(hunt_id, updates)

    def get_hunt(self, hunt_id: str) -> dict[str, object] | None:
        for entry in self.hunts:
            if entry.get("id") == hunt_id:
                return entry
        return None

class TibiaSearchApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tibia Search")
        self.root.resizable(True, True)
        self.root.minsize(620, 420)

        self.base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        self.tibia_resource_dir = self.base_dir / "resources" / "tibia"
        self.history_path = self.base_dir / "history.json"
        self.state_path = self.base_dir / "imbuements_state.json"
        self.items_state_path = self.base_dir / "items_state.json"
        self.character_path = self.base_dir / "characters_state.json"
        self.hunt_path = self.base_dir / "hunts_state.json"
        self.history = HistoryManager(self.history_path)
        self.store = ImbuementStore(self.state_path)
        self.item_price_store = ItemPriceStore(self.items_state_path)
        self.character_store = CharacterStore(self.character_path)
        self.hunt_store = HuntStore(self.hunt_path)
        self.creature_products = build_tibia_items(
            load_json_resource(self.tibia_resource_dir / "creature_products.json")
        )
        self.delivery_items = build_tibia_items(
            load_json_resource(self.tibia_resource_dir / "delivery_task_items.json")
        )

        self.always_on_top = False
        self.active_imbuement: Imbuement | None = None
        self.material_vars: dict[str, tk.StringVar] = {}
        self.material_rows: list[tuple[Material, ttk.Label]] = []
        self.character_window: "CharacterWindow" | None = None
        self.items_list_items: list[TibiaItem] = []
        self.items_tree_items: dict[str, TibiaItem] = {}
        self.active_hunt_id: str | None = None
        self.hunt_log_update_after: str | None = None
        self.hunt_detail_vars: dict[str, tk.StringVar] = {}
        self.hunt_rate_vars: dict[str, tk.StringVar] = {}
        self.hunt_equipment_var = tk.StringVar(value=EQUIPMENT_TAGS[0])
        self.hunt_character_var = tk.StringVar()
        self.hunt_kills_list: tk.Listbox | None = None
        self.hunt_loot_list: tk.Listbox | None = None
        self._suppress_hunt_equipment_change = False
        self._suppress_hunt_character_change = False
        self._suppress_hunt_log_change = False
        self._price_editor: ttk.Entry | None = None
        self.request_log: list[str] = []

        self._build_ui()
        self._bind_events()
        self._refresh_history_list()
        self._populate_imbuements()
        self._select_first_imbuement()
        self._start_market_refresh()

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

        self.log_button = ttk.Button(top_frame, text="Log", width=6, command=self.open_request_log)
        self.log_button.grid(row=0, column=4, padx=(6, 0))

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        self.history_tab = ttk.Frame(self.notebook)
        self.imbuements_tab = ttk.Frame(self.notebook)
        self.items_tab = ttk.Frame(self.notebook)
        self.hunts_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.history_tab, text="History")
        self.notebook.add(self.imbuements_tab, text="Imbuements")
        self.notebook.add(self.items_tab, text="Tibia Items")
        self.notebook.add(self.hunts_tab, text="Hunts")

        self._build_history_tab()
        self._build_imbuements_tab()
        self._build_items_tab()
        self._build_hunts_tab()

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

    def _build_items_tab(self) -> None:
        self.items_tab.columnconfigure(0, weight=1)
        self.items_tab.rowconfigure(1, weight=1)

        controls_frame = ttk.Frame(self.items_tab)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        controls_frame.columnconfigure(2, weight=1)

        self.items_filter_var = tk.StringVar(value="creature")
        creature_button = ttk.Radiobutton(
            controls_frame,
            text="Creature Products",
            variable=self.items_filter_var,
            value="creature",
        )
        delivery_button = ttk.Radiobutton(
            controls_frame,
            text="Delivery Items",
            variable=self.items_filter_var,
            value="delivery",
        )
        creature_button.grid(row=0, column=0, sticky="w")
        delivery_button.grid(row=0, column=1, sticky="w", padx=(6, 0))

        self.items_search_var = tk.StringVar()
        search_entry = ttk.Entry(controls_frame, textvariable=self.items_search_var)
        search_entry.grid(row=0, column=2, sticky="ew", padx=(12, 0))

        list_frame = ttk.Frame(self.items_tab)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.items_tree = ttk.Treeview(
            list_frame,
            columns=("name", "providers", "trader_price", "market_price"),
            show="headings",
        )
        self.items_tree.heading("name", text="Item")
        self.items_tree.heading("providers", text="Provider")
        self.items_tree.heading("trader_price", text="Händler VK")
        self.items_tree.heading("market_price", text="Auktionshaus VK")
        self.items_tree.column("name", width=220, anchor="w")
        self.items_tree.column("providers", width=300, anchor="w")
        self.items_tree.column("trader_price", width=110, anchor="e")
        self.items_tree.column("market_price", width=130, anchor="e")
        self.items_tree.grid(row=0, column=0, sticky="nsew")

        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.items_tree.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.items_tree.configure(yscrollcommand=list_scroll.set)

        self.items_filter_var.trace_add("write", lambda *_args: self._refresh_items_list())
        self.items_search_var.trace_add("write", lambda *_args: self._refresh_items_list())
        self._refresh_items_list()

    def _build_hunts_tab(self) -> None:
        self.hunts_tab.columnconfigure(0, weight=1)
        self.hunts_tab.rowconfigure(1, weight=1)

        header_frame = ttk.Frame(self.hunts_tab)
        header_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="Hunts").grid(row=0, column=0, sticky="w")
        ttk.Button(header_frame, text="＋ Hunt hinzufügen", command=self._open_add_hunt_dialog).grid(
            row=0, column=1, sticky="e"
        )

        list_frame = ttk.Frame(self.hunts_tab)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 6))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.hunts_tree = ttk.Treeview(
            list_frame,
            columns=("name", "character", "equipment", "xp"),
            show="headings",
            height=6,
        )
        self.hunts_tree.heading("name", text="Hunt-Name")
        self.hunts_tree.heading("character", text="Character")
        self.hunts_tree.heading("equipment", text="Ausrüstung")
        self.hunts_tree.heading("xp", text="XP Gain")
        self.hunts_tree.column("name", width=220, anchor="w")
        self.hunts_tree.column("character", width=140, anchor="center")
        self.hunts_tree.column("equipment", width=120, anchor="center")
        self.hunts_tree.column("xp", width=120, anchor="e")
        self.hunts_tree.grid(row=0, column=0, sticky="nsew")

        hunt_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.hunts_tree.yview)
        hunt_scroll.grid(row=0, column=1, sticky="ns")
        self.hunts_tree.configure(yscrollcommand=hunt_scroll.set)

        self.hunts_notebook = ttk.Notebook(self.hunts_tab)
        self.hunts_notebook.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self.hunt_details_tab = ttk.Frame(self.hunts_notebook)
        self.hunt_stats_tab = ttk.Frame(self.hunts_notebook)
        self.hunts_notebook.add(self.hunt_details_tab, text="Hunt-Details")
        self.hunts_notebook.add(self.hunt_stats_tab, text="Statistiken")

        self._build_hunt_details_tab()
        self._build_hunt_stats_tab()
        self._refresh_hunts_list()

    def _build_hunt_details_tab(self) -> None:
        self.hunt_details_tab.columnconfigure(0, weight=1)
        self.hunt_details_tab.rowconfigure(2, weight=1)

        equipment_frame = ttk.Frame(self.hunt_details_tab)
        equipment_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        equipment_frame.columnconfigure(1, weight=1)
        ttk.Label(equipment_frame, text="Character:").grid(row=0, column=0, sticky="w")
        self.hunt_character_combo = ttk.Combobox(
            equipment_frame,
            textvariable=self.hunt_character_var,
            state="readonly",
            width=18,
        )
        self.hunt_character_combo.grid(row=0, column=1, sticky="w", padx=(6, 0))

        ttk.Label(equipment_frame, text="Ausrüstung:").grid(row=1, column=0, sticky="w")
        self.hunt_equipment_combo = ttk.Combobox(
            equipment_frame,
            textvariable=self.hunt_equipment_var,
            values=EQUIPMENT_TAGS,
            state="readonly",
            width=18,
        )
        self.hunt_equipment_combo.grid(row=1, column=1, sticky="w", padx=(6, 0))

        stats_frame = ttk.Frame(self.hunt_details_tab)
        stats_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=(4, 6))
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.columnconfigure(1, weight=1)

        left_frame = ttk.LabelFrame(stats_frame, text="Ist-Werte")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_frame.columnconfigure(1, weight=1)

        right_frame = ttk.LabelFrame(stats_frame, text="Pro Stunde")
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(1, weight=1)

        detail_fields = [
            ("Dauer", "duration"),
            ("Kills (TOTAL)", "kills"),
            ("XP Gain", "xp_total"),
            ("Loot", "loot_total"),
            ("Supplies", "supplies_total"),
            ("Balance", "balance_total"),
            ("Damage", "damage_total"),
            ("Healing", "healing_total"),
        ]
        row = 0
        for label, key in detail_fields:
            ttk.Label(left_frame, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=6, pady=2)
            var = tk.StringVar(value="—")
            self.hunt_detail_vars[key] = var
            ttk.Label(left_frame, textvariable=var).grid(row=row, column=1, sticky="e", padx=6, pady=2)
            row += 1
            if key == "kills":
                kills_frame = ttk.LabelFrame(left_frame, text="Kills (pro Kreatur)")
                kills_frame.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=6, pady=(0, 6))
                kills_frame.columnconfigure(0, weight=1)
                kills_frame.rowconfigure(0, weight=1)
                self.hunt_kills_list = tk.Listbox(kills_frame, height=5)
                self.hunt_kills_list.grid(row=0, column=0, sticky="nsew")
                kills_scroll = ttk.Scrollbar(kills_frame, orient="vertical", command=self.hunt_kills_list.yview)
                kills_scroll.grid(row=0, column=1, sticky="ns")
                self.hunt_kills_list.configure(yscrollcommand=kills_scroll.set)
                left_frame.rowconfigure(row, weight=1)
                row += 1

        loot_frame = ttk.LabelFrame(left_frame, text="Looted Items")
        loot_frame.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=6, pady=(0, 6))
        loot_frame.columnconfigure(0, weight=1)
        loot_frame.rowconfigure(0, weight=1)
        self.hunt_loot_list = tk.Listbox(loot_frame, height=5)
        self.hunt_loot_list.grid(row=0, column=0, sticky="nsew")
        loot_scroll = ttk.Scrollbar(loot_frame, orient="vertical", command=self.hunt_loot_list.yview)
        loot_scroll.grid(row=0, column=1, sticky="ns")
        self.hunt_loot_list.configure(yscrollcommand=loot_scroll.set)
        left_frame.rowconfigure(row, weight=1)

        rate_fields = [
            ("XP/h", "xp_per_hour"),
            ("Balance/h", "balance_per_hour"),
            ("Kills/h", "kills_per_hour"),
            ("Damage/h", "damage_per_hour"),
            ("Healing/h", "healing_per_hour"),
        ]
        for row, (label, key) in enumerate(rate_fields):
            ttk.Label(right_frame, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=6, pady=2)
            var = tk.StringVar(value="—")
            self.hunt_rate_vars[key] = var
            ttk.Label(right_frame, textvariable=var).grid(row=row, column=1, sticky="e", padx=6, pady=2)

        log_frame = ttk.LabelFrame(self.hunt_details_tab, text="Session-Log")
        log_frame.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.hunt_log_text = tk.Text(log_frame, height=10, wrap="word")
        self.hunt_log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.hunt_log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.hunt_log_text.configure(yscrollcommand=log_scroll.set)
        self.hunt_log_text.bind("<<Modified>>", self._on_hunt_log_modified)

    def _build_hunt_stats_tab(self) -> None:
        self.hunt_stats_tab.columnconfigure(0, weight=1)
        self.hunt_stats_tab.columnconfigure(1, weight=1)
        self.hunt_stats_tab.rowconfigure(0, weight=1)

        profit_frame = ttk.LabelFrame(self.hunt_stats_tab, text="Top 5 nach Gold (Profit)")
        profit_frame.grid(row=0, column=0, sticky="nsew", padx=(6, 3), pady=6)
        profit_frame.columnconfigure(0, weight=1)
        profit_frame.rowconfigure(0, weight=1)

        self.hunt_profit_tree = ttk.Treeview(
            profit_frame,
            columns=("name", "character", "equipment", "balance"),
            show="headings",
            height=5,
        )
        self.hunt_profit_tree.heading("name", text="Hunt-Name")
        self.hunt_profit_tree.heading("character", text="Character")
        self.hunt_profit_tree.heading("equipment", text="Ausrüstung")
        self.hunt_profit_tree.heading("balance", text="Balance")
        self.hunt_profit_tree.column("name", width=180, anchor="w")
        self.hunt_profit_tree.column("character", width=140, anchor="center")
        self.hunt_profit_tree.column("equipment", width=120, anchor="center")
        self.hunt_profit_tree.column("balance", width=120, anchor="e")
        self.hunt_profit_tree.grid(row=0, column=0, sticky="nsew")

        profit_scroll = ttk.Scrollbar(profit_frame, orient="vertical", command=self.hunt_profit_tree.yview)
        profit_scroll.grid(row=0, column=1, sticky="ns")
        self.hunt_profit_tree.configure(yscrollcommand=profit_scroll.set)

        xp_frame = ttk.LabelFrame(self.hunt_stats_tab, text="Top 5 nach XP")
        xp_frame.grid(row=0, column=1, sticky="nsew", padx=(3, 6), pady=6)
        xp_frame.columnconfigure(0, weight=1)
        xp_frame.rowconfigure(0, weight=1)

        self.hunt_xp_tree = ttk.Treeview(
            xp_frame,
            columns=("name", "character", "equipment", "xp"),
            show="headings",
            height=5,
        )
        self.hunt_xp_tree.heading("name", text="Hunt-Name")
        self.hunt_xp_tree.heading("character", text="Character")
        self.hunt_xp_tree.heading("equipment", text="Ausrüstung")
        self.hunt_xp_tree.heading("xp", text="XP Gain")
        self.hunt_xp_tree.column("name", width=180, anchor="w")
        self.hunt_xp_tree.column("character", width=140, anchor="center")
        self.hunt_xp_tree.column("equipment", width=120, anchor="center")
        self.hunt_xp_tree.column("xp", width=120, anchor="e")
        self.hunt_xp_tree.grid(row=0, column=0, sticky="nsew")

        xp_scroll = ttk.Scrollbar(xp_frame, orient="vertical", command=self.hunt_xp_tree.yview)
        xp_scroll.grid(row=0, column=1, sticky="ns")
        self.hunt_xp_tree.configure(yscrollcommand=xp_scroll.set)

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

        self.items_tree.bind("<Double-Button-1>", self._on_items_tree_double_click)
        self.items_tree.bind("<Return>", self._open_selected_item)

        self.hunts_tree.bind("<<TreeviewSelect>>", self._on_hunt_select)
        self.hunt_profit_tree.bind("<<TreeviewSelect>>", self._on_hunt_stats_select)
        self.hunt_xp_tree.bind("<<TreeviewSelect>>", self._on_hunt_stats_select)
        self.hunt_equipment_var.trace_add("write", self._on_hunt_equipment_change)
        self.hunt_character_var.trace_add("write", self._on_hunt_character_change)

    def clear_entry(self) -> None:
        self.search_entry.delete(0, tk.END)

    def _active_items(self) -> tuple[TibiaItem, ...]:
        if self.items_filter_var.get() == "delivery":
            return self.delivery_items
        return self.creature_products

    def _refresh_items_list(self) -> None:
        query = self.items_search_var.get().strip().casefold()
        items = self._active_items()
        self.items_tree.delete(*self.items_tree.get_children())
        self.items_list_items = []
        self.items_tree_items = {}
        for item in items:
            providers_text = ", ".join(item.providers)
            search_text = f"{item.name} {providers_text}".casefold()
            if query and query not in search_text:
                continue
            name_display = item.name
            if not item.url:
                name_display = f"{name_display} (no link)"
            trader_display = self._format_price(self.item_price_store.get_price(item.name))
            market_display = self._format_price(item.gold)
            row_id = str(len(self.items_list_items))
            self.items_tree.insert(
                "",
                tk.END,
                iid=row_id,
                values=(name_display, providers_text, trader_display, market_display),
            )
            self.items_list_items.append(item)
            self.items_tree_items[row_id] = item

    def _format_price(self, value: int) -> str:
        if value <= 0:
            return ""
        return _format_number(value)

    def _open_selected_item(self, _event: tk.Event) -> None:
        selection = self.items_tree.selection()
        if not selection:
            return
        item = self.items_tree_items.get(selection[0])
        if not item:
            return
        if not item.url:
            return
        self._open_url(item.url, f"Item: {item.name}")

    def _on_items_tree_double_click(self, event: tk.Event) -> None:
        column = self.items_tree.identify_column(event.x)
        if column == "#3":
            self._begin_price_edit(event)
        else:
            self._open_selected_item(event)

    def _begin_price_edit(self, event: tk.Event) -> None:
        row_id = self.items_tree.identify_row(event.y)
        if not row_id:
            return
        column = self.items_tree.identify_column(event.x)
        if column != "#3":
            return
        item = self.items_tree_items.get(row_id)
        if not item:
            return
        bbox = self.items_tree.bbox(row_id, column)
        if not bbox:
            return
        if self._price_editor is not None:
            self._price_editor.destroy()
            self._price_editor = None
        x, y, width, height = bbox
        editor = ttk.Entry(self.items_tree)
        current_price = self.item_price_store.get_price(item.name)
        editor.insert(0, str(current_price) if current_price else "")
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        editor.select_range(0, tk.END)
        editor.bind("<Return>", lambda _event: self._commit_price_edit(row_id))
        editor.bind("<FocusOut>", lambda _event: self._commit_price_edit(row_id))
        self._price_editor = editor

    def _commit_price_edit(self, row_id: str) -> None:
        if self._price_editor is None:
            return
        editor = self._price_editor
        self._price_editor = None
        item = self.items_tree_items.get(row_id)
        if not item:
            editor.destroy()
            return
        raw_value = editor.get().strip()
        price_value = self._parse_price_input(raw_value)
        self.item_price_store.set_price(item.name, price_value)
        self.items_tree.set(row_id, "trader_price", self._format_price(price_value))
        editor.destroy()

    def _parse_price_input(self, value: str) -> int:
        if not value:
            return 0
        cleaned = value.replace(".", "").replace(",", "").strip()
        if cleaned in {"", "-", "+"}:
            return 0
        try:
            return int(cleaned)
        except (TypeError, ValueError):
            return 0

    def _open_add_hunt_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Hunt hinzufügen")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        name_var = tk.StringVar()
        character_var = tk.StringVar(value=self.character_store.get_active().get("name", "Default"))
        equipment_var = tk.StringVar(value=EQUIPMENT_TAGS[0])

        form_frame = ttk.Frame(dialog, padding=10)
        form_frame.grid(row=0, column=0, sticky="nsew")
        form_frame.columnconfigure(1, weight=1)

        ttk.Label(form_frame, text="Name:").grid(row=0, column=0, sticky="w", pady=4)
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=40)
        name_entry.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(form_frame, text="Character:").grid(row=1, column=0, sticky="w", pady=4)
        character_combo = ttk.Combobox(
            form_frame,
            textvariable=character_var,
            values=self._character_choices(),
            state="readonly",
            width=20,
        )
        character_combo.grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(form_frame, text="Ausrüstung:").grid(row=2, column=0, sticky="w", pady=4)
        equipment_combo = ttk.Combobox(
            form_frame,
            textvariable=equipment_var,
            values=EQUIPMENT_TAGS,
            state="readonly",
            width=20,
        )
        equipment_combo.grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(form_frame, text="Session-Log:").grid(row=3, column=0, sticky="nw", pady=4)
        log_text = tk.Text(form_frame, height=10, width=50, wrap="word")
        log_text.grid(row=3, column=1, sticky="ew", pady=4)

        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=4, column=1, sticky="e", pady=(6, 0))
        ttk.Button(button_frame, text="Anlegen", command=lambda: on_submit()).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(button_frame, text="Abbrechen", command=dialog.destroy).grid(row=0, column=1)

        def on_submit() -> None:
            name = name_var.get().strip()
            raw_log = log_text.get("1.0", tk.END).strip()
            equipment_tag = equipment_var.get()
            character_id = character_var.get().strip()
            if not name:
                messagebox.showwarning("Fehlender Name", "Bitte einen Hunt-Namen angeben.")
                return
            if not character_id:
                messagebox.showwarning("Fehlender Character", "Bitte einen Character auswählen.")
                return
            if not raw_log:
                messagebox.showwarning("Fehlender Log", "Bitte den Session-Log einfügen.")
                return
            hunt_id = self.hunt_store.add_hunt(name, character_id, equipment_tag, raw_log)
            self._refresh_hunts_list(select_id=hunt_id)
            dialog.destroy()

        name_entry.focus_set()

    def _refresh_hunts_list(self, select_id: str | None = None) -> None:
        self.hunts_tree.delete(*self.hunts_tree.get_children())
        hunts = sorted(
            self.hunt_store.hunts,
            key=lambda entry: self._hunt_sort_key(entry.get("created_at")),
            reverse=True,
        )
        for entry in hunts:
            xp_total = int(entry.get("xp_total") or 0)
            character_name = self._display_character_name(entry.get("character_id"))
            self.hunts_tree.insert(
                "",
                tk.END,
                iid=str(entry.get("id")),
                values=(entry.get("name"), character_name, entry.get("equipment_tag"), _format_number(xp_total)),
            )
        target_id = select_id or self.active_hunt_id
        if target_id and self.hunts_tree.exists(target_id):
            self.hunts_tree.selection_set(target_id)
        elif hunts:
            first_id = str(hunts[0].get("id"))
            self.hunts_tree.selection_set(first_id)
        else:
            self.active_hunt_id = None
            self._refresh_hunt_details()
        if target_id and self.hunts_tree.exists(target_id):
            self.active_hunt_id = target_id
        elif hunts:
            self.active_hunt_id = str(hunts[0].get("id"))
        self._refresh_hunt_details()
        self._refresh_hunt_stats()

    def _hunt_sort_key(self, value: object) -> datetime:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return datetime.min
        return datetime.min

    def _character_choices(self, current: str | None = None) -> list[str]:
        names = self.character_store.names()
        if not names:
            names = ["Default"]
        if current and current not in names:
            return [current, *names]
        return names

    def _display_character_name(self, value: object) -> str:
        name = str(value or "").strip()
        return name or "—"

    def _on_hunt_select(self, _event: tk.Event) -> None:
        selection = self.hunts_tree.selection()
        if not selection:
            return
        self._select_hunt(selection[0])

    def _select_hunt(self, hunt_id: str) -> None:
        if self.active_hunt_id == hunt_id:
            return
        self.active_hunt_id = hunt_id
        if self.hunts_tree.exists(hunt_id):
            self.hunts_tree.selection_set(hunt_id)
        self._refresh_hunt_details()

    def _refresh_hunt_details(self) -> None:
        entry = self.hunt_store.get_hunt(self.active_hunt_id) if self.active_hunt_id else None
        if not entry:
            for var in self.hunt_detail_vars.values():
                var.set("—")
            for var in self.hunt_rate_vars.values():
                var.set("—")
            self._set_breakdown_list(self.hunt_kills_list, {})
            self._set_breakdown_list(self.hunt_loot_list, {})
            self._suppress_hunt_equipment_change = True
            self.hunt_equipment_var.set(EQUIPMENT_TAGS[0])
            self._suppress_hunt_equipment_change = False
            self._suppress_hunt_character_change = True
            self.hunt_character_var.set("")
            self._suppress_hunt_character_change = False
            self.hunt_equipment_combo.configure(state="disabled")
            self.hunt_character_combo.configure(state="disabled")
            self._set_hunt_log_text("")
            return

        raw_log = str(entry.get("raw_log_text", ""))
        if raw_log:
            self.hunt_store.update_hunt_log(str(entry.get("id")), raw_log)
            entry = self.hunt_store.get_hunt(self.active_hunt_id) or entry

        self.hunt_equipment_combo.configure(state="readonly")
        self._suppress_hunt_equipment_change = True
        self.hunt_equipment_var.set(str(entry.get("equipment_tag", "Normal")))
        self._suppress_hunt_equipment_change = False
        character_id = str(entry.get("character_id", "")).strip()
        self.hunt_character_combo.configure(values=self._character_choices(character_id), state="readonly")
        self._suppress_hunt_character_change = True
        if character_id:
            self.hunt_character_var.set(character_id)
        else:
            self.hunt_character_var.set(self._character_choices()[0])
        self._suppress_hunt_character_change = False
        self._set_hunt_log_text(str(entry.get("raw_log_text", "")))

        duration_seconds = int(entry.get("duration_seconds") or 0)
        duration_hours = duration_seconds / 3600 if duration_seconds else 0

        self.hunt_detail_vars["duration"].set(self._format_duration(duration_seconds))
        self.hunt_detail_vars["kills"].set(_format_number(int(entry.get("kills_count") or 0)))
        self.hunt_detail_vars["xp_total"].set(_format_number(int(entry.get("xp_total") or 0)))
        self.hunt_detail_vars["loot_total"].set(_format_number(int(entry.get("loot_total") or 0)))
        self.hunt_detail_vars["supplies_total"].set(_format_number(int(entry.get("supplies_total") or 0)))
        self.hunt_detail_vars["balance_total"].set(_format_number(int(entry.get("balance_total") or 0)))
        self.hunt_detail_vars["damage_total"].set(_format_number(int(entry.get("damage_total") or 0)))
        self.hunt_detail_vars["healing_total"].set(_format_number(int(entry.get("healing_total") or 0)))
        self._set_breakdown_list(self.hunt_kills_list, entry.get("kills_breakdown") or {})
        self._set_breakdown_list(self.hunt_loot_list, entry.get("looted_items_breakdown") or {})

        if duration_hours:
            xp_rate = entry.get("xp_per_hour")
            damage_rate = entry.get("damage_per_hour")
            healing_rate = entry.get("healing_per_hour")
            balance_rate = int(entry.get("balance_total") or 0) / duration_hours
            kills_rate = int(entry.get("kills_count") or 0) / duration_hours
            self.hunt_rate_vars["xp_per_hour"].set(self._format_rate(xp_rate))
            self.hunt_rate_vars["balance_per_hour"].set(self._format_rate(balance_rate))
            self.hunt_rate_vars["kills_per_hour"].set(self._format_rate(kills_rate))
            self.hunt_rate_vars["damage_per_hour"].set(self._format_rate(damage_rate))
            self.hunt_rate_vars["healing_per_hour"].set(self._format_rate(healing_rate))
        else:
            for key in self.hunt_rate_vars:
                self.hunt_rate_vars[key].set("—")

    def _set_breakdown_list(self, listbox: tk.Listbox | None, breakdown: dict[str, int]) -> None:
        if listbox is None:
            return
        listbox.delete(0, tk.END)
        if not breakdown:
            listbox.insert(tk.END, "—")
            return
        sorted_items = sorted(breakdown.items(), key=lambda item: (-item[1], item[0].lower()))
        for name, count in sorted_items:
            listbox.insert(tk.END, f"{_format_number(count)}x {name}")

    def _set_hunt_log_text(self, value: str) -> None:
        self._suppress_hunt_log_change = True
        self.hunt_log_text.delete("1.0", tk.END)
        if value:
            self.hunt_log_text.insert("1.0", value)
        self.hunt_log_text.edit_modified(False)
        self._suppress_hunt_log_change = False

    def _on_hunt_log_modified(self, _event: tk.Event) -> None:
        if self._suppress_hunt_log_change:
            self.hunt_log_text.edit_modified(False)
            return
        if not self.hunt_log_text.edit_modified():
            return
        self.hunt_log_text.edit_modified(False)
        if self.hunt_log_update_after:
            self.root.after_cancel(self.hunt_log_update_after)
        self.hunt_log_update_after = self.root.after(400, self._commit_hunt_log_update)

    def _commit_hunt_log_update(self) -> None:
        self.hunt_log_update_after = None
        if not self.active_hunt_id:
            return
        raw_log = self.hunt_log_text.get("1.0", tk.END).strip()
        self.hunt_store.update_hunt_log(self.active_hunt_id, raw_log)
        self._refresh_hunts_list(select_id=self.active_hunt_id)
        self._refresh_hunt_details()

    def _on_hunt_equipment_change(self, *_args: object) -> None:
        if self._suppress_hunt_equipment_change or not self.active_hunt_id:
            return
        equipment_tag = self.hunt_equipment_var.get()
        self.hunt_store.update_hunt(self.active_hunt_id, {"equipment_tag": equipment_tag})
        self._refresh_hunts_list(select_id=self.active_hunt_id)

    def _on_hunt_character_change(self, *_args: object) -> None:
        if self._suppress_hunt_character_change or not self.active_hunt_id:
            return
        character_id = self.hunt_character_var.get()
        self.hunt_store.update_hunt(self.active_hunt_id, {"character_id": character_id})
        self._refresh_hunts_list(select_id=self.active_hunt_id)

    def _refresh_hunt_stats(self) -> None:
        self.hunt_profit_tree.delete(*self.hunt_profit_tree.get_children())
        self.hunt_xp_tree.delete(*self.hunt_xp_tree.get_children())

        hunts = self.hunt_store.hunts
        top_profit = sorted(hunts, key=lambda entry: int(entry.get("balance_total") or 0), reverse=True)[:5]
        top_xp = sorted(hunts, key=lambda entry: int(entry.get("xp_total") or 0), reverse=True)[:5]

        for entry in top_profit:
            balance = int(entry.get("balance_total") or 0)
            character_name = self._display_character_name(entry.get("character_id"))
            self.hunt_profit_tree.insert(
                "",
                tk.END,
                iid=str(entry.get("id")),
                values=(entry.get("name"), character_name, entry.get("equipment_tag"), _format_number(balance)),
            )

        for entry in top_xp:
            xp_total = int(entry.get("xp_total") or 0)
            character_name = self._display_character_name(entry.get("character_id"))
            self.hunt_xp_tree.insert(
                "",
                tk.END,
                iid=str(entry.get("id")),
                values=(entry.get("name"), character_name, entry.get("equipment_tag"), _format_number(xp_total)),
            )

    def _on_hunt_stats_select(self, event: tk.Event) -> None:
        tree = event.widget
        selection = tree.selection()
        if not selection:
            return
        hunt_id = selection[0]
        self._select_hunt(hunt_id)
        self.hunts_notebook.select(self.hunt_details_tab)

    def _format_duration(self, seconds: int) -> str:
        if seconds <= 0:
            return "—"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _format_rate(self, value: object) -> str:
        if value is None:
            return "—"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "—"
        if abs(numeric - round(numeric)) < 0.01:
            return _format_number(round(numeric))
        return _format_number(numeric, decimals=2)

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
        self._open_url(target_url, "Search")

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
            self._open_url(fandom_article_url(material.name), f"Material: {material.name}")

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
                lambda _event, name=material.name: self._open_url(
                    fandom_article_url(name),
                    f"Material: {name}",
                ),
            )

            var = tk.StringVar(value=str(self.store.get_price(material.name)))
            self.material_vars[material.name] = var
            entry = ttk.Entry(self.materials_frame, textvariable=var, width=10, validate="key")
            entry.configure(validatecommand=(self.root.register(self._validate_price), "%P"))
            entry.grid(row=row, column=2, sticky="w", padx=(6, 6))
            var.trace_add("write", lambda _name, _index, _mode, m=material, v=var: self._on_price_change(m, v))

            row_total = ttk.Label(
                self.materials_frame,
                text=self._format_gp(material.qty * self.store.get_price(material.name)),
            )
            row_total.grid(row=row, column=3, sticky="e", pady=2)
            self.material_rows.append((material, row_total))

        self._update_total_label(imbuement)

    def _open_url(self, url: str, label: str) -> None:
        self._append_request_log(f"{label} -> {url}")
        webbrowser.open_new_tab(url)

    def _append_request_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.request_log.append(f"[{timestamp}] {message}")

    def _log_market_request(self, message: str) -> None:
        self.root.after(0, lambda: self._append_request_log(f"MarketRefresh: {message}"))

    def _start_market_refresh(self) -> None:
        def run() -> None:
            result = refresh_market_prices("Antica", log=self._log_market_request)
            if isinstance(result, dict) and "updated_items" in result:
                self.root.after(0, self._reload_market_items)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _reload_market_items(self) -> None:
        self.creature_products = build_tibia_items(
            load_json_resource(self.tibia_resource_dir / "creature_products.json")
        )
        self.delivery_items = build_tibia_items(
            load_json_resource(self.tibia_resource_dir / "delivery_task_items.json")
        )
        self._refresh_items_list()

    def open_request_log(self) -> None:
        log_window = tk.Toplevel(self.root)
        log_window.title("Request Log")
        log_window.geometry("700x400")
        log_window.minsize(500, 300)

        log_frame = ttk.Frame(log_window, padding=8)
        log_frame.pack(fill="both", expand=True)

        text = tk.Text(log_frame, wrap="word", state="normal")
        text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=text.yview)
        scrollbar.pack(side="right", fill="y")
        text.configure(yscrollcommand=scrollbar.set)

        if self.request_log:
            text.insert("1.0", "\n".join(self.request_log))
        else:
            text.insert("1.0", "No outgoing requests logged yet.")
        text.configure(state="disabled")

    def _validate_price(self, proposed: str) -> bool:
        return proposed.isdigit() or proposed == ""

    def _on_price_change(self, material: Material, var: tk.StringVar) -> None:
        value = var.get().strip()
        price = int(value) if value.isdigit() else 0
        self.store.set_price(material.name, price)
        self._update_material_totals()
        self._refresh_imbuement_totals()
        if self.character_window and self.character_window.window.winfo_exists():
            self.character_window.refresh_summary()

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
        self.character_window = CharacterWindow(
            self.root,
            self.character_store,
            self.store,
            self._on_character_window_closed,
        )

    def _on_character_window_closed(self) -> None:
        self.character_window = None


class CharacterWindow:
    def __init__(
        self,
        root: tk.Tk,
        store: CharacterStore,
        price_store: ImbuementStore,
        on_close: Callable[[], None],
    ) -> None:
        self.root = root
        self.store = store
        self.price_store = price_store
        self.on_close = on_close
        self.window = tk.Toplevel(root)
        self.window.title("Character Window")
        self.window.resizable(True, True)
        self.window.minsize(980, 640)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self.active_slot: str = EQUIPMENT_SLOTS[0]
        self.current_character_name: str = str(self.store.get_active()["name"])

        self.item_map = {item.name: item for item in ITEMS}
        self.items_by_slot: dict[str, list[EquipmentItem]] = {slot: [] for slot in EQUIPMENT_SLOTS}
        for item in ITEMS:
            if item.slot in self.items_by_slot:
                self.items_by_slot[item.slot].append(item)
        self.imbuement_map = {imbuement.key: imbuement for imbuement in IMBUEMENTS}

        self.character_var = tk.StringVar(value=self.current_character_name)
        self.stats_vars: dict[str, tk.StringVar] = {}
        self.stats_entries: dict[str, ttk.Entry] = {}
        self.stats_widgets: dict[str, tk.Widget] = {}
        self.equipment_frames: dict[str, tk.Frame] = {}
        self.equipment_labels: dict[str, dict[str, tk.Label]] = {}
        self.imbue_remove_buttons: dict[str, list[ttk.Button]] = {}
        self._summary_refresh_after_id: str | None = None

        self._build_ui()
        self._bind_events()
        self._load_character(self.current_character_name)
        self._queue_summary_refresh()

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

        self._populate_items_for_slot(self.active_slot)

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
        self._populate_items_for_slot(slot)

    def _populate_items_for_slot(self, slot: str) -> None:
        self.items_tree.delete(*self.items_tree.get_children())
        for item in self.items_by_slot.get(slot, []):
            self.items_tree.insert("", tk.END, iid=item.name, values=(item.name, item.slot, item.imbue_slots))

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
        self._queue_summary_refresh()

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
        self._queue_summary_refresh()

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
        self._queue_summary_refresh()

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
        self._queue_summary_refresh()

    def _clear_item(self, slot: str) -> None:
        character = self.store.get_active()
        equipment = character.get("equipment", {})
        equipment[slot] = {"item": None, "imbues": []}
        character["equipment"] = equipment
        self.store.update_character(self.current_character_name, character)
        self._refresh_equipment()
        self._queue_summary_refresh()

    def refresh_summary(self) -> None:
        self._queue_summary_refresh()

    def _queue_summary_refresh(self) -> None:
        if self._summary_refresh_after_id is not None:
            self.window.after_cancel(self._summary_refresh_after_id)
        self._summary_refresh_after_id = self.window.after_idle(self._refresh_summary)

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

    def _format_gp(self, value: int) -> str:
        return f"{value:,}".replace(",", ".") + " gp"

    def _refresh_summary(self) -> None:
        self._summary_refresh_after_id = None
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
            for key in sorted(
                imbue_counts,
                key=lambda k: self.imbuement_map.get(k).name if self.imbuement_map.get(k) else k,
            ):
                count = imbue_counts[key]
                imbuement = self.imbuement_map.get(key)
                name = imbuement.name if imbuement else key
                imbue_total = 0
                if imbuement:
                    for material in imbuement.materials:
                        total_qty = material.qty * count
                        price = self.price_store.get_price(material.name)
                        imbue_total += total_qty * price
                lines.append(f"{name} (x{count}) – Total: {self._format_gp(imbue_total)}")
                if imbuement:
                    for material in imbuement.materials:
                        total_qty = material.qty * count
                        price = self.price_store.get_price(material.name)
                        line_total = total_qty * price
                        lines.append(
                            f"  {total_qty} × {material.name} – {self._format_gp(price)}/Stk – {self._format_gp(line_total)}"
                        )
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
                    price = self.price_store.get_price(name)
                    total_qty = totals[name]
                    line_total = total_qty * price
                    lines.append(
                        f"  {name}: {total_qty} × {self._format_gp(price)}/Stk – {self._format_gp(line_total)}"
                    )

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
