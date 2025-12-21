# Data-only resource file. Edit IMBUEMENTS_RESOURCE to change available imbuements.
IMBUEMENTS_RESOURCE = {
    "wiki_base": "https://tibia.fandom.com/wiki/",
    "imbuements": [
        {
            "type": "Scorch",
            "category": "Attack / Fire Damage",
            "tiers": [
                {
                    "name": "Basic Scorch",
                    "effect": "10% converted",
                    "sources": [{"name": "Fiery Heart", "qty": 25}],
                },
                {
                    "name": "Intricate Scorch",
                    "effect": "25% converted",
                    "sources": [
                        {"name": "Fiery Heart", "qty": 25},
                        {"name": "Green Dragon Scale", "qty": 5},
                    ],
                },
                {
                    "name": "Powerful Scorch",
                    "effect": "50% converted",
                    "sources": [
                        {"name": "Fiery Heart", "qty": 25},
                        {"name": "Green Dragon Scale", "qty": 5},
                        {"name": "Demon Horn", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Venom",
            "category": "Attack / Earth Damage",
            "tiers": [
                {
                    "name": "Basic Venom",
                    "effect": "10% converted",
                    "sources": [{"name": "Swamp Grass", "qty": 25}],
                },
                {
                    "name": "Intricate Venom",
                    "effect": "25% converted",
                    "sources": [
                        {"name": "Swamp Grass", "qty": 25},
                        {"name": "Poisonous Slime", "qty": 20},
                    ],
                },
                {
                    "name": "Powerful Venom",
                    "effect": "50% converted",
                    "sources": [
                        {"name": "Swamp Grass", "qty": 25},
                        {"name": "Poisonous Slime", "qty": 20},
                        {"name": "Slime Heart", "qty": 2},
                    ],
                },
            ],
        },
        {
            "type": "Frost",
            "category": "Attack / Ice Damage",
            "tiers": [
                {
                    "name": "Basic Frost",
                    "effect": "10% converted",
                    "sources": [{"name": "Frosty Heart", "qty": 25}],
                },
                {
                    "name": "Intricate Frost",
                    "effect": "25% converted",
                    "sources": [
                        {"name": "Frosty Heart", "qty": 25},
                        {"name": "Seacrest Hair", "qty": 10},
                    ],
                },
                {
                    "name": "Powerful Frost",
                    "effect": "50% converted",
                    "sources": [
                        {"name": "Frosty Heart", "qty": 25},
                        {"name": "Seacrest Hair", "qty": 10},
                        {"name": "Polar Bear Paw", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Electrify",
            "category": "Attack / Energy Damage",
            "tiers": [
                {
                    "name": "Basic Electrify",
                    "effect": "10% converted",
                    "sources": [{"name": "Rorc Feather", "qty": 25}],
                },
                {
                    "name": "Intricate Electrify",
                    "effect": "25% converted",
                    "sources": [
                        {"name": "Rorc Feather", "qty": 25},
                        {"name": "Peacock Feather Fan", "qty": 5},
                    ],
                },
                {
                    "name": "Powerful Electrify",
                    "effect": "50% converted",
                    "sources": [
                        {"name": "Rorc Feather", "qty": 25},
                        {"name": "Peacock Feather Fan", "qty": 5},
                        {"name": "Energy Vein", "qty": 1},
                    ],
                },
            ],
        },
        {
            "type": "Reap",
            "category": "Attack / Death Damage",
            "tiers": [
                {
                    "name": "Basic Reap",
                    "effect": "10% converted",
                    "sources": [{"name": "Pile of Grave Earth", "qty": 25}],
                },
                {
                    "name": "Intricate Reap",
                    "effect": "25% converted",
                    "sources": [
                        {"name": "Pile of Grave Earth", "qty": 25},
                        {"name": "Demonic Skeletal Hand", "qty": 20},
                    ],
                },
                {
                    "name": "Powerful Reap",
                    "effect": "50% converted",
                    "sources": [
                        {"name": "Pile of Grave Earth", "qty": 25},
                        {"name": "Demonic Skeletal Hand", "qty": 20},
                        {"name": "Petrified Scream", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Vampirism",
            "category": "Attack / Life Leech",
            "tiers": [
                {
                    "name": "Basic Vampirism",
                    "effect": "5% leeched",
                    "sources": [{"name": "Vampire Teeth", "qty": 25}],
                },
                {
                    "name": "Intricate Vampirism",
                    "effect": "10% leeched",
                    "sources": [
                        {"name": "Vampire Teeth", "qty": 25},
                        {"name": "Bloody Pincers", "qty": 15},
                    ],
                },
                {
                    "name": "Powerful Vampirism",
                    "effect": "25% leeched",
                    "sources": [
                        {"name": "Vampire Teeth", "qty": 25},
                        {"name": "Bloody Pincers", "qty": 15},
                        {"name": "Piece of Dead Brain", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Void",
            "category": "Attack / Mana Leech",
            "tiers": [
                {
                    "name": "Basic Void",
                    "effect": "3% leeched",
                    "sources": [{"name": "Rope Belt", "qty": 25}],
                },
                {
                    "name": "Intricate Void",
                    "effect": "5% leeched",
                    "sources": [
                        {"name": "Rope Belt", "qty": 25},
                        {"name": "Silencer Claw", "qty": 25},
                    ],
                },
                {
                    "name": "Powerful Void",
                    "effect": "8% leeched",
                    "sources": [
                        {"name": "Rope Belt", "qty": 25},
                        {"name": "Silencer Claw", "qty": 25},
                        {"name": "Some Grimeleech Wings", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Strike",
            "category": "Attack / Critical Hit",
            "tiers": [
                {
                    "name": "Basic Strike",
                    "effect": "5% chance / +5% crit dmg",
                    "sources": [{"name": "Protective Charm", "qty": 20}],
                },
                {
                    "name": "Intricate Strike",
                    "effect": "5% chance / +15% crit dmg",
                    "sources": [
                        {"name": "Protective Charm", "qty": 20},
                        {"name": "Sabretooth", "qty": 25},
                    ],
                },
                {
                    "name": "Powerful Strike",
                    "effect": "5% chance / +40% crit dmg",
                    "sources": [
                        {"name": "Protective Charm", "qty": 20},
                        {"name": "Sabretooth", "qty": 25},
                        {"name": "Vexclaw Talon", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Lich Shroud",
            "category": "Protective / Death Protection",
            "tiers": [
                {
                    "name": "Basic Lich Shroud",
                    "effect": "2% protection",
                    "sources": [{"name": "Flask of Embalming Fluid", "qty": 25}],
                },
                {
                    "name": "Intricate Lich Shroud",
                    "effect": "5% protection",
                    "sources": [
                        {"name": "Flask of Embalming Fluid", "qty": 25},
                        {"name": "Gloom Wolf Fur", "qty": 20},
                    ],
                },
                {
                    "name": "Powerful Lich Shroud",
                    "effect": "10% protection",
                    "sources": [
                        {"name": "Flask of Embalming Fluid", "qty": 25},
                        {"name": "Gloom Wolf Fur", "qty": 20},
                        {"name": "Mystical Hourglass", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Snake Skin",
            "category": "Protective / Earth Protection",
            "tiers": [
                {
                    "name": "Basic Snake Skin",
                    "effect": "3% protection",
                    "sources": [{"name": "Piece of Swampling Wood", "qty": 25}],
                },
                {
                    "name": "Intricate Snake Skin",
                    "effect": "8% protection",
                    "sources": [
                        {"name": "Piece of Swampling Wood", "qty": 25},
                        {"name": "Snake Skin", "qty": 20},
                    ],
                },
                {
                    "name": "Powerful Snake Skin",
                    "effect": "15% protection",
                    "sources": [
                        {"name": "Piece of Swampling Wood", "qty": 25},
                        {"name": "Snake Skin", "qty": 20},
                        {"name": "Brimstone Fang", "qty": 10},
                    ],
                },
            ],
        },
        {
            "type": "Dragon Hide",
            "category": "Protective / Fire Protection",
            "tiers": [
                {
                    "name": "Basic Dragon Hide",
                    "effect": "3% protection",
                    "sources": [{"name": "Green Dragon Leather", "qty": 20}],
                },
                {
                    "name": "Intricate Dragon Hide",
                    "effect": "8% protection",
                    "sources": [
                        {"name": "Green Dragon Leather", "qty": 20},
                        {"name": "Blazing Bone", "qty": 10},
                    ],
                },
                {
                    "name": "Powerful Dragon Hide",
                    "effect": "15% protection",
                    "sources": [
                        {"name": "Green Dragon Leather", "qty": 20},
                        {"name": "Blazing Bone", "qty": 10},
                        {"name": "Draken Sulphur", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Quara Scale",
            "category": "Protective / Ice Protection",
            "tiers": [
                {
                    "name": "Basic Quara Scale",
                    "effect": "3% protection",
                    "sources": [{"name": "Winter Wolf Fur", "qty": 25}],
                },
                {
                    "name": "Intricate Quara Scale",
                    "effect": "8% protection",
                    "sources": [
                        {"name": "Winter Wolf Fur", "qty": 25},
                        {"name": "Thick Fur", "qty": 15},
                    ],
                },
                {
                    "name": "Powerful Quara Scale",
                    "effect": "15% protection",
                    "sources": [
                        {"name": "Winter Wolf Fur", "qty": 25},
                        {"name": "Thick Fur", "qty": 15},
                        {"name": "Deepling Warts", "qty": 10},
                    ],
                },
            ],
        },
        {
            "type": "Cloud Fabric",
            "category": "Protective / Energy Protection",
            "tiers": [
                {
                    "name": "Basic Cloud Fabric",
                    "effect": "3% protection",
                    "sources": [{"name": "Wyvern Talisman", "qty": 20}],
                },
                {
                    "name": "Intricate Cloud Fabric",
                    "effect": "8% protection",
                    "sources": [
                        {"name": "Wyvern Talisman", "qty": 20},
                        {"name": "Crawler Head Plating", "qty": 15},
                    ],
                },
                {
                    "name": "Powerful Cloud Fabric",
                    "effect": "15% protection",
                    "sources": [
                        {"name": "Wyvern Talisman", "qty": 20},
                        {"name": "Crawler Head Plating", "qty": 15},
                        {"name": "Wyrm Scale", "qty": 10},
                    ],
                },
            ],
        },
        {
            "type": "Demon Presence",
            "category": "Protective / Holy Protection",
            "tiers": [
                {
                    "name": "Basic Demon Presence",
                    "effect": "3% protection",
                    "sources": [{"name": "Cultish Robe", "qty": 25}],
                },
                {
                    "name": "Intricate Demon Presence",
                    "effect": "8% protection",
                    "sources": [
                        {"name": "Cultish Robe", "qty": 25},
                        {"name": "Cultish Mask", "qty": 25},
                    ],
                },
                {
                    "name": "Powerful Demon Presence",
                    "effect": "15% protection",
                    "sources": [
                        {"name": "Cultish Robe", "qty": 25},
                        {"name": "Cultish Mask", "qty": 25},
                        {"name": "Hellspawn Tail", "qty": 20},
                    ],
                },
            ],
        },
        {
            "type": "Vibrancy",
            "category": "Protective / Paralysis Deflection",
            "tiers": [
                {
                    "name": "Basic Vibrancy",
                    "effect": "15% chance",
                    "sources": [{"name": "Wereboar Hooves", "qty": 20}],
                },
                {
                    "name": "Intricate Vibrancy",
                    "effect": "25% chance",
                    "sources": [
                        {"name": "Wereboar Hooves", "qty": 20},
                        {"name": "Crystallized Anger", "qty": 15},
                    ],
                },
                {
                    "name": "Powerful Vibrancy",
                    "effect": "50% chance",
                    "sources": [
                        {"name": "Wereboar Hooves", "qty": 20},
                        {"name": "Crystallized Anger", "qty": 15},
                        {"name": "Quill", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Swiftness",
            "category": "Support / Walking Speed",
            "tiers": [
                {
                    "name": "Basic Swiftness",
                    "effect": "+10 speed",
                    "sources": [{"name": "Damselfly Wing", "qty": 15}],
                },
                {
                    "name": "Intricate Swiftness",
                    "effect": "+15 speed",
                    "sources": [
                        {"name": "Damselfly Wing", "qty": 15},
                        {"name": "Compass", "qty": 25},
                    ],
                },
                {
                    "name": "Powerful Swiftness",
                    "effect": "+30 speed",
                    "sources": [
                        {"name": "Damselfly Wing", "qty": 15},
                        {"name": "Compass", "qty": 25},
                        {"name": "Waspoid Wing", "qty": 20},
                    ],
                },
            ],
        },
        {
            "type": "Featherweight",
            "category": "Support / Capacity",
            "tiers": [
                {
                    "name": "Basic Featherweight",
                    "effect": "+3% cap",
                    "sources": [{"name": "Fairy Wing", "qty": 20}],
                },
                {
                    "name": "Intricate Featherweight",
                    "effect": "+8% cap",
                    "sources": [
                        {"name": "Fairy Wing", "qty": 20},
                        {"name": "Little Bowl of Myrrh", "qty": 10},
                    ],
                },
                {
                    "name": "Powerful Featherweight",
                    "effect": "+15% cap",
                    "sources": [
                        {"name": "Fairy Wing", "qty": 20},
                        {"name": "Little Bowl of Myrrh", "qty": 10},
                        {"name": "Goosebump Leather", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Epiphany",
            "category": "Skill Improving / Magic Level",
            "tiers": [
                {
                    "name": "Basic Epiphany",
                    "effect": "+1 ML",
                    "sources": [{"name": "Elvish Talisman", "qty": 25}],
                },
                {
                    "name": "Intricate Epiphany",
                    "effect": "+2 ML",
                    "sources": [
                        {"name": "Elvish Talisman", "qty": 25},
                        {"name": "Broken Shamanic Staff", "qty": 15},
                    ],
                },
                {
                    "name": "Powerful Epiphany",
                    "effect": "+4 ML",
                    "sources": [
                        {"name": "Elvish Talisman", "qty": 25},
                        {"name": "Broken Shamanic Staff", "qty": 15},
                        {"name": "Strand of Medusa Hair", "qty": 15},
                    ],
                },
            ],
        },
        {
            "type": "Punch",
            "category": "Skill Improving / Fist Fighting",
            "tiers": [
                {
                    "name": "Basic Punch",
                    "effect": "+1",
                    "sources": [{"name": "Tarantula Egg", "qty": 25}],
                },
                {
                    "name": "Intricate Punch",
                    "effect": "+2",
                    "sources": [
                        {"name": "Tarantula Egg", "qty": 25},
                        {"name": "Mantassin Tail", "qty": 20},
                    ],
                },
                {
                    "name": "Powerful Punch",
                    "effect": "+4",
                    "sources": [
                        {"name": "Tarantula Egg", "qty": 25},
                        {"name": "Mantassin Tail", "qty": 20},
                        {"name": "Gold-Brocaded Cloth", "qty": 15},
                    ],
                },
            ],
        },
        {
            "type": "Bash",
            "category": "Skill Improving / Club Fighting",
            "tiers": [
                {
                    "name": "Basic Bash",
                    "effect": "+1",
                    "sources": [{"name": "Cyclops Toe", "qty": 20}],
                },
                {
                    "name": "Intricate Bash",
                    "effect": "+2",
                    "sources": [
                        {"name": "Cyclops Toe", "qty": 20},
                        {"name": "Ogre Nose Ring", "qty": 15},
                    ],
                },
                {
                    "name": "Powerful Bash",
                    "effect": "+4",
                    "sources": [
                        {"name": "Cyclops Toe", "qty": 20},
                        {"name": "Ogre Nose Ring", "qty": 15},
                        {"name": "Warmaster's Wristguards", "qty": 10},
                    ],
                },
            ],
        },
        {
            "type": "Slash",
            "category": "Skill Improving / Sword Fighting",
            "tiers": [
                {
                    "name": "Basic Slash",
                    "effect": "+1",
                    "sources": [{"name": "Lion's Mane", "qty": 25}],
                },
                {
                    "name": "Intricate Slash",
                    "effect": "+2",
                    "sources": [
                        {"name": "Lion's Mane", "qty": 25},
                        {"name": "Mooh'tah Shell", "qty": 25},
                    ],
                },
                {
                    "name": "Powerful Slash",
                    "effect": "+4",
                    "sources": [
                        {"name": "Lion's Mane", "qty": 25},
                        {"name": "Mooh'tah Shell", "qty": 25},
                        {"name": "War Crystal", "qty": 5},
                    ],
                },
            ],
        },
        {
            "type": "Chop",
            "category": "Skill Improving / Axe Fighting",
            "tiers": [
                {
                    "name": "Basic Chop",
                    "effect": "+1",
                    "sources": [{"name": "Orc Tooth", "qty": 20}],
                },
                {
                    "name": "Intricate Chop",
                    "effect": "+2",
                    "sources": [
                        {"name": "Orc Tooth", "qty": 20},
                        {"name": "Battle Stone", "qty": 25},
                    ],
                },
                {
                    "name": "Powerful Chop",
                    "effect": "+4",
                    "sources": [
                        {"name": "Orc Tooth", "qty": 20},
                        {"name": "Battle Stone", "qty": 25},
                        {"name": "Moohtant Horn", "qty": 20},
                    ],
                },
            ],
        },
        {
            "type": "Precision",
            "category": "Skill Improving / Distance Fighting",
            "tiers": [
                {
                    "name": "Basic Precision",
                    "effect": "+1",
                    "sources": [{"name": "Elven Scouting Glass", "qty": 25}],
                },
                {
                    "name": "Intricate Precision",
                    "effect": "+2",
                    "sources": [
                        {"name": "Elven Scouting Glass", "qty": 25},
                        {"name": "Elven Hoof", "qty": 20},
                    ],
                },
                {
                    "name": "Powerful Precision",
                    "effect": "+4",
                    "sources": [
                        {"name": "Elven Scouting Glass", "qty": 25},
                        {"name": "Elven Hoof", "qty": 20},
                        {"name": "Metal Spike", "qty": 10},
                    ],
                },
            ],
        },
        {
            "type": "Blockade",
            "category": "Skill Improving / Shielding",
            "tiers": [
                {
                    "name": "Basic Blockade",
                    "effect": "+1",
                    "sources": [{"name": "Piece of Scarab Shell", "qty": 20}],
                },
                {
                    "name": "Intricate Blockade",
                    "effect": "+2",
                    "sources": [
                        {"name": "Piece of Scarab Shell", "qty": 20},
                        {"name": "Brimstone Shell", "qty": 25},
                    ],
                },
                {
                    "name": "Powerful Blockade",
                    "effect": "+4",
                    "sources": [
                        {"name": "Piece of Scarab Shell", "qty": 20},
                        {"name": "Brimstone Shell", "qty": 25},
                        {"name": "Frazzle Skin", "qty": 25},
                    ],
                },
            ],
        },
    ],
}
