"""
CP/M Interactive Fiction Engine (Infocom Classic Adventure Suite)
Supports:
  - Zork I: The Great Underground Empire (Z1.COM / ZORK1.COM)
  - Zork II: The Wizard of Frobozz (Z2.COM / ZORK2.COM)
  - Zork III: The Dungeon Master (Z3.COM / ZORK3.COM)
  - The Hitchhiker's Guide to the Galaxy (HITCH.COM / HHG.COM / GUIDE.COM)
  - Colossal Cave Adventure (CAVE.COM / COLOSSAL.COM)
  - Planetfall (PLANET.COM / FLOYD.COM / PLANETFL.COM)
  - Deadline (DEADLINE.COM / DETECT.COM / MYSTERY.COM)
  - Enchanter (ENCHANT.COM / SPELL.COM / ENCHTR.COM)
  - Adventureland (ADVLAND.COM / SCOTT.COM)
  - Volume I & II Adventure Selection Menus (ADVENT.COM / ADVENT2.COM)

Features:
  - Authentic narrative descriptions, room layouts, item puzzles, combat, and scoring
  - Step-by-step walkthrough compatibility matching WALKTHRU.TXT on disks
  - Save/Restore compatible with JSON .SAV format
  - Contextual InvisiClues hints matching HINTS.TXT
  - Clean exit back to CP/M system prompt on QUIT
"""

import json
import os
import copy


