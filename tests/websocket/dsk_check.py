"""Functional check of the Downstream Keyer websocket API against a running OBS.

Usage: python dsk_check.py <existing scene name>
Creates a keyer named "DSK Test", asks the operator to rename it in OBS, then removes it.
"""
import asyncio
import sys

from dsk_client import ObsClient

results = []


def check(label, ok, detail=""):
    results.append(bool(ok))
    suffix = f"  {detail}" if detail and not ok else ""
    print(f"{'OK    ' if ok else 'FAILED'} {label}{suffix}")


async def main(scene):
    obs = await ObsClient.connect()
    try:
        version = await obs.vendor("get_version")
        check("get_version identifies the fork", version.get("fork") == "bluebroadcast", version)

        obs.events.clear()
        await obs.vendor("add_downstream_keyer", {"dsk_name": "DSK Test"})
        await asyncio.sleep(0.5)
        check("adding a keyer sends dsk_list_changed", obs.events_of("dsk_list_changed"), obs.events)

        keyer = await obs.vendor("get_downstream_keyer", {"dsk_name": "DSK Test"})
        check("hide_after is 0 on a new keyer", keyer.get("hide_after") == 0, keyer.get("hide_after"))

        obs.events.clear()
        added = await obs.vendor("dsk_add_scene", {"dsk_name": "DSK Test", "scene": scene})
        await asyncio.sleep(0.5)
        check("dsk_add_scene succeeds", added.get("success") is True, added)
        check("adding a scene sends dsk_list_changed", obs.events_of("dsk_list_changed"), obs.events)

        obs.events.clear()
        shown = await obs.vendor("dsk_select_scene", {"dsk_name": "DSK Test", "scene": scene})
        hidden = await obs.vendor("dsk_select_scene", {"dsk_name": "DSK Test", "scene": ""})
        await asyncio.sleep(0.5)
        check("show then hide succeed", shown.get("success") and hidden.get("success"), (shown, hidden))
        check("show and hide send two dsk_scene_changed", len(obs.events_of("dsk_scene_changed")) == 2, obs.events)

        print('\nIn OBS, rename the keyer "DSK Test" to "DSK Renamed"')
        print("(Downstream Keyer dock, gear button, Rename), then press Enter.")
        await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)
        renamed = await obs.vendor("dsk_select_scene", {"dsk_name": "DSK Renamed", "scene": scene})
        check("a renamed keyer answers to its new name", renamed.get("success") is True, renamed)
    finally:
        for name in ("DSK Renamed", "DSK Test"):
            try:
                await obs.vendor("dsk_select_scene", {"dsk_name": name, "scene": ""})
                await obs.vendor("remove_downstream_keyer", {"dsk_name": name})
            except Exception:
                pass
        await obs.close()
    print(f"\n{results.count(True)}/{len(results)} checks passed")
    return all(results)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(main(sys.argv[1])) else 1)
