import io
import time
import urllib.parse
import warnings

import tqdm as tqdm
from PIL import Image, UnidentifiedImageError
import numpy as np
import requests
from colorsys import hsv_to_rgb, rgb_to_hsv
import asyncio
import websockets
import json

import concurrent.futures

PHILLIPS_USER = '3S14qYX-fdFjoOEwHlnvwhncIvsGzO2ux4NMJ55w'


# 10: strip, 4: ceil, 5: ceil, 6: lamp, 7: lamp


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
                    # r, g, b = tuple(map(round, hsv_to_rgb(hue, saturation, value)))
                    # print(f"Scaled color: {(r, g, b)}")

                    data = {"on": True,
                            "sat": round(saturation * 255.),
                            "bri": round(value),
                            "hue": round(hue * 65535)}

                    start = time.perf_counter()
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        res = requests.put(f"https://192.168.50.89/api/{PHILLIPS_USER}/groups/1/action",
                                           json=data,
                                           verify=False)
                    print(f"Took {1000 * (time.perf_counter() - start):.2f}ms: ", res.status_code, res.json())

                    current_map = current_map_pending
                except UnidentifiedImageError:
                    continue
                except Exception as e:
                    print("Caught exception at outermost level: " + e.__class__.__name__)
                    continue

        except websockets.ConnectionClosed:
            continue


"""
const lightPut = async (data) => {
        return new Promise((resolve, reject) => {
                request({
                    method: 'PUT',
                    body: JSON.stringify(data.data),
                    url: `https://192.168.50.89/api/${PHILLIPS_USER}/lights/${data.device}/state`
                }, (error,response, body) => {
                        resolve(body);
                })
        })
}

const changeLight = async (light, color) => {
        new Promise(async (resolve, reject)=>{

                setTimeout(async ()=>{
                        console.log(color);
                        let rgbColor = hexToRgb(color);
                        console.log(rgbColor);
                        if(globalFlags.night) {
                                rgbColor.r = rgbColor.r * 100 / 255;
                                rgbColor.g = rgbColor.g * 100 / 255;
                                rgbColor.b = rgbColor.b * 100 / 255;
                                console.log('Reduced colors cause night:',rgbColor);
                        }

                        let colorHSV = rgb2hsv(rgbColor.r,rgbColor.g,rgbColor.b);

                        const result = await lightPut({
                                data: {"on":true, "sat":colorHSV.s, "bri":colorHSV.v, "hue":colorHSV.h},
                                device: light
                        });
                        console.log(light, result);
                        if(result) {
                                console.log(`Changed the light #${light} color to H:${colorHSV.h} S:${colorHSV.s} V:${colorHSV.v}`);
                                resolve(`Changed the light #${light} color to H:${colorHSV.h} S:${colorHSV.s} V:${colorHSV.v}`);
                        }
                }, 500);

        })
}
"""

if __name__ == "__main__":
    asyncio.run(main())
