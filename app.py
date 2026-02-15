import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
import winreg
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from history import HistoryManager
from imbuable_items_data import IMBUABLE_ITEMS_RESOURCE
from imbuements_data import IMBUEMENTS_RESOURCE
from scripts.refresh_market_prices import refresh_market_prices
from modules.credential_store import CredentialNotFoundError, CredentialStoreError, load_credentials
from modules.grid_overlay import GridOverlay
from modules.grid_cone_overlay import GridConeOverlay

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
VOCATIONS = ("Elder Druid", "Master Sorcerer", "Elite Knight", "Royal Paladin")
EQUIPMENT_TAGS = (
    "Normal",
    "Erdresi",
    "Feuerresi",
    "Eisresi",
    "Energiresi",
    "Todesresi",
    "Physresi",
)

GREEN_DJINN_BUYS: dict[str, tuple[tuple[str, int], ...]] = {
    "Yaman": (
        ("Ankh", 100),
        ("Dragon Necklace", 100),
        ("Dwarven Ring", 100),
        ("Energy Ring", 100),
        ("Glacial Rod", 6500),
        ("Hailstorm Rod", 3000),
        ("Life Ring", 50),
        ("Might Ring", 250),
        ("Moonlight Rod", 200),
        ("Muck Rod", 6000),
        ("Mysterious Fetish", 50),
        ("Necrotic Rod", 1000),
        ("Northwind Rod", 1500),
        ("Protection Amulet", 100),
        ("Ring of Healing", 100),
        ("Silver Amulet", 50),
        ("Snakebite Rod", 100),
        ("Springsprout Rod", 3600),
        ("Strange Talisman", 30),
        ("Terra Rod", 2000),
        ("Time Ring", 100),
        ("Underworld Rod", 4400),
    ),
    "Alesar": (
        ("Ancient Shield", 900),
        ("Black Shield", 800),
        ("Bonebreaker", 10000),
        ("Dark Armor", 400),
        ("Dark Helmet", 250),
        ("Dragon Hammer", 2000),
        ("Dreaded Cleaver", 15000),
        ("Earth Knight Axe", 2000),
        ("Energy Knight Axe", 2000),
        ("Fiery Knight Axe", 2000),
        ("Giant Sword", 17000),
        ("Haunted Blade", 8000),
        ("Icy Knight Axe", 2000),
        ("Knight Armor", 5000),
        ("Knight Axe", 2000),
        ("Knight Legs", 5000),
        ("Mystic Turban", 150),
        ("Onyx Flail", 22000),
        ("Ornamented Axe", 20000),
        ("Poison Dagger", 50),
        ("Scimitar", 150),
        ("Serpent Sword", 900),
        ("Skull Staff", 6000),
        ("Strange Helmet", 500),
        ("Titan Axe", 4000),
        ("Tower Shield", 8000),
        ("Vampire Shield", 15000),
        ("Warrior Helmet", 5000),
    ),
}

BLUE_DJINN_BUYS: dict[str, tuple[tuple[str, int], ...]] = {
    "Nah'Bob": (
        ("Angelic Axe", 5000),
        ("Blue Robe", 10000),
        ("Bonelord Shield", 1200),
        ("Boots of Haste", 30000),
        ("Broadsword", 500),
        ("Butcher's Axe", 18000),
        ("Crown Armor", 12000),
        ("Crown Helmet", 2500),
        ("Crown Legs", 12000),
        ("Crown Shield", 8000),
        ("Crusader Helmet", 6000),
        ("Dragon Lance", 9000),
        ("Dragon Shield", 4000),
        ("Earth Spike Sword", 1000),
        ("Earth War Hammer", 1200),
        ("Energy Spike Sword", 1000),
        ("Energy War Hammer", 1200),
        ("Fiery Spike Sword", 1000),
        ("Fiery War Hammer", 1200),
        ("Fire Axe", 8000),
        ("Fire Sword", 4000),
        ("Glorious Axe", 3000),
        ("Guardian Shield", 2000),
        ("Ice Rapier", 1000),
        ("Icy Spike Sword", 1000),
        ("Icy War Hammer", 1200),
        ("Noble Armor", 900),
        ("Obsidian Lance", 500),
        ("Phoenix Shield", 16000),
        ("Queen's Sceptre", 20000),
        ("Royal Helmet", 30000),
        ("Shadow Sceptre", 10000),
        ("Spike Sword", 1000),
        ("Thaian Sword", 16000),
        ("War Hammer", 1200),
    ),
    "Haroun": (
        ("Axe Ring", 100),
        ("Bronze Amulet", 50),
        ("Club Ring", 100),
        ("Elven Amulet", 100),
        ("Garlic Necklace", 50),
        ("Life Crystal", 50),
        ("Magic Light Wand", 35),
        ("Mind Stone", 100),
        ("Orb", 750),
        ("Power Ring", 50),
        ("Stealth Ring", 200),
        ("Stone Skin Amulet", 500),
        ("Sword Ring", 100),
        ("Wand of Cosmic Energy", 2000),
        ("Wand of Decay", 1000),
        ("Wand of Defiance", 6500),
        ("Wand of Draconia", 1500),
        ("Wand of Dragonbreath", 200),
        ("Wand of Everblazing", 6000),
        ("Wand of Inferno", 3000),
        ("Wand of Starstorm", 3600),
        ("Wand of Voodoo", 4400),
        ("Wand of Vortex", 100),
    ),
}

