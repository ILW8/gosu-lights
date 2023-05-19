import datetime
import io
import time
import warnings
import simpleobsws

from PIL import Image, UnidentifiedImageError
import numpy as np
import requests
from colorsys import rgb_to_hsv
import asyncio
import base64

PHILLIPS_USER = '3S14qYX-fdFjoOEwHlnvwhncIvsGzO2ux4NMJ55w'
LOOP_INTERVAL_SECONDS = 0.2
FORCE_UPDATE_THRESHOLD_SECONDS = 1.5


async def main():
    parameters = simpleobsws.IdentificationParameters()  # Create an IdentificationParameters object
    ws = simpleobsws.WebSocketClient(url='ws://ed-streaming-pc:4455',
                                     password='5zv3Wyek8UqLHbBO',
                                     identification_parameters=parameters)
    await ws.connect()
    await ws.wait_until_identified()

    last_loop = time.perf_counter()  # obs program image capture loop
    last_h, last_s, last_v = 0, 0, 0
    last_updated = time.perf_counter()  # actual update to lights
    while True:
        if (delta := time.perf_counter() - last_loop) < LOOP_INTERVAL_SECONDS:
            time.sleep(LOOP_INTERVAL_SECONDS - delta)
        last_loop = time.perf_counter()
        try:
            request_program_scene = simpleobsws.Request('GetCurrentProgramScene')
            program_scene = (await ws.call(request_program_scene)).responseData['currentProgramSceneName']

            request_image = simpleobsws.Request('GetSourceScreenshot', requestData={
                "sourceName": program_scene,
                "imageFormat": "jpg",
                "imageWidth": 800,
                "imageHeight": 450,
            })
            data = (await ws.call(request_image)).responseData['imageData']
            jpg_data = data.split(";base64,")[-1]
            jpg_decoded_data = io.BytesIO(base64.b64decode(jpg_data))
            i = Image.open(jpg_decoded_data).convert('RGBA')

            # noinspection PyTypeChecker
            np_img = np.asarray(i)
            if np_img.ndim < 3:
                print("np_img ndim < 3, skipping")
                continue
            chan_avg = np_img[:, :, :3].mean(axis=0).mean(axis=0)

            hue, saturation, value = rgb_to_hsv(*chan_avg)

            # scaling
            # value = value / 255 * 135 + 120  # map from 0-255 to 120-255
            value = value / 255 * 224 + 30  # map from 0-255 to 30-254
            # saturation = saturation * 0.6 + 0.4  # map from 0.0-1.0 to 0.4-1.0
            saturation = saturation * 0.85 + 0.15  # map from 0.0-1.0 to 0.15-1.0

            if abs(hue - last_h) / 65535. <= 0.08 and \
                    abs(saturation - last_s) / 254. < 0.08 and \
                    abs(value - last_v) / 254. < 0.08 and \
                    time.perf_counter() - last_updated < FORCE_UPDATE_THRESHOLD_SECONDS:
                continue
            last_h, last_s, last_v = hue, saturation, value
            last_updated = time.perf_counter()

            data = {"on": True, "sat": round(saturation * 255.), "bri": round(value), "hue": round(hue * 65535)}
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = requests.put(f"https://192.168.50.89/api/{PHILLIPS_USER}/groups/1/action",
                                   json=data,
                                   verify=False)
            print(f"[{datetime.datetime.utcnow().isoformat()}] Took {1000 * (time.perf_counter() - last_loop):.2f}ms: ",
                  res.status_code, res.json())

        except UnidentifiedImageError:
            continue
        except Exception as e:
            print("Caught exception at outermost level: " + e.__class__.__name__)
            continue


async def main_wrapper():
    try:
        await main()
    except KeyboardInterrupt:
        return

if __name__ == "__main__":
    asyncio.run(main_wrapper())
