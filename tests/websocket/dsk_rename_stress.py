"""Stress test: rename and remove scenes listed in a keyer while obs-websocket fires the requests.

source_rename / source_remove run on the thread that renames or removes the scene (here obs-websocket's),
and used to change the keyer's Qt list from that thread.
Usage: python dsk_rename_stress.py
"""
import asyncio
import sys

from dsk_client import ObsClient

KEYER = "DSK Rename Stress"


async def main():
    obs = await ObsClient.connect()
    ok = True
    try:
        await obs.vendor("add_downstream_keyer", {"dsk_name": KEYER})
        await asyncio.sleep(0.5)
        for round_index in range(20):
            name = f"dsk-stress-{round_index}"
            await obs.request("CreateScene", {"sceneName": name})
            await obs.vendor("dsk_add_scene", {"dsk_name": KEYER, "scene": name})
            futures = [obs.send("SetSceneName", {"sceneName": name if i % 2 == 0 else name + "-b",
                                                 "newSceneName": name + "-b" if i % 2 == 0 else name})
                       for i in range(20)]
            await asyncio.wait_for(asyncio.gather(*futures), 10)
            await obs.request("RemoveScene", {"sceneName": name})
        version = await obs.request("GetVersion")
        print(f"OK     20 rounds of 20 renames and a removal; OBS still answers (OBS {version['responseData']['obsVersion']})")
    except Exception as error:
        ok = False
        print(f"FAILED {type(error).__name__}: {error}")
    finally:
        try:
            await obs.vendor("remove_downstream_keyer", {"dsk_name": KEYER})
        except Exception:
            pass
        await obs.close()
    return ok


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(main()) else 1)
