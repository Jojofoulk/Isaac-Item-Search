from bs4 import BeautifulSoup
import requests
from colorthief import ColorThief
import io
import webcolors
from PIL import Image
import functools
import uuid
import json   

from _ctypes import PyObj_FromPtr
import json
import re

class NoIndent(object):
    """ Value wrapper. """
    def __init__(self, value):
        self.value = value


class MyEncoder(json.JSONEncoder):
    FORMAT_SPEC = '@@{}@@'
    regex = re.compile(FORMAT_SPEC.format(r'(\d+)'))

    def __init__(self, **kwargs):
        # Save copy of any keyword argument values needed for use here.
        self.__sort_keys = kwargs.get('sort_keys', None)
        super(MyEncoder, self).__init__(**kwargs)

    def default(self, obj):
        return (self.FORMAT_SPEC.format(id(obj)) if isinstance(obj, NoIndent)
                else super(MyEncoder, self).default(obj))

    def encode(self, obj):
        format_spec = self.FORMAT_SPEC  # Local var to expedite access.
        json_repr = super(MyEncoder, self).encode(obj)  # Default JSON.

        # Replace any marked-up object ids in the JSON repr with the
        # value returned from the json.dumps() of the corresponding
        # wrapped Python object.
        for match in self.regex.finditer(json_repr):
            # see https://stackoverflow.com/a/15012814/355230
            id = int(match.group(1))
            no_indent = PyObj_FromPtr(id)
            json_obj_repr = json.dumps(no_indent.value, sort_keys=self.__sort_keys)

            # Replace the matched id string with json formatted representation
            # of the corresponding Python object.
            json_repr = json_repr.replace(
                            '"{}"'.format(format_spec.format(id)), json_obj_repr)

        return json_repr

def closest_colour(requested_colour):
    min_colours = {}
    for key, name in webcolors.CSS21_HEX_TO_NAMES.items():
        r_c, g_c, b_c = webcolors.hex_to_rgb(key)
        rd = (r_c - requested_colour[0]) ** 2
        gd = (g_c - requested_colour[1]) ** 2
        bd = (b_c - requested_colour[2]) ** 2
        min_colours[(rd + gd + bd)] = name
    return min_colours[min(min_colours.keys())]

def get_colour_name(requested_colour):
    try:
        closest_name = webcolors.rgb_to_name(requested_colour)
    except ValueError:
        closest_name = closest_colour(requested_colour)
    return closest_name

class Item:
    def __init__(self, name, image, item_type, dlc):
        self.name = name
        self.image = image
        self.color = None
        self.dlc = dlc
        self.item_type = item_type
    
    def set_color(self, color):
        self.color = color


r = requests.get("https://bindingofisaacrebirth.gamepedia.com/Items")

soup = BeautifulSoup(r.content, "html.parser")
table = soup.find_all("table")

elem_list = table[0].find_all("tr", {"class": "row-collectible"})
active_size = len(elem_list)

item_list = []

for e in elem_list:
    content = e.find_all("td")[2]
    content = content.find("img")

    if content:
        _img = content["src"]
        _title = content["alt"]

    content = e.find_all("td")[0]
    content = content.find("img")
  
    if content:
        _dlc = content["alt"][9:]
    else:
        _dlc = None
    i = Item(_title, _img, "Active", _dlc)
    item_list.append(i)

# Add passive items
elem_list.extend(table[1].find_all("tr", {"class": "row-collectible"}))

for e in elem_list[active_size:]:
    content = e.find_all("td")[2]
    content = content.find("img")

    if content:
        _img = content["src"]
        _title = content["alt"]

    content = e.find_all("td")[0]
    content = content.find("img")

    if content:
        _dlc = content["alt"][9:]
    else:
        _dlc = None

    i = Item(_title, _img, "Passive", _dlc)
    item_list.append(i)
del i

items_dict = {}

print("Populating item dictionnary...")
for item in item_list:
    r = requests.get(item.image)
    byte_content = r.content
    f = io.BytesIO(byte_content)

    img = Image.open(f)
    img = img.convert('RGBA')


    # remove fully transparent pixels
    colors = list(filter(lambda c: c[1][3]>0, img.getcolors()))
    # sort by pixel count and format the list to top 3 colors
    colors = sorted(colors, key=lambda x: x[0], reverse=True)[:4]
    colors = list((map(lambda x: (x[0], get_colour_name((x[1][:3]))), colors)))

    # merges the pixel count of similar color, and only keeps one entry in the color list
    def sum_dup_colors(a, b):
        if type(a) is not list:
            if a[1] == b[1]:
                return [(a[0]+b[0], a[1])]
            else:
                # color is new
                return [(a), (b)]
        else:
            for i, _a in enumerate(a):
                if _a[1] == b[1]:
                    new_tuple = (_a[0] + b[0], _a[1])
                    a.remove(_a)
                    a.insert(i, new_tuple)
                    return a
            # color is new
            a.append(b)
            return a
        
    t = functools.reduce(sum_dup_colors, colors)
    # Ensures we get a list
    if type(t) is not list:
        t = [t]

    colors = sorted(t, key=lambda x: x[0], reverse=True)

    f.flush()

    items_dict[item.name] = {"name": item.name, "DLC": item.dlc, "colors": NoIndent(colors), "type": item.item_type}
    print("Added: ", item.name)


with open("items.json", "w", encoding="utf-8") as f:
    j = json.dumps(items_dict, indent=4, cls=MyEncoder, ensure_ascii=False)
    f.write(j)
    # f.seek(0)



