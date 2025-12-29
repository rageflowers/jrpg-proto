# jrpg_world.py

from dataclasses import dataclass
from typing import Dict, List, Callable

from engine.story.state import StoryState, StoryFlag
from legacy.entities.jrpg_entities import create_party, create_enemy_group
from legacy.combat.jrpg_battle import Battle
from engine.scenes.dialogue import play_scene


@dataclass
class Location:
    id: str
    name: str
    description: str
    neighbors: List[str]
    on_enter: Callable[[StoryState], None] = lambda s: None

class World:
    def __init__(self, story: StoryState):
        self.story = story
        self.locations: Dict[str, Location] = {}
        self.current_id: str = "velastra_gate"
        self.party = create_party()

    def add_location(self, loc: Location) -> None:
        self.locations[loc.id] = loc

    @property
    def current(self) -> Location:
        return self.locations[self.current_id]

    def move_to(self, loc_id: str) -> None:
        if loc_id not in self.current.neighbors:
            print("You can't go there yet.")
            return
        self.current_id = loc_id
        loc = self.current
        print(f"\n== {loc.name} ==")
        print(loc.description)
        loc.on_enter(self.story)

    def list_neighbors(self) -> None:
        print("\nYou can travel to:")
        for nid in self.current.neighbors:
            print(f" - {self.locations[nid].name} ({nid})")

# ---------- World Setup & Events ----------

def _velastra_training_event(story: StoryState, world: World) -> None:
    if not story.has(StoryFlag.TUTORIAL_BATTLE_WON):
        play_scene([
            ("Setia", "Back where it all started."),
            ("Nyra", "It feels disciplined. Heavy, but centered."),
            ("Kaira", "Tidy. Unsettling."),
            ("", "An Ash Wraith drifts from the far edge of the yard, testing your resolve."),
        ])
        enemies = create_enemy_group("tutorial")
        if Battle(world.party, enemies, rng_seed=1337).run():
            story.set(StoryFlag.TUTORIAL_BATTLE_WON)
            play_scene([
                ("", "The watching monks nod, whispers moving through the yard."),
                ("Setia", "They see we're serious."),
                ("Nyra", "One step closer."),
                ("Kaira", "Good. I'm itching for something bigger."),
            ])
        else:
            print("You fall in training... (for now).")

def _vaelaras_behemoth_event(story: StoryState, world: World) -> None:
    if not story.has(StoryFlag.TUTORIAL_BATTLE_WON):
        print("\nThe path hums with hostile Aether. You feel unprepared.")
        return

    if story.has(StoryFlag.VAELARAS_BEHEMOTH_DEFEATED):
        print("\nThe Obelisk of Vael'aras stands quiet. The echo of your battle remains.")
        return

    # Entry scene: distrust + tension lite
    play_scene([
        ("", "Shadows coil around the basalt obelisk. Hooded figures and skeletal sentinels watch your every step."),
        ("Kaira", "...Home."),
        ("Nyra", "They don't look thrilled to see us."),
        ("Setia", "We didn't come for a warm welcome."),
        ("", "A deep crack splits the air. The Obelisk runes flare sickly violet."),
        ("Setia", "Rift sign."),
        ("Kaira", "Of course it had to be now."),
        ("Nyra", "Ready."),
        ("", "A Nether Behemoth claws its way through the breach above the plaza."),
    ])

    enemies = create_enemy_group("behemoth_trial")
    if Battle(world.party, enemies, rng_seed=999).run():
        story.set(StoryFlag.VAELARAS_BEHEMOTH_DEFEATED)
        play_scene([
            ("", "The Behemoth collapses into ash and Aether."),
            ("Setia", "That should've earned us a conversation."),
            ("Nyra", "If this doesn't prove our intent, nothing will."),
            ("Kaira", "They saw. Whether they admit it or not."),
        ])
    else:
        print("The void swallows you. (Prototype note: try again.)")

def create_world(story: StoryState) -> World:
    w = World(story)

    # Velastra Gate
    w.add_location(Location(
        id="velastra_gate",
        name="Velastra Monastery Gate",
        description="Stone steps, banners of crimson, the disciplined heart of the monks.",
        neighbors=["velastra_yard"],
        on_enter=lambda s: s.set(StoryFlag.VELASTRA_INTRO_DONE),
    ))

    # Velastra Training Yard
    def yard_on_enter(s: StoryState, wref=w):
        _velastra_training_event(s, wref)

    w.add_location(Location(
        id="velastra_yard",
        name="Velastra Training Yard",
        description="You stand where Setia once honed her Aether fists.",
        neighbors=["velastra_gate", "world_crossroads"],
        on_enter=lambda s, wref=w: yard_on_enter(s, wref),
    ))

    # Crossroads toward other cities (placeholder)
    w.add_location(Location(
        id="world_crossroads",
        name="Ashen Crossroads",
        description="Paths stretch toward distant Aurethil and the shadowed Vael'aras.",
        neighbors=["velastra_yard", "vaelaras_obelisk"],
        on_enter=lambda s: None,
    ))


    # Vael'aras Obelisk (prototype of their arc)
    def vael_on_enter(s: StoryState, wref=w):
        _vaelaras_behemoth_event(s, wref)

    w.add_location(Location(
        id="vaelaras_obelisk",
        name="Vael'aras Obelisk",
        description="The shadowed spire hums with restrained power.",
        neighbors=["world_crossroads"],
        on_enter=lambda s, wref=w: vael_on_enter(s, wref),
    ))

    return w
