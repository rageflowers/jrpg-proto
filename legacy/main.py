# main.py

from __future__ import annotations
from engine.story.state import StoryState
from game.world.world_map import create_world

def main():
    story = StoryState()
    world = create_world(story)

    print("JRPG-Proto — Triad Saga (Prototype Skeleton)")
    print("You begin at Velastra.\n")
    print(f"== {world.current.name} ==")
    print(world.current.description)

    while True:
        print("\n--- Main Menu ---")
        print("1) Look around")
        print("2) Move to another location")
        print("3) Show party status")
        print("4) Show story flags (debug)")
        print("5) Quit")

        choice = input("> ").strip()

        if choice == "1":
            print(f"\n== {world.current.name} ==")
            print(world.current.description)

        elif choice == "2":
            world.list_neighbors()
            dest = input("Enter location id: ").strip()
            world.move_to(dest)

        elif choice == "3":
            print("\n--- Party ---")
            for a in world.party:
                status = "KO" if not a.alive else ""
                print(f"{a.name:8} HP {a.hp:>3}/{a.stats.max_hp:<3} MP {a.mp:>2}/{a.stats.max_mp:<2} {status}")

        elif choice == "4":
            story.debug()

        elif choice == "5":
            print("Goodbye for now.")
            break

        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
