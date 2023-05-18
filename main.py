import io
import urllib.parse
import warnings

import tqdm as tqdm
from PIL import Image
import numpy as np
import requests
from colorsys import hsv_to_rgb, rgb_to_hsv
import asyncio
import websockets
import json


async def main():
    uri = "ws://localhost:24050/ws"
    async for websocket in websockets.connect(uri, ping_interval=None):
        current_map = "n/a"
        try:
            async for message in websocket:
                try:
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    try:
                        # print(data["menu"]["bm"]["path"]["full"])
                        if data["menu"]["bm"]["path"]["full"] + "|" + data["menu"]["bm"]["md5"] == current_map:
                            continue
                        # artist = data["menu"]["bm"]["metadata"]["artist"]
                        # title = data["menu"]["bm"]["metadata"]["title"]
                        filename = urllib.parse.quote(data["menu"]["bm"]["path"]["full"].replace("\\", "/"))
                        current_map_pending = data["menu"]["bm"]["path"]["full"] + "|" + data["menu"]["bm"]["md5"]
                        print(f"New map: {current_map} --> {current_map_pending}")
                    except KeyError:
                        continue
                    img_url = f"http://127.0.0.1:24050/Songs/{filename}"
                    print("Sending request to " + img_url)
                    resp = requests.get(img_url)
                    if resp.status_code == 404:
                        print("No bg file found, skipping...")
                        current_map = current_map_pending
                        continue
                    if resp.status_code != 200:
                        continue
                    img_buffer = io.BytesIO()
                    for chunk in tqdm.tqdm(resp, unit="B", unit_scale=True, unit_divisor=1024):
                        img_buffer.write(chunk)
                    i = Image.open(img_buffer).convert('RGBA')
                    # noinspection PyTypeChecker
                    np_img = np.asarray(i)
                    if np_img.ndim < 3:
                        print("np_img ndim < 3, skipping")
                        continue
                    chan_avg = np_img[:, :, :3].mean(axis=0).mean(axis=0)
                    print(f"Average color of map: {chan_avg}")

                    hue, saturation, value = rgb_to_hsv(*chan_avg)
                    value = value / 255 * 135 + 120  # map from 0-255 to 120-255
                    saturation = saturation * 0.6 + 0.4  # map from 0.0-1.0 to 0.4-1.0
                    r, g, b = tuple(map(round, hsv_to_rgb(hue, saturation, value)))
                    print(f"Scaled color: {(r, g, b)}")

                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        res = requests.post("https://bigblock:2060/turn/lights/color",
                                            data={"color": f"#{r:02X}{g:02X}{b:02X}"},
                                            verify=False)
                        if res.status_code in range(200, 300):
                            print("Successfully set lights color")
                        else:
                            print(f"Got status {res.status_code} while setting lights")
                    current_map = current_map_pending
                except Exception as e:
                    print("Caught exception at outermost level: " + e.__class__.__name__)
                    continue

        except websockets.ConnectionClosed:
            continue


if __name__ == "__main__":
    asyncio.run(main())
