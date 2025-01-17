###############################################################################
# PrOMMiS was produced under the DOE Process Optimization and Modeling
# for Minerals Sustainability (“PrOMMiS”) initiative, and is
# Copyright © 2024-2025 by the software owners: The Regents of the
# University of California, through Lawrence Berkeley National
# Laboratory, National Technology & Engineering Solutions of Sandia, LLC,
# Carnegie Mellon University, West Virginia University Research
# Corporation, University of Notre Dame, and Georgia Institute of
# Technology. All rights reserved.
###############################################################################
"""
Generate Excalidraw input from the rendered SVG from another
drawing program (currently only tested with D2, but in theory
can work with Mermaid output with minimal changes).

This is an experimental functionality, not yet ready for
the general public to try out.
"""

from __future__ import annotations

import argparse
from collections import namedtuple
from hashlib import sha1
from io import IOBase
import json
import logging
import random
import re
import sys
import time
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

from pydantic import BaseModel

_log = logging.getLogger(__name__)


class AppState(BaseModel):
    gridSize: int
    gridStep: int
    gridModeEnabled: bool
    viewBackgroundColor: str


class Model(BaseModel):
    type: str
    version: int
    source: str
    elements: List[Dict]
    appState: AppState
    files: Dict[str, Any]


class Diagram:
    def __init__(self, model: Model):
        self._m = model

    def write(self, outfile: IOBase, **dump_kw):
        data = self._m.model_dump()
        json.dump(data, outfile, **dump_kw)

    @classmethod
    def from_svg(cls, infile: IOBase) -> Diagram:
        tree = ET.parse(infile)
        root = tree.getroot()
        svg_ns = "{http://www.w3.org/2000/svg}"
        svg = root.find(svg_ns + "svg")
        if svg is None:
            raise ValueError("Cannot find <svg> tag")

        model = Model(
            type="excalidraw",
            version=2,
            source="idaes",
            elements=[],
            appState={
                "gridSize": 20,
                "gridStep": 5,
                "gridModeEnabled": False,
                "viewBackgroundColor": "#ffffff",
            },
            files={},
        )
        svg_xc_map = {}
        shape_bounds = {}
        shape_elt_map = {}
        Bounds = namedtuple("Bounds", "x y width height")
        # Main loop
        for item in svg:
            # <g id="Unit_B">
            # <g class="shape" >
            # <rect x="286.000000" y="120.000000" width="132.000000"
            # height="66.000000" stroke="#0D32B2" fill="#F7F8FE"
            # class=" stroke-B1 fill-B6" style="stroke-width:2;" />
            # OR
            # <image href="data:image/svg+xml;base64,PD..."
            # x="228.000000" y="166.000000" width="128.000000" height="128.000000" stroke="#0D32B2"
            # fill="#FFFFFF" class=" stroke-B1 fill-N7" style="stroke-width:2;" />
            # </g>
            # <text x="352.000000" y="158.500000" fill="#0A0F25" class="text-bold fill-N1"
            # style="text-anchor:middle;font-size:16px">leach_mixer</text></g>
            g_tag = svg_ns + "g"
            if item.tag == g_tag:
                item_id = item.get("id")
                xc_id = cls._element_id()
                svg_xc_map[item_id] = xc_id
                # Find node and text
                g_rect, g_line, g_text, g_image = None, None, None, None
                for subitem in item:
                    if subitem.tag == g_tag and subitem.get("class", "") == "shape":
                        for elt in subitem:
                            if elt.tag == svg_ns + "rect":
                                g_rect = elt
                                break
                            if elt.tag == svg_ns + "image":
                                g_image = elt
                                break
                        if g_rect is None and g_image is None:
                            raise ValueError(
                                "shape element did not contain <rect> or <image>"
                            )
                    elif subitem.tag == svg_ns + "text":
                        g_text = subitem
                    elif subitem.tag == svg_ns + "path":
                        g_line = subitem
                rect_elt, text_elt, line_elt, image_elt = None, None, None, None
                now = int(time.time())
                if g_rect is not None:
                    rect_id = xc_id
                    bounds = Bounds(
                        *[
                            int(float(g_rect.get(c)))
                            for c in ("x", "y", "width", "height")
                        ]
                    )
                    rect_elt = {
                        "id": rect_id,
                        "type": "rectangle",
                        "x": bounds.x,
                        "y": bounds.y,
                        "width": bounds.width,
                        "height": bounds.height,
                        "angle": 0,
                        "strokeColor": "#000000",
                        "backgroundColor": "transparent",
                        "fillStyle": "solid",
                        "strokeWidth": 2,
                        "strokeStyle": "solid",
                        "roughness": 1,
                        "opacity": 100,
                        "roundness": {"type": 3},
                        "isDeleted": False,
                        "updated": now,
                        "locked": False,
                        "points": [],
                        "originalText": None,
                        "autoResize": True,
                        "lineHeight": 1.25,
                        "groupIds": [],
                        "frameId": None,
                        "link": None,
                        "boundElements": [],
                    }
                    shape_bounds[rect_id] = bounds
                    shape_elt_map[rect_id] = rect_elt
                if g_image is not None:
                    image_id = xc_id
                    bounds = Bounds(
                        *[
                            int(float(g_image.get(c)))
                            for c in ("x", "y", "width", "height")
                        ]
                    )
                    image_data = g_image.get("href")
                    image_file_id = cls._image_id(image_data)
                    image_file_elt = {
                        "mimeType": "image/svg+xml",
                        "id": image_file_id,
                        "dataURL": image_data,
                        "created": now,
                        "lastRetrieved": now,
                    }
                    image_elt = {
                        "id": image_id,
                        "type": "image",
                        "x": bounds.x,
                        "y": bounds.y,
                        "width": bounds.width,
                        "height": bounds.height,
                        "angle": 0,
                        "strokeColor": "#000000",
                        "backgroundColor": "transparent",
                        "fillStyle": "solid",
                        "strokeWidth": 2,
                        "strokeStyle": "solid",
                        "roughness": 1,
                        "opacity": 100,
                        "roundness": None,
                        "isDeleted": False,
                        "updated": now,
                        "locked": False,
                        "points": [],
                        "originalText": None,
                        "autoResize": True,
                        "lineHeight": 1.25,
                        "groupIds": [],
                        "frameId": None,
                        "link": None,
                        "boundElements": [],
                        "scale": [1, 1],
                        "crop": None,
                        "fileId": image_file_id,
                    }
                    shape_bounds[image_id] = bounds
                    shape_elt_map[image_id] = image_elt
                if g_text is not None:
                    # <text x="352.000000" y="158.500000" fill="#0A0F25"
                    # class="text-bold fill-N1"
                    # style="text-anchor:middle;font-size:16px">leach_mixer</text>
                    text_id = cls._element_id()
                    tb = Bounds(
                        *[int(float(g_text.get(c))) for c in ("x", "y")] + [0, 0]
                    )
                    text_value = g_text.text.strip()
                    # get font size
                    text_style = g_text.get("style", "")
                    match = re.search(r"font-size:\s*(\d+)px", text_style)
                    if match:
                        font_size = int(match.group(1))
                    else:
                        font_size = 12
                    # calculate SVG margin from text to rectangle
                    margin = 4  # (tb.x - rb.x) // 2
                    # create element
                    text_elt = {
                        "id": text_id,
                        "type": "text",
                        "x": bounds.x,
                        # center vertically
                        "y": bounds.y + (bounds.height / 2) - margin - (font_size / 2),
                        "width": bounds.width + font_size,  # padding
                        "height": font_size * 1.5,
                        "angle": 0,
                        "strokeColor": "#000000",
                        "backgroundColor": "transparent",
                        "fillStyle": "solid",
                        "strokeWidth": 2,
                        "strokeStyle": "solid",
                        "roughness": 1,
                        "opacity": 100,
                        "groupIds": [],
                        "frameId": None,
                        "roundness": None,
                        "isDeleted": False,
                        "boundElements": None,
                        "updated": now,
                        "link": None,
                        "locked": False,
                        "text": text_value,
                        "fontSize": font_size,
                        "fontFamily": 6,
                        "textAlign": "center",
                        "verticalAlign": "middle",
                        "containerId": None,
                        "originalText": text_value,
                        "autoResize": True,
                        "lineHeight": 1,
                    }
                if g_line is not None:
                    # <g id="(Unit_B -&gt; Unit_C)[0]">...</g>
                    # <path d="M 610.414213 155.085786 C 654.599976 110.900002 678.200012 110.900002 724.077373 153.769020"
                    # svg_xc_map[item_id] = xc_id
                    line_id = cls._element_id()
                    # extract start/end rect id
                    match = re.search(r"\((\S+)\s*->\s*(\S+)\).*", item_id)
                    if match is None:
                        raise ValueError(
                            f"could not find line endpoints in id '{item_id}'"
                        )
                    unit = match.group(1)
                    start_shape_id = svg_xc_map[unit]
                    unit = match.group(2)
                    end_shape_id = svg_xc_map[unit]
                    path_coords = g_line.get("d", None)
                    if path_coords is None:
                        # in absence of a path, just connect with straight line
                        start_bounds = shape_bounds[start_shape_id]
                        end_bounds = shape_bounds[end_shape_id]
                        # extract line points
                        dx = end_bounds.x - start_bounds.x
                        startx = start_bounds.width if dx > 0 else 0
                        dy = end_bounds.y - start_bounds.y
                        starty = start_bounds.height / 2
                        point_list = [[startx, starty], [dx, dy]]
                    else:
                        coord_items = re.split(r"[, ]+", path_coords)
                        if len(coord_items) < 10:
                            raise ValueError(
                                f"Wrong number of items (got {len(coord_items)}, expected 10 or more) "
                                f"for cubic path: {coord_items}"
                            )
                        if coord_items[0] != "M":
                            raise ValueError(
                                f"Expected 'M' as first item in path: {coord_items}"
                            )
                        if coord_items[3] != "C":
                            raise ValueError(
                                f"Expected 'C' as third item in path: {coord_items}"
                            )
                        # get start/end positions from path (ignore width/height)
                        start_bounds = Bounds(
                            float(coord_items[1]), float(coord_items[2]), 0, 0
                        )
                        end_bounds = Bounds(
                            float(coord_items[8]), float(coord_items[9]), 0, 0
                        )
                        # put path in point list
                        point_list = [[0, 0]]
                        # for xi, yi in ((4, 5), (-4, -3), (-2, -1)):
                        for xi, yi in ((4, 5), (-2, -1)):
                            x, y = float(coord_items[xi]), float(coord_items[yi])
                            point_list.append([x - start_bounds.x, y - start_bounds.y])
                        _log.debug(f"Line points: {point_list}")
                    # build element
                    line_elt = {
                        "id": line_id,
                        "type": "arrow",
                        "x": start_bounds.x,
                        "y": start_bounds.y,
                        "width": abs(end_bounds.x - start_bounds.x),
                        "height": abs(end_bounds.y - start_bounds.y),
                        "angle": 0,
                        "strokeColor": "#1e1e1e",
                        "backgroundColor": "transparent",
                        "fillStyle": "solid",
                        "strokeWidth": 2,
                        "strokeStyle": "solid",
                        "roughness": 1,
                        "opacity": 100,
                        "groupIds": [],
                        "frameId": None,
                        "roundness": {"type": 2},
                        "isDeleted": False,
                        "boundElements": None,
                        "updated": now,
                        "link": None,
                        "locked": False,
                        "points": point_list,
                        "lastCommittedPoint": None,
                        "startBinding": {
                            "elementId": start_shape_id,
                            "focus": 0,
                            "gap": 1,
                            "fixedPoint": None,
                        },
                        "endBinding": {
                            "elementId": end_shape_id,
                            "focus": 0,
                            "gap": 1,
                            "fixedPoint": None,
                        },
                        "startArrowhead": None,
                        "endArrowhead": "arrow",
                        "elbowed": False,
                    }
                    # assume all shapes go first
                    shape_elt_map[start_shape_id]["boundElements"].append(
                        {"type": "arrow", "id": line_id}
                    )
                    shape_elt_map[end_shape_id]["boundElements"].append(
                        {"type": "arrow", "id": line_id}
                    )
                if text_elt and rect_elt:
                    rect_elt["boundElements"].append({"type": "text", "id": text_id})
                    text_elt["containerId"] = rect_id
                elif text_elt and image_elt:
                    group_id = cls._element_id()
                    image_elt["groupIds"] = [group_id]
                    text_elt["groupIds"] = [group_id]
                    # move text below image
                    text_elt["y"] += image_elt["height"] / 2 + font_size / 2
                if rect_elt:
                    model.elements.append(rect_elt)
                if image_elt:
                    model.elements.append(image_elt)
                    model.files[image_file_id] = image_file_elt
                if text_elt:
                    model.elements.append(text_elt)
                if line_elt:
                    model.elements.append(line_elt)
        _log.debug(f"created {len(model.elements)} elements")
        if _log.isEnabledFor(logging.DEBUG):
            count = 0
            for e in model.elements:
                if e["type"] == "image":
                    count += 1
            _log.debug(f"image elements: {count}")
        return Diagram(model)

    # Alphabet for Excalidraw identifiers
    IDCHARS = (
        [chr(ord("A") + i) for i in range(26)]
        + [chr(ord("a") + i) for i in range(26)]
        + [chr(ord("0") + i) for i in range(10)]
    )

    @classmethod
    def _element_id(cls) -> str:
        "Generate random identifier in the style used by Excalidraw"
        items = random.choices(cls.IDCHARS, k=21)
        return "".join(items)

    @classmethod
    def _image_id(cls, data: str) -> str:
        "Generate random identifier for Excalidraw image"
        return sha1(data.encode("utf-8")).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("infile", metavar="input-file")
    p.add_argument("outfile", metavar="output-file")
    args = p.parse_args()

    # set up logging
    _log.setLevel(logging.DEBUG)  # XXX: for now
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter(fmt="{asctime} {levelname}: {message}", style="{"))
    _log.addHandler(h)

    # read and parse input
    _log.info(f"reading SVG from input file '{args.infile}'")
    with open(args.infile) as infile:
        diagram = Diagram.from_svg(infile)

    # write output
    with open(args.outfile, "w") as outfile:
        diagram.write(outfile, indent=2)
    _log.info(f"wrote JSON to output file '{args.outfile}'")

    return 0


if __name__ == "__main__":
    sys.exit(main())
