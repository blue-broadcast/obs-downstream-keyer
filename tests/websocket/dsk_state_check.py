"""The keyer state read back matches what is on air after a websocket request.

Usage: python dsk_state_check.py <existing scene name>
Creates a keyer named "DSK Test", shows and hides the scene through
dsk_select_scene, checks get_downstream_keyer after each step, then removes it.
The scene appears on the OBS output for about two seconds.
"""
import asyncio
import sys

from dsk_client import ObsClient

results = []


def check(label, ok, detail=""):
    results.append(bool(ok))
    suffix = f"  {detail}" if detail and not ok else ""
    print(f"{'OK    ' if ok else 'FAILED'} {label}{suffix}")


async def scene_of(obs):
    keyer = await obs.vendor("get_downstream_keyer", {"dsk_name": "DSK Test"})
    return keyer.get("scene", "")


async def main(scene):
    obs = await ObsClient.connect()
    try:
        await obs.vendor("add_downstream_keyer", {"dsk_name": "DSK Test"})
        await obs.vendor("dsk_add_scene", {"dsk_name": "DSK Test", "scene": scene})
        await asyncio.sleep(0.5)

        await obs.vendor("dsk_select_scene", {"dsk_name": "DSK Test", "scene": scene})
        await asyncio.sleep(0.5)
        check("after showing, the read state names the scene on air", await scene_of(obs) == scene, await scene_of(obs))

        await obs.vendor("dsk_select_scene", {"dsk_name": "DSK Test", "scene": ""})
        await asyncio.sleep(0.5)
        check("after hiding, the read state is empty", await scene_of(obs) == "", await scene_of(obs))

        # Shown again after a hide: the case where the current row was cleared
        obs.events.clear()
        await obs.vendor("dsk_select_scene", {"dsk_name": "DSK Test", "scene": scene})
        await asyncio.sleep(0.5)
        check("showing again after a hide sends dsk_scene_changed", obs.events_of("dsk_scene_changed"), obs.events)
        check("showing again after a hide is read back", await scene_of(obs) == scene, await scene_of(obs))
    finally:
        try:
            await obs.vendor("dsk_select_scene", {"dsk_name": "DSK Test", "scene": ""})
            await obs.vendor("remove_downstream_keyer", {"dsk_name": "DSK Test"})
        except Exception:
            pass
        await obs.close()
    print(f"\n{results.count(True)}/{len(results)} checks passed")
    return all(results)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(main(sys.argv[1])) else 1)
