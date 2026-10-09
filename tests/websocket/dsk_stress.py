"""Stress test: two clients fire 100 Downstream Keyer requests each without waiting.

Before the UI-thread fix, a burst like this crashed OBS (2026-10-09, OBS 32.2.2).
Usage: python dsk_stress.py <scene A> <scene B>
Both scenes are added to a temporary keyer "DSK Stress", which is removed at the end.
"""
import asyncio
import sys

from dsk_client import ObsClient

KEYER = "DSK Stress"


async def burst(obs, scene_a, scene_b, count):
    futures = []
    for i in range(count // 2):
        futures.append(obs.send_vendor("dsk_select_scene", {"dsk_name": KEYER, "scene": scene_a if i % 2 == 0 else ""}))
        futures.append(obs.send_vendor("dsk_add_scene" if i % 2 == 0 else "dsk_remove_scene",
                                       {"dsk_name": KEYER, "scene": scene_b}))
    responses = await asyncio.wait_for(asyncio.gather(*futures), 10)
    return sum(1 for r in responses if r["requestStatus"]["result"])


async def main(scene_a, scene_b):
    setup = await ObsClient.connect()
    await setup.vendor("add_downstream_keyer", {"dsk_name": KEYER})
    await asyncio.sleep(0.5)
    await setup.vendor("dsk_add_scene", {"dsk_name": KEYER, "scene": scene_a})
    clients = [await ObsClient.connect(), await ObsClient.connect()]
    ok = True
    try:
        answered = await asyncio.gather(*(burst(c, scene_a, scene_b, 100) for c in clients))
        print(f"OK     all 200 responses received ({answered[0]} + {answered[1]} accepted by obs-websocket)")
        version = await setup.request("GetVersion")
        print(f"OK     OBS still answers (OBS {version['responseData']['obsVersion']})")
    except Exception as error:
        ok = False
        print(f"FAILED {type(error).__name__}: {error}")
    finally:
        for client in clients:
            await client.close()
        try:
            await setup.vendor("dsk_select_scene", {"dsk_name": KEYER, "scene": ""})
            await setup.vendor("remove_downstream_keyer", {"dsk_name": KEYER})
        except Exception:
            pass
        await setup.close()
    return ok


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(main(sys.argv[1], sys.argv[2])) else 1)