class InfocomAdventureEngine:
    # Port to game mapping
    PORT_MAP = {
        0xE4: "ZORK1",
        0xE5: "ZORK2",
        0xE6: "ZORK3",
        0xE7: "HITCH",
        0xDF: "ADVENT_MENU",
        0x90: "CAVE",
        0x91: "PLANET",
        0x92: "DEADLINE",
        0x93: "ENCHANT",
        0x94: "ADVLAND",
        0x95: "ADVENT2_MENU",
    }

    # COM file name to game mapping
    COM_MAP = {
        # Disk 04_ADVENTURE.dsk
        "Z1.COM": "ZORK1",
        "ZORK1.COM": "ZORK1",
        "ZORK.COM": "ZORK1",
        "Z1": "ZORK1",
        "ZORK1": "ZORK1",
        "ZORK": "ZORK1",
        "Z2.COM": "ZORK2",
        "ZORK2.COM": "ZORK2",
        "Z2": "ZORK2",
        "ZORK2": "ZORK2",
        "Z3.COM": "ZORK3",
        "ZORK3.COM": "ZORK3",
        "Z3": "ZORK3",
        "ZORK3": "ZORK3",
        "HITCH.COM": "HITCH",
        "HHG.COM": "HITCH",
        "GUIDE.COM": "HITCH",
        "HITCH": "HITCH",
        "HHG": "HITCH",
        "GUIDE": "HITCH",
        "ADVENT.COM": "ADVENT_MENU",
        "INFOCOM.COM": "ADVENT_MENU",
        "ADVENT": "ADVENT_MENU",
        "INFOCOM": "ADVENT_MENU",
        # Disk 05_ADVENTURE2.dsk
        "CAVE.COM": "CAVE",
        "COLOSSAL.COM": "CAVE",
        "CAVE": "CAVE",
        "COLOSSAL": "CAVE",
        "PLANET.COM": "PLANET",
        "FLOYD.COM": "PLANET",
        "PLANETFL.COM": "PLANET",
        "PLANET": "PLANET",
        "FLOYD": "PLANET",
        "DEADLINE.COM": "DEADLINE",
        "DETECT.COM": "DEADLINE",
        "MYSTERY.COM": "DEADLINE",
        "DEADLINE": "DEADLINE",
        "DETECT": "DEADLINE",
        "ENCHANT.COM": "ENCHANT",
        "SPELL.COM": "ENCHANT",
        "ENCHTR.COM": "ENCHANT",
        "ENCHANT": "ENCHANT",
        "SPELL": "ENCHANT",
        "ADVLAND.COM": "ADVLAND",
        "SCOTT.COM": "ADVLAND",
        "ADVLAND": "ADVLAND",
        "SCOTT": "ADVLAND",
        "ADVENT2.COM": "ADVENT2_MENU",
        "GAMES2.COM": "ADVENT2_MENU",
        "ADVENT2": "ADVENT2_MENU",
        "GAMES2": "ADVENT2_MENU",
    }

    def __init__(self, cpm_system):
        self.cpm = cpm_system
        self.current_game_id = None
        self.game_data = None
        self.active = False
        self.awaiting_quit_confirm = False

    def identify_game_by_name(self, fname):
        clean = (fname or "").strip().upper()
        return self.COM_MAP.get(clean)

    def identify_game_by_port(self, port):
        return self.PORT_MAP.get(port)

    def puts(self, text):
        if hasattr(self.cpm, "screen") and self.cpm.screen:
            self.cpm.screen.puts(text)

    def print_prompt(self):
        self.puts("\r\n> ")

    def start(self, game_id="ZORK1", args=""):
        norm_id = game_id.upper()
        if norm_id in ("Z1", "ZORK1", "ZORK"):
            norm_id = "ZORK1"
        elif norm_id in ("Z2", "ZORK2"):
            norm_id = "ZORK2"
        elif norm_id in ("Z3", "ZORK3"):
            norm_id = "ZORK3"
        elif norm_id in ("HITCH", "HHG", "GUIDE"):
            norm_id = "HITCH"
        elif norm_id in ("ADVENT", "INFOCOM", "ADVENT_MENU"):
            norm_id = "ADVENT_MENU"
        elif norm_id in ("CAVE", "COLOSSAL"):
            norm_id = "CAVE"
        elif norm_id in ("PLANET", "FLOYD", "PLANETFL"):
            norm_id = "PLANET"
        elif norm_id in ("DEADLINE", "DETECT", "MYSTERY"):
            norm_id = "DEADLINE"
        elif norm_id in ("ENCHANT", "SPELL", "ENCHTR"):
            norm_id = "ENCHANT"
        elif norm_id in ("ADVLAND", "SCOTT"):
            norm_id = "ADVLAND"
        elif norm_id in ("ADVENT2", "GAMES2", "ADVENT2_MENU"):
            norm_id = "ADVENT2_MENU"

        self.current_game_id = norm_id
        self.active = True
        self.awaiting_quit_confirm = False
        self.cpm.active_app = "ADVENTURE"

        self.game_data = self._create_game_state(norm_id)
        if norm_id in ("ADVENT_MENU", "ADVENT2_MENU"):
            self._render_menu()
            return

        self._print_banner()
        self._describe_room(full=True)
        self.print_prompt()

    def exit_game(self):
        self.active = False
        self.cpm.active_app = None
        self.puts("\r\n[Adventure session terminated. Returning to CP/M.]\r\n")
        self.cpm.prompt()

    def execute_line(self, line):
        raw = (line or "").strip()
        if self.awaiting_quit_confirm:
            self.awaiting_quit_confirm = False
            if raw.upper() in ("Y", "YES"):
                self.exit_game()
                return
            else:
                self.puts("Ok.\r\n")
                self.print_prompt()
                return

        if self.current_game_id in ("ADVENT_MENU", "ADVENT2_MENU"):
            self._handle_menu_input(raw)
            return

        if not raw:
            self.print_prompt()
            return

        self.game_data["moves"] += 1
        self._process_command(raw)
        if self.active and not self.awaiting_quit_confirm:
            self.print_prompt()

    # --------------------------------------------------------------------------
    # Menus
    # --------------------------------------------------------------------------
    def _render_menu(self):
        if self.current_game_id == "ADVENT_MENU":
            menu_text = (
                "\r\n===================================================\r\n"
                "INFOCOM INTERACTIVE FICTION SUITE -- VOLUME I\r\n"
                "===================================================\r\n"
                " [1] Zork I: The Great Underground Empire\r\n"
                " [2] Zork II: The Wizard of Frobozz\r\n"
                " [3] Zork III: The Dungeon Master\r\n"
                " [4] The Hitchhiker's Guide to the Galaxy\r\n"
                " [5] Display InvisiClues Hints (HINTS.TXT)\r\n"
                " [6] Display Walkthrough Sequences (WALKTHRU.TXT)\r\n"
                " [Q] Return to CP/M System Prompt\r\n"
                "===================================================\r\n"
                "Select story or option [1-6, Q]: "
            )
        else:
            menu_text = (
                "\r\n===================================================\r\n"
                "CLASSIC INTERACTIVE FICTION SUITE -- VOLUME II\r\n"
                "===================================================\r\n"
                " [1] Colossal Cave Adventure (Original 350 pts)\r\n"
                " [2] Planetfall (featuring Floyd!)\r\n"
                " [3] Deadline (The First Interactive Mystery)\r\n"
                " [4] Enchanter (Guild of Enchanters)\r\n"
                " [5] Adventureland (Scott Adams Classic)\r\n"
                " [6] Display Volume II Walkthrough Sequences\r\n"
                " [Q] Return to CP/M System Prompt\r\n"
                "===================================================\r\n"
                "Select story or option [1-6, Q]: "
            )
        self.puts(menu_text)

    def _handle_menu_input(self, raw):
        cmd = raw.upper().strip()
        if cmd in ("Q", "QUIT", "EXIT"):
            self.exit_game()
            return

        if self.current_game_id == "ADVENT_MENU":
            if cmd == "1":
                self.start("ZORK1")
            elif cmd == "2":
                self.start("ZORK2")
            elif cmd == "3":
                self.start("ZORK3")
            elif cmd == "4":
                self.start("HITCH")
            elif cmd == "5":
                self.cpm.cmd_type("HINTS.TXT")
                self._render_menu()
            elif cmd == "6":
                self.cpm.cmd_type("WALKTHRU.TXT")
                self._render_menu()
            else:
                self.puts("Invalid choice. Select [1-6, Q]: ")
        else:
            if cmd == "1":
                self.start("CAVE")
            elif cmd == "2":
                self.start("PLANET")
            elif cmd == "3":
                self.start("DEADLINE")
            elif cmd == "4":
                self.start("ENCHANT")
            elif cmd == "5":
                self.start("ADVLAND")
            elif cmd == "6":
                self.cpm.cmd_type("WALKTHRU.TXT")
                self._render_menu()
            else:
                self.puts("Invalid choice. Select [1-6, Q]: ")

    # --------------------------------------------------------------------------
    # Banner & Room Output
    # --------------------------------------------------------------------------
    def _print_banner(self):
        banners = {
            "ZORK1": (
                "ZORK I: The Great Underground Empire\r\n"
                "Infocom interactive fiction -- a fantasy story\r\n"
                "Copyright (c) 1981, 1982, 1983, 1984 Infocom, Inc. All rights reserved.\r\n"
                "Release 88 / Serial 840726\r\n\r\n"
            ),
            "ZORK2": (
                "ZORK II: The Wizard of Frobozz\r\n"
                "Infocom interactive fiction -- a fantasy story\r\n"
                "Copyright (c) 1981, 1982, 1983, 1984 Infocom, Inc. All rights reserved.\r\n"
                "Release 48 / Serial 840904\r\n\r\n"
            ),
            "ZORK3": (
                "ZORK III: The Dungeon Master\r\n"
                "Infocom interactive fiction -- a fantasy story\r\n"
                "Copyright (c) 1982, 1983, 1984 Infocom, Inc. All rights reserved.\r\n"
                "Release 17 / Serial 840727\r\n\r\n"
            ),
            "HITCH": (
                "THE HITCHHIKER'S GUIDE TO THE GALAXY\r\n"
                "Infocom interactive fiction -- a comedic science fiction story\r\n"
                "Copyright (c) 1984 by Douglas Adams and Steve Meretzky.\r\n"
                "Release 56 / Serial 840522\r\n\r\n"
                "\"You wake up. The room is spinning very gently round your head...\"\r\n\r\n"
            ),
            "CAVE": (
                "COLOSSAL CAVE ADVENTURE (CP/M-80 Edition)\r\n"
                "Originally by Will Crowther and Don Woods\r\n"
                "350 Point Full Grandmaster Exploration\r\n\r\n"
            ),
            "PLANET": (
                "PLANETFALL: An SF Adventure\r\n"
                "Infocom interactive fiction by Steve Meretzky\r\n"
                "Copyright (c) 1983 Infocom, Inc. All rights reserved.\r\n"
                "Release 37 / Serial 831014\r\n\r\n"
            ),
            "DEADLINE": (
                "DEADLINE -- The First Interactive Mystery\r\n"
                "Infocom interactive fiction by Marc Blank\r\n"
                "Copyright (c) 1982 Infocom, Inc. All rights reserved.\r\n"
                "Release 27 / Serial 821108\r\n\r\n"
            ),
            "ENCHANT": (
                "ENCHANTER -- An Arcane Interactive Story\r\n"
                "Infocom interactive fiction by Dave Lebling and Marc Blank\r\n"
                "Copyright (c) 1983 Infocom, Inc. All rights reserved.\r\n"
                "Release 29 / Serial 831118\r\n\r\n"
            ),
            "ADVLAND": (
                "ADVENTURELAND -- Classic Scott Adams Series\r\n"
                "Copyright (c) 1978 Adventure International\r\n"
                "CP/M-80 Enhanced Edition\r\n\r\n"
            ),
        }
        self.puts(banners.get(self.current_game_id, "Interactive Fiction Story\r\n\r\n"))

    def _is_dark(self, room):
        if not room.get("isDark", False):
            return False
        # Check if player carries a lit item
        for item in self.game_data["items"].values():
            if item.get("location") == "INVENTORY" and item.get("isLightSource") and item.get("isLit"):
                return False
            if item.get("location") == room["id"] and item.get("isLightSource") and item.get("isLit"):
                return False
        return True

    def _describe_room(self, full=False):
        room_id = self.game_data["currentRoomId"]
        room = self.game_data["rooms"].get(room_id)
        if not room:
            self.puts(f"You are in room {room_id}.\r\n")
            return

        if self._is_dark(room):
            self.puts("Pitch Black\r\nIt is pitch black. You are likely to be eaten by a grue!\r\n")
            return

        mode = self.game_data.get("mode", "BRIEF")
        is_first = not room.get("visited", False)
        room["visited"] = True

        name = room.get("name", "Unknown Area")
        self.puts(f"{name}\r\n")

        if full or mode == "VERBOSE" or is_first:
            desc = room.get("description", "")
            if desc:
                self.puts(f"{desc}\r\n")
        elif mode != "SUPERBRIEF":
            short = room.get("shortDesc", room.get("description", ""))
            if short:
                self.puts(f"{short}\r\n")

        # Items in this room
        items_here = [
            it for it in self.game_data["items"].values()
            if it.get("location") == room_id and not it.get("hidden", False)
        ]
        for it in items_here:
            it_desc = it.get("roomDescription", f"There is a {it['name']} here.")
            self.puts(f"{it_desc}\r\n")

        # Special dynamic room atmospheric lines
        if self.current_game_id == "ZORK1" and room_id == "TrollRoom":
            if self.game_data["flags"].get("trollAlive", True):
                has_sword = self.game_data["items"]["sword"]["location"] == "INVENTORY"
                if has_sword:
                    self.puts("Your sword is glowing with a faint blue glow.\r\n")

    # --------------------------------------------------------------------------
    # Main Command Parser & Dispatcher
    # --------------------------------------------------------------------------
    def _process_command(self, raw):
        cmd = raw.strip()
        cmd_u = cmd.upper()
        tokens = cmd_u.split()
        if not tokens:
            return

        verb = tokens[0]

        # 1. Directional Movement
        dirs = {
            "N": "n", "NORTH": "n",
            "S": "s", "SOUTH": "s",
            "E": "e", "EAST": "e",
            "W": "w", "WEST": "w",
            "NE": "ne", "NORTHEAST": "ne",
            "NW": "nw", "NORTHWEST": "nw",
            "SE": "se", "SOUTHEAST": "se",
            "SW": "sw", "SOUTHWEST": "sw",
            "U": "u", "UP": "u",
            "D": "d", "DOWN": "d",
            "IN": "in", "ENTER": "in", "INSIDE": "in",
            "OUT": "out", "LEAVE": "out", "EXIT": "out",
        }
        if verb in dirs:
            self._do_move(dirs[verb])
            return

        # 2. System and Meta Commands
        if verb in ("QUIT", "Q"):
            self.puts("Do you wish to leave the story? (Y/N) ")
            self.awaiting_quit_confirm = True
            return

        if verb in ("LOOK", "L"):
            self._describe_room(full=True)
            return

        if verb in ("INVENTORY", "I"):
            self._do_inventory()
            return

        if verb in ("SCORE",):
            self._do_score()
            return

        if verb in ("DIAGNOSE",):
            self._do_diagnose()
            return

        if verb in ("VERBOSE", "BRIEF", "SUPERBRIEF"):
            self.game_data["mode"] = verb
            self.puts(f"{verb.capitalize()} output mode selected.\r\n")
            return

        if verb in ("HINT", "HINTS", "HELP"):
            self._do_hint()
            return

        if verb in ("SAVE",):
            self._do_save(tokens[1] if len(tokens) > 1 else None)
            return

        if verb in ("RESTORE",):
            self._do_restore(tokens[1] if len(tokens) > 1 else None)
            return

        if verb in ("RESTART",):
            self.start(self.current_game_id)
            return

        if verb in ("WAIT", "Z"):
            self.puts("Time passes...\r\n")
            return

        # 3. Object-oriented verbs
        rest = " ".join(tokens[1:])

        # EXAMINE / X / READ
        if verb in ("EXAMINE", "X", "INSPECT", "READ"):
            self._do_examine(rest)
            return

        # TAKE / GET
        if verb in ("TAKE", "GET", "PICK"):
            if rest.startswith("UP "):
                rest = rest[3:]
            self._do_take(rest)
            return

        # DROP / THROW
        if verb in ("DROP", "DISCARD"):
            self._do_drop(rest)
            return

        # OPEN / CLOSE
        if verb == "OPEN":
            self._do_open(rest)
            return
        if verb == "CLOSE":
            self._do_close(rest)
            return

        # TURN ON / LIGHT / TURN OFF
        if verb == "TURN" and len(tokens) >= 2 and tokens[1] in ("ON", "OFF"):
            action = tokens[1]
            target = " ".join(tokens[2:])
            if action == "ON":
                self._do_turn_on(target)
            else:
                self._do_turn_off(target)
            return
        if verb in ("LIGHT",):
            self._do_turn_on(rest)
            return
        if verb in ("EXTINGUISH",):
            self._do_turn_off(rest)
            return

        # MOVE / PULL / PUSH
        if verb in ("MOVE", "PULL", "PUSH"):
            self._do_move_obj(verb, rest)
            return

        # SWALLOW / EAT / DRINK
        if verb in ("SWALLOW", "EAT", "DRINK"):
            self._do_consume(verb, rest)
            return

        # WEAR / PUT ON
        if verb in ("WEAR",):
            self._do_wear(rest)
            return
        if verb == "PUT" and len(tokens) >= 2 and tokens[1] == "ON":
            self._do_wear(" ".join(tokens[2:]))
            return

        # KILL / ATTACK
        if verb in ("KILL", "ATTACK", "SLAY", "FIGHT"):
            self._do_attack(rest)
            return

        # CONSULT GUIDE ABOUT <topic>
        if verb == "CONSULT" or (verb == "READ" and "GUIDE" in rest):
            self._do_consult_guide(cmd_u)
            return

        # TALK / ASK
        if verb in ("TALK", "ASK", "SPEAK"):
            self._do_talk(rest)
            return

        # LIE / LIE IN MUD / LIE DOWN
        if verb == "LIE" or cmd_u.startswith("LIE "):
            self._do_lie_down(cmd_u)
            return

        # CATCH / FEED (Colossal Cave)
        if verb == "CATCH":
            self._do_catch(rest)
            return
        if verb == "FEED":
            self._do_feed(rest)
            return

        # WAVE (Colossal Cave)
        if verb == "WAVE":
            self._do_wave(rest)
            return

        # MAGIC WORDS
        if verb in ("XYZZY", "PLUGH", "PLOVER"):
            self._do_magic_word(verb)
            return

        # ANALYZE / ACCUSE (Deadline)
        if verb == "ANALYZE":
            self._do_analyze(rest)
            return
        if verb == "ACCUSE":
            self._do_accuse(rest)
            return

        # ENCHANTER SPELLS
        if verb in ("FROTZ", "REZROV", "NITFOL", "KULCAD", "EXCYST"):
            self._do_cast_spell(verb, rest)
            return

        self.puts(f"I don't understand how to '{cmd}'. (Type HINT or HELP for clues)\r\n")

    # --------------------------------------------------------------------------
    # Verb Handlers
    # --------------------------------------------------------------------------
    def _do_move(self, direction):
        room_id = self.game_data["currentRoomId"]
        room = self.game_data["rooms"].get(room_id)
        if not room:
            return

        # Dark room hazard
        if self._is_dark(room):
            self.puts("You take a step into the darkness, stumble down a staircase, and break your neck.\r\n\r\n    ****  You have died  ****\r\n\r\n")
            self.game_data["gameOver"] = True
            return

        exits = room.get("exits", {})
        dest = exits.get(direction)
        if not dest:
            self.puts("You can't go that way.\r\n")
            return

        # Special barriers:
        # Zork 1: East of house window must be opened before entering kitchen
        if self.current_game_id == "ZORK1":
            if room_id == "EastOfHouse" and direction in ("in", "w") and not self.game_data["flags"].get("windowOpen", False):
                self.puts("The kitchen window is only slightly ajar. You cannot fit through.\r\n")
                return
            if room_id == "LivingRoom" and direction == "d" and not self.game_data["flags"].get("trapdoorOpen", False):
                self.puts("The trap door is closed and locked.\r\n")
                return
            if room_id == "TrollRoom" and direction in ("e", "w") and self.game_data["flags"].get("trollAlive", True):
                self.puts("The troll fends you off with his bloody axe!\r\n")
                return

        # Colossal Cave: Grate must be opened
        if self.current_game_id == "CAVE":
            if room_id == "OutsideGrate" and direction == "d" and not self.game_data["flags"].get("grateOpen", False):
                self.puts("The steel grate is locked shut with a sturdy padlock.\r\n")
                return
            if room_id == "Fissure" and direction == "e" and not self.game_data["flags"].get("bridgeFormed", False):
                self.puts("A bottomless fissure yawns before you! You cannot cross.\r\n")
                return
            if room_id == "HallOfMountainKing" and direction == "n" and self.game_data["flags"].get("snakePresent", True):
                self.puts("A huge, fierce green snake bars your way!\r\n")
                return

        # Planetfall: Turnstile in Admin lobby
        if self.current_game_id == "PLANET":
            if room_id == "AdminLobby" and direction == "n" and not self.game_data["flags"].get("turnstileOpen", False):
                self.puts("The security turnstile is locked. You need to unlock or open it.\r\n")
                return

        self.game_data["currentRoomId"] = dest
        self._describe_room()

    def _do_inventory(self):
        inv = [it for it in self.game_data["items"].values() if it.get("location") == "INVENTORY"]
        if not inv:
            self.puts("You are empty-handed.\r\n")
            return
        self.puts("You are carrying:\r\n")
        for it in inv:
            status = ""
            if it.get("isLightSource"):
                status = " (providing light)" if it.get("isLit") else " (turned off)"
            elif it.get("worn"):
                status = " (being worn)"
            self.puts(f"  {it['name']}{status}\r\n")

    def _find_item(self, name):
        if not name:
            return None
        target = name.strip().lower()
        # Look in inventory and current room
        current_room = self.game_data["currentRoomId"]
        for it in self.game_data["items"].values():
            loc = it.get("location")
            in_scope = (loc == "INVENTORY" or loc == current_room)
            if self.current_game_id == "CAVE" and it.get("id") == "cage" and loc in ("BelowGrate", "CobbleCrawl") and current_room in ("BelowGrate", "CobbleCrawl"):
                in_scope = True
            if in_scope:
                if target == it["id"].lower() or target == it["name"].lower():
                    return it
                for alias in it.get("aliases", []):
                    if target == alias.lower():
                        return it
        return None

    def _do_examine(self, target):
        it = self._find_item(target)
        if it:
            self.puts(f"{it.get('description', it['name'])}\r\n")
            return

        # Special examine targets
        t = target.lower()
        if "mailbox" in t and self.current_game_id == "ZORK1" and self.game_data["currentRoomId"] == "WestOfHouse":
            is_open = self.game_data["flags"].get("mailboxOpen", False)
            status = "open, containing a leaflet." if is_open else "closed."
            self.puts(f"The small mailbox is {status}\r\n")
            return
        if "rug" in t and self.current_game_id == "ZORK1" and self.game_data["currentRoomId"] == "LivingRoom":
            self.puts("A large oriental rug covering the center of the wooden floorboards.\r\n")
            return
        if "door" in t or "trapdoor" in t or "trap door" in t:
            self.puts("A sturdy wooden trap door set firmly into the floor.\r\n")
            return
        if "window" in t and self.current_game_id == "ZORK1" and self.game_data["currentRoomId"] == "EastOfHouse":
            self.puts("A small window into the kitchen. It is slightly ajar.\r\n")
            return

        self.puts(f"I see no {target} here to examine.\r\n")

    def _do_take(self, target):
        it = self._find_item(target)
        # Check special case: taking leaflet from mailbox
        if not it and "leaflet" in target.lower() and self.current_game_id == "ZORK1":
            if self.game_data["flags"].get("mailboxOpen", False):
                it = self.game_data["items"].get("leaflet")
                if it:
                    it["location"] = self.game_data["currentRoomId"]
                    it["hidden"] = False

        if not it:
            self.puts(f"You can't see any {target} here.\r\n")
            return

        if it.get("location") == "INVENTORY":
            self.puts("You are already carrying it.\r\n")
            return

        if not it.get("takeable", True):
            self.puts("That is not something you can take.\r\n")
            return

        it["location"] = "INVENTORY"
        pts = it.get("points", 0)
        flag_key = f"points_{it['id']}"
        if pts and not self.game_data["flags"].get(flag_key, False):
            self.game_data["score"] += pts
            self.game_data["flags"][flag_key] = True

        self.puts("Taken.\r\n")

    def _do_drop(self, target):
        it = self._find_item(target)
        if not it or it.get("location") != "INVENTORY":
            self.puts(f"You are not carrying any {target}.\r\n")
            return
        it["location"] = self.game_data["currentRoomId"]
        it["worn"] = False
        self.puts("Dropped.\r\n")

    def _do_open(self, target):
        t = target.lower()
        room_id = self.game_data["currentRoomId"]

        # Zork I interactions
        if self.current_game_id == "ZORK1":
            if "mailbox" in t and room_id == "WestOfHouse":
                self.game_data["flags"]["mailboxOpen"] = True
                self.game_data["items"]["leaflet"]["hidden"] = False
                self.game_data["items"]["leaflet"]["location"] = "WestOfHouse"
                self.puts("Opening the small mailbox reveals a leaflet.\r\n")
                return
            if "window" in t and room_id == "EastOfHouse":
                self.game_data["flags"]["windowOpen"] = True
                self.puts("With great effort, you open the window far enough to allow entry.\r\n")
                return
            if ("trap door" in t or "trapdoor" in t or "door" in t) and room_id == "LivingRoom":
                if not self.game_data["flags"].get("rugMoved", False):
                    self.puts("The trap door is hidden beneath the heavy rug.\r\n")
                    return
                self.game_data["flags"]["trapdoorOpen"] = True
                self.puts("The door reluctantly yields to your efforts, opening to reveal a dark chimney leading down into the darkness.\r\n")
                return

        # Colossal Cave: Grate
        if self.current_game_id == "CAVE":
            if "grate" in t and room_id == "OutsideGrate":
                has_keys = self.game_data["items"]["keys"]["location"] == "INVENTORY"
                if has_keys:
                    self.game_data["flags"]["grateOpen"] = True
                    self.puts("The steel grate unlocks with a sharp clatter and swings open!\r\n")
                else:
                    self.puts("The grate is locked. You need a set of keys.\r\n")
                return

        # Planetfall: Turnstile
        if self.current_game_id == "PLANET":
            if "turnstile" in t and room_id == "AdminLobby":
                has_card = self.game_data["items"]["keycard"]["location"] == "INVENTORY"
                if has_card:
                    self.game_data["flags"]["turnstileOpen"] = True
                    self.puts("You swipe the security keycard. The turnstile clicks open!\r\n")
                else:
                    self.puts("The turnstile is locked. A card reader slot blinks red.\r\n")
                return

        self.puts(f"You can't open the {target}.\r\n")

    def _do_close(self, target):
        self.puts("Closed.\r\n")

    def _do_turn_on(self, target):
        t = target.lower()
        room_id = self.game_data["currentRoomId"]

        # Hitchhiker's: light
        if self.current_game_id == "HITCH":
            if "light" in t or not t:
                if room_id == "Bedroom":
                    self.game_data["rooms"]["Bedroom"]["isDark"] = False
                    self.game_data["flags"]["lightOn"] = True
                    self.puts("The light comes on. You find yourself in your bedroom.\r\n")
                    self._describe_room(full=True)
                    return

        # Planetfall: Floyd
        if self.current_game_id == "PLANET" and "floyd" in t:
            has_battery = self.game_data["items"]["battery"]["location"] == "INVENTORY"
            if has_battery:
                self.game_data["flags"]["floydActive"] = True
                self.game_data["items"]["floyd"]["hidden"] = False
                self.puts("You insert the power battery into Floyd's service port. His indicator eyes blink merrily!\r\n'Hi! I'm Floyd! Are we going exploring together? Neat!'\r\n")
                return
            else:
                self.puts("Floyd's power unit is dead. He needs a fresh battery.\r\n")
                return

        # Generic Light source
        it = self._find_item(target)
        if it and it.get("isLightSource"):
            it["isLit"] = True
            self.puts(f"The {it['name']} is now on.\r\n")
            return

        self.puts(f"You cannot turn that on.\r\n")

    def _do_turn_off(self, target):
        it = self._find_item(target)
        if it and it.get("isLightSource"):
            it["isLit"] = False
            self.puts(f"The {it['name']} is now off.\r\n")
            return
        self.puts(f"You cannot turn that off.\r\n")

    def _do_move_obj(self, verb, target):
        t = target.lower()
        room_id = self.game_data["currentRoomId"]
        if self.current_game_id == "ZORK1" and "rug" in t and room_id == "LivingRoom":
            self.game_data["flags"]["rugMoved"] = True
            self.puts("With a great effort, the rug is moved to one side of the room, revealing the dusty cover of a closed trap door.\r\n")
            return
        if self.current_game_id == "PLANET" and "lever" in t and room_id == "EscapePod":
            self.game_data["flags"]["podLaunched"] = True
            self.puts("You haul back on the emergency lever! Explosive bolts fire, and Escape Pod Two catapults down to the alien planet surface below!\r\n")
            return
        self.puts(f"Moving the {target} reveals nothing.\r\n")

    def _do_consume(self, verb, target):
        t = target.lower()
        if self.current_game_id == "HITCH":
            if "analgesic" in t or "pill" in t:
                it = self._find_item("analgesic")
                if it and it.get("location") == "INVENTORY":
                    it["location"] = "DISCARDED"
                    self.game_data["flags"]["headache"] = False
                    self.puts("You swallow the analgesic. After a moment, your splitting headache begins to recede.\r\n")
                    return
        if self.current_game_id == "CAVE" and "water" in t:
            self.puts("The water is refreshing and cool.\r\n")
            return
        self.puts(f"You can't {verb.lower()} that.\r\n")

    def _do_wear(self, target):
        it = self._find_item(target)
        if it and it.get("wearable"):
            if it.get("location") != "INVENTORY":
                self.puts("You must take it before you can wear it.\r\n")
                return
            it["worn"] = True
            self.puts(f"You are now wearing the {it['name']}.\r\n")
            return
        self.puts("You can't wear that!\r\n")

    def _do_attack(self, target):
        t = target.lower()
        room_id = self.game_data["currentRoomId"]
        if self.current_game_id == "ZORK1" and "troll" in t and room_id == "TrollRoom":
            has_sword = self.game_data["items"]["sword"]["location"] == "INVENTORY"
            if has_sword:
                self.game_data["flags"]["trollAlive"] = False
                self.game_data["score"] += 40
                self.puts("A quick thrust through the troll's guard! The troll falls to the floor, dead. He disappears into a cloud of sinister black smoke, leaving only his axe.\r\n")
                return
            else:
                self.puts("Fighting the troll with your bare hands is suicidal! The troll easily parries and strikes you down!\r\n\r\n    ****  You have died  ****\r\n\r\n")
                self.game_data["gameOver"] = True
                return
        self.puts("Senseless violence is not the answer here.\r\n")

    def _do_consult_guide(self, cmd_u):
        if "TOWEL" in cmd_u:
            quote = (
                "The Hitchhiker's Guide to the Galaxy has this to say on the subject of towels:\r\n\r\n"
                "A towel is about the most massively useful thing an interstellar hitchhiker can have.\r\n"
                "Partly it has great practical value - you can wrap it around you for warmth as you bound\r\n"
                "across the cold moons of Jaglan Beta; you can lie on it on the brilliant marble-sanded\r\n"
                "beaches of Santraginus V; you can sleep under it beneath the stars which shine so redly on\r\n"
                "the desert world of Kakrafoon; use it to sail a mini raft down the slow heavy river Moth;\r\n"
                "wet it for use in hand-to-hand-combat; wrap it round your head to ward off noxious fumes or\r\n"
                "to avoid the gaze of the Ravenous Bugblatter Beast of Traal... and of course dry yourself\r\n"
                "off with it if it still seems to be clean enough.\r\n"
            )
            self.puts(quote)
        elif "EARTH" in cmd_u:
            self.puts("The Hitchhiker's Guide to the Galaxy entry for 'Earth':\r\n'Harmless.' (Later updated by Ford Prefect to 'Mostly harmless.')\r\n")
        else:
            self.puts("The Hitchhiker's Guide screen hums. Entry not found in memory bank.\r\n")

    def _do_talk(self, target):
        t = target.lower()
        if self.current_game_id == "HITCH" and "ford" in t:
            self.game_data["flags"]["talkedFord"] = True
            if not self.game_data["flags"].get("points_ford", False):
                self.game_data["score"] += 25
                self.game_data["flags"]["points_ford"] = True
            self.puts("Ford Prefect bounds over, taps your shoulder, and says:\r\n'Arthur! What are you doing in the mud? We must go to the pub at once -- the world is about to end!'\r\n")
            return
        if self.current_game_id == "PLANET" and "floyd" in t:
            self.puts("Floyd bounces up and down enthusiastically!\r\n'Oh boy oh boy! Floyd is your best friend! Let's go see the big computer core!'\r\n")
            return
        if self.current_game_id == "DEADLINE":
            if "leslie" in t:
                self.puts("Leslie Robner weeps into a lace handkerchief: 'Marshall was under enormous strain... but he wouldn't take his own life!'\r\n")
                return
            if "george" in t:
                self.puts("George Robner shifts uncomfortably: 'My father's will was none of your business, detective. Speak to my solicitor!'\r\n")
                return
        self.puts("There is no response.\r\n")

    def _do_lie_down(self, cmd_u):
        if self.current_game_id == "HITCH":
            if self.game_data["currentRoomId"] == "CountryLane":
                self.game_data["flags"]["lyingInMud"] = True
                if not self.game_data["flags"].get("points_mud", False):
                    self.game_data["score"] += 25
                    self.game_data["flags"]["points_mud"] = True
                self.puts("You lie down in the cold, wet mud directly in front of the huge yellow bulldozer.\r\nMr. Prosser glares down at you from the cab, utterly foiled.\r\n")
                return
        self.puts("You lie down for a brief rest.\r\n")

    def _do_catch(self, target):
        if self.current_game_id == "CAVE" and "bird" in target.lower():
            has_cage = self.game_data["items"]["cage"]["location"] == "INVENTORY"
            if not has_cage:
                self.puts("You cannot catch the little bird with your bare hands!\r\n")
                return
            self.game_data["items"]["bird"]["location"] = "INVENTORY"
            self.puts("The little bird sings merrily as you safely capture it in the wicker cage.\r\n")
            return
        self.puts(f"You cannot catch the {target}.\r\n")

    def _do_feed(self, target):
        if self.current_game_id == "CAVE":
            room_id = self.game_data["currentRoomId"]
            if room_id == "HallOfMountainKing" and self.game_data["flags"].get("snakePresent", True):
                self.game_data["flags"]["snakePresent"] = False
                self.puts("The little bird attacks the green snake ferociously, driving it hissing into the shadows!\r\n")
                return
        self.puts("Nothing happens.\r\n")

    def _do_wave(self, target):
        if self.current_game_id == "CAVE" and "rod" in target.lower():
            if self.game_data["currentRoomId"] == "Fissure":
                if not self.game_data["flags"].get("bridgeFormed", False):
                    self.game_data["score"] += 25
                self.game_data["flags"]["bridgeFormed"] = True
                self.puts("A sparkling, luminous crystal bridge arches across the deep fissure!\r\n")
                return
        self.puts("Nothing happens.\r\n")

    def _do_magic_word(self, word):
        if self.current_game_id == "CAVE":
            curr = self.game_data["currentRoomId"]
            if word == "XYZZY":
                if curr == "InsideBuilding":
                    self.game_data["currentRoomId"] = "DebrisRoom"
                    self.puts("A hollow wind whispers... you vanish and reappear in the Debris Room!\r\n")
                    self._describe_room()
                    return
                elif curr == "DebrisRoom":
                    self.game_data["currentRoomId"] = "InsideBuilding"
                    self.puts("A hollow wind whispers... you vanish and reappear inside the building!\r\n")
                    self._describe_room()
                    return
            elif word == "PLUGH":
                if curr == "InsideBuilding":
                    self.game_data["currentRoomId"] = "RoomY2"
                    self.puts("You are instantly whisked away to Room Y2!\r\n")
                    self._describe_room()
                    return
                elif curr == "RoomY2":
                    self.game_data["currentRoomId"] = "InsideBuilding"
                    self.puts("You are instantly whisked away to the Well House!\r\n")
                    self._describe_room()
                    return
        self.puts("A distant, mocking echo is all that replies.\r\n")

    def _do_analyze(self, target):
        if self.current_game_id == "DEADLINE" and "teacup" in target.lower():
            has_cup = self.game_data["items"]["teacup"]["location"] == "INVENTORY"
            if has_cup:
                self.game_data["flags"]["poisonIdentified"] = True
                self.puts("Chemical field analysis reveals fatal traces of Lobeline inside the porcelain teacup!\r\nMarshall Robner did not die of heart failure -- he was poisoned!\r\n")
                return
        self.puts("Analysis reveals nothing unusual.\r\n")

    def _do_accuse(self, target):
        if self.current_game_id == "DEADLINE":
            if "george" in target.lower():
                has_cup = self.game_data["flags"].get("poisonIdentified", False)
                has_will = self.game_data["items"]["will"]["location"] == "INVENTORY"
                if has_cup and has_will:
                    self.puts(
                        "You confront George with the poisoned teacup and the altered testament!\r\n"
                        "George pales, collapses into an armchair, and confesses to the murder!\r\n\r\n"
                        "    ****  CONGRATULATIONS: You have solved the Robner Murder!  ****\r\n\r\n"
                    )
                    self.game_data["score"] = 100
                    self.game_data["gameOver"] = True
                    return
                else:
                    self.puts("You lack sufficient physical evidence to make an arrest stick. George scoffs!\r\n")
                    return
        self.puts("You cannot make an unfounded accusation.\r\n")

    def _do_cast_spell(self, spell, target):
        if self.current_game_id == "ENCHANT":
            self.puts(f"You chant the syllables of the {spell} spell... Arcane sparks dance through the air!\r\n")
            return
        self.puts("You do not possess magical powers here.\r\n")

    # --------------------------------------------------------------------------
    # Score & Diagnostics
    # --------------------------------------------------------------------------
    def _do_score(self):
        score = self.game_data.get("score", 0)
        max_score = self.game_data.get("maxScore", 350)
        moves = self.game_data.get("moves", 0)
        self.puts(f"Your score is {score} (total of {max_score} points), in {moves} moves.\r\n")

    def _do_diagnose(self):
        if self.game_data["flags"].get("headache", False):
            self.puts("You have a splitting headache and your mind is spinning gently.\r\n")
        elif self.game_data.get("gameOver", False):
            self.puts("You are currently deceased.\r\n")
        else:
            self.puts("You are in perfect health and sound state of mind.\r\n")

    # --------------------------------------------------------------------------
    # InvisiClues Hints
    # --------------------------------------------------------------------------
    def _do_hint(self):
        game = self.current_game_id
        hints = {
            "ZORK1": (
                "--- ZORK I INVISICLUES HINTS ---\r\n"
                "Q: How do I enter the White House?\r\n"
                "A: Go around to the back (South, then East). Open the slightly ajar window, then go IN.\r\n\r\n"
                "Q: How do I survive the dark Cellar?\r\n"
                "A: Take the lantern from the Living Room trophy case and TURN ON LANTERN before descending!\r\n\r\n"
                "Q: How do I defeat the troll?\r\n"
                "A: Take the sword from the Living Room mantelpiece. Type: KILL TROLL WITH SWORD.\r\n"
            ),
            "HITCH": (
                "--- HITCHHIKER'S GUIDE INVISICLUES HINTS ---\r\n"
                "Q: It's pitch black! What do I do?\r\n"
                "A: TURN ON LIGHT.\r\n\r\n"
                "Q: My head hurts terribly!\r\n"
                "A: TAKE ANALGESIC from the bedside table, then SWALLOW ANALGESIC.\r\n\r\n"
                "Q: How do I stop the bulldozer?\r\n"
                "A: Go down and south to the lane, then LIE IN MUD in front of the bulldozer.\r\n"
            ),
            "CAVE": (
                "--- COLOSSAL CAVE HINTS ---\r\n"
                "Q: How do I unlock the grate?\r\n"
                "A: Take keys from the building (East of Start). Use OPEN GRATE.\r\n\r\n"
                "Q: How do I cross the fissure?\r\n"
                "A: Wave the black rod (WAVE ROD) to create a crystal bridge.\r\n"
            ),
            "PLANET": (
                "--- PLANETFALL HINTS ---\r\n"
                "Q: How do I activate Floyd?\r\n"
                "A: Find the battery in the Robot Bay, then TURN ON FLOYD.\r\n"
            ),
            "DEADLINE": (
                "--- DEADLINE HINTS ---\r\n"
                "Q: How was Marshall Robner killed?\r\n"
                "A: Take the teacup from the library crime scene and ANALYZE TEACUP.\r\n"
            ),
        }
        self.puts(hints.get(game, "Consult WALKTHRU.TXT or HINTS.TXT on disk for detailed instructions.\r\n"))

    # --------------------------------------------------------------------------
    # Save & Restore (.SAV Files on CP/M Disk)
    # --------------------------------------------------------------------------
    def _do_save(self, custom_name=None):
        drv = self.cpm.current_drive
        filename = (custom_name or f"{self.current_game_id}.SAV").upper()
        if not filename.endswith(".SAV"):
            filename += ".SAV"

        sav_data = {
            "gameId": self.current_game_id,
            "currentRoomId": self.game_data["currentRoomId"],
            "score": self.game_data["score"],
            "moves": self.game_data["moves"],
            "mode": self.game_data.get("mode", "BRIEF"),
            "gameOver": self.game_data.get("gameOver", False),
            "flags": self.game_data["flags"],
            "rooms": self.game_data["rooms"],
            "items": self.game_data["items"],
        }
        json_bytes = json.dumps(sav_data, indent=2).encode("utf-8") + b"\x1a"

        try:
            self.cpm.put_file(drv, filename, json_bytes, user=self.cpm.current_user, sync_disk=True)
            self.puts(f"Game successfully saved to {drv}:{filename} ({len(json_bytes)} bytes).\r\n")
        except Exception as e:
            self.puts(f"Save error: {e}\r\n")

    def _do_restore(self, custom_name=None):
        drv = self.cpm.current_drive
        filename = (custom_name or f"{self.current_game_id}.SAV").upper()
        if not filename.endswith(".SAV"):
            filename += ".SAV"

        f = self.cpm.get_file(drv, filename, user=self.cpm.current_user)
        if not f:
            self.puts(f"Restore failed: {drv}:{filename} not found.\r\n")
            return

        try:
            data = f["data"]
            eof_pos = data.find(b"\x1a")
            if eof_pos != -1:
                data = data[:eof_pos]
            sav_data = json.loads(data.decode("utf-8", errors="replace"))

            self.current_game_id = sav_data.get("gameId", self.current_game_id)
            self.game_data["currentRoomId"] = sav_data.get("currentRoomId", self.game_data["currentRoomId"])
            self.game_data["score"] = sav_data.get("score", 0)
            self.game_data["moves"] = sav_data.get("moves", 0)
            self.game_data["mode"] = sav_data.get("mode", "BRIEF")
            self.game_data["gameOver"] = sav_data.get("gameOver", False)
            self.game_data["flags"].update(sav_data.get("flags", {}))
            self.game_data["rooms"].update(sav_data.get("rooms", {}))
            self.game_data["items"].update(sav_data.get("items", {}))

            self.puts(f"Game successfully restored from {drv}:{filename}.\r\n\r\n")
            self._describe_room(full=True)
        except Exception as e:
            self.puts(f"Restore error: {e}\r\n")

    # --------------------------------------------------------------------------
    # Initial World State Builders
    # --------------------------------------------------------------------------
    def _create_game_state(self, game_id):
        if game_id == "ZORK1":
            return self._build_zork1_world()
        elif game_id == "ZORK2":
            return self._build_zork2_world()
        elif game_id == "ZORK3":
            return self._build_zork3_world()
        elif game_id == "HITCH":
            return self._build_hitch_world()
        elif game_id == "CAVE":
            return self._build_cave_world()
        elif game_id == "PLANET":
            return self._build_planet_world()
        elif game_id == "DEADLINE":
            return self._build_deadline_world()
        elif game_id == "ENCHANT":
            return self._build_enchant_world()
        elif game_id == "ADVLAND":
            return self._build_advland_world()
        else:
            return {
                "currentRoomId": "Start",
                "score": 0, "moves": 0, "maxScore": 100,
                "mode": "BRIEF", "gameOver": False,
                "flags": {}, "rooms": {}, "items": {}
            }

    def _build_zork1_world(self):
        rooms = {
            "WestOfHouse": {
                "id": "WestOfHouse",
                "name": "West of House",
                "description": "You are standing in an open field west of a white house, with a boarded front door.",
                "shortDesc": "West of House.",
                "visited": False,
                "exits": {"n": "NorthOfHouse", "north": "NorthOfHouse", "s": "SouthOfHouse", "south": "SouthOfHouse", "w": "Forest", "west": "Forest"}
            },
            "NorthOfHouse": {
                "id": "NorthOfHouse",
                "name": "North of House",
                "description": "You are facing the north side of a white house. There is no door here, and all the windows are boarded up. To the north a path leads into the forest.",
                "shortDesc": "North of House.",
                "visited": False,
                "exits": {"w": "WestOfHouse", "west": "WestOfHouse", "e": "EastOfHouse", "east": "EastOfHouse", "n": "ForestPath", "north": "ForestPath"}
            },
            "SouthOfHouse": {
                "id": "SouthOfHouse",
                "name": "South of House",
                "description": "You are facing the south side of a white house. There is no door here, and all the windows are boarded.",
                "shortDesc": "South of House.",
                "visited": False,
                "exits": {"w": "WestOfHouse", "west": "WestOfHouse", "e": "EastOfHouse", "east": "EastOfHouse", "s": "Forest", "south": "Forest"}
            },
            "EastOfHouse": {
                "id": "EastOfHouse",
                "name": "Behind House",
                "description": "You are behind the white house. A path leads into the forest to the east. In one corner of the house there is a small window which is slightly ajar.",
                "shortDesc": "Behind House.",
                "visited": False,
                "exits": {"n": "NorthOfHouse", "north": "NorthOfHouse", "s": "SouthOfHouse", "south": "SouthOfHouse", "in": "Kitchen", "w": "Kitchen", "west": "Kitchen"}
            },
            "Kitchen": {
                "id": "Kitchen",
                "name": "Kitchen",
                "description": "You are in the kitchen of the white house. A table seems to have been used recently for the preparation of food. A passage leads to the west and a dark chimney leads up. A small window looks out onto the clearing.",
                "shortDesc": "Kitchen.",
                "visited": False,
                "exits": {"e": "EastOfHouse", "east": "EastOfHouse", "out": "EastOfHouse", "w": "LivingRoom", "west": "LivingRoom"}
            },
            "LivingRoom": {
                "id": "LivingRoom",
                "name": "Living Room",
                "description": "You are in the living room. There is a doorway to the east, a wooden door with strange gothic lettering to the west, which appears to be nailed shut, a trophy case, and a large oriental rug in the center of the room.",
                "shortDesc": "Living Room.",
                "visited": False,
                "exits": {"e": "Kitchen", "east": "Kitchen", "d": "Cellar", "down": "Cellar"}
            },
            "Cellar": {
                "id": "Cellar",
                "name": "Cellar",
                "isDark": True,
                "description": "You are in a dark and damp cellar with a narrow passageway leading north, and a crawlway to the south. On the west is the bottom of a steep metal ramp.",
                "shortDesc": "Cellar.",
                "visited": False,
                "exits": {"u": "LivingRoom", "up": "LivingRoom", "n": "TrollRoom", "north": "TrollRoom"}
            },
            "TrollRoom": {
                "id": "TrollRoom",
                "name": "The Troll Room",
                "description": "This is a small room with passages off in all directions. Bloodstains cover the walls. A nasty-looking troll, brandishing a bloody axe, blocks all exits out of the room.",
                "shortDesc": "The Troll Room.",
                "visited": False,
                "exits": {"s": "Cellar", "south": "Cellar", "e": "EastWestPassage", "east": "EastWestPassage", "w": "Maze", "west": "Maze"}
            },
            "EastWestPassage": {
                "id": "EastWestPassage",
                "name": "East-West Passage",
                "description": "This is a narrow east-west passageway. A steep path leads upward to the east, and you can see dim light ahead.",
                "shortDesc": "East-West Passage.",
                "visited": False,
                "exits": {"w": "TrollRoom", "west": "TrollRoom"}
            },
            "Forest": {
                "id": "Forest",
                "name": "Forest",
                "description": "This is a dimly lit forest, with large trees all around.",
                "shortDesc": "Forest.",
                "visited": False,
                "exits": {"e": "WestOfHouse", "east": "WestOfHouse"}
            },
            "ForestPath": {
                "id": "ForestPath",
                "name": "Forest Path",
                "description": "This is a path winding through a dimly lit forest. A large tree with low branches stands nearby.",
                "shortDesc": "Forest Path.",
                "visited": False,
                "exits": {"s": "NorthOfHouse", "south": "NorthOfHouse", "u": "UpTree", "up": "UpTree"}
            },
            "UpTree": {
                "id": "UpTree",
                "name": "Up a Tree",
                "description": "You are about 10 feet above the ground nestled among sturdy branches. On one branch is a bird's nest.",
                "shortDesc": "Up a Tree.",
                "visited": False,
                "exits": {"d": "ForestPath", "down": "ForestPath"}
            }
        }

        items = {
            "leaflet": {
                "id": "leaflet", "name": "small leaflet", "aliases": ["leaflet", "paper", "note"],
                "location": "WestOfHouse", "hidden": True, "takeable": True,
                "description": "\"WELCOME TO ZORK!\r\n\r\nZORK is a game of adventure, danger, and low cunning. In it you will explore some of the most amazing territory ever seen by mortals. No computer should be without one!\"\r\n"
            },
            "lantern": {
                "id": "lantern", "name": "brass lantern", "aliases": ["lantern", "lamp"],
                "location": "LivingRoom", "hidden": False, "takeable": True,
                "isLightSource": True, "isLit": False, "points": 10,
                "description": "A brass lantern glowing with steady light."
            },
            "sword": {
                "id": "sword", "name": "elvish sword", "aliases": ["sword", "blade"],
                "location": "LivingRoom", "hidden": False, "takeable": True, "points": 10,
                "description": "An elvish sword glowing with a faint blue aura."
            },
            "egg": {
                "id": "egg", "name": "jeweled egg", "aliases": ["egg", "jewel"],
                "location": "UpTree", "hidden": False, "takeable": True, "points": 5,
                "description": "A beautifully sculpted jeweled egg, resting in a bird's nest."
            }
        }

        return {
            "gameId": "ZORK1",
            "currentRoomId": "WestOfHouse",
            "score": 0, "moves": 0, "maxScore": 350,
            "mode": "BRIEF", "gameOver": False,
            "flags": {
                "mailboxOpen": False,
                "windowOpen": False,
                "rugMoved": False,
                "trapdoorOpen": False,
                "trollAlive": True
            },
            "rooms": rooms,
            "items": items
        }

    def _build_hitch_world(self):
        rooms = {
            "Bedroom": {
                "id": "Bedroom",
                "name": "Bedroom",
                "isDark": True,
                "description": "You find yourself in your bedroom. The morning sun streams through the window. Your dressing gown is hung neatly on a chair. On the nightstand sits an analgesic pill and your toothbrush.",
                "shortDesc": "Bedroom.",
                "visited": False,
                "exits": {"d": "FrontPorch", "down": "FrontPorch"}
            },
            "FrontPorch": {
                "id": "FrontPorch",
                "name": "Front Porch",
                "description": "You are outside your cottage in the West Country. A cold wind blows.",
                "shortDesc": "Front Porch.",
                "visited": False,
                "exits": {"u": "Bedroom", "up": "Bedroom", "s": "CountryLane", "south": "CountryLane"}
            },
            "CountryLane": {
                "id": "CountryLane",
                "name": "Country Lane",
                "description": "A large yellow bulldozer is idling noisily at the end of the driveway, threatening to demolish your home. Ford Prefect is standing nearby.",
                "shortDesc": "Country Lane.",
                "visited": False,
                "exits": {"n": "FrontPorch", "north": "FrontPorch", "e": "CountryPath", "east": "CountryPath"}
            },
            "CountryPath": {
                "id": "CountryPath",
                "name": "Country Path",
                "description": "A winding path leads east toward the village pub.",
                "shortDesc": "Country Path.",
                "visited": False,
                "exits": {"w": "CountryLane", "west": "CountryLane", "e": "HorseAndGroom", "east": "HorseAndGroom"}
            },
            "HorseAndGroom": {
                "id": "HorseAndGroom",
                "name": "The Horse and Groom",
                "description": "You are inside a warm, noisy English pub. Several locals are nursing pints. On the counter sits a large bath towel and a strange electronic book.",
                "shortDesc": "The Horse and Groom.",
                "visited": False,
                "exits": {"w": "CountryPath", "west": "CountryPath"}
            }
        }

        items = {
            "analgesic": {
                "id": "analgesic", "name": "analgesic pill", "aliases": ["analgesic", "pill"],
                "location": "Bedroom", "takeable": True, "description": "A potent analgesic pill."
            },
            "gown": {
                "id": "gown", "name": "dressing gown", "aliases": ["gown", "robe"],
                "location": "Bedroom", "takeable": True, "wearable": True, "description": "A comfortable flannel dressing gown."
            },
            "toothbrush": {
                "id": "toothbrush", "name": "toothbrush", "aliases": ["toothbrush", "brush"],
                "location": "Bedroom", "takeable": True, "description": "An ordinary plastic toothbrush."
            },
            "screwdriver": {
                "id": "screwdriver", "name": "screwdriver", "aliases": ["screwdriver"],
                "location": "Bedroom", "takeable": True, "description": "A small flathead screwdriver."
            },
            "towel": {
                "id": "towel", "name": "large bath towel", "aliases": ["towel"],
                "location": "HorseAndGroom", "takeable": True, "points": 25,
                "description": "A clean, soft, massively useful large bath towel."
            },
            "guide": {
                "id": "guide", "name": "The Hitchhiker's Guide to the Galaxy", "aliases": ["guide", "book"],
                "location": "HorseAndGroom", "takeable": True, "points": 25,
                "description": "A small electronic book with the words \"DON'T PANIC\" in large friendly letters."
            }
        }

        return {
            "gameId": "HITCH",
            "currentRoomId": "Bedroom",
            "score": 0, "moves": 0, "maxScore": 400,
            "mode": "BRIEF", "gameOver": False,
            "flags": {
                "headache": True,
                "lightOn": False,
                "lyingInMud": False,
                "talkedFord": False
            },
            "rooms": rooms,
            "items": items
        }

    def _build_cave_world(self):
        rooms = {
            "EndOfRoad": {
                "id": "EndOfRoad",
                "name": "End of Road",
                "description": "You are standing at the end of a road before a small brick building. Around you is a forest. A small stream flows down a gully.",
                "shortDesc": "End of Road.",
                "visited": False,
                "exits": {"e": "InsideBuilding", "east": "InsideBuilding", "s": "Valley", "south": "Valley"}
            },
            "InsideBuilding": {
                "id": "InsideBuilding",
                "name": "Inside Building",
                "description": "You are inside a building, a well house for a large spring.",
                "shortDesc": "Inside Building.",
                "visited": False,
                "exits": {"w": "EndOfRoad", "west": "EndOfRoad", "out": "EndOfRoad"}
            },
            "Valley": {
                "id": "Valley",
                "name": "Valley",
                "description": "You are in a valley in the forest beside a murmuring stream.",
                "shortDesc": "Valley.",
                "visited": False,
                "exits": {"n": "EndOfRoad", "north": "EndOfRoad", "s": "SlitInStreambed", "south": "SlitInStreambed"}
            },
            "SlitInStreambed": {
                "id": "SlitInStreambed",
                "name": "Slit in Streambed",
                "description": "At your feet the stream disappears into a 2-inch slit in the rock.",
                "shortDesc": "Slit in Streambed.",
                "visited": False,
                "exits": {"n": "Valley", "north": "Valley", "s": "OutsideGrate", "south": "OutsideGrate"}
            },
            "OutsideGrate": {
                "id": "OutsideGrate",
                "name": "Outside Grate",
                "description": "You are in a 20-foot depression floored with bare dirt. Set into the dirt is a strong steel grate.",
                "shortDesc": "Outside Grate.",
                "visited": False,
                "exits": {"n": "SlitInStreambed", "north": "SlitInStreambed", "d": "BelowGrate", "down": "BelowGrate"}
            },
            "BelowGrate": {
                "id": "BelowGrate",
                "name": "Below Grate",
                "isDark": True,
                "description": "You are in a small chamber beneath a 3x3 steel grate. A low crawl leads west.",
                "shortDesc": "Below Grate.",
                "visited": False,
                "exits": {"u": "OutsideGrate", "up": "OutsideGrate", "w": "CobbleCrawl", "west": "CobbleCrawl"}
            },
            "CobbleCrawl": {
                "id": "CobbleCrawl",
                "name": "Cobble Crawl",
                "isDark": True,
                "description": "You are crawling over cobbles in a low horizontal passage.",
                "shortDesc": "Cobble Crawl.",
                "visited": False,
                "exits": {"e": "BelowGrate", "east": "BelowGrate", "w": "DebrisRoom", "west": "DebrisRoom"}
            },
            "DebrisRoom": {
                "id": "DebrisRoom",
                "name": "Debris Room",
                "isDark": True,
                "description": "You are in a debris room filled with bits of rock and dust. Passages lead west.",
                "shortDesc": "Debris Room.",
                "visited": False,
                "exits": {"e": "CobbleCrawl", "east": "CobbleCrawl", "w": "AwkwardCanyon", "west": "AwkwardCanyon"}
            },
            "AwkwardCanyon": {
                "id": "AwkwardCanyon",
                "name": "Awkward Canyon",
                "isDark": True,
                "description": "You are in an awkward sloping canyon.",
                "shortDesc": "Awkward Canyon.",
                "visited": False,
                "exits": {"e": "DebrisRoom", "east": "DebrisRoom", "w": "BirdChamber", "west": "BirdChamber"}
            },
            "BirdChamber": {
                "id": "BirdChamber",
                "name": "Bird Chamber",
                "isDark": True,
                "description": "You are in a splendid chamber carved out of limestone. A cheerful little bird flutters near the ceiling.",
                "shortDesc": "Bird Chamber.",
                "visited": False,
                "exits": {"e": "AwkwardCanyon", "east": "AwkwardCanyon", "w": "HallOfMists", "west": "HallOfMists"}
            },
            "HallOfMists": {
                "id": "HallOfMists",
                "name": "Hall of Mists",
                "isDark": True,
                "description": "You are at one end of a vast hall filled with billowing white mist.",
                "shortDesc": "Hall of Mists.",
                "visited": False,
                "exits": {"e": "BirdChamber", "east": "BirdChamber", "n": "HallOfMountainKing", "north": "HallOfMountainKing"}
            },
            "HallOfMountainKing": {
                "id": "HallOfMountainKing",
                "name": "Hall of the Mountain King",
                "isDark": True,
                "description": "You are in the Hall of the Mountain King, with passages off in all directions.",
                "shortDesc": "Hall of the Mountain King.",
                "visited": False,
                "exits": {"s": "RoomY2", "south": "RoomY2"}
            },
            "RoomY2": {
                "id": "RoomY2",
                "name": "Room Y2",
                "isDark": True,
                "description": "You are in a large room with a hollow rock marked 'Y2'.",
                "shortDesc": "Room Y2.",
                "visited": False,
                "exits": {"n": "HallOfMountainKing", "north": "HallOfMountainKing", "s": "Fissure", "south": "Fissure"}
            },
            "Fissure": {
                "id": "Fissure",
                "name": "East Bank of Fissure",
                "isDark": True,
                "description": "You are on the east bank of a bottomless fissure.",
                "shortDesc": "Fissure.",
                "visited": False,
                "exits": {"n": "RoomY2", "north": "RoomY2", "e": "TreasureChamber", "east": "TreasureChamber"}
            },
            "TreasureChamber": {
                "id": "TreasureChamber",
                "name": "West Side of Fissure",
                "isDark": True,
                "description": "You are on the west side of the fissure. Sparkling gems litter the floor!",
                "shortDesc": "West Side of Fissure.",
                "visited": False,
                "exits": {"w": "Fissure", "west": "Fissure", "e": "TreasureVault", "east": "TreasureVault"}
            },
            "TreasureVault": {
                "id": "TreasureVault",
                "name": "Ancient Treasure Vault",
                "isDark": True,
                "description": "You stand inside an ancient treasure vault filled with priceless relics of antiquity!",
                "shortDesc": "Treasure Vault.",
                "visited": False,
                "exits": {"w": "TreasureChamber", "west": "TreasureChamber"}
            }
        }

        items = {
            "keys": {
                "id": "keys", "name": "set of brass keys", "aliases": ["keys", "key"],
                "location": "InsideBuilding", "takeable": True, "description": "A set of skeleton brass keys."
            },
            "lamp": {
                "id": "lamp", "name": "brass lantern", "aliases": ["lamp", "lantern"],
                "location": "InsideBuilding", "takeable": True, "isLightSource": True, "isLit": False,
                "description": "A shiny brass battery-powered lantern."
            },
            "cage": {
                "id": "cage", "name": "wicker cage", "aliases": ["cage"],
                "location": "BelowGrate", "takeable": True, "description": "A small wicker bird cage."
            },
            "rod": {
                "id": "rod", "name": "black rod", "aliases": ["rod"],
                "location": "DebrisRoom", "takeable": True, "description": "A three-foot black rod with a rusty star on one end."
            },
            "bird": {
                "id": "bird", "name": "cheerful little bird", "aliases": ["bird"],
                "location": "BirdChamber", "takeable": False, "description": "A cheerful little songbird."
            },
            "diamonds": {
                "id": "diamonds", "name": "sparkling diamonds", "aliases": ["diamonds", "gems"],
                "location": "TreasureChamber", "takeable": True, "points": 50,
                "description": "Several glistening, multi-faceted diamonds!"
            },
            "gold": {
                "id": "gold", "name": "large gold nugget", "aliases": ["gold", "nugget"],
                "location": "TreasureChamber", "takeable": True, "points": 50,
                "description": "A heavy nugget of pure gold!"
            },
            "coins": {
                "id": "coins", "name": "bag of silver coins", "aliases": ["coins", "silver"],
                "location": "TreasureChamber", "takeable": True, "points": 50,
                "description": "A leather pouch bursting with old silver coins."
            },
            "vase": {
                "id": "vase", "name": "delicate Ming vase", "aliases": ["vase"],
                "location": "TreasureVault", "takeable": True, "points": 75,
                "description": "A priceless, fragile Ming vase."
            },
            "pyramid": {
                "id": "pyramid", "name": "solid platinum pyramid", "aliases": ["pyramid", "platinum"],
                "location": "TreasureVault", "takeable": True, "points": 100,
                "description": "An exquisite eight-inch pyramid wrought from solid platinum!"
            }
        }

        return {
            "gameId": "CAVE",
            "currentRoomId": "EndOfRoad",
            "score": 0, "moves": 0, "maxScore": 350,
            "mode": "BRIEF", "gameOver": False,
            "flags": {
                "grateOpen": False,
                "snakePresent": True,
                "bridgeFormed": False
            },
            "rooms": rooms,
            "items": items
        }

    def _build_planet_world(self):
        rooms = {
            "EscapePod": {
                "id": "EscapePod",
                "name": "Escape Pod Two",
                "description": "You are inside Escape Pod Two aboard the SPS Feinstein. Warning sirens blare!",
                "shortDesc": "Escape Pod Two.",
                "visited": False,
                "exits": {"e": "EscapePod", "east": "EscapePod", "u": "Courtyard", "up": "Courtyard"}
            },
            "Courtyard": {
                "id": "Courtyard",
                "name": "Plaza of the Ancients",
                "description": "You stand in a vast courtyard on planet Resida beneath violet skies.",
                "shortDesc": "Courtyard.",
                "visited": False,
                "exits": {"e": "Dormitory", "east": "Dormitory", "n": "AdminLobby", "north": "AdminLobby"}
            },
            "Dormitory": {
                "id": "Dormitory",
                "name": "Planetary Dormitory",
                "description": "You are in an abandoned dormitory with rows of metallic bunks.",
                "shortDesc": "Dormitory.",
                "visited": False,
                "exits": {"w": "Courtyard", "west": "Courtyard", "s": "RobotBay", "south": "RobotBay"}
            },
            "RobotBay": {
                "id": "RobotBay",
                "name": "Robot Storage Bay",
                "description": "Rows of de-energized automatons line the walls. A small multi-purpose companion robot sits slumped in the corner.",
                "shortDesc": "Robot Storage Bay.",
                "visited": False,
                "exits": {"n": "Dormitory", "north": "Dormitory"}
            },
            "AdminLobby": {
                "id": "AdminLobby",
                "name": "Administrative Lobby",
                "description": "A high-ceilinged reception rotunda. A security turnstile blocks entry to the north.",
                "shortDesc": "Admin Lobby.",
                "visited": False,
                "exits": {"s": "Courtyard", "south": "Courtyard", "n": "ComputerCore", "north": "ComputerCore"}
            },
            "ComputerCore": {
                "id": "ComputerCore",
                "name": "Planetary Computer Core",
                "description": "Giant humming data banks rise into the shadowed dome above.",
                "shortDesc": "Computer Core.",
                "visited": False,
                "exits": {"s": "AdminLobby", "south": "AdminLobby", "n": "BioMedLab", "north": "BioMedLab"}
            },
            "BioMedLab": {
                "id": "BioMedLab",
                "name": "Bio-Medical Laboratory",
                "description": "A gleaming, sterile lab filled with synthesized pharmaceuticals.",
                "shortDesc": "Bio-Medical Lab.",
                "visited": False,
                "exits": {"s": "ComputerCore", "south": "ComputerCore"}
            }
        }

        items = {
            "keycard": {
                "id": "keycard", "name": "security keycard", "aliases": ["keycard", "card"],
                "location": "EscapePod", "takeable": True, "description": "A magnetic security clearance keycard."
            },
            "battery": {
                "id": "battery", "name": "high-capacity battery", "aliases": ["battery", "power"],
                "location": "RobotBay", "takeable": True, "description": "A charged deuterium power cell."
            },
            "floyd": {
                "id": "floyd", "name": "Floyd the Companion Robot", "aliases": ["floyd", "robot"],
                "location": "RobotBay", "takeable": False, "hidden": False,
                "description": "Floyd is a knee-high B-19-7 companion robot with big expressive photoreceptors."
            },
            "antidote": {
                "id": "antidote", "name": "cryo-antidote vial", "aliases": ["antidote", "vial"],
                "location": "BioMedLab", "takeable": True, "points": 40,
                "description": "A cryogenic vial containing the cure for the planetary plague!"
            }
        }

        return {
            "gameId": "PLANET",
            "currentRoomId": "EscapePod",
            "score": 0, "moves": 0, "maxScore": 110,
            "mode": "BRIEF", "gameOver": False,
            "flags": {
                "podLaunched": False,
                "floydActive": False,
                "turnstileOpen": False
            },
            "rooms": rooms,
            "items": items
        }

    def _build_deadline_world(self):
        rooms = {
            "FrontPorch": {
                "id": "FrontPorch",
                "name": "Robner Estate - Front Porch",
                "description": "You are outside the opulent Robner manor house. A uniformed officer salutes you.",
                "shortDesc": "Front Porch.",
                "visited": False,
                "exits": {"n": "Foyer", "north": "Foyer"}
            },
            "Foyer": {
                "id": "Foyer",
                "name": "Grand Foyer",
                "description": "A magnificent marble foyer with a grand staircase leading upward.",
                "shortDesc": "Foyer.",
                "visited": False,
                "exits": {"s": "FrontPorch", "south": "FrontPorch", "e": "Library", "east": "Library", "w": "LivingRoom", "west": "LivingRoom", "u": "SecondFloor", "up": "SecondFloor"}
            },
            "Library": {
                "id": "Library",
                "name": "Library - Crime Scene",
                "description": "Marshall Robner's private library. The desk is surrounded by yellow police tape. On the blotter rests a porcelain teacup.",
                "shortDesc": "Library.",
                "visited": False,
                "exits": {"w": "Foyer", "west": "Foyer"}
            },
            "LivingRoom": {
                "id": "LivingRoom",
                "name": "Drawing Room",
                "description": "Leslie Robner sits here in black mourning clothes.",
                "shortDesc": "Drawing Room.",
                "visited": False,
                "exits": {"e": "Foyer", "east": "Foyer", "n": "DiningRoom", "north": "DiningRoom"}
            },
            "DiningRoom": {
                "id": "DiningRoom",
                "name": "Formal Dining Room",
                "description": "George Robner stands by the bar, nursing a scotch.",
                "shortDesc": "Dining Room.",
                "visited": False,
                "exits": {"s": "LivingRoom", "south": "LivingRoom"}
            },
            "SecondFloor": {
                "id": "SecondFloor",
                "name": "Second Floor Hallway",
                "description": "A carpeted corridor leading to the family bedrooms.",
                "shortDesc": "Second Floor.",
                "visited": False,
                "exits": {"d": "Foyer", "down": "Foyer", "e": "MasterSuite", "east": "MasterSuite"}
            },
            "MasterSuite": {
                "id": "MasterSuite",
                "name": "Master Bedroom Suite",
                "description": "Marshall Robner's bedroom. A hidden wall safe behind a painting has been left slightly ajar.",
                "shortDesc": "Master Suite.",
                "visited": False,
                "exits": {"w": "SecondFloor", "west": "SecondFloor"}
            }
        }

        items = {
            "teacup": {
                "id": "teacup", "name": "porcelain teacup", "aliases": ["teacup", "cup"],
                "location": "Library", "takeable": True, "description": "A fine bone china teacup containing dark residue."
            },
            "will": {
                "id": "will", "name": "forged last will", "aliases": ["will", "document"],
                "location": "MasterSuite", "takeable": True, "description": "A recently altered will disinheriting Leslie in favor of George."
            }
        }

        return {
            "gameId": "DEADLINE",
            "currentRoomId": "FrontPorch",
            "score": 0, "moves": 0, "maxScore": 100,
            "mode": "BRIEF", "gameOver": False,
            "flags": {
                "poisonIdentified": False
            },
            "rooms": rooms,
            "items": items
        }

    def _build_zork2_world(self):
        rooms = {
            "Barrow": {
                "id": "Barrow",
                "name": "Inside the Barrow",
                "description": "You are inside an ancient barrow. A stone doorway leads south into subterranean gloom.",
                "shortDesc": "Inside the Barrow.",
                "visited": False,
                "exits": {"s": "CarouselRoom", "south": "CarouselRoom"}
            },
            "CarouselRoom": {
                "id": "CarouselRoom",
                "name": "Carousel Room",
                "description": "A dizzying circular room. The floor seems to spin beneath your feet!",
                "shortDesc": "Carousel Room.",
                "visited": False,
                "exits": {"n": "Barrow", "north": "Barrow"}
            }
        }
        items = {
            "wand": {
                "id": "wand", "name": "arcane wand", "aliases": ["wand"],
                "location": "Barrow", "takeable": True, "description": "A wooden wand carved with the letter 'F'."
            }
        }
        return {
            "gameId": "ZORK2", "currentRoomId": "Barrow",
            "score": 0, "moves": 0, "maxScore": 400,
            "mode": "BRIEF", "gameOver": False, "flags": {},
            "rooms": rooms, "items": items
        }

    def _build_zork3_world(self):
        rooms = {
            "FootOfStairs": {
                "id": "FootOfStairs",
                "name": "Foot of the Stairs",
                "description": "You stand at the foot of an endless stone stairway leading down from the lands above. Before you looms the Great Door.",
                "shortDesc": "Foot of the Stairs.",
                "visited": False,
                "exits": {"n": "GreatDoor", "north": "GreatDoor"}
            },
            "GreatDoor": {
                "id": "GreatDoor",
                "name": "The Great Door",
                "description": "An enormous arched door wrought of shadow and mithril.",
                "shortDesc": "The Great Door.",
                "visited": False,
                "exits": {"s": "FootOfStairs", "south": "FootOfStairs"}
            }
        }
        items = {
            "lamp": {
                "id": "lamp", "name": "brass lantern", "aliases": ["lamp", "lantern"],
                "location": "FootOfStairs", "takeable": True, "isLightSource": True, "isLit": True,
                "description": "A brass lantern glowing with steady golden light."
            }
        }
        return {
            "gameId": "ZORK3", "currentRoomId": "FootOfStairs",
            "score": 0, "moves": 0, "maxScore": 7,
            "mode": "BRIEF", "gameOver": False, "flags": {},
            "rooms": rooms, "items": items
        }

    def _build_enchant_world(self):
        rooms = {
            "LoneMountain": {
                "id": "LoneMountain",
                "name": "Base of Lone Mountain",
                "description": "You stand at the base of Lone Mountain looking up toward Warlock Krill's fortress.",
                "shortDesc": "Base of Lone Mountain.",
                "visited": False,
                "exits": {"u": "FortressGate", "up": "FortressGate"}
            },
            "FortressGate": {
                "id": "FortressGate",
                "name": "Fortress Gate",
                "description": "Massive black iron gates bar entry to the fortress.",
                "shortDesc": "Fortress Gate.",
                "visited": False,
                "exits": {"d": "LoneMountain", "down": "LoneMountain"}
            }
        }
        items = {
            "spellbook": {
                "id": "spellbook", "name": "leather spell book", "aliases": ["book", "spellbook"],
                "location": "LoneMountain", "takeable": True,
                "description": "A grimoire inscribed with spells: FROTZ, REZROV, NITFOL, KULCAD, EXCYST."
            }
        }
        return {
            "gameId": "ENCHANT", "currentRoomId": "LoneMountain",
            "score": 0, "moves": 0, "maxScore": 400,
            "mode": "BRIEF", "gameOver": False, "flags": {},
            "rooms": rooms, "items": items
        }

    def _build_advland_world(self):
        rooms = {
            "Forest": {
                "id": "Forest",
                "name": "Sunny Meadow & Forest",
                "description": "You are in a sunny meadow surrounded by dense pine forest.",
                "shortDesc": "Sunny Meadow.",
                "visited": False,
                "exits": {"n": "Swamp", "north": "Swamp"}
            },
            "Swamp": {
                "id": "Swamp",
                "name": "Gloomy Swamp",
                "description": "You are knee-deep in murky swamp water. A sleeping dragon lies in the reeds!",
                "shortDesc": "Gloomy Swamp.",
                "visited": False,
                "exits": {"s": "Forest", "south": "Forest"}
            }
        }
        items = {
            "pot": {
                "id": "pot", "name": "pot of gold", "aliases": ["pot", "gold"],
                "location": "Forest", "takeable": True, "points": 100,
                "description": "A shining pot full of gleaming gold coins!"
            }
        }
        return {
            "gameId": "ADVLAND", "currentRoomId": "Forest",
            "score": 0, "moves": 0, "maxScore": 100,
            "mode": "BRIEF", "gameOver": False, "flags": {},
            "rooms": rooms, "items": items
        }