MORPEL_BUYS: tuple[tuple[str, int], ...] = (
    ("Axe", 7),
    ("Barbarian Axe", 185),
    ("Battle Axe", 80),
    ("Battle Hammer", 120),
    ("Battle Shield", 95),
    ("Bone Club", 5),
    ("Bone Sword", 20),
    ("Brass Armor", 150),
    ("Brass Helmet", 30),
    ("Brass Legs", 49),
    ("Brass Shield", 25),
    ("Carlin Sword", 118),
    ("Chain Armor", 70),
    ("Chain Helmet", 17),
    ("Chain Legs", 25),
    ("Clerical Mace", 170),
    ("Club", 1),
    ("Coat", 1),
    ("Copper Shield", 50),
    ("Crowbar", 50),
    ("Dagger", 2),
    ("Double Axe", 260),
    ("Doublet", 3),
    ("Dwarven Shield", 100),
    ("Fire Sword", 1000),
    ("Halberd", 400),
    ("Hand Axe", 4),
    ("Hatchet", 25),
    ("Iron Helmet", 150),
    ("Jacket", 1),
    ("Katana", 35),
    ("Leather Armor", 12),
    ("Leather Boots", 2),
    ("Leather Helmet", 4),
    ("Leather Legs", 9),
    ("Legion Helmet", 22),
    ("Longsword", 51),
    ("Mace", 30),
    ("Morning Star", 100),
    ("Nunchaku", 135),
    ("Orcish Axe", 350),
    ("Pair of Monk Fists", 90),
    ("Plate Armor", 400),
    ("Plate Legs", 115),
    ("Plate Shield", 45),
    ("Rapier", 5),
    ("Sabre", 12),
    ("Sai", 180),
    ("Scale Armor", 75),
    ("Short Sword", 10),
    ("Sickle", 3),
    ("Small Axe", 5),
    ("Soldier Helmet", 16),
    ("Spike Sword", 240),
    ("Steel Helmet", 293),
    ("Steel Shield", 80),
    ("Studded Armor", 25),
    ("Studded Club", 10),
    ("Studded Helmet", 20),
    ("Studded Legs", 15),
    ("Studded Shield", 16),
    ("Swampling Club", 40),
    ("Sword", 25),
    ("Throwing Knife", 2),
    ("Two Handed Sword", 450),
    ("Viking Helmet", 66),
    ("Viking Shield", 85),
    ("War Hammer", 470),
    ("Wooden Shield", 5),
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
    "hp": 0,
    "mana": 0,
    "mana_regen_hungry": 0,
    "mana_regen_fed": 0,
    "mana_regen_depot": 0,
    "hp_regen_hungry": 0,
    "hp_regen_fed": 0,
    "hp_regen_depot": 0,
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

FLOAT_STATS = {
    "ml_percent",
    "mana_regen_hungry",
    "mana_regen_fed",
    "mana_regen_depot",
    "hp_regen_hungry",
    "hp_regen_fed",
    "hp_regen_depot",
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
                    if key in FLOAT_STATS:
                        try:
                            merged_stats[key] = float(stats[key])
                        except (TypeError, ValueError):
                            merged_stats[key] = 0.0
                    else:
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
                json.dump({"prices": self.prices, "favorites": self.favorites}, handle, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_price(self, item_name: str) -> int:
        return int(self.prices.get(item_name, 0))

    def set_price(self, item_name: str, price: int) -> None:
        self.prices[item_name] = max(0, int(price))
        self._save()

    def is_favorite(self, key: str) -> bool:
        return bool(self.favorites.get(key, False))

    def set_favorite(self, key: str, value: bool) -> None:
        self.favorites[key] = bool(value)
        self._save()

    def has_favorite_entry(self, key: str) -> bool:
        return key in self.favorites


class RuneStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.runes: list[dict[str, object]] = []
        self.active_id: str | None = None
        self._load()

    def _default_runes(self) -> list[dict[str, object]]:
        defaults = [
            ("Animate Dead Rune", 1, 600, 5, 375, 0),
            ("Avalanche Rune", 4, 530, 3, 64, 0),
            ("Chameleon Rune", 1, 600, 2, 210, 0),
            ("Convince Creature Rune", 1, 200, 3, 80, 0),
            ("Cure Poison Rune (Item)", 1, 200, 1, 65, 0),
            ("Destroy Field Rune", 3, 120, 2, 15, 0),
            ("Disintegrate Rune", 3, 200, 3, 26, 0),
            ("Energy Bomb Rune", 2, 880, 5, 203, 0),
            ("Energy Field Rune", 3, 320, 2, 38, 0),
            ("Energy Wall Rune", 4, 1000, 5, 85, 0),
            ("Explosion Rune", 6, 570, 4, 31, 0),
            ("Fire Bomb Rune", 2, 600, 4, 147, 0),
            ("Fire Field Rune", 3, 240, 1, 28, 0),
            ("Fire Wall Rune", 4, 780, 4, 61, 0),
            ("Fireball Rune", 5, 460, 3, 30, 0),
            ("Great Fireball Rune", 4, 530, 3, 64, 0),
            ("Heavy Magic Missile Rune", 10, 350, 2, 12, 0),
            ("Holy Missile Rune", 5, 300, 3, 16, 0),
            ("Icicle Rune", 5, 460, 3, 30, 0),
            ("Intense Healing Rune (Item)", 1, 120, 2, 95, 0),
            ("Light Magic Missile Rune", 10, 120, 1, 4, 0),
            ("Magic Wall Rune", 3, 750, 5, 116, 0),
            ("Paralyse Rune", 1, 1400, 3, 700, 0),
            ("Poison Bomb Rune", 2, 520, 2, 85, 0),
            ("Poison Field Rune", 3, 200, 1, 21, 0),
            ("Poison Wall Rune", 4, 640, 3, 52, 0),
            ("Soulfire Rune", 3, 420, 3, 46, 0),
            ("Stalagmite Rune", 10, 350, 2, 12, 0),
            ("Stone Shower Rune", 4, 430, 3, 41, 0),
            ("Sudden Death Rune", 3, 985, 5, 162, 0),
            ("Thunderstorm Rune", 4, 430, 3, 52, 0),
            ("Ultimate Healing Rune (Item)", 1, 400, 3, 175, 0),
            ("Wild Growth Rune", 2, 600, 5, 160, 0),
        ]
        runes: list[dict[str, object]] = []
        for name, per_cast, mana, soul, ek_gp, vk_gp in defaults:
            runes.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "runes_per_cast": per_cast,
                    "mana": mana,
                    "soul_points": soul,
                    "ek_gp": ek_gp,
                    "vk_gp": vk_gp,
                }
            )
        return runes

    def _load(self) -> None:
        if not self.path.exists():
            self.runes = self._default_runes()
            self.active_id = str(self.runes[0]["id"]) if self.runes else None
            self._save()
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            data = {}
        runes: list[dict[str, object]] = []
        for entry in data.get("runes", []):
            if not isinstance(entry, dict):
                continue
            rune_id = str(entry.get("id") or uuid.uuid4())
            name = str(entry.get("name", "")).strip() or "Unnamed Rune"
            runes_per_cast = entry.get("runes_per_cast", 1)
            mana = entry.get("mana", 0)
            soul_points = entry.get("soul_points", 0)
            try:
                runes_per_cast = int(runes_per_cast)
            except (TypeError, ValueError):
                runes_per_cast = 1
            try:
                mana = int(mana)
            except (TypeError, ValueError):
                mana = 0
            try:
                soul_points = int(soul_points)
            except (TypeError, ValueError):
                soul_points = 0
            ek_gp = entry.get("ek_gp", 0)
            vk_gp = entry.get("vk_gp", 0)
            try:
                ek_gp = int(ek_gp)
            except (TypeError, ValueError):
                ek_gp = 0
            try:
                vk_gp = int(vk_gp)
            except (TypeError, ValueError):
                vk_gp = 0
            runes.append(
                {
                    "id": rune_id,
                    "name": name,
                    "runes_per_cast": max(1, runes_per_cast),
                    "mana": max(0, mana),
                    "soul_points": max(0, soul_points),
                    "ek_gp": max(0, ek_gp),
                    "vk_gp": max(0, vk_gp),
                }
            )
        if not runes:
            runes = self._default_runes()
        self.runes = runes
        active_id = data.get("active_rune_id")
        self.active_id = active_id if any(entry.get("id") == active_id for entry in runes) else str(runes[0]["id"])

    def _save(self) -> None:
        payload = {"runes": self.runes, "active_rune_id": self.active_id}
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def names(self) -> list[str]:
        return [str(entry.get("name", "")) for entry in self.runes]

    def get_by_id(self, rune_id: str) -> dict[str, object] | None:
        for entry in self.runes:
            if str(entry.get("id")) == rune_id:
                return entry
        return None

    def get_by_name(self, name: str) -> dict[str, object] | None:
        for entry in self.runes:
            if str(entry.get("name")) == name:
                return entry
        return None

    def get_active(self) -> dict[str, object]:
        if self.active_id:
            entry = self.get_by_id(self.active_id)
            if entry:
                return entry
        if self.runes:
            self.active_id = str(self.runes[0]["id"])
            return self.runes[0]
        default = self._default_rune()
        self.runes = [default]
        self.active_id = str(default["id"])
        self._save()
        return default

    def set_active(self, rune_id: str) -> None:
        self.active_id = rune_id
        self._save()

    def is_name_unique(self, name: str, ignore_id: str | None = None) -> bool:
        lowered = name.casefold()
        for entry in self.runes:
            if ignore_id and str(entry.get("id")) == ignore_id:
                continue
            if str(entry.get("name", "")).casefold() == lowered:
                return False
        return True

    def add_rune(self, rune: dict[str, object]) -> None:
        self.runes.append(rune)
        self.active_id = str(rune.get("id"))
        self._save()

    def update_rune(self, rune_id: str, updates: dict[str, object]) -> None:
        for idx, entry in enumerate(self.runes):
            if str(entry.get("id")) == rune_id:
                self.runes[idx] = updates
                break
        if self.active_id == rune_id:
            self.active_id = str(updates.get("id", rune_id))
        self._save()

    def delete_rune(self, rune_id: str) -> None:
        self.runes = [entry for entry in self.runes if str(entry.get("id")) != rune_id]
        if not self.runes:
            self.runes = [self._default_rune()]
        if self.active_id == rune_id:
            self.active_id = str(self.runes[0]["id"])
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
        self.mana_items_state_path = self.base_dir / "mana_items_state.json"
        self.runes_state_path = self.base_dir / "runes_state.json"
        self.character_path = self.base_dir / "characters_state.json"
        self.hunt_path = self.base_dir / "hunts_state.json"
        self.search_window_state_path = self.base_dir / "search_window_state.json"
        self.history = HistoryManager(self.history_path)
        self.store = ImbuementStore(self.state_path)
        self.item_price_store = ItemPriceStore(self.items_state_path)
        self.mana_items_prices: dict[str, float] = {}
        self.rune_store = RuneStore(self.runes_state_path)
        self.character_store = CharacterStore(self.character_path)
        self.hunt_store = HuntStore(self.hunt_path)
        self.imbuement_material_names = self._collect_imbuement_material_names()
        self.imbuement_material_names_lower = {name.casefold() for name in self.imbuement_material_names}
        self.creature_products = build_tibia_items(
            load_json_resource(self.tibia_resource_dir / "creature_products.json")
        )
        self.delivery_items = build_tibia_items(
            load_json_resource(self.tibia_resource_dir / "delivery_task_items.json")
        )
        self._seed_imbuement_material_favorites()

        self.always_on_top = False
        self.search_window: tk.Toplevel | None = None
        self.search_window_state: dict[str, object] = {}
        self._search_window_save_after: str | None = None
        self._search_window_ready = False
        self._search_window_restore_pending = False
        self._search_window_position_dirty = False
        self._search_window_commit_position_on_save = False
        self._search_window_drag_start: tuple[int, int] | None = None
        self._search_window_drag_origin: tuple[int, int] | None = None
        self.search_window_width_var = tk.StringVar()
        self.search_window_height_var = tk.StringVar()
        self.search_window_x_var = tk.StringVar()
        self.search_window_y_var = tk.StringVar()
        self.search_window_lock_var = tk.BooleanVar(value=True)
        self.active_imbuement: Imbuement | None = None
        self.material_vars: dict[str, tk.StringVar] = {}
        self.material_rows: list[tuple[Material, ttk.Label]] = []
        self.character_window: "CharacterWindow" | None = None
        self.items_list_items: list[TibiaItem] = []
        self.items_tree_items: dict[str, TibiaItem] = {}
        self.items_sort_field: str = "name"
        self.items_sort_desc: bool = False
        self.active_hunt_id: str | None = None
        self.hunt_log_update_after: str | None = None
        self.hunt_detail_vars: dict[str, tk.StringVar] = {}
        self.hunt_rate_vars: dict[str, tk.StringVar] = {}
        self.hunt_equipment_var = tk.StringVar(value=EQUIPMENT_TAGS[0])
        self.hunt_character_var = tk.StringVar()
        self.character_search_var = tk.StringVar()
        self.rune_character_var = tk.StringVar()
        self.rune_spell_var = tk.StringVar()
        self.rune_time_minutes_var = tk.StringVar(value="0")
        self.rune_use_depot_bonus_var = tk.BooleanVar(value=False)
        self.rune_regen_mode_var = tk.StringVar(value="Fed")
        self.rune_regen_start_percent_var = tk.StringVar(value="0%")
        self.rune_regen_show_formulas_var = tk.BooleanVar(value=False)
        self.rune_soul_show_formulas_var = tk.BooleanVar(value=False)
        self.rune_mana_item_rows: list[dict[str, object]] = []
        self.rune_potion_var = tk.StringVar(value="None")
        self.rune_potion_count_var = tk.StringVar(value="0")
        self.rune_potion_hint_var = tk.StringVar(value="")
        self.rune_soul_potion_var = tk.StringVar(value="None")
        self.rune_potion_count_entry: ttk.Entry | None = None
        self.rune_potion_vars: dict[str, tk.StringVar] = {}
        self.rune_soul_result_vars: dict[str, tk.StringVar] = {}
        self.rune_soul_formula_vars: dict[str, tk.StringVar] = {}
        self.rune_soul_formula_labels: list[ttk.Label] = []
        self.rune_stats_vars: dict[str, tk.StringVar] = {}
        self.rune_editor_vars: dict[str, tk.StringVar] = {}
        self.rune_result_vars: dict[str, tk.StringVar] = {}
        self.rune_spell_combo: ttk.Combobox | None = None
        self.hunt_kills_list: tk.Listbox | None = None
        self.hunt_loot_list: tk.Listbox | None = None
        self._suppress_hunt_equipment_change = False
        self._suppress_hunt_character_change = False
        self._suppress_hunt_log_change = False
        self._price_editor: ttk.Entry | None = None
        self.request_log: list[str] = []
        self.module_windows: dict[str, tk.Toplevel] = {}
        self._hunt_traces_bound = False
        self.hotkeys_dir = self.base_dir / "ahk"
        self.hotkeys_script_path = self.hotkeys_dir / "tibia_hotkeys.ahk"
        self.hotkeys_json_path = self.hotkeys_dir / "hotkeys.json"
        self.hotkeys_events_path = self.hotkeys_dir / "hotkeys_events.log"
        self.hotkeys_cmd_path = self.hotkeys_dir / "hotkeys_cmd.txt"
        self.tibia_exe_path = self._resolve_tibia_exe_path()
        self.auto_start_tibia_on_launch = True
        self.tibia_login_target = "com.tibiasearch.tibia.login.main"
        self.tibia_paste_script_path = self.hotkeys_dir / "tibia_login_paste.ahk"
        self.tibia_paste_log_path = self.base_dir / "tibia_paste.log"
        self.cone_script_path = self.hotkeys_dir / "tibia_cones.ahk"
        self.cone_events_path = self.hotkeys_dir / "cone_events.log"
        self.cone_process: subprocess.Popen[str] | None = None
        self.tibia_login_after_id: str | None = None
        self.tibia_login_remaining = 0
        self.tibia_login_status_var = tk.StringVar(value="")
        self.hotkeys_process: subprocess.Popen[str] | None = None
        self.hotkeys_tree: ttk.Treeview | None = None
        self.hotkey_entry: ttk.Entry | None = None
        self.action_entry: ttk.Entry | None = None
        self.hotkeys_status_var = tk.StringVar(value="Stopped")
        self.hotkeys_overlay_var = tk.StringVar(value="Overlay: Off")
        self.hotkeys_admin_var = tk.StringVar(value="AHK admin: ?")
        self.hotkeys_admin_warning_var = tk.StringVar(value="")
        self.hotkeys_target_win = "ahk_exe client.exe"
        self.hotkeys_defs: list[dict[str, object]] = []
        self.hotkeys_admin_state: bool | None = None
        self._cone_events_pos = 0
        self._cone_events_buffer = ""
        self.python_is_admin = self._is_admin()
        self.cooldowns_state_path = self.base_dir / "cooldowns_state.json"
        self.grid_overlay_state_path = self.base_dir / "grid_overlay_state.json"
        self.cooldowns_tree: ttk.Treeview | None = None
        self.cooldown_action_entry: ttk.Entry | None = None
        self.cooldown_name_entry: ttk.Entry | None = None
        self.cooldown_ms_entry: ttk.Entry | None = None
        self.cooldown_icon_entry: ttk.Entry | None = None
        self.cooldowns_defs: list[dict[str, object]] = []
        self.grid_overlay = GridOverlay(self.root, on_change=self._save_grid_overlay_state)
        self.grid_cone_overlay = GridConeOverlay(
            self.grid_overlay,
            on_change=self._on_cones_change,
            title="Cone Great Firewave",
        )
        self.grid_cone_overlay_alt = GridConeOverlay(
            self.grid_overlay,
            on_change=self._on_cones_change,
            title="Cone Great Energybeam",
            pattern=(1, 1, 3, 3, 3),
        )
        self.grid_cone_overlay_alt.line_color = "#3366cc"

        self._apply_fantasy_theme()
        self._load_mana_items_prices()
        self._load_grid_overlay_state()
        self._load_search_window_state()
        self._build_ui()
        self._bind_events()
        self._refresh_history_list()
        self._start_market_refresh()
        self._schedule_hotkeys_status_refresh()
        self._schedule_cone_events_poll()
        self.root.after(0, self._start_hotkeys_script)
        self.root.after(250, self._auto_start_tibia)

        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

    def _apply_fantasy_theme(self) -> None:
        base_bg = "#f3e4c7"
        panel_bg = "#f9f1dd"
        accent_bg = "#7a2a1d"
        accent_bg_alt = "#8c3a2a"
        border = "#5a2a1d"
        text = "#2b1a10"
        highlight = "#e2cfb2"

        self.root.configure(bg=base_bg)
        self.root.option_add("*Font", ("Georgia", 10))
        self.root.option_add("*Foreground", text)
        self.root.option_add("*Background", base_bg)
        self.root.option_add("*Entry.background", panel_bg)
        self.root.option_add("*Entry.foreground", text)
        self.root.option_add("*Text.background", panel_bg)
        self.root.option_add("*Text.foreground", text)
        self.root.option_add("*Text.insertBackground", text)
        self.root.option_add("*Listbox.background", panel_bg)
        self.root.option_add("*Listbox.foreground", text)
        self.root.option_add("*Listbox.selectBackground", accent_bg_alt)
        self.root.option_add("*Listbox.selectForeground", "#fff6e8")

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Georgia", 10), background=base_bg, foreground=text)
        style.configure("TFrame", background=base_bg)
        style.configure("TLabel", background=base_bg, foreground=text)
        style.configure("TLabelFrame", background=base_bg, foreground=accent_bg, bordercolor=border)
        style.configure(
            "TLabelFrame.Label",
            background=base_bg,
            foreground=accent_bg,
            font=("Georgia", 10, "bold"),
        )
        style.configure("TNotebook", background=base_bg, bordercolor=border)
        style.configure(
            "TNotebook.Tab",
            background=highlight,
            foreground=text,
            padding=(10, 6),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", panel_bg)],
            foreground=[("selected", accent_bg)],
        )
        style.configure(
            "TButton",
            background=accent_bg,
            foreground="#fff6e8",
            padding=(10, 4),
            bordercolor=border,
        )
        style.map(
            "TButton",
            background=[("active", accent_bg_alt)],
            foreground=[("active", "#fff6e8")],
        )
        style.configure(
            "TEntry",
            fieldbackground=panel_bg,
            foreground=text,
            bordercolor=border,
        )
        style.configure(
            "TCombobox",
            fieldbackground=panel_bg,
            foreground=text,
        )
        style.map("TCombobox", fieldbackground=[("readonly", panel_bg)])
        style.configure(
            "Treeview",
            background=panel_bg,
            fieldbackground=panel_bg,
            foreground=text,
            bordercolor=border,
            rowheight=22,
        )
        style.configure(
            "Treeview.Heading",
            background=highlight,
            foreground=accent_bg,
            font=("Georgia", 10, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", accent_bg_alt)],
            foreground=[("selected", "#fff6e8")],
        )
        style.configure("Formula.TLabel", font=("Georgia", 9, "italic"), foreground="#6b4b3b")
        style.configure("Warning.TEntry", foreground="#b00020")

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self._build_search_window()

        top_bar = ttk.Frame(self.root)
        top_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        top_bar.columnconfigure(0, weight=1)
        ttk.Button(top_bar, text="Neustart", command=self._restart_app).grid(
            row=0, column=1, sticky="e"
        )

        content_frame = ttk.Frame(self.root)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(content_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        modules_frame = ttk.LabelFrame(left_frame, text="Modules")
        modules_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        modules_frame.columnconfigure(0, weight=1)

        ttk.Button(
            modules_frame,
            text="Imbuements",
            command=lambda: self._open_module_window("imbuements"),
        ).grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
        ttk.Button(
            modules_frame,
            text="Tibia Items",
            command=lambda: self._open_module_window("items"),
        ).grid(row=1, column=0, sticky="ew", padx=6, pady=4)
        ttk.Button(
            modules_frame,
            text="Hunts",
            command=lambda: self._open_module_window("hunts"),
        ).grid(row=2, column=0, sticky="ew", padx=6, pady=4)
        ttk.Button(
            modules_frame,
            text="Hotkeys",
            command=lambda: self._open_module_window("hotkeys"),
        ).grid(row=3, column=0, sticky="ew", padx=6, pady=4)
        ttk.Button(
            modules_frame,
            text="Grid Overlay",
            command=lambda: self._open_module_window("grid_overlay"),
        ).grid(row=4, column=0, sticky="ew", padx=6, pady=4)
        ttk.Button(
            modules_frame,
            text="Grid Cones",
            command=lambda: self._open_module_window("grid_cones"),
        ).grid(row=5, column=0, sticky="ew", padx=6, pady=4)
        ttk.Button(
            modules_frame,
            text="Cooldowns",
            command=lambda: self._open_module_window("cooldowns"),
        ).grid(row=6, column=0, sticky="ew", padx=6, pady=(4, 6))
        ttk.Button(
            modules_frame,
            text="Hunting Ground",
            command=lambda: self._open_module_window("hunting_ground"),
        ).grid(row=7, column=0, sticky="ew", padx=6, pady=(4, 6))
        ttk.Button(
            modules_frame,
            text="Charakter suchen",
            command=lambda: self._open_module_window("character_search"),
        ).grid(row=8, column=0, sticky="ew", padx=6, pady=(4, 6))
        ttk.Button(
            modules_frame,
            text="Runen Rechner",
            command=lambda: self._open_module_window("rune_calculator"),
        ).grid(row=9, column=0, sticky="ew", padx=6, pady=(4, 6))
        ttk.Button(
            modules_frame,
            text="Suchfenster",
            command=lambda: self._open_module_window("search_window"),
        ).grid(row=10, column=0, sticky="ew", padx=6, pady=(4, 6))
        ttk.Button(
            modules_frame,
            text="Djinn Selling",
            command=lambda: self._open_module_window("djinn_selling"),
        ).grid(row=11, column=0, sticky="ew", padx=6, pady=(4, 6))

        actions_frame = ttk.LabelFrame(left_frame, text="Actions")
        actions_frame.grid(row=1, column=0, sticky="nsew")
        actions_frame.columnconfigure(0, weight=1)

        ttk.Button(actions_frame, text="Character Window", command=self.open_character_window).grid(
            row=0, column=0, sticky="ew", padx=6, pady=(6, 4)
        )
        ttk.Button(actions_frame, text="Log", command=self.open_request_log).grid(
            row=1, column=0, sticky="ew", padx=6, pady=(4, 6)
        )
        ttk.Button(actions_frame, text="Start Tibia", command=lambda: self._start_tibia(False)).grid(
            row=2, column=0, sticky="ew", padx=6, pady=(4, 4)
        )
        ttk.Button(actions_frame, text="Start Tibia (Admin)", command=lambda: self._start_tibia(True)).grid(
            row=3, column=0, sticky="ew", padx=6, pady=(0, 6)
        )
        ttk.Button(actions_frame, text="Copy Tibia Password", command=self._copy_tibia_password).grid(
            row=4, column=0, sticky="ew", padx=6, pady=(0, 6)
        )
        ttk.Label(actions_frame, textvariable=self.tibia_login_status_var).grid(
            row=5, column=0, sticky="w", padx=6, pady=(0, 6)
        )

        history_frame = ttk.LabelFrame(content_frame, text="Search History")
        history_frame.grid(row=0, column=1, sticky="nsew")
        self._build_history_tab(history_frame)

    def _build_search_window(self) -> None:
        self.search_window = tk.Toplevel(self.root)
        self.search_window.resizable(True, True)
        self.search_window.configure(bg=self.root.cget("bg"), borderwidth=0, highlightthickness=0)
        self.search_window.overrideredirect(True)
        self.search_window.rowconfigure(0, weight=1)
        self.search_window.columnconfigure(0, weight=1)

        frame = ttk.Frame(self.search_window, padding=0)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.search_entry = ttk.Entry(frame, width=28, style="Search.TEntry")
        self.search_entry.grid(row=0, column=0, sticky="nsew")
        self.search_entry.focus_set()

        self.top_button = ttk.Button(frame, text="Top", width=3, command=self.toggle_topmost, style="Search.TButton")
        self.top_button.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        for widget in (self.search_window, frame, self.search_entry, self.top_button):
            widget.bind("<Alt-ButtonPress-1>", self._on_search_window_drag_start, add="+")
            widget.bind("<Alt-B1-Motion>", self._on_search_window_drag_move, add="+")
            widget.bind("<Alt-ButtonRelease-1>", self._on_search_window_drag_end, add="+")

        self.search_window.update_idletasks()
        self._apply_saved_search_window_geometry()
        self._search_window_restore_pending = True
        self.root.after(50, lambda: self._restore_pending_search_window_geometry(finalize=False))
        self.root.after(300, lambda: self._restore_pending_search_window_geometry(finalize=True))
        self._apply_search_window_lock_state()
        self._update_search_window_padding()
        self.search_window.minsize(self.search_window.winfo_width(), self.search_window.winfo_height())
        self.search_window.bind("<Configure>", self._on_search_window_resize)
        self._search_window_ready = False
        self.root.after(300, self._mark_search_window_ready)

    def _mark_search_window_ready(self) -> None:
        self._search_window_ready = True

    def _restore_pending_search_window_geometry(self, finalize: bool) -> None:
        if not self._search_window_restore_pending:
            return
        if not self.search_window or not self.search_window.winfo_exists():
            return
        state = self.search_window_state or {}
        width = state.get("width")
        height = state.get("height")
        x = state.get("x")
        y = state.get("y")
        if all(isinstance(value, int) for value in (width, height, x, y)):
            self.search_window.geometry(f"{width}x{height}+{x}+{y}")
            self.search_window.minsize(max(1, width), max(1, height))
            self.search_window.update_idletasks()
            self._sync_search_window_vars()
        if finalize:
            self._search_window_restore_pending = False

    def _build_history_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        self.history_list = tk.Listbox(parent, height=6)
        self.history_list.grid(row=0, column=0, sticky="nsew")

        history_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.history_list.yview)
        history_scroll.grid(row=0, column=1, sticky="ns")
        self.history_list.configure(yscrollcommand=history_scroll.set)

    def _build_hotkeys_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0)
        parent.rowconfigure(2, weight=1)

        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header_frame.columnconfigure(4, weight=1)

        ttk.Label(header_frame, text="Status:").grid(row=0, column=0, sticky="w")
        ttk.Label(header_frame, textvariable=self.hotkeys_status_var).grid(row=0, column=1, sticky="w", padx=(4, 12))
        ttk.Label(header_frame, textvariable=self.hotkeys_admin_var).grid(row=0, column=2, sticky="w", padx=(0, 12))
        ttk.Label(header_frame, textvariable=self.hotkeys_admin_warning_var).grid(
            row=0, column=3, sticky="w", padx=(0, 12)
        )
        ttk.Button(header_frame, textvariable=self.hotkeys_overlay_var, command=self._toggle_overlay).grid(
            row=0, column=4, sticky="e"
        )

        editor_frame = ttk.LabelFrame(parent, text="Hotkey Editor")
        editor_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        editor_frame.columnconfigure(1, weight=1)
        editor_frame.columnconfigure(3, weight=1)

        ttk.Label(editor_frame, text="Hotkey").grid(row=0, column=0, sticky="w", padx=6, pady=(6, 2))
        self.hotkey_entry = ttk.Entry(editor_frame, width=16)
        self.hotkey_entry.grid(row=0, column=1, sticky="w", padx=6, pady=(6, 2))

        ttk.Label(editor_frame, text="Action / Send").grid(row=0, column=2, sticky="w", padx=6, pady=(6, 2))
        self.action_entry = ttk.Entry(editor_frame, width=26)
        self.action_entry.grid(row=0, column=3, sticky="ew", padx=6, pady=(6, 2))

        ttk.Button(editor_frame, text="Add New", command=self._add_hotkey).grid(
            row=1, column=3, sticky="e", padx=6, pady=(2, 6)
        )

        list_frame = ttk.Frame(parent)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 6))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.hotkeys_tree = ttk.Treeview(
            list_frame,
            columns=("hotkey", "action"),
            show="headings",
            height=10,
        )
        self.hotkeys_tree.heading("hotkey", text="Hotkey")
        self.hotkeys_tree.heading("action", text="Action / Send")
        self.hotkeys_tree.column("hotkey", width=140, anchor="w")
        self.hotkeys_tree.column("action", width=240, anchor="w")
        self.hotkeys_tree.grid(row=0, column=0, sticky="nsew")
        self.hotkeys_tree.bind("<<TreeviewSelect>>", self._on_hotkeys_select)
        self.hotkeys_tree.bind("<Double-Button-1>", lambda _event: self._edit_selected_hotkey())

        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.hotkeys_tree.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.hotkeys_tree.configure(yscrollcommand=list_scroll.set)

        row_actions = ttk.Frame(parent)
        row_actions.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 6))
        ttk.Button(row_actions, text="Edit Selected", command=self._edit_selected_hotkey).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(row_actions, text="Update Selected", command=self._update_selected_hotkey).grid(
            row=0, column=1, sticky="w", padx=(6, 0)
        )
        ttk.Button(row_actions, text="Delete Selected", command=self._remove_hotkey).grid(
            row=0, column=2, sticky="w", padx=(6, 0)
        )

        actions_frame = ttk.Frame(parent)
        actions_frame.grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 8))
        actions_frame.columnconfigure(0, weight=1)

        ttk.Button(actions_frame, text="Save", command=self._save_hotkeys_mappings).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(actions_frame, text="Start", command=self._start_hotkeys_script).grid(
            row=0, column=1, sticky="w", padx=(6, 0)
        )
        ttk.Button(actions_frame, text="Stop", command=self._stop_hotkeys_script).grid(
            row=0, column=2, sticky="w", padx=(6, 0)
        )
        ttk.Button(actions_frame, text="Restart", command=self._restart_hotkeys_script).grid(
            row=0, column=3, sticky="w", padx=(6, 0)
        )
        ttk.Button(actions_frame, text="Restart as Admin", command=self._restart_hotkeys_as_admin).grid(
            row=0, column=4, sticky="w", padx=(6, 0)
        )

    def _build_grid_overlay_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        settings_frame = self.grid_overlay.build_settings_frame(parent)
        settings_frame.grid(row=0, column=0, sticky="nw", padx=8, pady=8)

    def _build_grid_cones_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        settings_frame = self.grid_cone_overlay.build_settings_frame(parent)
        settings_frame.grid(row=0, column=0, sticky="nw", padx=8, pady=(8, 4))
        alt_frame = self.grid_cone_overlay_alt.build_settings_frame(parent)
        alt_frame.grid(row=1, column=0, sticky="nw", padx=8, pady=(4, 8))

    def _build_cooldowns_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0)
        parent.rowconfigure(2, weight=1)

        editor_frame = ttk.LabelFrame(parent, text="Cooldown Editor")
        editor_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        editor_frame.columnconfigure(1, weight=1)
        editor_frame.columnconfigure(3, weight=1)
        editor_frame.columnconfigure(4, weight=0)

        ttk.Label(editor_frame, text="Action ID").grid(row=0, column=0, sticky="w", padx=6, pady=(6, 2))
        self.cooldown_action_entry = ttk.Entry(editor_frame, width=18)
        self.cooldown_action_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=(6, 2))

        ttk.Label(editor_frame, text="Name").grid(row=0, column=2, sticky="w", padx=6, pady=(6, 2))
        self.cooldown_name_entry = ttk.Entry(editor_frame, width=22)
        self.cooldown_name_entry.grid(row=0, column=3, sticky="ew", padx=6, pady=(6, 2))

        ttk.Label(editor_frame, text="Cooldown (ms)").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        self.cooldown_ms_entry = ttk.Entry(editor_frame, width=12)
        self.cooldown_ms_entry.grid(row=1, column=1, sticky="w", padx=6, pady=2)

        ttk.Label(editor_frame, text="Icon").grid(row=1, column=2, sticky="w", padx=6, pady=2)
        self.cooldown_icon_entry = ttk.Entry(editor_frame, width=28)
        self.cooldown_icon_entry.grid(row=1, column=3, sticky="ew", padx=6, pady=2)
        ttk.Button(editor_frame, text="Browse", command=self._browse_cooldown_icon).grid(
            row=1, column=4, sticky="w", padx=(0, 6), pady=2
        )

        ttk.Button(editor_frame, text="Add New", command=self._add_cooldown).grid(
            row=2, column=3, sticky="e", padx=6, pady=(2, 6)
        )

        list_frame = ttk.Frame(parent)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 6))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.cooldowns_tree = ttk.Treeview(
            list_frame,
            columns=("action_id", "name", "cooldown_ms", "icon"),
            show="headings",
            height=10,
        )
        self.cooldowns_tree.heading("action_id", text="Action ID")
        self.cooldowns_tree.heading("name", text="Name")
        self.cooldowns_tree.heading("cooldown_ms", text="Cooldown (ms)")
        self.cooldowns_tree.heading("icon", text="Icon")
        self.cooldowns_tree.column("action_id", width=140, anchor="w")
        self.cooldowns_tree.column("name", width=180, anchor="w")
        self.cooldowns_tree.column("cooldown_ms", width=130, anchor="e")
        self.cooldowns_tree.column("icon", width=220, anchor="w")
        self.cooldowns_tree.grid(row=0, column=0, sticky="nsew")
        self.cooldowns_tree.bind("<<TreeviewSelect>>", self._on_cooldown_select)
        self.cooldowns_tree.bind("<Double-Button-1>", lambda _event: self._edit_selected_cooldown())

        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.cooldowns_tree.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.cooldowns_tree.configure(yscrollcommand=list_scroll.set)

        row_actions = ttk.Frame(parent)
        row_actions.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(row_actions, text="Edit Selected", command=self._edit_selected_cooldown).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(row_actions, text="Update Selected", command=self._update_selected_cooldown).grid(
            row=0, column=1, sticky="w", padx=(6, 0)
        )
        ttk.Button(row_actions, text="Delete Selected", command=self._remove_cooldown).grid(
            row=0, column=2, sticky="w", padx=(6, 0)
        )

        self._load_cooldowns_table()

    def _build_hunting_ground_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        list_frame = ttk.LabelFrame(parent, text="Hunting Ground Links")
        list_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        list_frame.columnconfigure(0, weight=1)

        links = [
            ("TibiaPal - Hunting", "https://tibiapal.com/hunting"),
            (
                "TibiaRoute - Hunting Places",
                "https://tibiaroute.com/de/hunting-places?page=1&level=100&levelType=Lower&size=Solo&voc=MS",
            ),
            ("TibiaWiki - Hunting Places", "https://tibia.fandom.com/wiki/Hunting_Places"),
            ("inTibia - Hunts", "https://intibia.com/hunts?level=100&vocation=sorcerer"),
        ]

        for row, (label, url) in enumerate(links):
            link_label = ttk.Label(list_frame, text=label, foreground="#0a66cc", cursor="hand2")
            link_label.grid(row=row, column=0, sticky="w", padx=6, pady=4)
            link_label.bind("<Button-1>", lambda _event, target=url: self._open_url(target, label))

    def _build_character_search_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        frame = ttk.LabelFrame(parent, text="Charakter suchen")
        frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Name").grid(row=0, column=0, sticky="w", padx=6, pady=(6, 2))
        entry = ttk.Entry(frame, textvariable=self.character_search_var)
        entry.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
        entry.bind("<Return>", lambda _event: self._search_character())

        ttk.Button(frame, text="Suchen", command=self._search_character).grid(
            row=2, column=0, sticky="w", padx=6, pady=(0, 6)
        )

    def _build_djinn_selling_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(3, weight=1)
        parent.rowconfigure(5, weight=1)
        delivery_names = {item.name.casefold() for item in self.delivery_items}
        self._djinn_filter_vars: dict[str, tk.BooleanVar] = {
            "green": tk.BooleanVar(value=False),
            "blue": tk.BooleanVar(value=False),
            "morpel": tk.BooleanVar(value=False),
        }

        def build_tree(
            container: ttk.LabelFrame,
            items: tuple[tuple[str, int], ...],
            only_delivery_var: tk.BooleanVar,
        ) -> ttk.Treeview:
            tree = ttk.Treeview(container, columns=("item", "price", "delivery"), show="headings", height=14)
            tree.heading("item", text="Item")
            tree.heading("price", text="Price")
            tree.heading("delivery", text="Delivery")
            tree.column("item", width=220, anchor="w")
            tree.column("price", width=120, anchor="e")
            tree.column("delivery", width=75, anchor="center", stretch=False)
            tree.grid(row=0, column=0, sticky="nsew")
            scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
            scrollbar.grid(row=0, column=1, sticky="ns")
            tree.configure(yscrollcommand=scrollbar.set)
            tree.tag_configure("delivery-item", foreground="#1a7f37")

            def refresh_rows() -> None:
                tree.delete(*tree.get_children())
                only_delivery = bool(only_delivery_var.get())
                for item_name, price in items:
                    is_delivery = item_name.casefold() in delivery_names
                    if only_delivery and not is_delivery:
                        continue
                    tree.insert(
                        "",
                        tk.END,
                        values=(item_name, f"{_format_number(price)} Gold", "Yes" if is_delivery else ""),
                        tags=("delivery-item",) if is_delivery else (),
                    )

            only_delivery_var.trace_add("write", lambda *_args: refresh_rows())
            refresh_rows()
            tree.bind("<Double-Button-1>", lambda _event, t=tree: self._search_selected_djinn_item(t))
            tree.bind("<Return>", lambda _event, t=tree: self._search_selected_djinn_item(t))
            return tree

        green_header = ttk.Frame(parent)
        green_header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 4))
        green_header.columnconfigure(0, weight=1)
        ttk.Label(green_header, text="Green Djinns - Efreet Faction (Alesar & Yaman) - Buys").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Checkbutton(green_header, text="nur Delivery", variable=self._djinn_filter_vars["green"]).grid(
            row=0, column=1, sticky="e"
        )
        yaman_frame = ttk.LabelFrame(parent, text="Yaman")
        yaman_frame.grid(row=1, column=0, sticky="nsew", padx=(6, 3), pady=6)
        yaman_frame.columnconfigure(0, weight=1)
        yaman_frame.rowconfigure(0, weight=1)
        alesar_frame = ttk.LabelFrame(parent, text="Alesar")
        alesar_frame.grid(row=1, column=1, sticky="nsew", padx=(3, 6), pady=6)
        alesar_frame.columnconfigure(0, weight=1)
        alesar_frame.rowconfigure(0, weight=1)
        build_tree(yaman_frame, GREEN_DJINN_BUYS["Yaman"], self._djinn_filter_vars["green"])
        build_tree(alesar_frame, GREEN_DJINN_BUYS["Alesar"], self._djinn_filter_vars["green"])

        blue_header = ttk.Frame(parent)
        blue_header.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 4))
        blue_header.columnconfigure(0, weight=1)
        ttk.Label(blue_header, text="Blue Djinns - Marid Faction (Nah'Bob & Haroun) - Buys").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Checkbutton(blue_header, text="nur Delivery", variable=self._djinn_filter_vars["blue"]).grid(
            row=0, column=1, sticky="e"
        )
        nahbob_frame = ttk.LabelFrame(parent, text="Nah'Bob")
        nahbob_frame.grid(row=3, column=0, sticky="nsew", padx=(6, 3), pady=6)
        nahbob_frame.columnconfigure(0, weight=1)
        nahbob_frame.rowconfigure(0, weight=1)
        haroun_frame = ttk.LabelFrame(parent, text="Haroun")
        haroun_frame.grid(row=3, column=1, sticky="nsew", padx=(3, 6), pady=6)
        haroun_frame.columnconfigure(0, weight=1)
        haroun_frame.rowconfigure(0, weight=1)
        build_tree(nahbob_frame, BLUE_DJINN_BUYS["Nah'Bob"], self._djinn_filter_vars["blue"])
        build_tree(haroun_frame, BLUE_DJINN_BUYS["Haroun"], self._djinn_filter_vars["blue"])

        morpel_header = ttk.Frame(parent)
        morpel_header.grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 4))
        morpel_header.columnconfigure(0, weight=1)
        ttk.Label(morpel_header, text="Normaler Loot (Morpel) - Buys").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(morpel_header, text="nur Delivery", variable=self._djinn_filter_vars["morpel"]).grid(
            row=0, column=1, sticky="e"
        )
        morpel_frame = ttk.LabelFrame(parent, text="Morpel")
        morpel_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
        morpel_frame.columnconfigure(0, weight=1)
        morpel_frame.rowconfigure(0, weight=1)
        build_tree(morpel_frame, MORPEL_BUYS, self._djinn_filter_vars["morpel"])

    def _search_selected_djinn_item(self, tree: ttk.Treeview) -> None:
        selection = tree.selection()
        if not selection:
            return
        values = tree.item(selection[0], "values")
        if not values:
            return
        item_name = str(values[0]).strip()
        if item_name:
            self.open_search(item_name)

    def _build_rune_calculator_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        header.columnconfigure(1, weight=1)
        header.columnconfigure(3, weight=1)
        header.columnconfigure(6, weight=1)

        ttk.Label(header, text="Character").grid(row=0, column=0, sticky="w")
        self.rune_character_var.set(self.character_store.active_name or self._character_choices()[0])
        character_combo = ttk.Combobox(
            header,
            textvariable=self.rune_character_var,
            values=self._character_choices(),
            state="readonly",
            width=18,
        )
        character_combo.grid(row=0, column=1, sticky="w", padx=(6, 12))
        character_combo.bind("<<ComboboxSelected>>", self._on_rune_character_change)

        stats_frame = ttk.Frame(header)
        stats_frame.grid(row=0, column=2, columnspan=4, sticky="w")
        for idx, (label, key) in enumerate(
            (
                ("Level", "level"),
                ("Max Mana", "max_mana"),
                ("Soul", "soul_points"),
                ("Magic Level", "magic_level"),
                ("ML& to go", "ml_percent"),
            )
        ):
            ttk.Label(stats_frame, text=label).grid(row=0, column=idx * 2, sticky="w", padx=(0, 4))
            var = tk.StringVar(value="0")
            ttk.Label(stats_frame, textvariable=var).grid(row=0, column=idx * 2 + 1, sticky="w", padx=(0, 12))
            self.rune_stats_vars[key] = var

        notebook = ttk.Notebook(parent)
        notebook.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        runes_tab = ttk.Frame(notebook)
        regen_tab = ttk.Frame(notebook)
        soul_cycle_tab = ttk.Frame(notebook)
        potions_tab = ttk.Frame(notebook)
        notebook.add(runes_tab, text="Runen")
        notebook.add(regen_tab, text="Regeneration")
        notebook.add(soul_cycle_tab, text="Soul Zyklus")
        notebook.add(potions_tab, text="Potions")

        # Runen tab
        runes_tab.columnconfigure(1, weight=1)
        runes_tab.columnconfigure(2, weight=1)
        runes_tab.rowconfigure(0, weight=1)

        list_frame = ttk.LabelFrame(runes_tab, text="Runenliste")
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=8)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(2, weight=1)

        ttk.Label(list_frame, text="Suche").grid(row=0, column=0, sticky="w", padx=6, pady=(6, 2))
        self.rune_filter_var = tk.StringVar()
        filter_entry = ttk.Entry(list_frame, textvariable=self.rune_filter_var)
        filter_entry.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

        self.rune_listbox = tk.Listbox(list_frame, height=12)
        self.rune_listbox.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))
        rune_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.rune_listbox.yview)
        rune_scroll.grid(row=2, column=1, sticky="ns", pady=(0, 6))
        self.rune_listbox.configure(yscrollcommand=rune_scroll.set)

        def refresh_rune_list() -> None:
            query = self.rune_filter_var.get().strip().casefold()
            names = [name for name in self.rune_store.names() if name]
            if query:
                names = [name for name in names if query in name.casefold()]
            self.rune_listbox.delete(0, tk.END)
            for name in names:
                self.rune_listbox.insert(tk.END, name)

        def on_rune_select(_event: tk.Event) -> None:
            selection = self.rune_listbox.curselection()
            if not selection:
                return
            name = self.rune_listbox.get(selection[0])
            self.rune_spell_var.set(name)
            self._on_rune_spell_change()

        self.rune_filter_var.trace_add("write", lambda *_: refresh_rune_list())
        self.rune_listbox.bind("<<ListboxSelect>>", on_rune_select)

        details_frame = ttk.LabelFrame(runes_tab, text="Rune Details")
        details_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
        details_frame.columnconfigure(1, weight=1)
        details_frame.columnconfigure(3, weight=1)

        self.rune_result_vars = {}
        detail_fields = [
            ("Runes/Spell", "runes_per_cast"),
            ("Mana Cost", "mana_cost"),
            ("Soul Points", "soul_cost"),
            ("EK (gp)", "ek_gp"),
            ("VK (gp)", "vk_gp"),
            ("Casts from Max. Mana", "casts_from_mana"),
            ("Runes from Max. Mana", "runes_from_mana"),
            ("Max Casts", "casts_possible"),
            ("Max Runes", "runes_possible"),
            ("ML Gewinn (Regen)", "ml_gain_regen"),
            ("ML Gewinn (Potions)", "ml_gain_potion"),
        ]
        for row, (label, key) in enumerate(detail_fields):
            col = 0 if row < 5 else 2
            display_row = row if row < 5 else row - 5
            ttk.Label(details_frame, text=label).grid(row=display_row, column=col, sticky="w", padx=6, pady=2)
            var = tk.StringVar(value="0")
            ttk.Label(details_frame, textvariable=var).grid(row=display_row, column=col + 1, sticky="w", padx=6, pady=2)
            self.rune_result_vars[key] = var

        editor_frame = ttk.LabelFrame(runes_tab, text="Editor")
        editor_frame.grid(row=0, column=2, sticky="nsew", pady=8)
        editor_frame.columnconfigure(0, weight=1)

        self.rune_editor_vars = {}
        for key in ("name", "runes_per_cast", "mana_cost", "soul_cost", "ek_gp", "vk_gp"):
            self.rune_editor_vars[key] = tk.StringVar()

        ttk.Button(editor_frame, text="Bearbeiten…", command=self._open_rune_editor_dialog).grid(
            row=0, column=0, sticky="ew", padx=6, pady=(6, 2)
        )
        ttk.Button(editor_frame, text="Add New", command=self._add_rune).grid(
            row=1, column=0, sticky="ew", padx=6, pady=2
        )
        ttk.Button(editor_frame, text="Update", command=self._update_rune).grid(
            row=2, column=0, sticky="ew", padx=6, pady=2
        )
        ttk.Button(editor_frame, text="Delete", command=self._remove_rune).grid(
            row=3, column=0, sticky="ew", padx=6, pady=(2, 6)
        )

        # Regeneration tab
        regen_tab.columnconfigure(0, weight=1)
        regen_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(regen_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        controls.columnconfigure(5, weight=1)

        ttk.Label(controls, text="⏱ Sitting Time (min)").grid(row=0, column=0, sticky="w")
        time_entry = ttk.Entry(controls, textvariable=self.rune_time_minutes_var, width=10)
        time_entry.grid(row=0, column=1, sticky="w", padx=(6, 12))
        time_entry.bind("<FocusOut>", lambda _event: self._refresh_rune_calculations())
        time_entry.bind("<Return>", lambda _event: self._refresh_rune_calculations())

        ttk.Label(controls, text="🍖 Food").grid(row=0, column=2, sticky="w")
        mode_combo = ttk.Combobox(
            controls,
            textvariable=self.rune_regen_mode_var,
            values=("Hungry", "Fed"),
            state="readonly",
            width=10,
        )
        mode_combo.grid(row=0, column=3, sticky="w", padx=(6, 12))
        mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_rune_calculations())

        ttk.Checkbutton(
            controls,
            text="🛏 Depot/Resting (Daily Reward x2)",
            variable=self.rune_use_depot_bonus_var,
            command=self._refresh_rune_calculations,
        ).grid(row=0, column=4, sticky="w", padx=(12, 0))

        items_frame = ttk.LabelFrame(regen_tab, text="💧 Mana Regen Items")
        items_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        items_frame.columnconfigure(0, weight=1)
        items_frame.rowconfigure(0, weight=1)

        columns = ("active", "item", "regen", "duration", "price", "needed", "cost")
        self.mana_items_tree = ttk.Treeview(items_frame, columns=columns, show="headings", height=8)
        self.mana_items_tree.heading("active", text="Aktiv")
        self.mana_items_tree.heading("item", text="Item")
        self.mana_items_tree.heading("regen", text="Regen/5s")
        self.mana_items_tree.heading("duration", text="Dauer")
        self.mana_items_tree.heading("price", text="Preis (gp)")
        self.mana_items_tree.heading("needed", text="Benötigt")
        self.mana_items_tree.heading("cost", text="Kosten")
        self.mana_items_tree.column("active", width=60, anchor="center")
        self.mana_items_tree.column("item", width=160, anchor="w")
        self.mana_items_tree.column("regen", width=90, anchor="e")
        self.mana_items_tree.column("duration", width=90, anchor="e")
        self.mana_items_tree.column("price", width=90, anchor="e")
        self.mana_items_tree.column("needed", width=90, anchor="e")
        self.mana_items_tree.column("cost", width=90, anchor="e")
        self.mana_items_tree.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        tree_scroll = ttk.Scrollbar(items_frame, orient="vertical", command=self.mana_items_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns", pady=6)
        self.mana_items_tree.configure(yscrollcommand=tree_scroll.set)

        self.rune_mana_item_rows = []
        for item in self._mana_regen_items():
            if item["name"] == "None":
                continue
            default_price = 10000.0 if item["name"] == "Soft Boots" else float(
                self.mana_items_prices.get(item["name"], 0.0)
            )
            row = {
                "item": item,
                "selected_var": tk.BooleanVar(value=False),
                "price_var": tk.StringVar(value=self._format_rune_value(default_price)),
                "needed_var": tk.StringVar(value="0"),
                "cost_var": tk.StringVar(value="0"),
            }
            self.rune_mana_item_rows.append(row)
            self.mana_items_tree.insert(
                "",
                tk.END,
                iid=item["name"],
                values=(
                    "",
                    item["name"],
                    self._format_rune_value(float(item.get("mana_per_sec", 0.0)) * 5.0),
                    self._format_duration_minutes(int(item.get("duration_sec", 0) or 0)),
                    row["price_var"].get(),
                    row["needed_var"].get(),
                    row["cost_var"].get(),
                ),
            )

        def _toggle_item(_event: tk.Event) -> None:
            selection = self.mana_items_tree.selection()
            if not selection:
                return
            name = selection[0]
            row = next((r for r in self.rune_mana_item_rows if r["item"]["name"] == name), None)
            if not row:
                return
            row["selected_var"].set(not row["selected_var"].get())
            self._refresh_rune_calculations()

        def _edit_price(_event: tk.Event) -> None:
            selection = self.mana_items_tree.selection()
            if not selection:
                return
            name = selection[0]
            if name == "Soft Boots":
                return
            row = next((r for r in self.rune_mana_item_rows if r["item"]["name"] == name), None)
            if not row:
                return
            value = row["price_var"].get()
            new_value = simpledialog.askstring("Preis", f"Preis für {name}:", initialvalue=value)
            if new_value is None:
                return
            row["price_var"].set(new_value)
            self._save_mana_item_price(name, row["price_var"])
            self._refresh_rune_calculations()

        self.mana_items_tree.bind("<Double-Button-1>", _toggle_item)
        self.mana_items_tree.bind("<Return>", _toggle_item)
        self.mana_items_tree.bind("<Button-3>", _edit_price)

        results_frame = ttk.LabelFrame(regen_tab, text="📊 Ergebnis")
        results_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        results_frame.columnconfigure(1, weight=1)
        results_frame.columnconfigure(3, weight=1)

        ttk.Label(results_frame, text="Start Mana").grid(row=0, column=0, sticky="w", padx=6, pady=(6, 2))
        start_percent_values = [f"{value}%" for value in range(0, 101, 10)]
        start_percent_combo = ttk.Combobox(
            results_frame,
            textvariable=self.rune_regen_start_percent_var,
            values=start_percent_values,
            state="readonly",
            width=8,
        )
        start_percent_combo.grid(row=0, column=1, sticky="w", padx=6, pady=(6, 2))
        start_percent_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_rune_calculations())

        show_formulas_check = ttk.Checkbutton(
            results_frame,
            text="Formeln",
            variable=self.rune_regen_show_formulas_var,
            command=self._toggle_rune_regen_formulas,
        )
        show_formulas_check.grid(row=0, column=3, sticky="e", padx=6, pady=(6, 2))

        calc_fields = [
            ("⏳ Zeit bis Mana wieder bei 100%", "time_to_full"),
            ("⏱ Zeit", "time_used"),
            ("💧 Mana regeneriert", "mana_regenerated"),
            ("🔮 Soulpunkte regeneriert (x Min)", "soul_regenerated"),
            ("🔮 Soulpunkte verfügbar (Start 200)", "soul_available"),
            ("⚠️ Soulpunkte benötigt (x Min)", "soul_needed_regen"),
            ("🔥 Mana verbraucht (x Min)", "mana_spent_regen"),
            ("📈 ML Gewinn", "ml_gain_regen"),
            ("🎯 Casts insgesamt", "casts_from_regen"),
            ("📜 Runen insgesamt", "runes_from_regen"),
            ("💰 Gold für Runen insgesamt", "gold_from_regen"),
            ("🏦 Gewinn durch Deposit", "deposit_gain"),
            ("🧾 Item-Kosten", "item_cost"),
            ("🪵 Blank Rune Kosten", "blank_rune_cost"),
            ("⚖️ Netto (Runen - Kosten)", "net_regen"),
            ("🏭 Kosten pro Rune", "cost_per_rune"),
            ("📈 Gewinn/Verlust pro Rune", "profit_per_rune"),
            ("🛒 EK vs Produktion (pro Rune)", "buy_vs_make_per_rune"),
        ]
        self.rune_regen_result_vars = {}
        self.rune_regen_formula_vars = {}
        self.rune_regen_formula_labels = []
        for idx, (label, key) in enumerate(calc_fields):
            col = 0 if idx < 6 else 2
            display_row = ((idx if idx < 6 else idx - 6) * 2) + 1
            ttk.Label(results_frame, text=label).grid(row=display_row, column=col, sticky="w", padx=6, pady=2)
            value_var = tk.StringVar(value="0")
            formula_var = tk.StringVar(value="")
            ttk.Label(results_frame, textvariable=value_var).grid(
                row=display_row, column=col + 1, sticky="w", padx=6, pady=2
            )
            formula_label = ttk.Label(results_frame, textvariable=formula_var, style="Formula.TLabel")
            formula_label.grid(
                row=display_row + 1, column=col + 1, sticky="w", padx=6, pady=(0, 6)
            )
            self.rune_regen_result_vars[key] = value_var
            self.rune_regen_formula_vars[key] = formula_var
            self.rune_regen_formula_labels.append(formula_label)

        self._toggle_rune_regen_formulas()

        self._build_rune_soul_cycle_tab(soul_cycle_tab)

        # Potions tab
        potions_tab.columnconfigure(1, weight=1)

        potion_frame = ttk.LabelFrame(potions_tab, text="🧪 Mana Potion Calculator")
        potion_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        potion_frame.columnconfigure(1, weight=1)

        ttk.Label(potion_frame, text="🧪 Potion").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        potion_names = [item["name"] for item in self._mana_potions()]
        potion_combo = ttk.Combobox(
            potion_frame,
            textvariable=self.rune_potion_var,
            values=potion_names,
            state="readonly",
            width=26,
        )
        potion_combo.grid(row=0, column=1, sticky="w", padx=6, pady=6)
        potion_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_potion_stats())

        ttk.Label(potion_frame, text="🔢 Count").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        potion_count_entry = ttk.Entry(potion_frame, textvariable=self.rune_potion_count_var, width=8)
        potion_count_entry.grid(row=0, column=3, sticky="w", padx=6, pady=6)
        potion_count_entry.bind("<FocusOut>", lambda _event: self._refresh_potion_stats())
        potion_count_entry.bind("<Return>", lambda _event: self._refresh_potion_stats())
        self.rune_potion_count_entry = potion_count_entry

        hint_label = ttk.Label(potion_frame, textvariable=self.rune_potion_hint_var, foreground="#b00020")
        hint_label.grid(row=1, column=2, columnspan=2, sticky="w", padx=6, pady=(0, 6))

        self.rune_potion_vars = {}
        self.rune_potion_formula_vars = {}
        potion_fields = [
            ("💧 Avg. Mana Regain", "mana_gain"),
            ("💰 Price (gp)", "price"),
            ("__sep__", "__sep__"),
            ("⏱ Time Needed", "time_needed"),
            ("💧 Mana from Potions", "mana_total"),
            ("🔥 Mana Spent", "mana_spent"),
            ("📈 ML Gewinn", "ml_gain_potion"),
            ("🧾 Potion Cost", "potion_cost"),
            ("🪵 Blank Rune Kosten", "blank_rune_cost"),
            ("🏦 Deposit", "deposit"),
            ("🔮 Soul Regenerated", "soul_regen"),
            ("🔮 Soul Needed", "soul_needed"),
            ("📜 Runes from Potions", "runes_from_potions"),
            ("💰 Gold from Runes", "gold_from_runes"),
            ("⚖️ Net (Runes - Costs)", "net_profit"),
            ("🏭 Kosten pro Rune", "cost_per_rune"),
            ("📈 Gewinn/Verlust pro Rune", "profit_per_rune"),
            ("🛒 EK vs Produktion (pro Rune)", "buy_vs_make_per_rune"),
            ("⏳ Time to Soul 200", "time_to_soul_200"),
        ]
        for idx, (label, key) in enumerate(potion_fields, start=1):
            display_row = (idx - 1) * 2 + 1
            if key == "__sep__":
                sep = ttk.Separator(potion_frame, orient="horizontal")
                sep.grid(row=display_row, column=0, columnspan=4, sticky="ew", padx=6, pady=6)
                continue
            ttk.Label(potion_frame, text=label).grid(row=display_row, column=0, sticky="w", padx=6, pady=2)
            value_var = tk.StringVar(value="0")
            formula_var = tk.StringVar(value="")
            ttk.Label(potion_frame, textvariable=value_var).grid(
                row=display_row, column=1, columnspan=3, sticky="w", padx=6, pady=2
            )
            ttk.Label(potion_frame, textvariable=formula_var, style="Formula.TLabel").grid(
                row=display_row + 1, column=1, columnspan=3, sticky="w", padx=6, pady=(0, 6)
            )
            self.rune_potion_vars[key] = value_var
            self.rune_potion_formula_vars[key] = formula_var

        refresh_rune_list()
        self._refresh_rune_spell_choices()
        self._refresh_rune_character_stats()
        self._sync_rune_editor_from_selection()
        self._refresh_rune_calculations()
        self._refresh_potion_stats()

    def _open_rune_editor_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Rune Editor")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        editor_fields = [
            ("Name", "name"),
            ("Runes/Spell", "runes_per_cast"),
            ("Mana Cost", "mana_cost"),
            ("Soul Points", "soul_cost"),
            ("EK (gp)", "ek_gp"),
            ("VK (gp)", "vk_gp"),
        ]
        for row, (label, key) in enumerate(editor_fields):
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=2)
            var = self.rune_editor_vars.get(key) or tk.StringVar()
            ttk.Entry(dialog, textvariable=var, width=20).grid(row=row, column=1, sticky="w", padx=6, pady=2)
            self.rune_editor_vars[key] = var

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=len(editor_fields), column=0, columnspan=2, sticky="e", padx=6, pady=6)
        ttk.Button(button_frame, text="Add New", command=self._add_rune).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(button_frame, text="Update", command=self._update_rune).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(button_frame, text="Delete", command=self._remove_rune).grid(row=0, column=2)

    def _toggle_rune_regen_formulas(self) -> None:
        show = bool(self.rune_regen_show_formulas_var.get())
        for label in getattr(self, "rune_regen_formula_labels", []):
            if show:
                label.grid()
            else:
                label.grid_remove()

    def _toggle_rune_soul_formulas(self) -> None:
        show = bool(self.rune_soul_show_formulas_var.get())
        for label in getattr(self, "rune_soul_formula_labels", []):
            if show:
                label.grid()
            else:
                label.grid_remove()

    def _build_rune_soul_cycle_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        controls = ttk.LabelFrame(parent, text="Simulation")
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        controls.columnconfigure(9, weight=1)

        ttk.Label(controls, text="⏱ Zeit (Min)").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        time_entry = ttk.Entry(controls, textvariable=self.rune_time_minutes_var, width=10)
        time_entry.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=6)
        time_entry.bind("<FocusOut>", lambda _event: self._refresh_rune_calculations())
        time_entry.bind("<Return>", lambda _event: self._refresh_rune_calculations())

        ttk.Label(controls, text="Start Mana").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        start_percent_values = [f"{value}%" for value in range(0, 101, 10)]
        start_percent_combo = ttk.Combobox(
            controls,
            textvariable=self.rune_regen_start_percent_var,
            values=start_percent_values,
            state="readonly",
            width=8,
        )
        start_percent_combo.grid(row=0, column=3, sticky="w", padx=(0, 10), pady=6)
        start_percent_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_rune_calculations())

        ttk.Label(controls, text="🍖 Food").grid(row=0, column=4, sticky="w", padx=6, pady=6)
        mode_combo = ttk.Combobox(
            controls,
            textvariable=self.rune_regen_mode_var,
            values=("Hungry", "Fed"),
            state="readonly",
            width=10,
        )
        mode_combo.grid(row=0, column=5, sticky="w", padx=(0, 10), pady=6)
        mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_rune_calculations())

        ttk.Checkbutton(
            controls,
            text="🛏 Depot/Resting (Daily Reward x2)",
            variable=self.rune_use_depot_bonus_var,
            command=self._refresh_rune_calculations,
        ).grid(row=0, column=6, sticky="w", padx=(0, 10), pady=6)

        ttk.Label(controls, text="🧪 Auto-Potion").grid(row=0, column=7, sticky="w", padx=6, pady=6)
        potion_names = [item["name"] for item in self._mana_potions()]
        potion_combo = ttk.Combobox(
            controls,
            textvariable=self.rune_soul_potion_var,
            values=potion_names,
            state="readonly",
            width=22,
        )
        potion_combo.grid(row=0, column=8, sticky="w", padx=(0, 6), pady=6)
        potion_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_rune_soul_cycle_stats())

        ttk.Label(
            controls,
            text="Start Soul = 0, Cast-Versuch bei Soul >= 5",
            style="Formula.TLabel",
        ).grid(row=1, column=0, columnspan=9, sticky="w", padx=6, pady=(0, 6))

        result_frame = ttk.LabelFrame(parent, text="Ergebnis")
        result_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        result_frame.columnconfigure(1, weight=1)
        result_frame.columnconfigure(3, weight=1)
        ttk.Checkbutton(
            result_frame,
            text="Formeln",
            variable=self.rune_soul_show_formulas_var,
            command=self._toggle_rune_soul_formulas,
        ).grid(row=0, column=3, sticky="e", padx=6, pady=(6, 2))

        fields = [
            ("⏱ Simulierte Zeit", "time_used"),
            ("💧 Nat. Mana Regen", "natural_mana_regen"),
            ("🔮 Soul regeneriert", "soul_regenerated"),
            ("📈 ML Gewinn (x Min)", "ml_gain_cycle"),
            ("🎯 Casts gesamt", "casts"),
            ("📜 Runen gesamt", "runes_total"),
            ("🔥 Mana verbraucht", "mana_spent"),
            ("🔮 Soul verbraucht", "soul_spent"),
            ("🧪 Potions getrunken", "potions_used"),
            ("💧 Mana aus Potions", "mana_from_potions"),
            ("🧾 Potion-Kosten", "potion_cost"),
            ("🧾 Item-Kosten", "item_cost"),
            ("🪵 Blank Rune Kosten", "blank_rune_cost"),
            ("💰 Gold aus Runen", "gold_from_runes"),
            ("⚖️ Netto", "net_profit"),
            ("🏭 Kosten pro Rune", "cost_per_rune"),
            ("📈 Gewinn/Verlust pro Rune", "profit_per_rune"),
            ("🛒 EK vs Produktion (pro Rune)", "buy_vs_make_per_rune"),
            ("💧 End-Mana", "end_mana"),
            ("🔮 End-Soul", "end_soul"),
        ]
        self.rune_soul_result_vars = {}
        self.rune_soul_formula_vars = {}
        self.rune_soul_formula_labels = []
        for idx, (label, key) in enumerate(fields):
            col = 0 if idx < 8 else 2
            row = ((idx if idx < 8 else idx - 8) * 2) + 1
            ttk.Label(result_frame, text=label).grid(row=row, column=col, sticky="w", padx=6, pady=2)
            value_var = tk.StringVar(value="0")
            formula_var = tk.StringVar(value="")
            ttk.Label(result_frame, textvariable=value_var).grid(row=row, column=col + 1, sticky="w", padx=6, pady=2)
            formula_label = ttk.Label(result_frame, textvariable=formula_var, style="Formula.TLabel")
            formula_label.grid(row=row + 1, column=col + 1, sticky="w", padx=6, pady=(0, 6))
            self.rune_soul_result_vars[key] = value_var
            self.rune_soul_formula_vars[key] = formula_var
            self.rune_soul_formula_labels.append(formula_label)
        self._toggle_rune_soul_formulas()

    def _build_search_window_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        self._sync_search_window_vars()

        ttk.Label(parent, text="Breite").grid(row=0, column=0, sticky="w", padx=6, pady=(6, 2))
        ttk.Entry(parent, textvariable=self.search_window_width_var, width=10).grid(
            row=0, column=1, sticky="w", padx=6, pady=(6, 2)
        )

        ttk.Label(parent, text="HÃ¶he").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(parent, textvariable=self.search_window_height_var, width=10).grid(
            row=1, column=1, sticky="w", padx=6, pady=2
        )

        ttk.Label(parent, text="Position X").grid(row=2, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(parent, textvariable=self.search_window_x_var, width=10).grid(
            row=2, column=1, sticky="w", padx=6, pady=2
        )

        ttk.Label(parent, text="Position Y").grid(row=3, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(parent, textvariable=self.search_window_y_var, width=10).grid(
            row=3, column=1, sticky="w", padx=6, pady=2
        )
        ttk.Checkbutton(
            parent,
            text="Position gelockt (Alt + Ziehen zum Verschieben wenn aus)",
            variable=self.search_window_lock_var,
            command=self._on_search_window_lock_toggle,
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=6, pady=2)

        action_frame = ttk.Frame(parent)
        action_frame.grid(row=5, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 6))

        ttk.Button(action_frame, text="Fenster zeigen", command=self._show_search_window).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(action_frame, text="Aktuell laden", command=self._sync_search_window_vars).grid(
            row=0, column=1, padx=(0, 6)
        )
        ttk.Button(action_frame, text="Ãœbernehmen", command=self._apply_search_window_geometry).grid(
            row=0, column=2
        )

    def _on_search_window_resize(self, _event: tk.Event) -> None:
        self._update_search_window_padding()
        self._sync_search_window_vars()
        if not self.search_window_lock_var.get() and self._search_window_position_dirty:
            return
        self._queue_search_window_save()

    def _on_search_window_lock_toggle(self) -> None:
        self._apply_search_window_lock_state()
        if self.search_window_lock_var.get():
            self._queue_search_window_save(commit_position=True)

    def _apply_search_window_lock_state(self) -> None:
        if not self.search_window or not self.search_window.winfo_exists():
            return
        if self.search_window_lock_var.get():
            self.search_window.configure(cursor="")
        else:
            self.search_window.configure(cursor="fleur")

    def _on_search_window_drag_start(self, event: tk.Event) -> None:
        if self.search_window_lock_var.get():
            return
        if not self.search_window or not self.search_window.winfo_exists():
            return
        self._search_window_drag_start = (int(event.x_root), int(event.y_root))
        self._search_window_drag_origin = (int(self.search_window.winfo_x()), int(self.search_window.winfo_y()))

    def _on_search_window_drag_move(self, event: tk.Event) -> None:
        if self.search_window_lock_var.get():
            return
        if not self.search_window or not self.search_window.winfo_exists():
            return
        if self._search_window_drag_start is None or self._search_window_drag_origin is None:
            return
        start_x, start_y = self._search_window_drag_start
        origin_x, origin_y = self._search_window_drag_origin
        new_x = origin_x + int(event.x_root) - start_x
        new_y = origin_y + int(event.y_root) - start_y
        self.search_window.geometry(f"+{new_x}+{new_y}")
        self._search_window_position_dirty = True
        self._sync_search_window_vars()

    def _on_search_window_drag_end(self, _event: tk.Event) -> None:
        self._search_window_drag_start = None
        self._search_window_drag_origin = None

    def _update_search_window_padding(self) -> None:
        if not self.search_window or not self.search_window.winfo_exists():
            return
        height = self.search_window.winfo_height()
        entry_req = self.search_entry.winfo_reqheight()
        button_req = self.top_button.winfo_reqheight()
        target = max(entry_req, button_req, 1)
        extra = max(0, height - target)
        pad = extra // 2
        style = ttk.Style(self.root)
        style.configure("Search.TEntry", padding=(4, pad))
        style.configure("Search.TButton", padding=(6, pad))

    def _sync_search_window_vars(self) -> None:
        if not self.search_window or not self.search_window.winfo_exists():
            return
        self.search_window.update_idletasks()
        width = self.search_window.winfo_width()
        height = self.search_window.winfo_height()
        x = self.search_window.winfo_x()
        y = self.search_window.winfo_y()
        self.search_window_width_var.set(str(width))
        self.search_window_height_var.set(str(height))
        self.search_window_x_var.set(str(x))
        self.search_window_y_var.set(str(y))

    def _show_search_window(self) -> None:
        if not self.search_window or not self.search_window.winfo_exists():
            self._build_search_window()
            return
        self.search_window.deiconify()
        self.search_window.lift()
        self.search_window.focus_force()

    def _apply_search_window_geometry(self) -> None:
        if not self.search_window or not self.search_window.winfo_exists():
            return
        width = self._parse_int_value(self.search_window_width_var.get())
        height = self._parse_int_value(self.search_window_height_var.get())
        x = self._parse_int_value(self.search_window_x_var.get())
        y = self._parse_int_value(self.search_window_y_var.get())
        if width is None or height is None or x is None or y is None:
            messagebox.showwarning("UngÃ¼ltig", "Bitte gÃ¼ltige Zahlen fÃ¼r Breite, HÃ¶he, X und Y eingeben.")
            return
        width = max(1, width)
        height = max(1, height)
        self.search_window.geometry(f"{width}x{height}+{x}+{y}")
        self.search_window.minsize(width, height)
        self._update_search_window_padding()
        self._search_window_position_dirty = True
        self._queue_search_window_save(commit_position=True)

    def _apply_saved_search_window_geometry(self) -> None:
        state = self.search_window_state
        if not state:
            return
        width = state.get("width")
        height = state.get("height")
        x = state.get("x")
        y = state.get("y")
        if all(isinstance(value, int) for value in (width, height, x, y)):
            self.search_window.geometry(f"{width}x{height}+{x}+{y}")
            self.search_window.minsize(max(1, width), max(1, height))
        topmost = state.get("topmost")
        if isinstance(topmost, bool):
            self.always_on_top = topmost
            self.search_window.attributes("-topmost", self.always_on_top)
        position_locked = state.get("position_locked")
        if isinstance(position_locked, bool):
            self.search_window_lock_var.set(position_locked)

    def _queue_search_window_save(self, commit_position: bool = False) -> None:
        self._search_window_commit_position_on_save = self._search_window_commit_position_on_save or commit_position
        if self._search_window_save_after is not None:
            self.root.after_cancel(self._search_window_save_after)
        self._search_window_save_after = self.root.after(200, self._save_search_window_state)

    def _save_search_window_state(self, force_position: bool = False) -> None:
        self._search_window_save_after = None
        commit_position = self._search_window_commit_position_on_save or force_position
        self._search_window_commit_position_on_save = False
        if not self._search_window_ready:
            return
        if not self.search_window or not self.search_window.winfo_exists():
            return
        width = int(self.search_window.winfo_width())
        height = int(self.search_window.winfo_height())
        x = int(self.search_window.winfo_x())
        y = int(self.search_window.winfo_y())
        prev = self.search_window_state or {}
        if width <= 1 or height <= 1:
            width = int(prev.get("width", width) or width)
            height = int(prev.get("height", height) or height)
        if x == 0 and y == 0:
            prev_x = prev.get("x")
            prev_y = prev.get("y")
            if isinstance(prev_x, int) and isinstance(prev_y, int) and (prev_x, prev_y) != (0, 0):
                x, y = prev_x, prev_y
        if self._search_window_position_dirty and not (self.search_window_lock_var.get() or commit_position):
            prev_x = prev.get("x")
            prev_y = prev.get("y")
            if isinstance(prev_x, int) and isinstance(prev_y, int):
                x, y = prev_x, prev_y
        else:
            self._search_window_position_dirty = False
        payload = {
            "width": width,
            "height": height,
            "x": x,
            "y": y,
            "topmost": bool(self.always_on_top),
            "position_locked": bool(self.search_window_lock_var.get()),
        }
        self.search_window_state = payload
        self.search_window_state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def _load_search_window_state(self) -> None:
        if not self.search_window_state_path.exists():
            return
        try:
            payload = json.loads(self.search_window_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        if isinstance(payload, dict):
            self.search_window_state = payload

    def _load_mana_items_prices(self) -> None:
        if not self.mana_items_state_path.exists():
            self.mana_items_prices = {}
            return
        try:
            payload = json.loads(self.mana_items_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.mana_items_prices = {}
            return
        if isinstance(payload, dict):
            self.mana_items_prices = {str(k): float(v) for k, v in payload.items()}

    def _save_mana_items_prices(self) -> None:
        try:
            self.mana_items_state_path.write_text(
                json.dumps(self.mana_items_prices, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _save_mana_item_price(self, name: str, var: tk.StringVar) -> None:
        value = self._parse_float_value(var.get())
        if value is None:
            return
        self.mana_items_prices[name] = value
        self._save_mana_items_prices()

    def _parse_int_value(self, value: str) -> int | None:
        value = value.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _parse_float_value(self, value: str) -> float | None:
        value = value.strip().replace(",", ".")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _format_rune_value(self, value: float) -> str:
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _format_de_number(self, value: float, decimals: int = 0) -> str:
        return _format_number(value, decimals)

    def _format_with_unit(self, value: float, unit: str, decimals: int = 0) -> str:
        return f"{self._format_de_number(value, decimals)} {unit}"

    def _format_gp_float(self, value: float, decimals: int = 2) -> str:
        return f"{self._format_de_number(value, decimals)} gp"

    def _format_gp_per_rune(self, value: float, decimals: int = 2) -> str:
        return f"{self._format_de_number(value, decimals)} gp/Rune"

    def _format_signed_gp_per_rune(self, value: float, decimals: int = 2) -> str:
        prefix = "+" if value > 0 else ""
        return f"{prefix}{self._format_de_number(value, decimals)} gp/Rune"

    def _magic_level_percent_gain(self, mana_spent: float, magic_level: int, vocation_value: str) -> float:
        if mana_spent <= 0:
            return 0.0
        b_map = {
            "Elite Knight": 3.0,
            "Royal Paladin": 1.4,
            "Master Sorcerer": 1.1,
            "Elder Druid": 1.1,
        }
        b = b_map.get(vocation_value, 1.1)
        if b <= 1.0:
            mana_to_next = 1600.0 * (b ** max(0, magic_level))
            if mana_to_next <= 0:
                return 0.0
            return (mana_spent / mana_to_next) * 100.0
        remaining_mana = float(mana_spent)
        current_ml = max(0, int(magic_level))
        gained_percent = 0.0
        iterations = 0
        while remaining_mana > 0 and iterations < 10000:
            iterations += 1
            mana_to_next = 1600.0 * (b ** current_ml)
            if mana_to_next <= 0:
                break
            if remaining_mana >= mana_to_next:
                gained_percent += 100.0
                remaining_mana -= mana_to_next
                current_ml += 1
                continue
            gained_percent += (remaining_mana / mana_to_next) * 100.0
            break
        return gained_percent

    def _compute_derived_stats(
        self,
        level: int,
        magic_level: int,
        vocation_value: str,
        existing_stats: dict[str, object],
    ) -> dict[str, object]:
        mage_vocations = {"Elder Druid", "Master Sorcerer"}
        is_mage = vocation_value in mage_vocations

        if is_mage:
            hp = 5 * (level + 29)
            mana = 30 * level - 150
            capacity = 10 * (level + 19)
        else:
            hp = int(existing_stats.get("hp") or 0)
            mana = int(existing_stats.get("mana") or 0)
            capacity = int(existing_stats.get("capacity") or 0)

        speed = 109 + level
        soul_points = 200
        ml_percent = float(existing_stats.get("ml_percent") or 0.0)

        if is_mage:
            mana_regen_hungry = 5.0
            mana_regen_fed = 6.0
            hp_regen_hungry = 4.0
            hp_regen_fed = 5.0
        else:
            mana_regen_hungry = 2.0 * 5.0 / 6.0
            mana_regen_fed = 2.0
            hp_regen_hungry = 8.0
            hp_regen_fed = 10.0

        mana_regen_depot = mana_regen_fed * 2.0
        hp_regen_depot = hp_regen_fed * 2.0

        return {
            "hp": hp,
            "mana": mana,
            "capacity": capacity,
            "speed": speed,
            "soul_points": soul_points,
            "ml_percent": ml_percent,
            "mana_regen_hungry": mana_regen_hungry,
            "mana_regen_fed": mana_regen_fed,
            "mana_regen_depot": mana_regen_depot,
            "hp_regen_hungry": hp_regen_hungry,
            "hp_regen_fed": hp_regen_fed,
            "hp_regen_depot": hp_regen_depot,
        }

    def _mana_regen_items(self) -> list[dict[str, object]]:
        return [
            {"name": "None", "mana_per_sec": 0.0, "duration_sec": 0},
            {"name": "Soft Boots", "mana_per_sec": 2.0, "duration_sec": 4 * 60 * 60},
            {"name": "Ring of Healing", "mana_per_sec": 4.0, "duration_sec": 7 * 60 + 30},
            {"name": "Life Ring", "mana_per_sec": 8.0 / 6.0, "duration_sec": 20 * 60},
            {"name": "Tiara of Power", "mana_per_sec": 8.0 / 6.0, "duration_sec": 60 * 60},
            {"name": "Collar of Green Plasma", "mana_per_sec": 8.0 / 6.0, "duration_sec": 30 * 60},
        ]

    def _format_duration_minutes(self, duration_sec: int) -> str:
        if duration_sec <= 0:
            return "â€”"
        minutes = duration_sec // 60
        hours = minutes // 60
        minutes = minutes % 60
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def _format_minutes_seconds(self, seconds: float) -> str:
        if seconds < 0:
            seconds = 0.0
        total_seconds = int(round(seconds))
        minutes = total_seconds // 60
        secs = total_seconds % 60
        return f"{minutes} Minuten {secs} Sekunden"

    def _mana_potions(self) -> list[dict[str, object]]:
        return [
            {"name": "None", "mana_gain": 0, "price": 0},
            {"name": "Mana Potion", "mana_gain": 100, "price": 51},
            {"name": "Strong Mana Potion", "mana_gain": 150, "price": 88},
            {"name": "Great Mana Potion", "mana_gain": 200, "price": 139},
            {"name": "Ultimate Mana Potion", "mana_gain": 500, "price": 433},
            {"name": "Great Spirit Potion", "mana_gain": 150, "price": 185},
            {"name": "Ultimate Spirit Potion", "mana_gain": 200, "price": 345},
        ]

    def _refresh_potion_stats(self) -> None:
        selected = self.rune_potion_var.get().strip() or "None"
        entry = next((item for item in self._mana_potions() if item["name"] == selected), None)
        if not entry:
            entry = self._mana_potions()[0]
        mana_gain = int(entry.get("mana_gain", 0) or 0)
        price = int(entry.get("price", 0) or 0)
        count = self._parse_int_value(self.rune_potion_count_var.get()) or 0
        rune = self._get_selected_rune() or {}
        mana_cost = int(rune.get("mana", 0) or 0)
        runes_per_cast = int(rune.get("runes_per_cast", 0) or 0)
        ek_gp = int(rune.get("ek_gp", 0) or 0)
        vk_gp = int(rune.get("vk_gp", 0) or 0)
        soul_cost = int(rune.get("soul_points", 0) or 0)

        def _count_ok(candidate: int) -> bool:
            if candidate <= 0:
                return True
            if mana_gain <= 0 or mana_cost <= 0:
                return False
            if soul_cost <= 0:
                return True
            mana_casts = (mana_gain * candidate) // mana_cost
            soul_available = 200 + (candidate / 16.0)
            soul_casts = int(soul_available // soul_cost)
            return mana_casts <= soul_casts

        max_count = count
        if mana_gain > 0 and mana_cost > 0 and soul_cost > 0:
            if not _count_ok(count):
                lo, hi = 0, count
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if _count_ok(mid):
                        max_count = mid
                        lo = mid + 1
                    else:
                        hi = mid - 1
        if max_count < count:
            count = max_count
            self.rune_potion_count_var.set(str(count))
            if self.rune_potion_count_entry:
                self.rune_potion_count_entry.configure(style="Warning.TEntry")
            self.rune_potion_hint_var.set("Maximal wegen Soul-Limit")
        else:
            if self.rune_potion_count_entry:
                self.rune_potion_count_entry.configure(style="TEntry")
            self.rune_potion_hint_var.set("")

        character = self._get_character_by_name(self.rune_character_var.get().strip())
        stats = character.get("stats", {})
        if not isinstance(stats, dict):
            stats = {}
        max_mana = int(stats.get("mana") or 0)

        total_mana = mana_gain * count
        total_mana_available = max_mana + total_mana
        potion_cost = price * count
        deposit = count * 5
        time_seconds = count
        time_minutes = time_seconds / 60.0
        time_hours = time_seconds / 3600.0

        soul_regen_per_5s = 5.0 / 16.0
        soul_regenerated = soul_regen_per_5s * (time_seconds / 5.0) if time_seconds > 0 else 0.0
        soul_available = 200 + soul_regenerated

        casts_from_potions = total_mana_available // mana_cost if mana_cost > 0 else 0
        if soul_cost > 0:
            casts_from_potions = min(casts_from_potions, int(soul_available // soul_cost))
        runes_from_potions = casts_from_potions * runes_per_cast
        gold_from_runes = runes_from_potions * vk_gp
        blank_rune_cost = casts_from_potions * 10
        net_profit = gold_from_runes - potion_cost - blank_rune_cost + deposit
        soul_needed = casts_from_potions * soul_cost
        mana_spent = casts_from_potions * mana_cost
        mana_spent_from_potions = max(0, mana_spent - max_mana)
        vocation = str(self._get_character_by_name(self.rune_character_var.get().strip()).get("vocation", VOCATIONS[0]))
        magic_level = int(self._get_character_by_name(self.rune_character_var.get().strip()).get("stats", {}).get("magic_level", 0) or 0)
        ml_gain_potion = self._magic_level_percent_gain(mana_spent, magic_level, vocation)
        soul_remaining = max(0.0, soul_available - soul_needed)
        soul_missing = max(0.0, 200 - soul_remaining)
        time_to_soul_200_sec = soul_missing * 16.0

        if "mana_gain" in self.rune_potion_vars:
            self.rune_potion_vars["mana_gain"].set(self._format_with_unit(mana_gain, "Mana", 0))
            self.rune_potion_formula_vars["mana_gain"].set("")
        if "price" in self.rune_potion_vars:
            self.rune_potion_vars["price"].set(self._format_gp(price))
            self.rune_potion_formula_vars["price"].set("")
        if "time_needed" in self.rune_potion_vars:
            self.rune_potion_vars["time_needed"].set(
                f"{self._format_de_number(time_seconds, 0)} Sekunden / "
                f"{self._format_de_number(time_minutes, 2)} Minuten / "
                f"{self._format_de_number(time_hours, 2)} Stunden"
            )
            self.rune_potion_formula_vars["time_needed"].set(
                f"({count} × 1s)"
            )
        if "mana_total" in self.rune_potion_vars:
            self.rune_potion_vars["mana_total"].set(
                f"{self._format_de_number(total_mana_available, 0)} Mana"
            )
            self.rune_potion_formula_vars["mana_total"].set(
                f"({self._format_de_number(max_mana, 0)} + {mana_gain} × {count})"
            )
        if "mana_spent" in self.rune_potion_vars:
            self.rune_potion_vars["mana_spent"].set(
                f"{self._format_de_number(mana_spent, 0)} Mana"
            )
            self.rune_potion_formula_vars["mana_spent"].set(
                f"({casts_from_potions} × {mana_cost}) = "
                f"{self._format_de_number(mana_spent_from_potions, 0)} Mana aus Potions"
            )
        if "ml_gain_potion" in self.rune_potion_vars:
            self.rune_potion_vars["ml_gain_potion"].set(
                f"{self._format_de_number(ml_gain_potion, 2)} %"
            )
            self.rune_potion_formula_vars["ml_gain_potion"].set(
                f"(stufenweise ab ML {magic_level}, Mana gesamt {self._format_de_number(mana_spent, 0)})"
            )
            if "ml_gain_potion" in self.rune_result_vars:
                self.rune_result_vars["ml_gain_potion"].set(f"{self._format_de_number(ml_gain_potion, 2)} %")
        if "potion_cost" in self.rune_potion_vars:
            self.rune_potion_vars["potion_cost"].set(self._format_gp(int(potion_cost)))
            self.rune_potion_formula_vars["potion_cost"].set(
                f"({price} × {count})"
            )
        if "blank_rune_cost" in self.rune_potion_vars:
            self.rune_potion_vars["blank_rune_cost"].set(self._format_gp(int(blank_rune_cost)))
            self.rune_potion_formula_vars["blank_rune_cost"].set(
                f"({casts_from_potions} × 10)"
            )
        if "deposit" in self.rune_potion_vars:
            self.rune_potion_vars["deposit"].set(self._format_gp(int(deposit)))
            self.rune_potion_formula_vars["deposit"].set(
                f"({count} × 5)"
            )
        if "soul_regen" in self.rune_potion_vars:
            self.rune_potion_vars["soul_regen"].set(
                f"{self._format_de_number(soul_regenerated, 0)} Soul"
            )
            self.rune_potion_formula_vars["soul_regen"].set(
                f"({self._format_de_number(soul_regen_per_5s, 2)} × "
                f"{self._format_de_number(time_seconds, 0)} / 5)"
            )
        if "soul_needed" in self.rune_potion_vars:
            self.rune_potion_vars["soul_needed"].set(
                f"{self._format_de_number(soul_needed, 0)} Soul"
            )
            self.rune_potion_formula_vars["soul_needed"].set(
                f"({casts_from_potions} × {soul_cost})"
            )
        if "runes_from_potions" in self.rune_potion_vars:
            self.rune_potion_vars["runes_from_potions"].set(
                f"{self._format_de_number(runes_from_potions, 0)} Runen"
            )
            self.rune_potion_formula_vars["runes_from_potions"].set(
                f"({casts_from_potions} × {runes_per_cast})"
            )
        if "gold_from_runes" in self.rune_potion_vars:
            self.rune_potion_vars["gold_from_runes"].set(self._format_gp(int(gold_from_runes)))
            self.rune_potion_formula_vars["gold_from_runes"].set(
                f"({runes_from_potions} × {vk_gp})"
            )
        if "net_profit" in self.rune_potion_vars:
            self.rune_potion_vars["net_profit"].set(self._format_gp(int(net_profit)))
            self.rune_potion_formula_vars["net_profit"].set(
                f"({self._format_de_number(gold_from_runes, 0)} - "
                f"{self._format_de_number(potion_cost, 0)} - "
                f"{self._format_de_number(blank_rune_cost, 0)} + {deposit})"
            )
        if "cost_per_rune" in self.rune_potion_vars:
            cost_total = float(potion_cost) + float(blank_rune_cost) - float(deposit)
            if runes_from_potions > 0:
                cost_per_rune = cost_total / float(runes_from_potions)
                self.rune_potion_vars["cost_per_rune"].set(self._format_gp_per_rune(cost_per_rune, 2))
                self.rune_potion_formula_vars["cost_per_rune"].set(
                    f"(({self._format_de_number(potion_cost, 0)} + {self._format_de_number(blank_rune_cost, 0)} - "
                    f"{self._format_de_number(deposit, 0)}) / {self._format_de_number(runes_from_potions, 0)})"
                )
            else:
                self.rune_potion_vars["cost_per_rune"].set("—")
                self.rune_potion_formula_vars["cost_per_rune"].set("")
        if "profit_per_rune" in self.rune_potion_vars:
            cost_total = float(potion_cost) + float(blank_rune_cost) - float(deposit)
            if runes_from_potions > 0:
                cost_per_rune = cost_total / float(runes_from_potions)
                profit_per_rune = float(vk_gp) - cost_per_rune
                self.rune_potion_vars["profit_per_rune"].set(self._format_signed_gp_per_rune(profit_per_rune, 2))
                self.rune_potion_formula_vars["profit_per_rune"].set(f"({vk_gp} - Kosten/Rune)")
            else:
                self.rune_potion_vars["profit_per_rune"].set("—")
                self.rune_potion_formula_vars["profit_per_rune"].set("")
        if "buy_vs_make_per_rune" in self.rune_potion_vars:
            cost_total = float(potion_cost) + float(blank_rune_cost) - float(deposit)
            if runes_from_potions > 0:
                cost_per_rune = cost_total / float(runes_from_potions)
                buy_delta = float(ek_gp) - cost_per_rune
                note = "Produzieren günstiger" if buy_delta > 0 else "Kaufen günstiger" if buy_delta < 0 else "gleich"
                self.rune_potion_vars["buy_vs_make_per_rune"].set(
                    f"{self._format_signed_gp_per_rune(buy_delta, 2)} ({note})"
                )
                self.rune_potion_formula_vars["buy_vs_make_per_rune"].set(f"({ek_gp} - Kosten/Rune)")
            else:
                self.rune_potion_vars["buy_vs_make_per_rune"].set("—")
                self.rune_potion_formula_vars["buy_vs_make_per_rune"].set("")
        if "time_to_soul_200" in self.rune_potion_vars:
            self.rune_potion_vars["time_to_soul_200"].set(
                f"{self._format_de_number(time_to_soul_200_sec, 0)} Sekunden / "
                f"{self._format_de_number(time_to_soul_200_sec / 60.0, 2)} Minuten / "
                f"{self._format_de_number(time_to_soul_200_sec / 3600.0, 2)} Stunden"
            )
            self.rune_potion_formula_vars["time_to_soul_200"].set(
                f"({self._format_de_number(soul_missing, 2)} × 16)"
            )

    def _get_character_by_name(self, name: str) -> dict[str, object]:
        for entry in self.character_store.characters:
            if str(entry.get("name")) == name:
                return entry
        return self.character_store.get_active()

    def _refresh_rune_character_stats(self) -> None:
        name = self.rune_character_var.get().strip()
        character = self._get_character_by_name(name)
        level = int(character.get("level") or 1)
        stats = character.get("stats", {})
        if not isinstance(stats, dict):
            stats = {}
        vocation = str(character.get("vocation", VOCATIONS[0]))
        magic_level = int(stats.get("magic_level", 0) or 0)
        derived = self._compute_derived_stats(level, magic_level, vocation, stats)
        merged_stats = DEFAULT_STATS.copy()
        merged_stats.update(stats)
        merged_stats.update(derived)
        character["stats"] = merged_stats
        self.character_store.update_character(str(character.get("name", "")), character)

        max_mana = int(merged_stats.get("mana") or 0)
        soul_points = int(merged_stats.get("soul_points") or 0)
        magic_level_value = int(merged_stats.get("magic_level") or 0)
        regen_hungry = float(merged_stats.get("mana_regen_hungry") or 0.0)
        regen_fed = float(merged_stats.get("mana_regen_fed") or 0.0)
        regen_depot = float(merged_stats.get("mana_regen_depot") or 0.0)

        if "level" in self.rune_stats_vars:
            self.rune_stats_vars["level"].set(str(level))
        if "max_mana" in self.rune_stats_vars:
            self.rune_stats_vars["max_mana"].set(str(max_mana))
        if "soul_points" in self.rune_stats_vars:
            self.rune_stats_vars["soul_points"].set(str(soul_points))
        if "magic_level" in self.rune_stats_vars:
            self.rune_stats_vars["magic_level"].set(str(magic_level_value))
        if "ml_percent" in self.rune_stats_vars:
            self.rune_stats_vars["ml_percent"].set(self._format_rune_value(float(merged_stats.get("ml_percent") or 0.0)))
        if "regen_hungry" in self.rune_stats_vars:
            self.rune_stats_vars["regen_hungry"].set(self._format_rune_value(regen_hungry))
        if "regen_fed" in self.rune_stats_vars:
            self.rune_stats_vars["regen_fed"].set(self._format_rune_value(regen_fed))
        if "regen_depot" in self.rune_stats_vars:
            self.rune_stats_vars["regen_depot"].set(self._format_rune_value(regen_depot))

    def _refresh_rune_spell_choices(self, select_name: str | None = None) -> None:
        names = [name for name in self.rune_store.names() if name]
        if not names:
            self.rune_spell_var.set("")
            return
        if select_name and select_name in names:
            self.rune_spell_var.set(select_name)
        else:
            active_name = str(self.rune_store.get_active().get("name", ""))
            self.rune_spell_var.set(active_name if active_name in names else names[0])
        if self.rune_spell_combo:
            self.rune_spell_combo.configure(values=names, state="readonly")
        selected = self.rune_spell_var.get().strip()
        rune = self.rune_store.get_by_name(selected)
        if rune:
            self.rune_store.set_active(str(rune.get("id")))
        if hasattr(self, "rune_listbox"):
            query = self.rune_filter_var.get().strip().casefold() if hasattr(self, "rune_filter_var") else ""
            filtered = [name for name in names if not query or query in name.casefold()]
            self.rune_listbox.delete(0, tk.END)
            for name in filtered:
                self.rune_listbox.insert(tk.END, name)
            if selected in filtered:
                idx = filtered.index(selected)
                self.rune_listbox.selection_set(idx)
                self.rune_listbox.see(idx)

    def _get_selected_rune(self) -> dict[str, object] | None:
        name = self.rune_spell_var.get().strip()
        if not name:
            return None
        return self.rune_store.get_by_name(name)

    def _sync_rune_editor_from_selection(self) -> None:
        rune = self._get_selected_rune()
        if not rune:
            for var in self.rune_editor_vars.values():
                var.set("")
            return
        if "name" in self.rune_editor_vars:
            self.rune_editor_vars["name"].set(str(rune.get("name", "")))
        if "runes_per_cast" in self.rune_editor_vars:
            self.rune_editor_vars["runes_per_cast"].set(str(rune.get("runes_per_cast", 1)))
        if "mana_cost" in self.rune_editor_vars:
            self.rune_editor_vars["mana_cost"].set(str(rune.get("mana", 0)))
        if "soul_cost" in self.rune_editor_vars:
            self.rune_editor_vars["soul_cost"].set(str(rune.get("soul_points", 0)))
        if "ek_gp" in self.rune_editor_vars:
            self.rune_editor_vars["ek_gp"].set(str(rune.get("ek_gp", 0)))
        if "vk_gp" in self.rune_editor_vars:
            self.rune_editor_vars["vk_gp"].set(str(rune.get("vk_gp", 0)))

    def _collect_rune_editor_values(self, existing_id: str | None = None) -> dict[str, object] | None:
        name = self.rune_editor_vars["name"].get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Rune name is required.")
            return None
        if not self.rune_store.is_name_unique(name, ignore_id=existing_id):
            messagebox.showwarning("Name exists", "Rune name must be unique.")
            return None
        runes_per_cast = self._parse_int_value(self.rune_editor_vars["runes_per_cast"].get())
        if runes_per_cast is None or runes_per_cast < 1:
            messagebox.showwarning("Invalid Runes", "Runes/Spell must be an integer >= 1.")
            return None
        mana_cost = self._parse_int_value(self.rune_editor_vars["mana_cost"].get())
        if mana_cost is None or mana_cost < 1:
            messagebox.showwarning("Invalid Mana", "Mana Cost must be an integer >= 1.")
            return None
        soul_cost = self._parse_int_value(self.rune_editor_vars["soul_cost"].get())
        if soul_cost is None or soul_cost < 0:
            messagebox.showwarning("Invalid Soul Points", "Soul Points must be an integer >= 0.")
            return None
        vk_gp = self._parse_int_value(self.rune_editor_vars["vk_gp"].get())
        if vk_gp is None or vk_gp < 0:
            messagebox.showwarning("Invalid VK", "VK (gp) must be an integer >= 0.")
            return None
        ek_input = self._parse_int_value(self.rune_editor_vars.get("ek_gp", tk.StringVar()).get())
        if ek_input is not None and ek_input < 0:
            messagebox.showwarning("Invalid EK", "EK (gp) must be an integer >= 0.")
            return None
        ek_gp = int(ek_input) if ek_input is not None else 0
        if ek_input is None and existing_id:
            existing = self.rune_store.get_by_id(existing_id)
            if existing:
                ek_gp = int(existing.get("ek_gp", 0) or 0)
        return {
            "id": existing_id or str(uuid.uuid4()),
            "name": name,
            "runes_per_cast": runes_per_cast,
            "mana": mana_cost,
            "soul_points": soul_cost,
            "ek_gp": ek_gp,
            "vk_gp": vk_gp,
        }

    def _on_rune_character_change(self, *_args: object) -> None:
        self._refresh_rune_character_stats()
        self._refresh_rune_calculations()

    def _on_rune_spell_change(self, *_args: object) -> None:
        rune = self._get_selected_rune()
        if rune:
            self.rune_store.set_active(str(rune.get("id")))
        self._sync_rune_editor_from_selection()
        self._refresh_rune_calculations()

    def _add_rune(self) -> None:
        payload = self._collect_rune_editor_values()
        if not payload:
            return
        self.rune_store.add_rune(payload)
        self._refresh_rune_spell_choices(select_name=payload["name"])
        self._sync_rune_editor_from_selection()
        self._refresh_rune_calculations()

    def _update_rune(self) -> None:
        rune = self._get_selected_rune()
        if not rune:
            messagebox.showwarning("No Selection", "Select a rune to update.")
            return
        rune_id = str(rune.get("id"))
        payload = self._collect_rune_editor_values(existing_id=rune_id)
        if not payload:
            return
        self.rune_store.update_rune(rune_id, payload)
        self._refresh_rune_spell_choices(select_name=payload["name"])
        self._sync_rune_editor_from_selection()
        self._refresh_rune_calculations()

    def _remove_rune(self) -> None:
        rune = self._get_selected_rune()
        if not rune:
            messagebox.showwarning("No Selection", "Select a rune to delete.")
            return
        name = str(rune.get("name", ""))
        if not messagebox.askyesno("Delete Rune", f"Delete {name}?"):
            return
        self.rune_store.delete_rune(str(rune.get("id")))
        self._refresh_rune_spell_choices()
        self._sync_rune_editor_from_selection()
        self._refresh_rune_calculations()

    def _refresh_rune_calculations(self) -> None:
        rune = self._get_selected_rune()
        if not rune:
            for key, var in self.rune_result_vars.items():
                var.set("0")
            if hasattr(self, "rune_regen_result_vars"):
                for var in self.rune_regen_result_vars.values():
                    var.set("0")
            if hasattr(self, "rune_regen_formula_vars"):
                for var in self.rune_regen_formula_vars.values():
                    var.set("")
            if hasattr(self, "rune_soul_result_vars"):
                for var in self.rune_soul_result_vars.values():
                    var.set("0")
            if hasattr(self, "rune_soul_formula_vars"):
                for var in self.rune_soul_formula_vars.values():
                    var.set("")
            if hasattr(self, "rune_potion_formula_vars"):
                for var in self.rune_potion_formula_vars.values():
                    var.set("")
            return

        runes_per_cast = int(rune.get("runes_per_cast", 0) or 0)
        mana_cost = int(rune.get("mana", 0) or 0)
        soul_cost = int(rune.get("soul_points", 0) or 0)

        character = self._get_character_by_name(self.rune_character_var.get().strip())
        stats = character.get("stats", {})
        if not isinstance(stats, dict):
            stats = {}
        vocation = str(character.get("vocation", VOCATIONS[0]))
        level = int(character.get("level") or 1)
        magic_level = int(stats.get("magic_level", 0) or 0)
        derived = self._compute_derived_stats(level, magic_level, vocation, stats)
        merged_stats = DEFAULT_STATS.copy()
        merged_stats.update(stats)
        merged_stats.update(derived)

        max_mana = int(merged_stats.get("mana") or 0)
        soul_points = int(merged_stats.get("soul_points") or 0)
        mana_regen_hungry = float(merged_stats.get("mana_regen_hungry") or 0.0)
        mana_regen_fed = float(merged_stats.get("mana_regen_fed") or 0.0)
        mana_regen_depot = float(merged_stats.get("mana_regen_depot") or 0.0)

        casts_from_mana = max_mana // mana_cost if mana_cost > 0 else 0
        casts_possible = casts_from_mana

        minutes = self._parse_float_value(self.rune_time_minutes_var.get()) or 0.0
        seconds = max(0.0, minutes) * 60.0
        regen_mode = self.rune_regen_mode_var.get().strip().casefold()
        base_regen = mana_regen_hungry if regen_mode == "hungry" else mana_regen_fed
        mana_regen_per_5s = mana_regen_depot if self.rune_use_depot_bonus_var.get() else base_regen
        base_mana_regenerated = mana_regen_per_5s * (seconds / 5.0) if seconds > 0 else 0.0
        item_mana_regenerated = 0.0
        item_regen_per_5s = 0.0
        total_item_cost = 0.0
        for row in self.rune_mana_item_rows:
            if not row["selected_var"].get():
                continue
            item = row["item"]
            duration_sec = int(item.get("duration_sec", 0) or 0)
            if duration_sec <= 0:
                continue
            item_per_5s = float(item.get("mana_per_sec", 0.0)) * 5.0
            if self.rune_use_depot_bonus_var.get():
                item_per_5s *= 2.0
            item_regen_per_5s += item_per_5s
        if seconds > 0:
            for row in self.rune_mana_item_rows:
                item = row["item"]
                selected_var = row["selected_var"]
                price_var = row["price_var"]
                needed_var = row["needed_var"]
                cost_var = row["cost_var"]
                if not selected_var.get():
                    needed_var.set("0")
                    cost_var.set("0")
                    if hasattr(self, "mana_items_tree") and self.mana_items_tree.exists(item["name"]):
                        self.mana_items_tree.item(
                            item["name"],
                            values=(
                                "",
                                item["name"],
                                self._format_rune_value(float(item.get("mana_per_sec", 0.0)) * 5.0),
                                self._format_duration_minutes(int(item.get("duration_sec", 0) or 0)),
                                price_var.get(),
                                needed_var.get(),
                                cost_var.get(),
                            ),
                        )
                    continue
                duration_sec = int(item.get("duration_sec", 0) or 0)
                if duration_sec <= 0:
                    needed_var.set("0")
                    cost_var.set("0")
                    continue
                items_needed = seconds / duration_sec
                price = self._parse_float_value(price_var.get()) or 0.0
                cost = items_needed * price
                needed_var.set(self._format_rune_value(items_needed))
                cost_var.set(self._format_rune_value(cost))
                total_item_cost += cost
                if hasattr(self, "mana_items_tree") and self.mana_items_tree.exists(item["name"]):
                    self.mana_items_tree.item(
                        item["name"],
                        values=(
                            "✓",
                            item["name"],
                            self._format_rune_value(float(item.get("mana_per_sec", 0.0)) * 5.0),
                            self._format_duration_minutes(int(item.get("duration_sec", 0) or 0)),
                            price_var.get(),
                            needed_var.get(),
                            cost_var.get(),
                        ),
                    )

                item_per_5s = float(item.get("mana_per_sec", 0.0)) * 5.0
                if self.rune_use_depot_bonus_var.get():
                    item_per_5s *= 2.0
                item_mana_regenerated += item_per_5s * (seconds / 5.0)
        else:
            for row in self.rune_mana_item_rows:
                row["needed_var"].set("0")
                row["cost_var"].set("0")
                item = row["item"]
                if hasattr(self, "mana_items_tree") and self.mana_items_tree.exists(item["name"]):
                    self.mana_items_tree.item(
                        item["name"],
                        values=(
                            "",
                            item["name"],
                            self._format_rune_value(float(item.get("mana_per_sec", 0.0)) * 5.0),
                            self._format_duration_minutes(int(item.get("duration_sec", 0) or 0)),
                            row["price_var"].get(),
                            row["needed_var"].get(),
                            row["cost_var"].get(),
                        ),
                    )

        mana_regenerated = base_mana_regenerated + item_mana_regenerated
        total_regen_per_5s = mana_regen_per_5s + item_regen_per_5s
        soul_regen_per_5s = 5.0 / 16.0
        soul_regenerated = soul_regen_per_5s * (seconds / 5.0) if seconds > 0 else 0.0
        soul_available = 200 + soul_regenerated
        casts_from_soul = int(soul_available // soul_cost) if soul_cost > 0 else 0
        casts_from_regen = int(mana_regenerated // mana_cost) if mana_cost > 0 else 0
        casts_from_regen = min(casts_from_regen, casts_from_soul) if soul_cost > 0 else casts_from_regen
        runes_from_regen = casts_from_regen * runes_per_cast

        runes_from_mana = casts_from_mana * runes_per_cast
        casts_possible = min(casts_from_mana, casts_from_soul) if soul_cost > 0 else casts_from_mana
        runes_possible = casts_possible * runes_per_cast
        vk_gp = int(rune.get("vk_gp", 0) or 0)
        gold_from_regen = runes_from_regen * vk_gp
        blank_rune_cost = casts_from_regen * 10
        deposit_gain = 0
        net_regen = gold_from_regen - total_item_cost - blank_rune_cost + deposit_gain
        gold_from_max = runes_possible * vk_gp

        start_percent_raw = self.rune_regen_start_percent_var.get().strip().replace("%", "")
        start_percent = self._parse_float_value(start_percent_raw) or 0.0
        start_percent = min(100.0, max(0.0, start_percent))
        start_mana = max_mana * (start_percent / 100.0)
        mana_missing = max(0.0, max_mana - start_mana)
        total_regen_per_sec = total_regen_per_5s / 5.0
        time_to_full_seconds = mana_missing / total_regen_per_sec if total_regen_per_sec > 0 else 0.0

        self.rune_result_vars["runes_per_cast"].set(str(runes_per_cast))
        self.rune_result_vars["mana_cost"].set(str(mana_cost))
        self.rune_result_vars["soul_cost"].set(str(soul_cost))
        self.rune_result_vars["ek_gp"].set(str(int(rune.get("ek_gp", 0) or 0)))
        self.rune_result_vars["vk_gp"].set(str(int(rune.get("vk_gp", 0) or 0)))
        soul_needed_regen = casts_from_regen * soul_cost
        mana_spent_regen = casts_from_regen * mana_cost
        b_map = {
            "Elite Knight": 3.0,
            "Royal Paladin": 1.4,
            "Master Sorcerer": 1.1,
            "Elder Druid": 1.1,
        }
        b_value = b_map.get(vocation, 1.1)
        ml_gain_regen = self._magic_level_percent_gain(mana_spent_regen, magic_level, vocation)
        if "ml_gain_regen" in self.rune_result_vars or "ml_gain_potion" in self.rune_result_vars:
            if "ml_gain_regen" in self.rune_result_vars:
                self.rune_result_vars["ml_gain_regen"].set(f"{self._format_de_number(ml_gain_regen, 2)} %")

        if hasattr(self, "rune_regen_result_vars"):
            self.rune_regen_result_vars["time_used"].set(self._format_with_unit(seconds, "Sekunden", 0))
            self.rune_regen_formula_vars["time_used"].set(
                f"({self._format_de_number(minutes, 2)} × 60)"
            )

            if mana_missing <= 0:
                time_to_full_display = self._format_minutes_seconds(0)
            elif total_regen_per_sec <= 0:
                time_to_full_display = "â€”"
            else:
                time_to_full_display = self._format_minutes_seconds(time_to_full_seconds)
            self.rune_regen_result_vars["time_to_full"].set(time_to_full_display)
            if total_regen_per_sec > 0:
                self.rune_regen_formula_vars["time_to_full"].set(
                    f"({self._format_de_number(mana_missing, 0)} / "
                    f"{self._format_de_number(total_regen_per_5s, 2)} × 5) "
                    f"[Start {self._format_de_number(start_percent, 0)}%]"
                )
            else:
                self.rune_regen_formula_vars["time_to_full"].set("")

            self.rune_regen_result_vars["mana_regenerated"].set(
                self._format_with_unit(mana_regenerated, "Mana", 0)
            )
            self.rune_regen_formula_vars["mana_regenerated"].set(
                f"({self._format_de_number(mana_regen_per_5s, 2)} × "
                f"{self._format_de_number(seconds, 0)} / 5 + items)"
            )

            self.rune_regen_result_vars["soul_regenerated"].set(
                self._format_with_unit(soul_regenerated, "Soul", 0)
            )
            self.rune_regen_formula_vars["soul_regenerated"].set(
                f"({self._format_de_number(soul_regen_per_5s, 2)} × "
                f"{self._format_de_number(seconds, 0)} / 5) in {self._format_de_number(minutes, 2)} Min"
            )

            self.rune_regen_result_vars["soul_available"].set(
                self._format_with_unit(soul_available, "Soul", 0)
            )
            self.rune_regen_formula_vars["soul_available"].set(
                f"(200 + {self._format_de_number(soul_regenerated, 2)})"
            )

            self.rune_regen_result_vars["soul_needed_regen"].set(
                self._format_with_unit(soul_needed_regen, "Soul", 0)
            )
            self.rune_regen_formula_vars["soul_needed_regen"].set(
                f"({casts_from_regen} × {soul_cost}) in {self._format_de_number(minutes, 2)} Min"
            )

            self.rune_regen_result_vars["mana_spent_regen"].set(
                self._format_with_unit(mana_spent_regen, "Mana", 0)
            )
            self.rune_regen_formula_vars["mana_spent_regen"].set(
                f"({casts_from_regen} × {mana_cost}) in {self._format_de_number(minutes, 2)} Min"
            )

            self.rune_regen_result_vars["ml_gain_regen"].set(
                f"{self._format_de_number(ml_gain_regen, 2)} %"
            )
            self.rune_regen_formula_vars["ml_gain_regen"].set(
                f"(stufenweise ab ML {magic_level}, b={self._format_de_number(b_value, 2)}, "
                f"Mana {self._format_de_number(mana_spent_regen, 0)})"
            )

            self.rune_regen_result_vars["casts_from_regen"].set(
                self._format_with_unit(casts_from_regen, "Casts", 0)
            )
            self.rune_regen_formula_vars["casts_from_regen"].set(
                f"(min({self._format_de_number(mana_regenerated, 0)} // {mana_cost}, "
                f"{self._format_de_number(soul_available, 0)} // {soul_cost}))"
            )

            self.rune_regen_result_vars["runes_from_regen"].set(
                self._format_with_unit(runes_from_regen, "Runen", 0)
            )
            self.rune_regen_formula_vars["runes_from_regen"].set(
                f"({casts_from_regen} × {runes_per_cast})"
            )

            self.rune_regen_result_vars["gold_from_regen"].set(self._format_gp(int(gold_from_regen)))
            self.rune_regen_formula_vars["gold_from_regen"].set(
                f"({runes_from_regen} × {vk_gp})"
            )

            self.rune_regen_result_vars["deposit_gain"].set(self._format_gp(int(deposit_gain)))
            self.rune_regen_formula_vars["deposit_gain"].set("")

            self.rune_regen_result_vars["item_cost"].set(self._format_gp(int(total_item_cost)))
            self.rune_regen_formula_vars["item_cost"].set("(Summe Items)")

            self.rune_regen_result_vars["blank_rune_cost"].set(self._format_gp(int(blank_rune_cost)))
            self.rune_regen_formula_vars["blank_rune_cost"].set(
                f"({casts_from_regen} × 10)"
            )

            self.rune_regen_result_vars["net_regen"].set(self._format_gp(int(net_regen)))
            self.rune_regen_formula_vars["net_regen"].set(
                f"({self._format_de_number(gold_from_regen, 0)} - "
                f"{self._format_de_number(total_item_cost, 0)} - "
                f"{self._format_de_number(blank_rune_cost, 0)} + "
                f"{self._format_de_number(deposit_gain, 0)})"
            )

            ek_gp = int(rune.get("ek_gp", 0) or 0)
            cost_total = float(total_item_cost) + float(blank_rune_cost) - float(deposit_gain)
            if runes_from_regen > 0:
                cost_per_rune = cost_total / float(runes_from_regen)
                profit_per_rune = float(vk_gp) - cost_per_rune
                buy_delta = float(ek_gp) - cost_per_rune
                self.rune_regen_result_vars["cost_per_rune"].set(self._format_gp_per_rune(cost_per_rune, 2))
                self.rune_regen_formula_vars["cost_per_rune"].set(
                    f"(({self._format_de_number(total_item_cost, 0)} + {self._format_de_number(blank_rune_cost, 0)} - "
                    f"{self._format_de_number(deposit_gain, 0)}) / {self._format_de_number(runes_from_regen, 0)})"
                )
                self.rune_regen_result_vars["profit_per_rune"].set(self._format_signed_gp_per_rune(profit_per_rune, 2))
                self.rune_regen_formula_vars["profit_per_rune"].set(f"({vk_gp} - Kosten/Rune)")
                note = "Produzieren günstiger" if buy_delta > 0 else "Kaufen günstiger" if buy_delta < 0 else "gleich"
                self.rune_regen_result_vars["buy_vs_make_per_rune"].set(
                    f"{self._format_signed_gp_per_rune(buy_delta, 2)} ({note})"
                )
                self.rune_regen_formula_vars["buy_vs_make_per_rune"].set(f"({ek_gp} - Kosten/Rune)")
            else:
                for key in ("cost_per_rune", "profit_per_rune", "buy_vs_make_per_rune"):
                    self.rune_regen_result_vars[key].set("—")
                    self.rune_regen_formula_vars[key].set("")

        self._refresh_rune_soul_cycle_stats()
        self._refresh_potion_stats()

    def _refresh_rune_soul_cycle_stats(self) -> None:
        if not hasattr(self, "rune_soul_result_vars") or not self.rune_soul_result_vars:
            return
        rune = self._get_selected_rune()
        if not rune:
            for var in self.rune_soul_result_vars.values():
                var.set("0")
            for var in self.rune_soul_formula_vars.values():
                var.set("")
            return

        runes_per_cast = int(rune.get("runes_per_cast", 0) or 0)
        mana_cost = int(rune.get("mana", 0) or 0)
        soul_cost = int(rune.get("soul_points", 0) or 0)
        ek_gp = int(rune.get("ek_gp", 0) or 0)
        vk_gp = int(rune.get("vk_gp", 0) or 0)

        character = self._get_character_by_name(self.rune_character_var.get().strip())
        stats = character.get("stats", {})
        if not isinstance(stats, dict):
            stats = {}
        vocation = str(character.get("vocation", VOCATIONS[0]))
        level = int(character.get("level") or 1)
        magic_level = int(stats.get("magic_level", 0) or 0)
        derived = self._compute_derived_stats(level, magic_level, vocation, stats)
        merged_stats = DEFAULT_STATS.copy()
        merged_stats.update(stats)
        merged_stats.update(derived)

        max_mana = float(merged_stats.get("mana") or 0.0)
        mana_regen_hungry = float(merged_stats.get("mana_regen_hungry") or 0.0)
        mana_regen_fed = float(merged_stats.get("mana_regen_fed") or 0.0)
        mana_regen_depot = float(merged_stats.get("mana_regen_depot") or 0.0)

        minutes = self._parse_float_value(self.rune_time_minutes_var.get()) or 0.0
        seconds = max(0.0, minutes) * 60.0

        start_percent_raw = self.rune_regen_start_percent_var.get().strip().replace("%", "")
        start_percent = self._parse_float_value(start_percent_raw) or 0.0
        start_percent = min(100.0, max(0.0, start_percent))
        mana = max_mana * (start_percent / 100.0)
        soul = 0.0

        regen_mode = self.rune_regen_mode_var.get().strip().casefold()
        base_regen_per_5s = mana_regen_hungry if regen_mode == "hungry" else mana_regen_fed
        mana_regen_per_5s = mana_regen_depot if self.rune_use_depot_bonus_var.get() else base_regen_per_5s
        item_regen_per_5s = 0.0
        total_item_cost = 0.0
        item_cost_parts: list[str] = []
        for row in self.rune_mana_item_rows:
            if not row["selected_var"].get():
                continue
            item = row["item"]
            duration_sec = int(item.get("duration_sec", 0) or 0)
            if duration_sec <= 0:
                continue
            item_per_5s = float(item.get("mana_per_sec", 0.0)) * 5.0
            if self.rune_use_depot_bonus_var.get():
                item_per_5s *= 2.0
            item_regen_per_5s += item_per_5s
            price = self._parse_float_value(row["price_var"].get()) or 0.0
            part_cost = (seconds / duration_sec) * price if seconds > 0 else 0.0
            total_item_cost += part_cost
            item_cost_parts.append(
                f"{item['name']}: ({self._format_de_number(seconds, 0)} / {duration_sec}) × {self._format_de_number(price, 2)}"
            )
        total_mana_regen_per_sec = (mana_regen_per_5s + item_regen_per_5s) / 5.0
        soul_regen_per_sec = 1.0 / 16.0
        soul_target = max(5.0, float(soul_cost)) if soul_cost > 0 else 5.0

        potion_name = self.rune_soul_potion_var.get().strip() or "None"
        potion_entry = next((item for item in self._mana_potions() if item["name"] == potion_name), None)
        if not potion_entry:
            potion_entry = self._mana_potions()[0]
        potion_mana_gain = int(potion_entry.get("mana_gain", 0) or 0)
        potion_price = int(potion_entry.get("price", 0) or 0)

        elapsed = 0.0
        casts = 0
        mana_spent = 0.0
        soul_spent = 0.0
        potions_used = 0
        mana_from_potions = 0.0
        natural_mana_regenerated = 0.0

        if seconds > 0 and mana_cost > 0 and runes_per_cast > 0:
            iterations = 0
            max_iterations = 200000
            while elapsed < seconds and iterations < max_iterations:
                iterations += 1
                if soul < soul_target:
                    wait_to_soul = (soul_target - soul) / soul_regen_per_sec
                else:
                    wait_to_soul = 0.0

                remaining = seconds - elapsed
                if wait_to_soul > remaining:
                    mana_before = mana
                    mana = min(max_mana, mana + total_mana_regen_per_sec * remaining)
                    natural_mana_regenerated += max(0.0, mana - mana_before)
                    soul += soul_regen_per_sec * remaining
                    elapsed = seconds
                    break

                if wait_to_soul > 0:
                    mana_before = mana
                    mana = min(max_mana, mana + total_mana_regen_per_sec * wait_to_soul)
                    natural_mana_regenerated += max(0.0, mana - mana_before)
                    soul += soul_regen_per_sec * wait_to_soul
                    elapsed += wait_to_soul

                if mana < mana_cost and potion_mana_gain > 0 and mana < max_mana:
                    before = mana
                    drink_guard = 0
                    while mana < mana_cost and mana < max_mana and drink_guard < 10000:
                        mana = min(max_mana, mana + potion_mana_gain)
                        potions_used += 1
                        drink_guard += 1
                    mana_from_potions += max(0.0, mana - before)

                if mana < mana_cost:
                    if total_mana_regen_per_sec <= 0:
                        break
                    needed = (mana_cost - mana) / total_mana_regen_per_sec
                    if needed <= 0:
                        break
                    remaining = seconds - elapsed
                    wait_for_mana = min(needed, remaining)
                    mana_before = mana
                    mana = min(max_mana, mana + total_mana_regen_per_sec * wait_for_mana)
                    natural_mana_regenerated += max(0.0, mana - mana_before)
                    soul += soul_regen_per_sec * wait_for_mana
                    elapsed += wait_for_mana
                    continue

                if soul_cost > 0 and soul < soul_cost:
                    continue

                mana -= mana_cost
                if soul_cost > 0:
                    soul -= soul_cost
                casts += 1
                mana_spent += mana_cost
                soul_spent += max(0, soul_cost)

        runes_total = casts * runes_per_cast
        gold_from_runes = runes_total * vk_gp
        blank_rune_cost = casts * 10
        potion_cost = potions_used * potion_price
        net_profit = gold_from_runes - blank_rune_cost - potion_cost - total_item_cost

        soul_regenerated = soul_regen_per_sec * seconds if seconds > 0 else 0.0
        ml_gain_cycle = self._magic_level_percent_gain(mana_spent, magic_level, vocation)
        b_map = {
            "Elite Knight": 3.0,
            "Royal Paladin": 1.4,
            "Master Sorcerer": 1.1,
            "Elder Druid": 1.1,
        }
        b_value = b_map.get(vocation, 1.1)

        self.rune_soul_result_vars["time_used"].set(self._format_with_unit(seconds, "Sekunden", 0))
        self.rune_soul_result_vars["natural_mana_regen"].set(self._format_with_unit(natural_mana_regenerated, "Mana", 0))
        self.rune_soul_result_vars["soul_regenerated"].set(self._format_with_unit(soul_regenerated, "Soul", 0))
        self.rune_soul_result_vars["ml_gain_cycle"].set(f"{self._format_de_number(ml_gain_cycle, 2)} %")
        self.rune_soul_result_vars["casts"].set(self._format_with_unit(casts, "Casts", 0))
        self.rune_soul_result_vars["runes_total"].set(self._format_with_unit(runes_total, "Runen", 0))
        self.rune_soul_result_vars["mana_spent"].set(self._format_with_unit(mana_spent, "Mana", 0))
        self.rune_soul_result_vars["soul_spent"].set(self._format_with_unit(soul_spent, "Soul", 0))
        self.rune_soul_result_vars["potions_used"].set(self._format_de_number(potions_used, 0))
        self.rune_soul_result_vars["mana_from_potions"].set(self._format_with_unit(mana_from_potions, "Mana", 0))
        self.rune_soul_result_vars["potion_cost"].set(self._format_gp(int(potion_cost)))
        self.rune_soul_result_vars["item_cost"].set(self._format_gp(int(total_item_cost)))
        self.rune_soul_result_vars["blank_rune_cost"].set(self._format_gp(int(blank_rune_cost)))
        self.rune_soul_result_vars["gold_from_runes"].set(self._format_gp(int(gold_from_runes)))
        self.rune_soul_result_vars["net_profit"].set(self._format_gp(int(net_profit)))
        if runes_total > 0:
            cost_total = float(blank_rune_cost) + float(potion_cost) + float(total_item_cost)
            cost_per_rune = cost_total / float(runes_total)
            profit_per_rune = float(vk_gp) - cost_per_rune
            buy_delta = float(ek_gp) - cost_per_rune
            self.rune_soul_result_vars["cost_per_rune"].set(self._format_gp_per_rune(cost_per_rune, 2))
            self.rune_soul_result_vars["profit_per_rune"].set(self._format_signed_gp_per_rune(profit_per_rune, 2))
            note = "Produzieren günstiger" if buy_delta > 0 else "Kaufen günstiger" if buy_delta < 0 else "gleich"
            self.rune_soul_result_vars["buy_vs_make_per_rune"].set(
                f"{self._format_signed_gp_per_rune(buy_delta, 2)} ({note})"
            )
        else:
            for key in ("cost_per_rune", "profit_per_rune", "buy_vs_make_per_rune"):
                self.rune_soul_result_vars[key].set("—")
        self.rune_soul_result_vars["end_mana"].set(self._format_with_unit(mana, "Mana", 0))
        self.rune_soul_result_vars["end_soul"].set(self._format_with_unit(soul, "Soul", 0))

        if self.rune_soul_formula_vars:
            self.rune_soul_formula_vars["time_used"].set(
                f"({self._format_de_number(minutes, 2)} × 60)"
            )
            self.rune_soul_formula_vars["natural_mana_regen"].set(
                f"(({self._format_de_number(mana_regen_per_5s, 2)} + {self._format_de_number(item_regen_per_5s, 2)}) × {self._format_de_number(seconds, 0)} / 5)"
            )
            self.rune_soul_formula_vars["soul_regenerated"].set(
                f"({self._format_de_number(seconds, 0)} / 16)"
            )
            self.rune_soul_formula_vars["ml_gain_cycle"].set(
                f"(stufenweise ab ML {magic_level}, b={self._format_de_number(b_value, 2)}, "
                f"Mana {self._format_de_number(mana_spent, 0)})"
            )
            self.rune_soul_formula_vars["casts"].set("(Erfolgreiche Casts aus Simulation)")
            self.rune_soul_formula_vars["runes_total"].set(f"({casts} × {runes_per_cast})")
            self.rune_soul_formula_vars["mana_spent"].set(f"({casts} × {mana_cost})")
            self.rune_soul_formula_vars["soul_spent"].set(f"({casts} × {soul_cost})")
            self.rune_soul_formula_vars["potions_used"].set(
                f"(Auto bei Soul >= {self._format_de_number(soul_target, 0)} und Mana < {mana_cost})"
            )
            self.rune_soul_formula_vars["mana_from_potions"].set(
                f"({potions_used} × {potion_mana_gain}, capped bei Max Mana)"
            )
            self.rune_soul_formula_vars["potion_cost"].set(f"({potions_used} × {potion_price})")
            self.rune_soul_formula_vars["item_cost"].set(
                "(" + (" + ".join(item_cost_parts) if item_cost_parts else "keine aktiven Items") + ")"
            )
            self.rune_soul_formula_vars["blank_rune_cost"].set(f"({casts} × 10)")
            self.rune_soul_formula_vars["gold_from_runes"].set(f"({runes_total} × {vk_gp})")
            self.rune_soul_formula_vars["net_profit"].set(
                f"({self._format_de_number(gold_from_runes, 0)} - {self._format_de_number(blank_rune_cost, 0)} - "
                f"{self._format_de_number(potion_cost, 0)} - {self._format_de_number(total_item_cost, 0)})"
            )
            if runes_total > 0:
                self.rune_soul_formula_vars["cost_per_rune"].set(
                    f"(({self._format_de_number(blank_rune_cost, 0)} + {self._format_de_number(potion_cost, 0)} + "
                    f"{self._format_de_number(total_item_cost, 0)}) / {self._format_de_number(runes_total, 0)})"
                )
                self.rune_soul_formula_vars["profit_per_rune"].set(f"({vk_gp} - Kosten/Rune)")
                self.rune_soul_formula_vars["buy_vs_make_per_rune"].set(f"({ek_gp} - Kosten/Rune)")
            else:
                for key in ("cost_per_rune", "profit_per_rune", "buy_vs_make_per_rune"):
                    self.rune_soul_formula_vars[key].set("")
            self.rune_soul_formula_vars["end_mana"].set(
                "(Start + nat. Regen + Potions - Mana für Casts)"
            )
            self.rune_soul_formula_vars["end_soul"].set(
                f"(0 + {self._format_de_number(soul_regenerated, 2)} - {self._format_de_number(soul_spent, 0)})"
            )

    def _search_character(self) -> None:
        raw_name = self.character_search_var.get().strip()
        if not raw_name:
            messagebox.showwarning("Fehlender Name", "Bitte einen Charakter-Namen eingeben.")
            return
        encoded = "+".join(quote(part, safe="") for part in raw_name.split())
        url = f"https://www.tibia.com/community/?subtopic=characters&name={encoded}"
        fallback_url = "https://www.tibia.com/community/?subtopic=worlds&world=Xyla&order=level_desc"

        def run() -> None:
            target_url = fallback_url if self._url_returns_404(url) else url
            self.root.after(0, lambda: self._open_url(target_url, f"Charakter: {raw_name}"))

        threading.Thread(target=run, daemon=True).start()

    def _url_returns_404(self, url: str) -> bool:
        status = self._check_url_status(url, "HEAD")
        if status == 404:
            return True
        if status == 405:
            status = self._check_url_status(url, "GET")
        return status == 404

    def _check_url_status(self, url: str, method: str) -> int | None:
        request = Request(url, method=method, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=5) as response:
                return getattr(response, "status", None)
        except HTTPError as exc:
            return exc.code
        except URLError:
            return None

    def _ensure_hotkeys_files(self) -> None:
        self.hotkeys_dir.mkdir(parents=True, exist_ok=True)
        if not self.hotkeys_events_path.exists():
            self.hotkeys_events_path.write_text("", encoding="utf-8")
        if not self.hotkeys_cmd_path.exists():
            self.hotkeys_cmd_path.write_text("", encoding="utf-8")
        if not self.hotkeys_json_path.exists():
            self._ensure_default_hotkeys()

    def _ensure_cones_files(self) -> None:
        self.hotkeys_dir.mkdir(parents=True, exist_ok=True)
        if not self.cone_events_path.exists():
            self.cone_events_path.write_text("", encoding="utf-8")

    def _load_hotkeys_table(self) -> None:
        if not self.hotkeys_tree or not self.hotkeys_tree.winfo_exists():
            return
        self._ensure_hotkeys_files()
        self._load_hotkeys_state()
        self._refresh_hotkeys_table()


    def _on_hotkeys_select(self, _event: tk.Event) -> None:
        if not self.hotkeys_tree or not self.hotkeys_tree.winfo_exists():
            return
        selection = self.hotkeys_tree.selection()
        if not selection:
            return
        self._edit_selected_hotkey()

    def _edit_selected_hotkey(self) -> None:
        if not self.hotkeys_tree or not self.hotkeys_tree.winfo_exists():
            return
        selection = self.hotkeys_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        data = next((entry for entry in self.hotkeys_defs if str(entry.get("id")) == item_id), None)
        if not data:
            return
        if self.hotkey_entry:
            self.hotkey_entry.delete(0, tk.END)
            self.hotkey_entry.insert(0, str(data.get("hotkey", "")))
        if self.action_entry:
            self.action_entry.delete(0, tk.END)
            self.action_entry.insert(0, str(data.get("action", "")))

    def _collect_hotkey_form(self) -> dict[str, object] | None:
        if not self.hotkey_entry or not self.action_entry:
            return None
        hotkey = self.hotkey_entry.get().strip()
        action = self.action_entry.get().strip()
        if not hotkey or not action:
            messagebox.showwarning("Missing Data", "Hotkey and Action are required.")
            return None
        return {
            "hotkey": hotkey,
            "action": action,
        }

    def _add_hotkey(self) -> None:
        data = self._collect_hotkey_form()
        if not data:
            return
        data["id"] = str(uuid.uuid4())
        self.hotkeys_defs.append(data)
        self._refresh_hotkeys_table()
        self._clear_hotkeys_form()

    def _update_selected_hotkey(self) -> None:
        if not self.hotkeys_tree or not self.hotkeys_tree.winfo_exists():
            return
        selection = self.hotkeys_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a hotkey to update.")
            return
        data = self._collect_hotkey_form()
        if not data:
            return
        item_id = selection[0]
        for entry in self.hotkeys_defs:
            if str(entry.get("id")) == item_id:
                entry.update(data)
                break
        self._refresh_hotkeys_table()
        self._clear_hotkeys_form()

    def _remove_hotkey(self) -> None:
        if not self.hotkeys_tree or not self.hotkeys_tree.winfo_exists():
            return
        selection = self.hotkeys_tree.selection()
        if not selection:
            return
        selected_ids = {str(item) for item in selection}
        self.hotkeys_defs = [entry for entry in self.hotkeys_defs if str(entry.get("id")) not in selected_ids]
        self._refresh_hotkeys_table()

    def _save_hotkeys_mappings(self) -> None:
        if not self.hotkeys_tree or not self.hotkeys_tree.winfo_exists():
            return
        self._ensure_hotkeys_files()
        self._save_hotkeys_state()
        if self._is_hotkeys_running():
            self._apply_hotkeys_changes()
        messagebox.showinfo("Saved", "Hotkeys mapping saved.")

    def _is_hotkeys_running(self) -> bool:
        return self.hotkeys_process is not None and self.hotkeys_process.poll() is None

    def _start_hotkeys_script(self) -> None:
        if self._is_hotkeys_running():
            self.hotkeys_status_var.set("Running")
            return
        self._ensure_hotkeys_files()
        if not self.hotkeys_script_path.exists():
            messagebox.showerror(
                "AutoHotkey Script Missing",
                f"Missing script: {self.hotkeys_script_path}",
            )
            return
        ahk_exe = self._resolve_ahk_exe()
        if not ahk_exe:
            messagebox.showerror(
                "AutoHotkey Missing",
                "AutoHotkey v2 was not found in PATH or the default install location.",
            )
            return
        try:
            self.hotkeys_process = subprocess.Popen([ahk_exe, str(self.hotkeys_script_path)])
        except OSError as exc:
            messagebox.showerror("AutoHotkey Error", f"Failed to start AutoHotkey: {exc}")
            return
        self.hotkeys_status_var.set("Running")

    def _stop_hotkeys_script(self) -> None:
        if not self._is_hotkeys_running():
            self.hotkeys_status_var.set("Stopped")
            return
        if self.hotkeys_process:
            self.hotkeys_process.terminate()
            try:
                self.hotkeys_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.hotkeys_process.kill()
        self.hotkeys_process = None
        self.hotkeys_status_var.set("Stopped")

    def _restart_hotkeys_script(self) -> None:
        self._stop_hotkeys_script()
        self._start_hotkeys_script()

    def _is_cones_running(self) -> bool:
        return self.cone_process is not None and self.cone_process.poll() is None

    def _start_cones_script(self) -> None:
        if self._is_cones_running():
            return
        self._ensure_cones_files()
        if not self.cone_script_path.exists():
            messagebox.showerror(
                "AutoHotkey Script Missing",
                f"Missing script: {self.cone_script_path}",
            )
            return
        ahk_exe = self._resolve_ahk_exe()
        if not ahk_exe:
            messagebox.showerror(
                "AutoHotkey Missing",
                "AutoHotkey v2 was not found in PATH or the default install location.",
            )
            return
        try:
            self.cone_process = subprocess.Popen([ahk_exe, str(self.cone_script_path)])
        except OSError as exc:
            messagebox.showerror("AutoHotkey Error", f"Failed to start AutoHotkey: {exc}")

    def _stop_cones_script(self) -> None:
        if not self._is_cones_running():
            return
        if self.cone_process:
            self.cone_process.terminate()
            try:
                self.cone_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.cone_process.kill()
        self.cone_process = None

    def _schedule_hotkeys_status_refresh(self) -> None:
        self.hotkeys_status_var.set("Running" if self._is_hotkeys_running() else "Stopped")
        self._refresh_hotkeys_admin_status()
        self.root.after(1000, self._schedule_hotkeys_status_refresh)

    def _schedule_cone_events_poll(self) -> None:
        self._poll_cone_events()
        self.root.after(100, self._schedule_cone_events_poll)

    def _poll_cone_events(self) -> None:
        if not self.cone_events_path.exists():
            return
        try:
            with self.cone_events_path.open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                if size < self._cone_events_pos:
                    self._cone_events_pos = 0
                    self._cone_events_buffer = ""
                handle.seek(self._cone_events_pos)
                payload = handle.read()
                self._cone_events_pos = handle.tell()
        except OSError:
            return

        if not payload:
            return

        text = payload.decode("utf-8", errors="ignore")
        self._cone_events_buffer += text
        lines = self._cone_events_buffer.splitlines()
        if self._cone_events_buffer and not self._cone_events_buffer.endswith(("\n", "\r")):
            self._cone_events_buffer = lines.pop() if lines else self._cone_events_buffer
        else:
            self._cone_events_buffer = ""

        for line in lines:
            cleaned = line.strip()
            if not cleaned.startswith("MOVE|"):
                continue
            direction = None
            for part in cleaned.split("|")[1:]:
                if part.startswith("dir="):
                    direction = part[4:].strip().upper()
                    break
            if direction in {"UP", "RIGHT", "DOWN", "LEFT"}:
                self._set_cone_direction(direction)

    def _toggle_overlay(self) -> None:
        self._ensure_hotkeys_files()
        self._send_hotkeys_command("TOGGLE_OVERLAY")
        current = self.hotkeys_overlay_var.get()
        self.hotkeys_overlay_var.set("Overlay: On" if "Off" in current else "Overlay: Off")

    def _are_cones_enabled(self) -> bool:
        return bool(self.grid_cone_overlay.enabled or self.grid_cone_overlay_alt.enabled)

    def _on_cones_change(self) -> None:
        if self._are_cones_enabled():
            self._start_cones_script()
        else:
            self._stop_cones_script()

    def _send_hotkeys_command(self, command: str) -> None:
        payload = f"{command}\n"
        self.hotkeys_cmd_path.write_text(payload, encoding="utf-8")

    def _apply_hotkeys_changes(self) -> None:
        if not self._is_hotkeys_running():
            return
        try:
            self._send_hotkeys_command("RELOAD")
        except OSError:
            self._restart_hotkeys_script()
            return
        self.root.after(800, self._ensure_hotkeys_running_after_reload)

    def _ensure_hotkeys_running_after_reload(self) -> None:
        if not self._is_hotkeys_running():
            self._restart_hotkeys_script()

    def _resolve_ahk_exe(self) -> str | None:
        return (
            shutil.which("AutoHotkey64.exe")
            or shutil.which("AutoHotkey.exe")
            or r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"
        )

    def _resolve_tibia_exe_path(self) -> Path:
        """Best-effort resolution of the Tibia executable.

        Historically this was hardcoded to a single user profile path. That breaks as soon
        as Tibia is installed for a different Windows user or installed into Program Files.
        """
        candidates: list[Path] = []

        # Local override file next to the app (one line: full path to tibia.exe/client.exe).
        try:
            override_file = getattr(self, "base_dir", Path(".")) / "tibia_exe_path.txt"
            if override_file.exists():
                payload = override_file.read_text(encoding="utf-8", errors="replace").strip().strip('"')
                if payload:
                    candidates.append(Path(payload))
        except OSError:
            pass

        # Allow an explicit override (useful for portable installs or uncommon locations).
        override = (os.environ.get("TIBIA_EXE") or os.environ.get("TIBIA_PATH") or "").strip().strip('"')
        if override:
            candidates.append(Path(override))

        # Try to discover install location via Windows "Uninstall" registry keys.
        for install_dir in self._find_tibia_install_dirs_from_registry():
            candidates.extend(
                [
                    install_dir / "client.exe",
                    install_dir / "Client.exe",
                    install_dir / "tibia.exe",
                    install_dir / "Tibia.exe",
                ]
            )

        # Common install locations (per-user and machine-wide).
        local_appdata = os.environ.get("LOCALAPPDATA") or ""
        program_files = os.environ.get("ProgramFiles") or ""
        program_files_x86 = os.environ.get("ProgramFiles(x86)") or ""
        userprofile = os.environ.get("USERPROFILE") or ""

        # Newer Tibia installs can place the actual client in a packages folder.
        # Example: %LOCALAPPDATA%\Tibia\packages\Tibia\bin\client.exe
        if local_appdata:
            tibia_root = Path(local_appdata) / "Tibia"
            packages_dir = tibia_root / "packages"
            try:
                if packages_dir.exists():
                    for p in packages_dir.glob("**/bin/client.exe"):
                        candidates.append(p)
                    for p in packages_dir.glob("**/bin/Client.exe"):
                        candidates.append(p)
                    for p in packages_dir.glob("**/bin/tibia.exe"):
                        candidates.append(p)
                    for p in packages_dir.glob("**/bin/Tibia.exe"):
                        candidates.append(p)
            except OSError:
                pass

        for base in (local_appdata, userprofile and str(Path(userprofile) / "AppData" / "Local")):
            if base:
                candidates.extend(
                    [
                        Path(base) / "Tibia" / "client.exe",
                        Path(base) / "Tibia" / "tibia.exe",
                        Path(base) / "Programs" / "Tibia" / "tibia.exe",
                        Path(base) / "Programs" / "Tibia" / "client.exe",
                    ]
                )
        for base in (program_files, program_files_x86):
            if base:
                candidates.extend(
                    [
                        Path(base) / "Tibia" / "client.exe",
                        Path(base) / "Tibia" / "tibia.exe",
                    ]
                )

        # Prefer the first existing candidate.
        seen: set[str] = set()
        for path in candidates:
            key = str(path).casefold()
            if key in seen:
                continue
            seen.add(key)
            try:
                if path.exists():
                    return path
            except OSError:
                continue

        # Fallback to the historical default (may not exist; callers handle this).
        if local_appdata:
            client = Path(local_appdata) / "Tibia" / "client.exe"
            if client.exists():
                return client
            return Path(local_appdata) / "Tibia" / "tibia.exe"
        return Path(r"C:\Users\Administrator\AppData\Local\Tibia\tibia.exe")

    def _find_tibia_install_dirs_from_registry(self) -> list[Path]:
        install_dirs: list[Path] = []

        def _reg_get_str(key: winreg.HKEYType, value_name: str) -> str:
            try:
                value, _ = winreg.QueryValueEx(key, value_name)
            except OSError:
                return ""
            if not value:
                return ""
            return str(value).strip().strip('"')

        uninstall_keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for root, path in uninstall_keys:
            try:
                base = winreg.OpenKey(root, path)
            except OSError:
                continue
            try:
                count, _, _ = winreg.QueryInfoKey(base)
                for i in range(count):
                    try:
                        sub_name = winreg.EnumKey(base, i)
                        sub = winreg.OpenKey(base, sub_name)
                    except OSError:
                        continue
                    try:
                        display_name = _reg_get_str(sub, "DisplayName").casefold()
                        if "tibia" not in display_name:
                            continue
                        install_loc = _reg_get_str(sub, "InstallLocation")
                        if install_loc:
                            install_dirs.append(Path(install_loc))
                        display_icon = _reg_get_str(sub, "DisplayIcon")
                        if display_icon:
                            # Often formatted like: C:\Path\To\tibia.exe,0
                            icon_path = display_icon.split(",", 1)[0].strip().strip('"')
                            if icon_path:
                                install_dirs.append(Path(icon_path).parent)
                    finally:
                        try:
                            sub.Close()
                        except Exception:
                            pass
            finally:
                try:
                    base.Close()
                except Exception:
                    pass

        # Deduplicate while preserving order.
        deduped: list[Path] = []
        seen = set()
        for p in install_dirs:
            key = str(p).casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(p)
        return deduped

    def _restart_hotkeys_as_admin(self) -> None:
        if self._is_hotkeys_running():
            self._stop_hotkeys_script()
        ahk_exe = self._resolve_ahk_exe()
        if not ahk_exe:
            messagebox.showerror(
                "AutoHotkey Missing",
                "AutoHotkey v2 was not found in PATH or the default install location.",
            )
            return
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                ahk_exe,
                f"\"{self.hotkeys_script_path}\"",
                None,
                1,
            )
        except OSError as exc:
            messagebox.showerror("AutoHotkey Error", f"Failed to start AutoHotkey as admin: {exc}")

    def _refresh_hotkeys_admin_status(self) -> None:
        admin_state = self._read_ahk_admin_state()
        if admin_state is None:
            self.hotkeys_admin_var.set("AHK admin: ?")
            self.hotkeys_admin_warning_var.set("")
            return
        self.hotkeys_admin_state = admin_state
        self.hotkeys_admin_var.set("AHK admin: yes" if admin_state else "AHK admin: no")
        if admin_state != self.python_is_admin:
            self.hotkeys_admin_warning_var.set("Admin mismatch")
        else:
            self.hotkeys_admin_warning_var.set("")

    def _read_ahk_admin_state(self) -> bool | None:
        if not self.hotkeys_events_path.exists():
            return None
        try:
            with self.hotkeys_events_path.open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - 4096))
                payload = handle.read().decode("utf-8", errors="ignore")
        except OSError:
            return None
        for line in reversed(payload.splitlines()):
            line = line.strip()
            if line.startswith("ADMIN|"):
                return line.endswith("1")
        return None

    @staticmethod
    def _is_admin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except OSError:
            return False

    def _load_cooldowns_table(self) -> None:
        if not self.cooldowns_tree or not self.cooldowns_tree.winfo_exists():
            return
        self._load_cooldowns_state()
        self._refresh_cooldowns_table()

    def _on_cooldown_select(self, _event: tk.Event) -> None:
        if not self.cooldowns_tree or not self.cooldowns_tree.winfo_exists():
            return
        selection = self.cooldowns_tree.selection()
        if not selection:
            return
        self._edit_selected_cooldown()

    def _edit_selected_cooldown(self) -> None:
        if not self.cooldowns_tree or not self.cooldowns_tree.winfo_exists():
            return
        selection = self.cooldowns_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        data = next((entry for entry in self.cooldowns_defs if str(entry.get("id")) == item_id), None)
        if not data:
            return
        if self.cooldown_action_entry:
            self.cooldown_action_entry.delete(0, tk.END)
            self.cooldown_action_entry.insert(0, str(data.get("action_id", "")))
        if self.cooldown_name_entry:
            self.cooldown_name_entry.delete(0, tk.END)
            self.cooldown_name_entry.insert(0, str(data.get("name", "")))
        if self.cooldown_ms_entry:
            self.cooldown_ms_entry.delete(0, tk.END)
            self.cooldown_ms_entry.insert(0, str(data.get("cooldown_ms", "")))
        if self.cooldown_icon_entry:
            self.cooldown_icon_entry.delete(0, tk.END)
            self.cooldown_icon_entry.insert(0, str(data.get("icon_path", "")))

    def _collect_cooldown_form(self) -> dict[str, object] | None:
        if (
            not self.cooldown_action_entry
            or not self.cooldown_name_entry
            or not self.cooldown_ms_entry
            or not self.cooldown_icon_entry
        ):
            return None
        action_id = self.cooldown_action_entry.get().strip()
        name = self.cooldown_name_entry.get().strip()
        cooldown_text = self.cooldown_ms_entry.get().strip()
        icon_path = self.cooldown_icon_entry.get().strip()
        if not action_id or not name:
            messagebox.showwarning("Missing Data", "Action ID and Name are required.")
            return None
        try:
            cooldown_ms = int(cooldown_text) if cooldown_text else 0
        except ValueError:
            messagebox.showwarning("Invalid Cooldown", "Cooldown must be an integer in milliseconds.")
            return None
        return {
            "action_id": action_id,
            "name": name,
            "cooldown_ms": max(0, cooldown_ms),
            "icon_path": icon_path,
        }

    def _add_cooldown(self) -> None:
        data = self._collect_cooldown_form()
        if not data:
            return
        data["id"] = str(uuid.uuid4())
        self.cooldowns_defs.append(data)
        self._refresh_cooldowns_table()
        self._clear_cooldown_form()
        self._save_cooldowns_state()

    def _update_selected_cooldown(self) -> None:
        if not self.cooldowns_tree or not self.cooldowns_tree.winfo_exists():
            return
        selection = self.cooldowns_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a cooldown entry to update.")
            return
        data = self._collect_cooldown_form()
        if not data:
            return
        item_id = selection[0]
        for entry in self.cooldowns_defs:
            if str(entry.get("id")) == item_id:
                entry.update(data)
                break
        self._refresh_cooldowns_table()
        self._clear_cooldown_form()
        self._save_cooldowns_state()

    def _remove_cooldown(self) -> None:
        if not self.cooldowns_tree or not self.cooldowns_tree.winfo_exists():
            return
        selection = self.cooldowns_tree.selection()
        if not selection:
            return
        selected_ids = {str(item) for item in selection}
        self.cooldowns_defs = [entry for entry in self.cooldowns_defs if str(entry.get("id")) not in selected_ids]
        self._refresh_cooldowns_table()
        self._save_cooldowns_state()

    def _refresh_cooldowns_table(self) -> None:
        if not self.cooldowns_tree or not self.cooldowns_tree.winfo_exists():
            return
        self.cooldowns_tree.delete(*self.cooldowns_tree.get_children())
        for entry in self.cooldowns_defs:
            item_id = str(entry.get("id") or uuid.uuid4())
            entry["id"] = item_id
            values = (
                str(entry.get("action_id", "")),
                str(entry.get("name", "")),
                str(entry.get("cooldown_ms", "")),
                str(entry.get("icon_path", "")),
            )
            self.cooldowns_tree.insert("", tk.END, iid=item_id, values=values)

    def _clear_cooldown_form(self) -> None:
        for widget in (
            self.cooldown_action_entry,
            self.cooldown_name_entry,
            self.cooldown_ms_entry,
            self.cooldown_icon_entry,
        ):
            if widget:
                widget.delete(0, tk.END)

    def _browse_cooldown_icon(self) -> None:
        if not self.cooldown_icon_entry:
            return
        path = filedialog.askopenfilename(title="Select Icon")
        if not path:
            return
        self.cooldown_icon_entry.delete(0, tk.END)
        self.cooldown_icon_entry.insert(0, path)

    def _load_cooldowns_state(self) -> None:
        if not self.cooldowns_state_path.exists():
            self.cooldowns_defs = []
            self._ensure_default_cooldowns()
            return
        try:
            payload = json.loads(self.cooldowns_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.cooldowns_defs = []
            self._ensure_default_cooldowns()
            return
        cleaned: list[dict[str, object]] = []
        if isinstance(payload, list):
            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                action_id = str(entry.get("action_id", "")).strip()
                name = str(entry.get("name", "")).strip()
                if not action_id or not name:
                    continue
                cooldown_ms = entry.get("cooldown_ms", 0)
                try:
                    cooldown_ms = max(0, int(cooldown_ms))
                except (TypeError, ValueError):
                    cooldown_ms = 0
                cleaned.append(
                    {
                        "id": str(entry.get("id") or uuid.uuid4()),
                        "action_id": action_id,
                        "name": name,
                        "cooldown_ms": cooldown_ms,
                        "icon_path": str(entry.get("icon_path", "")).strip(),
                    }
                )
        self.cooldowns_defs = cleaned
        self._ensure_default_cooldowns()

    def _save_cooldowns_state(self) -> None:
        payload = [
            {
                "id": str(entry.get("id") or uuid.uuid4()),
                "action_id": str(entry.get("action_id", "")).strip(),
                "name": str(entry.get("name", "")).strip(),
                "cooldown_ms": int(entry.get("cooldown_ms") or 0),
                "icon_path": str(entry.get("icon_path", "")).strip(),
            }
            for entry in self.cooldowns_defs
            if str(entry.get("action_id", "")).strip() and str(entry.get("name", "")).strip()
        ]
        self.cooldowns_state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def _ensure_default_cooldowns(self) -> None:
        if self.cooldowns_defs:
            return
        defaults = [
            {
                "id": str(uuid.uuid4()),
                "action_id": "HASTE",
                "name": "Haste",
                "cooldown_ms": 21000,
                "icon_path": "",
            },
            {
                "id": str(uuid.uuid4()),
                "action_id": "FIRE_WAVE",
                "name": "Fire Wave",
                "cooldown_ms": 4000,
                "icon_path": "",
            },
            {
                "id": str(uuid.uuid4()),
                "action_id": "GEB",
                "name": "Great Energy Beam",
                "cooldown_ms": 8000,
                "icon_path": "",
            },
            {
                "id": str(uuid.uuid4()),
                "action_id": "EB",
                "name": "Energy Beam",
                "cooldown_ms": 6000,
                "icon_path": "",
            },
            {
                "id": str(uuid.uuid4()),
                "action_id": "HELLS_CORE",
                "name": "Hell's Core",
                "cooldown_ms": 40000,
                "icon_path": "",
            },
        ]
        self.cooldowns_defs = defaults
        self._save_cooldowns_state()

    def _load_hotkeys_state(self) -> None:
        if not self.hotkeys_json_path.exists():
            self.hotkeys_defs = []
            self._ensure_default_hotkeys()
            return
        try:
            payload = json.loads(self.hotkeys_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.hotkeys_defs = []
            self._ensure_default_hotkeys()
            return
        cleaned: list[dict[str, object]] = []
        if isinstance(payload, dict):
            target_win = str(payload.get("target_win", "")).strip()
            if target_win:
                self.hotkeys_target_win = target_win
            hotkeys_payload = payload.get("hotkeys", [])
            if isinstance(hotkeys_payload, list):
                for entry in hotkeys_payload:
                    if not isinstance(entry, dict):
                        continue
                    hotkey = str(entry.get("hotkey", "")).strip()
                    action = str(entry.get("action", "")).strip()
                    if not hotkey or not action:
                        continue
                    cleaned.append(
                        {
                            "id": str(entry.get("id") or uuid.uuid4()),
                            "hotkey": hotkey,
                            "action": action,
                        }
                    )
        self.hotkeys_defs = cleaned
        self._ensure_default_hotkeys()

    def _load_grid_overlay_state(self) -> None:
        if not self.grid_overlay_state_path.exists():
            return
        try:
            payload = json.loads(self.grid_overlay_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return

        updates: dict[str, int | bool] = {}
        if "enabled" in payload:
            raw_enabled = payload.get("enabled")
            if isinstance(raw_enabled, bool):
                updates["enabled"] = raw_enabled
            else:
                updates["enabled"] = str(raw_enabled).strip().lower() in {"1", "true", "yes", "on"}
        for key in ("offset_x", "offset_y", "center_x", "center_y"):
            if key not in payload:
                continue
            updates[key] = _parse_int_safe(str(payload.get(key, 0)))
        if "cell_size" in payload:
            cell_size = _parse_int_safe(str(payload.get("cell_size", 0)))
            updates["cell_size"] = max(
                self.grid_overlay.MIN_CELL_SIZE,
                min(self.grid_overlay.MAX_CELL_SIZE, cell_size),
            )
        if "line_color" in payload:
            color = str(payload.get("line_color", "")).strip()
            if color:
                updates["line_color"] = color
        self.grid_overlay.apply_settings(**updates, notify=False)

    def _save_grid_overlay_state(self) -> None:
        payload = self.grid_overlay.get_state()
        self.grid_overlay_state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def _save_hotkeys_state(self) -> None:
        payload = [
            {
                "hotkey": str(entry.get("hotkey", "")).strip(),
                "action": str(entry.get("action", "")).strip(),
            }
            for entry in self.hotkeys_defs
            if str(entry.get("hotkey", "")).strip() and str(entry.get("action", "")).strip()
        ]
        data = {"target_win": self.hotkeys_target_win, "hotkeys": payload}
        self.hotkeys_json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def _ensure_default_hotkeys(self) -> None:
        if self.hotkeys_defs:
            return
        defaults = [
            {
                "id": str(uuid.uuid4()),
                "hotkey": "MButton",
                "action": "F4",
            },
            {
                "id": str(uuid.uuid4()),
                "hotkey": "!MButton",
                "action": "F5",
            },
            {
                "id": str(uuid.uuid4()),
                "hotkey": "^MButton",
                "action": "F6",
            },
            {
                "id": str(uuid.uuid4()),
                "hotkey": "XButton1",
                "action": "F10",
            },
            {
                "id": str(uuid.uuid4()),
                "hotkey": "$WheelUp",
                "action": "HASTE",
            },
            {
                "id": str(uuid.uuid4()),
                "hotkey": "$WheelDown",
                "action": "ALT_Q",
            },
            {
                "id": str(uuid.uuid4()),
                "hotkey": "~3",
                "action": "FIRE_WAVE",
            },
            {
                "id": str(uuid.uuid4()),
                "hotkey": "~4",
                "action": "GEB",
            },
            {
                "id": str(uuid.uuid4()),
                "hotkey": "~!4",
                "action": "EB",
            },
            {
                "id": str(uuid.uuid4()),
                "hotkey": "~!2",
                "action": "HELLS_CORE",
            },
            {
                "id": str(uuid.uuid4()),
                "hotkey": "~!r",
                "action": "HASTE",
            },
        ]
        self.hotkeys_defs = defaults
        self._save_hotkeys_state()

    def _refresh_hotkeys_table(self) -> None:
        if not self.hotkeys_tree or not self.hotkeys_tree.winfo_exists():
            return
        self.hotkeys_tree.delete(*self.hotkeys_tree.get_children())
        for entry in self.hotkeys_defs:
            item_id = str(entry.get("id") or uuid.uuid4())
            entry["id"] = item_id
            values = (
                str(entry.get("hotkey", "")),
                str(entry.get("action", "")),
            )
            self.hotkeys_tree.insert("", tk.END, iid=item_id, values=values)

    def _clear_hotkeys_form(self) -> None:
        for widget in (self.hotkey_entry, self.action_entry):
            if widget:
                widget.delete(0, tk.END)

    def _open_module_window(self, module_key: str) -> None:
        existing = self.module_windows.get(module_key)
        if existing and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title(
            {
                "imbuements": "Imbuements",
                "items": "Tibia Items",
                "hunts": "Hunts",
                "hotkeys": "Hotkeys",
                "grid_overlay": "Grid Overlay",
                "grid_cones": "Grid Cones",
                "cooldowns": "Cooldowns",
                "hunting_ground": "Hunting Ground",
                "character_search": "Charakter suchen",
                "rune_calculator": "Runen Rechner",
                "search_window": "Suchfenster",
                "djinn_selling": "Djinn Selling",
            }.get(module_key, "Module")
        )
        window.minsize(720, 480)
        window.rowconfigure(0, weight=1)
        window.columnconfigure(0, weight=1)
        window.protocol("WM_DELETE_WINDOW", lambda key=module_key, w=window: self._close_module_window(key, w))

        container = ttk.Frame(window, padding=8)
        container.grid(row=0, column=0, sticky="nsew")

        if module_key == "imbuements":
            self._build_imbuements_tab(container)
            self._bind_imbuements_events()
            self._populate_imbuements()
            self._select_first_imbuement()
        elif module_key == "items":
            self._build_items_tab(container)
            self._bind_items_events()
            self._refresh_items_list()
        elif module_key == "hunts":
            self._build_hunts_tab(container)
            self._bind_hunts_events()
            self._refresh_hunts_list()
        elif module_key == "hotkeys":
            self._build_hotkeys_tab(container)
            self._load_hotkeys_table()
        elif module_key == "grid_overlay":
            self._build_grid_overlay_tab(container)
        elif module_key == "grid_cones":
            self._build_grid_cones_tab(container)
        elif module_key == "cooldowns":
            self._build_cooldowns_tab(container)
        elif module_key == "hunting_ground":
            self._build_hunting_ground_tab(container)
        elif module_key == "character_search":
            self._build_character_search_tab(container)
        elif module_key == "rune_calculator":
            self._build_rune_calculator_tab(container)
        elif module_key == "search_window":
            self._build_search_window_tab(container)
        elif module_key == "djinn_selling":
            self._build_djinn_selling_tab(container)

        self.module_windows[module_key] = window

    def _close_module_window(self, module_key: str, window: tk.Toplevel) -> None:
        if module_key in self.module_windows:
            self.module_windows.pop(module_key, None)
        window.destroy()

    def _build_imbuements_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(parent)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        self.imbuement_tree = ttk.Treeview(left_frame, columns=("fav", "name", "total"), show="headings", height=12)
        self.imbuement_tree.heading("fav", text="â˜…")
        self.imbuement_tree.heading("name", text="Imbuement")
        self.imbuement_tree.heading("total", text="Total")
        self.imbuement_tree.column("fav", width=32, anchor="center", stretch=False)
        self.imbuement_tree.column("name", width=220, anchor="w")
        self.imbuement_tree.column("total", width=110, anchor="e")
        self.imbuement_tree.grid(row=0, column=0, sticky="nsew")

        tree_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.imbuement_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.imbuement_tree.configure(yscrollcommand=tree_scroll.set)

        right_frame = ttk.Frame(parent)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)

        header_frame = ttk.Frame(right_frame)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(0, weight=1)

        title_font = tkfont.Font(self.root, size=12, weight="bold")
        self.imbuement_title = ttk.Label(header_frame, text="Select an Imbuement", font=title_font)
        self.imbuement_title.grid(row=0, column=0, sticky="w")

        self.favorite_button = ttk.Button(header_frame, text="â˜†", width=3, command=self.toggle_selected_favorite)
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

    def _build_items_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        controls_frame = ttk.Frame(parent)
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

        list_frame = ttk.Frame(parent)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.items_tree = ttk.Treeview(
            list_frame,
            columns=("fav", "name", "providers", "trader_price", "market_price"),
            show="headings",
        )
        self.items_tree.heading("fav", text="â˜…")
        self.items_tree.heading("name", text="Item", command=lambda: self._set_items_sort("name"))
        self.items_tree.heading("providers", text="Provider")
        self.items_tree.heading("trader_price", text="HÃ¤ndler VK")
        self.items_tree.heading(
            "market_price",
            text="Auktionshaus VK",
            command=lambda: self._set_items_sort("market_price"),
        )
        self.items_tree.column("fav", width=36, anchor="center", stretch=False)
        self.items_tree.column("name", width=220, anchor="w")
        self.items_tree.column("providers", width=300, anchor="w")
        self.items_tree.column("trader_price", width=110, anchor="e")
        self.items_tree.column("market_price", width=130, anchor="e")
        self.items_tree.tag_configure("imbuement-material", foreground="#1a7f37")
        self.items_tree.grid(row=0, column=0, sticky="nsew")

        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.items_tree.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.items_tree.configure(yscrollcommand=list_scroll.set)

        self.items_filter_var.trace_add("write", lambda *_args: self._refresh_items_list())
        self.items_search_var.trace_add("write", lambda *_args: self._refresh_items_list())
        self._refresh_items_list()

    def _build_hunts_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="Hunts").grid(row=0, column=0, sticky="w")
        ttk.Button(header_frame, text="ï¼‹ Hunt hinzufÃ¼gen", command=self._open_add_hunt_dialog).grid(
            row=0, column=1, sticky="e"
        )

        content_frame = ttk.Frame(parent)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=4)
        content_frame.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(content_frame)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
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
        self.hunts_tree.heading("equipment", text="AusrÃ¼stung")
        self.hunts_tree.heading("xp", text="XP Gain")
        self.hunts_tree.column("name", width=220, anchor="w")
        self.hunts_tree.column("character", width=140, anchor="center")
        self.hunts_tree.column("equipment", width=120, anchor="center")
        self.hunts_tree.column("xp", width=120, anchor="e")
        self.hunts_tree.grid(row=0, column=0, sticky="nsew")

        hunt_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.hunts_tree.yview)
        hunt_scroll.grid(row=0, column=1, sticky="ns")
        self.hunts_tree.configure(yscrollcommand=hunt_scroll.set)

        self.hunts_notebook = ttk.Notebook(content_frame)
        self.hunts_notebook.grid(row=0, column=1, sticky="nsew")

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

        ttk.Label(equipment_frame, text="AusrÃ¼stung:").grid(row=1, column=0, sticky="w")
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
            var = tk.StringVar(value="â€”")
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
            var = tk.StringVar(value="â€”")
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
        self.hunt_profit_tree.heading("equipment", text="AusrÃ¼stung")
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
        self.hunt_xp_tree.heading("equipment", text="AusrÃ¼stung")
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
        self.root.bind("<Control-Shift-f>", lambda _event: self._show_search_window())
        self.root.bind("<FocusIn>", lambda _event: self._show_search_window())
        self.root.bind_all("<KeyPress>", self._on_movement_key, add=True)

        self.history_list.bind("<ButtonRelease-1>", self.load_from_history)
        self.history_list.bind("<Double-Button-1>", lambda _event: self.search_from_history())
        self.history_list.bind("<Return>", lambda _event: self.search_from_history())

    def _bind_imbuements_events(self) -> None:
        if not getattr(self, "imbuement_tree", None) or not self.imbuement_tree.winfo_exists():
            return
        self.imbuement_tree.bind("<<TreeviewSelect>>", self.on_imbuement_select)
        self.imbuement_tree.bind("<Double-Button-1>", lambda _event: self.search_selected_imbuement())
        self.imbuement_tree.bind("<Return>", lambda _event: self.search_selected_imbuement())
        self.imbuement_tree.bind("<Button-1>", self.on_tree_click)

    def _bind_items_events(self) -> None:
        if not getattr(self, "items_tree", None) or not self.items_tree.winfo_exists():
            return
        self.items_tree.bind("<Double-Button-1>", self._on_items_tree_double_click)
        self.items_tree.bind("<Return>", self._open_selected_item)
        self.items_tree.bind("<Button-1>", self._on_items_tree_click)

    def _bind_hunts_events(self) -> None:
        if not getattr(self, "hunts_tree", None) or not self.hunts_tree.winfo_exists():
            return
        self.hunts_tree.bind("<<TreeviewSelect>>", self._on_hunt_select)
        self.hunt_profit_tree.bind("<<TreeviewSelect>>", self._on_hunt_stats_select)
        self.hunt_xp_tree.bind("<<TreeviewSelect>>", self._on_hunt_stats_select)
        if not self._hunt_traces_bound:
            self.hunt_equipment_var.trace_add("write", self._on_hunt_equipment_change)
            self.hunt_character_var.trace_add("write", self._on_hunt_character_change)
            self._hunt_traces_bound = True

    def clear_entry(self) -> None:
        self.search_entry.delete(0, tk.END)

    def _on_movement_key(self, event: tk.Event) -> None:
        if isinstance(event.widget, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox)):
            return
        key = event.keysym.lower()
        direction_map = {"w": "UP", "d": "RIGHT", "s": "DOWN", "a": "LEFT"}
        direction = direction_map.get(key)
        if not direction:
            return
        self._set_cone_direction(direction)

    def _set_cone_direction(self, direction: str) -> None:
        self.grid_cone_overlay.set_direction(direction)
        self.grid_cone_overlay_alt.set_direction(direction)

    def _collect_imbuement_material_names(self) -> set[str]:
        names: set[str] = set()
        for imbuement in IMBUEMENTS:
            for material in imbuement.materials:
                names.add(material.name)
        return names

    def _seed_imbuement_material_favorites(self) -> None:
        for name in self.imbuement_material_names:
            if not self.item_price_store.has_favorite_entry(name):
                self.item_price_store.set_favorite(name, True)

    def _is_imbuement_material(self, item_name: str) -> bool:
        return item_name.casefold() in self.imbuement_material_names_lower

    def _active_items(self) -> tuple[TibiaItem, ...]:
        if self.items_filter_var.get() == "delivery":
            return self.delivery_items
        return self.creature_products

    def _refresh_items_list(self) -> None:
        if not getattr(self, "items_tree", None) or not self.items_tree.winfo_exists():
            return
        if not getattr(self, "items_filter_var", None) or not getattr(self, "items_search_var", None):
            return
        query = self.items_search_var.get().strip().casefold()
        items = [
            item
            for item in self._active_items()
            if not query or query in f"{item.name} {' '.join(item.providers)}".casefold()
        ]
        favorites = [item for item in items if self.item_price_store.is_favorite(item.name)]
        non_favorites = [item for item in items if not self.item_price_store.is_favorite(item.name)]
        favorites_sorted = sorted(favorites, key=self._items_sort_value, reverse=self.items_sort_desc)
        non_favorites_sorted = sorted(non_favorites, key=self._items_sort_value, reverse=self.items_sort_desc)
        sorted_items = favorites_sorted + non_favorites_sorted

        self.items_tree.delete(*self.items_tree.get_children())
        self.items_list_items = []
        self.items_tree_items = {}
        for item in sorted_items:
            providers_text = ", ".join(item.providers)
            name_display = item.name
            if not item.url:
                name_display = f"{name_display} (no link)"
            trader_price = self.item_price_store.get_price(item.name)
            trader_display = self._format_price(trader_price)
            market_display = self._format_price(item.gold)
            row_id = str(len(self.items_list_items))
            fav = "â˜…" if self.item_price_store.is_favorite(item.name) else "â˜†"
            tags = ("imbuement-material",) if self._is_imbuement_material(item.name) else ()
            self.items_tree.insert(
                "",
                tk.END,
                iid=row_id,
                values=(fav, name_display, providers_text, trader_display, market_display),
                tags=tags,
            )
            self.items_list_items.append(item)
            self.items_tree_items[row_id] = item

    def _items_sort_value(self, item: TibiaItem) -> object:
        if self.items_sort_field == "market_price":
            return item.gold
        return item.name.casefold()

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
        if column == "#4":
            self._begin_price_edit(event)
        else:
            self._open_selected_item(event)

    def _on_items_tree_click(self, event: tk.Event) -> None:
        region = self.items_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self.items_tree.identify_column(event.x)
        row_id = self.items_tree.identify_row(event.y)
        if column == "#1" and row_id:
            item = self.items_tree_items.get(row_id)
            if item:
                self._toggle_item_favorite(item)
                self._refresh_items_list()

    def _set_items_sort(self, field: str) -> None:
        if field == self.items_sort_field:
            self.items_sort_desc = not self.items_sort_desc
        else:
            self.items_sort_field = field
            self.items_sort_desc = False
        self._refresh_items_list()

    def _begin_price_edit(self, event: tk.Event) -> None:
        row_id = self.items_tree.identify_row(event.y)
        if not row_id:
            return
        column = self.items_tree.identify_column(event.x)
        if column != "#4":
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

    def _toggle_item_favorite(self, item: TibiaItem) -> None:
        is_favorite = self.item_price_store.is_favorite(item.name)
        self.item_price_store.set_favorite(item.name, not is_favorite)

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
        dialog.title("Hunt hinzufÃ¼gen")
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

        ttk.Label(form_frame, text="AusrÃ¼stung:").grid(row=2, column=0, sticky="w", pady=4)
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
                messagebox.showwarning("Fehlender Character", "Bitte einen Character auswÃ¤hlen.")
                return
            if not raw_log:
                messagebox.showwarning("Fehlender Log", "Bitte den Session-Log einfÃ¼gen.")
                return
            hunt_id = self.hunt_store.add_hunt(name, character_id, equipment_tag, raw_log)
            self._refresh_hunts_list(select_id=hunt_id)
            dialog.destroy()

        name_entry.focus_set()

    def _refresh_hunts_list(self, select_id: str | None = None) -> None:
        if not getattr(self, "hunts_tree", None) or not self.hunts_tree.winfo_exists():
            return
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
        return name or "â€”"

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
                var.set("â€”")
            for var in self.hunt_rate_vars.values():
                var.set("â€”")
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
                self.hunt_rate_vars[key].set("â€”")

    def _set_breakdown_list(self, listbox: tk.Listbox | None, breakdown: dict[str, int]) -> None:
        if listbox is None:
            return
        listbox.delete(0, tk.END)
        if not breakdown:
            listbox.insert(tk.END, "â€”")
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
        if not getattr(self, "hunt_profit_tree", None) or not self.hunt_profit_tree.winfo_exists():
            return
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
            return "â€”"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _format_rate(self, value: object) -> str:
        if value is None:
            return "â€”"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "â€”"
        if abs(numeric - round(numeric)) < 0.01:
            return _format_number(round(numeric))
        return _format_number(numeric, decimals=2)

    def toggle_topmost(self) -> None:
        self.always_on_top = not self.always_on_top
        target = self.search_window if self.search_window and self.search_window.winfo_exists() else self.root
        target.attributes("-topmost", self.always_on_top)
        self.top_button.config(text="Top")
        self._queue_search_window_save()

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
        if not getattr(self, "imbuement_tree", None) or not self.imbuement_tree.winfo_exists():
            return
        self.imbuement_tree.delete(*self.imbuement_tree.get_children())
        ordered = sorted(
            IMBUEMENTS,
            key=lambda item: (not self.store.is_favorite(item.key),),
        )
        for imbuement in ordered:
            self._insert_imbuement(imbuement)

    def _insert_imbuement(self, imbuement: Imbuement) -> None:
        fav = "â˜…" if self.store.is_favorite(imbuement.key) else "â˜†"
        total = self._format_gp(self._calculate_total(imbuement))
        self.imbuement_tree.insert("", tk.END, iid=imbuement.key, values=(fav, imbuement.name, total))

    def _select_first_imbuement(self) -> None:
        if not getattr(self, "imbuement_tree", None) or not self.imbuement_tree.winfo_exists():
            return
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
        self.favorite_button.config(text="â˜…" if self.store.is_favorite(imbuement.key) else "â˜†")

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
            result = refresh_market_prices("Xyla", log=self._log_market_request)
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
            fav = "â˜…" if self.store.is_favorite(imbuement.key) else "â˜†"
            self.imbuement_tree.item(child, values=(fav, imbuement.name, total))

    def _calculate_total(self, imbuement: Imbuement) -> int:
        return sum(material.qty * self.store.get_price(material.name) for material in imbuement.materials)

    def _format_gp(self, value: int) -> str:
        return f"{value:,}".replace(",", ".") + " gp"

    def _restart_app(self) -> None:
        if not messagebox.askyesno("Neustart", "Tibia Search jetzt neu starten?"):
            return
        try:
            if self._is_hotkeys_running():
                self._stop_hotkeys_script()
            if self._is_cones_running():
                self._stop_cones_script()
            self._save_search_window_state(force_position=True)
            self.grid_cone_overlay.shutdown()
            self.grid_cone_overlay_alt.shutdown()
            self.grid_overlay.shutdown()
            self.root.update_idletasks()

            if getattr(sys, "frozen", False):
                args = [sys.executable, *sys.argv[1:]]
            else:
                args = [sys.executable, *sys.argv]
            os.execv(sys.executable, args)
        except Exception as exc:
            messagebox.showerror("Neustart fehlgeschlagen", str(exc))

    def exit_app(self) -> None:
        if self._is_hotkeys_running():
            self._stop_hotkeys_script()
        if self._is_cones_running():
            self._stop_cones_script()
        self._save_search_window_state(force_position=True)
        self.grid_cone_overlay.shutdown()
        self.grid_cone_overlay_alt.shutdown()
        self.grid_overlay.shutdown()
        self.root.destroy()

    def _auto_start_tibia(self) -> None:
        if not self.auto_start_tibia_on_launch:
            return
        if not self.tibia_exe_path.exists():
            self.tibia_exe_path = self._resolve_tibia_exe_path()
        if not self.tibia_exe_path.exists():
            self._log_tibia_paste(
                f"Autostart skipped. Missing Tibia executable (resolved): {self.tibia_exe_path}"
            )
            return
        if self._is_tibia_running():
            self._log_tibia_paste("Autostart skipped. Tibia is already running.")
            return
        self._start_tibia(False, schedule_login=False)

    def _start_tibia(self, as_admin: bool, schedule_login: bool = True) -> None:
        if not self.tibia_exe_path.exists():
            self.tibia_exe_path = self._resolve_tibia_exe_path()
        if not self.tibia_exe_path.exists():
            messagebox.showerror(
                "Tibia Missing",
                "Tibia-Executable nicht gefunden.\n\n"
                f"Gesucht (resolved): {self.tibia_exe_path}\n\n"
                "Fix:\n"
                "- Lege eine Datei 'tibia_exe_path.txt' neben TibiaSearch (einzeilig: voller Pfad zu client.exe/tibia.exe)\n"
                "- oder setze die Umgebungsvariable TIBIA_EXE auf den vollen Pfad.",
            )
            self._log_tibia_paste(f"Tibia start failed. Missing executable: {self.tibia_exe_path}")
            return
        if self._is_tibia_running():
            self.tibia_login_status_var.set("Tibia läuft bereits.")
            self._log_tibia_paste("Start skipped. Tibia is already running.")
            return
        try:
            if as_admin:
                rc = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    str(self.tibia_exe_path),
                    None,
                    str(self.tibia_exe_path.parent),
                    1,
                )
                if rc <= 32:
                    raise OSError(f"ShellExecuteW failed with code {rc}")
            else:
                subprocess.Popen([str(self.tibia_exe_path)], cwd=str(self.tibia_exe_path.parent))
            if schedule_login:
                self._schedule_tibia_login()
        except OSError as exc:
            messagebox.showerror("Tibia Error", f"Failed to start Tibia: {exc}")
            self._log_tibia_paste(f"Tibia start failed: {exc}")

    def _is_tibia_running(self) -> bool:
        if self._find_tibia_window() is not None:
            return True
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for image_name in ("client.exe", "tibia.exe"):
            try:
                proc = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    creationflags=creation_flags,
                )
            except OSError:
                continue
            output = (proc.stdout or "").strip().casefold()
            if not output:
                continue
            if "no tasks are running" in output or "keine tasks ausgeführt" in output:
                continue
            if image_name.casefold() in output:
                return True
        return False

    def _schedule_tibia_login(self) -> None:
        if self.tibia_login_after_id is not None:
            self.root.after_cancel(self.tibia_login_after_id)
            self.tibia_login_after_id = None
        self.tibia_login_remaining = 20
        self.tibia_login_status_var.set("Tibia login in 20s")
        self._log_tibia_paste("Timer started (20s).")
        self.tibia_login_after_id = self.root.after(1000, self._tick_tibia_login)

    def _tick_tibia_login(self) -> None:
        self.tibia_login_remaining -= 1
        if self.tibia_login_remaining <= 0:
            self.tibia_login_after_id = None
            self.tibia_login_status_var.set("Sending password...")
            self._log_tibia_paste("Timer elapsed. Sending password.")
            self._send_tibia_password()
            return
        self.tibia_login_status_var.set(f"Tibia login in {self.tibia_login_remaining}s")
        self.tibia_login_after_id = self.root.after(1000, self._tick_tibia_login)

    def _send_tibia_password(self) -> None:
        try:
            _username, password = load_credentials(self.tibia_login_target)
        except CredentialNotFoundError:
            self.tibia_login_status_var.set("")
            messagebox.showerror(
                "Credentials Missing",
                f"No credentials found for target '{self.tibia_login_target}'.",
            )
            return
        except CredentialStoreError as exc:
            self.tibia_login_status_var.set("")
            messagebox.showerror("Credential Error", str(exc))
            return

        hwnd = self._find_tibia_window()
        if hwnd is None or not ctypes.windll.user32.SetForegroundWindow(hwnd):
            self.tibia_login_status_var.set("")
            messagebox.showerror("Tibia Window", "Tibia window not found or not focusable.")
            return

        self.tibia_login_status_var.set("Preparing paste...")
        self._log_tibia_paste("Tibia window focused. Preparing paste.")
        self.root.after(200, lambda: self._finish_tibia_login(password))

    def _finish_tibia_login(self, password: str) -> None:
        if not self._set_clipboard_text(password):
            messagebox.showerror("Clipboard Error", "Failed to copy password to clipboard.")
            return
        self.tibia_login_status_var.set("Clipboard set, running paste script...")
        self._log_tibia_paste("Clipboard set. Launching paste script.")
        self._run_tibia_paste_script()

    def _copy_tibia_password(self) -> None:
        try:
            _username, password = load_credentials(self.tibia_login_target)
        except CredentialNotFoundError:
            messagebox.showerror(
                "Credentials Missing",
                f"No credentials found for target '{self.tibia_login_target}'.",
            )
            return
        except CredentialStoreError as exc:
            messagebox.showerror("Credential Error", str(exc))
            return
        if not self._set_clipboard_text(password):
            messagebox.showerror("Clipboard Error", "Failed to copy password to clipboard.")
            return
        messagebox.showinfo("Clipboard", "Password copied to clipboard.")

    def _find_tibia_window(self) -> int | None:
        user32 = ctypes.windll.user32
        results: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_proc(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.casefold()
            if "tibia" in title and title != "tibia search":
                results.append(hwnd)
                return False
            return True

        user32.EnumWindows(enum_proc, 0)
        return results[0] if results else None

    def _set_clipboard_text(self, text: str) -> bool:
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
            return True
        except tk.TclError:
            return False

    def _run_tibia_paste_script(self) -> None:
        if not self.tibia_paste_script_path.exists():
            messagebox.showerror(
                "Paste Script Missing",
                f"Missing script: {self.tibia_paste_script_path}",
            )
            self._log_tibia_paste("Paste script missing.")
            return
        ahk_exe = self._resolve_ahk_exe()
        if not ahk_exe:
            messagebox.showerror(
                "AutoHotkey Missing",
                "AutoHotkey v2 was not found in PATH or the default install location.",
            )
            self._log_tibia_paste("AutoHotkey missing.")
            return
        try:
            subprocess.Popen([ahk_exe, str(self.tibia_paste_script_path)])
            self.tibia_login_status_var.set("Paste script started.")
            self._log_tibia_paste(f"Paste script started via: {ahk_exe}")
        except OSError as exc:
            messagebox.showerror("AutoHotkey Error", f"Failed to start paste script: {exc}")
            self._log_tibia_paste(f"Paste script failed: {exc}")

    def _log_tibia_paste(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self.tibia_paste_log_path.open("a", encoding="utf-8", errors="replace") as handle:
                handle.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

    def open_character_window(self) -> None:
        if self.character_window and self.character_window.window.winfo_exists():
            self.character_window.window.deiconify()
            self.character_window.window.lift()
            self.character_window.window.focus_force()
            return
        market_price_lookup: dict[str, int] = {}
        for item in (*self.creature_products, *self.delivery_items):
            key = item.name.casefold()
            gold = int(item.gold or 0)
            if key not in market_price_lookup or gold > market_price_lookup[key]:
                market_price_lookup[key] = gold
        self.character_window = CharacterWindow(
            self.root,
            self.character_store,
            market_price_lookup,
            self._on_character_window_closed,
        )

    def _on_character_window_closed(self) -> None:
        self.character_window = None


class CharacterWindow:
    def __init__(
        self,
        root: tk.Tk,
        store: CharacterStore,
        market_price_lookup: dict[str, int],
        on_close: Callable[[], None],
    ) -> None:
        self.root = root
        self.store = store
        self.market_price_lookup = market_price_lookup
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
            ("ML& to go", "ml_percent"),
            ("HP", "hp"),
            ("Mana", "mana"),
            ("Mana Regen (Hungry /5s)", "mana_regen_hungry"),
            ("Mana Regen (Fed /5s)", "mana_regen_fed"),
            ("Mana Regen (Depot /5s, Daily Reward x2)", "mana_regen_depot"),
            ("HP Regen (Hungry /5s)", "hp_regen_hungry"),
            ("HP Regen (Fed /5s)", "hp_regen_fed"),
            ("HP Regen (Depot /5s, Daily Reward x2)", "hp_regen_depot"),
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

        readonly_fields = {
            "hp",
            "mana",
            "mana_regen_hungry",
            "mana_regen_fed",
            "mana_regen_depot",
            "hp_regen_hungry",
            "hp_regen_fed",
            "hp_regen_depot",
            "capacity",
            "speed",
            "soul_points",
        }

        for row, (label, key) in enumerate(fields):
            ttk.Label(stats_frame, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=2)
            if key == "vocation":
                var = tk.StringVar()
                entry = ttk.Combobox(stats_frame, textvariable=var, values=VOCATIONS, state="readonly")
                entry.grid(row=row, column=1, sticky="ew", padx=6, pady=2)
                self.stats_widgets[key] = entry
            else:
                var = tk.StringVar()
                entry_state = "readonly" if key in readonly_fields else "normal"
                entry = ttk.Entry(stats_frame, textvariable=var, state=entry_state)
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
            item_label = tk.Label(slot_frame, text="â€” leer â€”")
            item_label.grid(row=0, column=1, sticky="w", padx=4, pady=2)

            imbue_info = tk.Label(slot_frame, text="Imbues: 0/0")
            imbue_info.grid(row=1, column=0, columnspan=2, sticky="w", padx=4)

            imbue_labels = []
            remove_buttons = []
            for slot_idx in range(3):
                label = tk.Label(slot_frame, text=f"Slot {slot_idx + 1}: â€”")
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
        vocation_widget = self.stats_widgets.get("vocation")
        if vocation_widget:
            vocation_widget.bind("<<ComboboxSelected>>", lambda _event: self._save_stats("vocation"))

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
            self.stats_vars[key].set(self._format_stat_value(key, value))

        derived = self._compute_derived_stats(
            int(character.get("level", 1) or 1),
            int(stats.get("magic_level", 0) or 0) if isinstance(stats, dict) else 0,
            str(character.get("vocation", VOCATIONS[0])),
            stats if isinstance(stats, dict) else {},
        )
        if isinstance(stats, dict):
            stats.update(derived)
        for key, value in derived.items():
            self.stats_vars[key].set(self._format_stat_value(key, value))
        character["stats"] = stats
        self.store.update_character(self.current_character_name, character)
        self._update_stat_entry_states(str(character.get("vocation", VOCATIONS[0])))

        self._set_active_slot(self.active_slot)
        self._refresh_equipment()
        self._queue_summary_refresh()

    def _save_stats(self, changed_key: str) -> None:
        character = self.store.get_active()
        old_name = str(character["name"])
        name_value = self.stats_vars["name"].get().strip()
        vocation_value = self.stats_vars["vocation"].get().strip() or VOCATIONS[0]
        level_value = self._parse_int(self.stats_vars["level"].get(), minimum=1)
        magic_level_value = self._parse_int(self.stats_vars["magic_level"].get(), minimum=0)

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
        if magic_level_value is None:
            self._mark_invalid("magic_level", character.get("stats", {}).get("magic_level", 0))
            return

        stats = character.get("stats", {})
        if not isinstance(stats, dict):
            stats = {}
        updated_stats = DEFAULT_STATS.copy()
        updated_stats.update(stats)

        mage_vocations = {"Elder Druid", "Master Sorcerer"}
        is_mage = vocation_value in mage_vocations
        editable_keys = {
            "magic_level",
            "ml_percent",
            "stamina",
            "shielding",
            "sword",
            "axe",
            "club",
            "distance",
        }
        if not is_mage:
            editable_keys.update({"hp", "mana", "capacity"})
        for key in editable_keys:
            raw = self.stats_vars[key].get()
            if key == "ml_percent":
                value = self._parse_float_value(raw)
                if value is None:
                    self._mark_invalid(key, updated_stats.get(key, 0))
                    return
                value = max(0.0, min(100.0, value))
                updated_stats[key] = value
                self._clear_invalid(key)
                continue
            value = self._parse_int(raw, minimum=0)
            if value is None:
                self._mark_invalid(key, updated_stats.get(key, 0))
                return
            updated_stats[key] = value
            self._clear_invalid(key)

        derived = self._compute_derived_stats(
            level_value,
            magic_level_value,
            vocation_value,
            updated_stats,
        )
        for key, value in derived.items():
            updated_stats[key] = value
            self.stats_vars[key].set(self._format_stat_value(key, value))
            self._clear_invalid(key)
        self._update_stat_entry_states(vocation_value)

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

    def _parse_float_value(self, value: str) -> float | None:
        value = value.strip().replace(",", ".")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _format_stat_value(self, key: str, value: object) -> str:
        if key in FLOAT_STATS:
            try:
                return f"{float(value):.2f}"
            except (TypeError, ValueError):
                return "0.00"
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "0"

    def _update_stat_entry_states(self, vocation_value: str) -> None:
        mage_vocations = {"Elder Druid", "Master Sorcerer"}
        is_mage = vocation_value in mage_vocations
        for key in ("hp", "mana", "capacity"):
            entry = self.stats_entries.get(key)
            if not entry:
                continue
            entry.configure(state="readonly" if is_mage else "normal")

    def _compute_derived_stats(
        self,
        level: int,
        magic_level: int,
        vocation_value: str,
        existing_stats: dict[str, object],
    ) -> dict[str, object]:
        mage_vocations = {"Elder Druid", "Master Sorcerer"}
        is_mage = vocation_value in mage_vocations

        if is_mage:
            hp = 5 * (level + 29)
            mana = 30 * level - 150
            capacity = 10 * (level + 19)
        else:
            hp = int(existing_stats.get("hp") or 0)
            mana = int(existing_stats.get("mana") or 0)
            capacity = int(existing_stats.get("capacity") or 0)

        speed = 109 + level
        soul_points = 200
        ml_percent = float(existing_stats.get("ml_percent") or 0.0)

        if is_mage:
            mana_regen_hungry = 5.0
            mana_regen_fed = 6.0
            hp_regen_hungry = 4.0
            hp_regen_fed = 5.0
        else:
            mana_regen_hungry = 2.0 * 5.0 / 6.0
            mana_regen_fed = 2.0
            hp_regen_hungry = 8.0
            hp_regen_fed = 10.0

        mana_regen_depot = mana_regen_fed * 2.0
        hp_regen_depot = hp_regen_fed * 2.0

        return {
            "hp": hp,
            "mana": mana,
            "capacity": capacity,
            "speed": speed,
            "soul_points": soul_points,
            "ml_percent": ml_percent,
            "mana_regen_hungry": mana_regen_hungry,
            "mana_regen_fed": mana_regen_fed,
            "mana_regen_depot": mana_regen_depot,
            "hp_regen_hungry": hp_regen_hungry,
            "hp_regen_fed": hp_regen_fed,
            "hp_regen_depot": hp_regen_depot,
        }

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

            item_label.config(text=item_name or "â€” leer â€”")
            item = self.item_map.get(item_name) if item_name else None
            max_slots = item.imbue_slots if item else 0
            imbue_info.config(text=f"Imbues: {len(imbues)}/{max_slots}")

            for idx in range(3):
                label_key = f"slot_{idx + 1}"
                label = self.equipment_labels[slot][label_key]
                if idx < max_slots:
                    name = "â€”"
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
                        price = self.market_price_lookup.get(material.name.casefold(), 0)
                        imbue_total += total_qty * price
                lines.append(f"{name} (x{count}) â€“ Total: {self._format_gp(imbue_total)}")
                if imbuement:
                    for material in imbuement.materials:
                        total_qty = material.qty * count
                        price = self.market_price_lookup.get(material.name.casefold(), 0)
                        line_total = total_qty * price
                        lines.append(
                            f"  {total_qty} Ã— {material.name} â€“ {self._format_gp(price)}/Stk â€“ {self._format_gp(line_total)}"
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
                    price = self.market_price_lookup.get(name.casefold(), 0)
                    total_qty = totals[name]
                    line_total = total_qty * price
                    lines.append(
                        f"  {name}: {total_qty} Ã— {self._format_gp(price)}/Stk â€“ {self._format_gp(line_total)}"
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


