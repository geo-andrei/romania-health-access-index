"""Command line entry point: `hai download|prepare|analyse|load|export|all`."""
import argparse

from . import analyse, download, export, load_postgis, prepare

STEPS = {
    "download": download.run,
    "prepare": prepare.run,
    "analyse": analyse.run,
    "load": load_postgis.run,
    "export": export.run,
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("step", choices=[*STEPS, "all"])
    args = p.parse_args()
    for name, fn in STEPS.items():
        if args.step in (name, "all"):
            print(f"== {name} ==")
            fn()


if __name__ == "__main__":
    main()
