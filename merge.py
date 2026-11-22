# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Sloučí všechny SVG značky ze složky do jednoho velkého SVG s popisky (bílé pozadí).
"""

import argparse
import copy
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
ET.register_namespace("inkscape", "http://www.inkscape.org/namespaces/inkscape")
ET.register_namespace("sodipodi", "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd")
FONT = "DejaVu Sans, Arial, sans-serif"


def tag(name):
    return f"{{{SVG_NS}}}{name}"


def cislo(s, vychozi):
    m = re.match(r"\s*([\d.]+)", s or "")
    return float(m.group(1)) if m else vychozi


def nazev(root, soubor):
    t = root.find(tag("title"))
    if t is not None and (t.text or "").strip():
        return t.text.strip()
    return re.sub(r"^\d+[_\- ]*", "", soubor.stem).replace("_", " ")


def zalom(text, max_znaku):
    """Rozdělí popisek na řádky podle slov."""
    radky, akt = [], ""
    for slovo in text.split():
        if akt and len(akt) + 1 + len(slovo) > max_znaku:
            radky.append(akt)
            akt = slovo
        else:
            akt = f"{akt} {slovo}".strip()
    if akt:
        radky.append(akt)
    return radky or [""]


def main():
    ap = argparse.ArgumentParser(description="Sloučení SVG značek do jednoho SVG s popisky")
    ap.add_argument("slozka", nargs="?", default="znacky", help="složka se SVG značkami (výchozí: znacky)")
    ap.add_argument("-o", "--vystup", default="vsechny_znacky.svg", help="výstupní SVG")
    ap.add_argument("--sloupce", type=int, default=6, help="počet sloupců (výchozí 6)")
    ap.add_argument("--velikost", type=float, default=16, help="velikost políčka pro značku v mm (výchozí 16)")
    ap.add_argument("--pismo", type=float, default=3.2, help="velikost písma popisku v mm (výchozí 3,2)")
    ap.add_argument("--nadpis", default="", help="nadpis nad značkami (výchozí žádný)")
    ap.add_argument("--soubory", action="store_true", help="pod popisek přidat i název souboru")
    ap.add_argument("--meritko", type=float, default=None,
                    help="zachovat vzájemné velikosti značek: skutečná velikost × MERITKO "
                         "(např. 3); bez této volby se každá značka zvětší na celé políčko")
    args = ap.parse_args()

    soubory = sorted(Path(args.slozka).glob("*.svg"))
    soubory = [f for f in soubory if f.resolve() != Path(args.vystup).resolve()]
    if not soubory:
        sys.exit(f"Ve složce {args.slozka} nejsou žádné SVG soubory.")

    polozky = []
    for f in soubory:
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError as e:
            print(f"Přeskakuji {f.name}: nejde načíst ({e})")
            continue
        vb = root.get("viewBox") or f"0 0 {cislo(root.get('width'), 100)} {cislo(root.get('height'), 100)}"
        w_mm = cislo(root.get("width"), 0) if (root.get("width") or "").strip().endswith("mm") else 0
        h_mm = cislo(root.get("height"), 0) if (root.get("height") or "").strip().endswith("mm") else 0
        polozky.append((f, root, vb, nazev(root, f), w_mm, h_mm))

    V = args.velikost            # políčko se značkou
    P = args.pismo
    sirka_bunky = V * 2.2         # šířka sloupce (místo na popisek)
    max_znaku = max(8, int(sirka_bunky / (P * 0.55)))
    radky_popisku = max(len(zalom(p[3], max_znaku)) for p in polozky)
    vyska_popisku = radky_popisku * P * 1.25 + (P * 1.1 if args.soubory else 0)
    vyska_bunky = V + 2 + vyska_popisku + 4
    okraj = 8.0
    nadpis_v = P * 3 if args.nadpis else 0
    sl = max(1, args.sloupce)
    rd = (len(polozky) + sl - 1) // sl
    W = 2 * okraj + sl * sirka_bunky
    H = 2 * okraj + nadpis_v + rd * vyska_bunky

    doc = ET.Element(tag("svg"), {"width": f"{W:.1f}mm", "height": f"{H:.1f}mm", "viewBox": f"0 0 {W:.2f} {H:.2f}"})
    ET.SubElement(doc, tag("rect"), {"id": "pozadi", "width": f"{W:.2f}", "height": f"{H:.2f}", "fill": "#ffffff"})
    if args.nadpis:
        t = ET.SubElement(doc, tag("text"), {"x": f"{W / 2:.2f}", "y": f"{okraj + P * 1.6:.2f}", "font-family": FONT,
                                            "font-size": f"{P * 1.6:.2f}", "font-weight": "bold",
                                            "text-anchor": "middle", "fill": "#1b1b1b"})
        t.text = args.nadpis

    for i, (f, root, vb, jmeno, w_mm, h_mm) in enumerate(polozky):
        s, r = i % sl, i // sl
        x0 = okraj + s * sirka_bunky
        y0 = okraj + nadpis_v + r * vyska_bunky
        cx = x0 + sirka_bunky / 2
        g = ET.SubElement(doc, tag("g"), {"id": f"znacka-{f.stem}"})
        znacka = copy.deepcopy(root)
        for k in ("width", "height", "x", "y"):
            znacka.attrib.pop(k, None)
        zw = zh = V
        if args.meritko and w_mm and h_mm:
            k = min(args.meritko, V / w_mm, V / h_mm)      # nikdy větší než políčko
            zw, zh = w_mm * k, h_mm * k
        znacka.set("x", f"{cx - zw / 2:.2f}")
        znacka.set("y", f"{y0 + (V - zh) / 2:.2f}")
        znacka.set("width", f"{zw:.2f}")
        znacka.set("height", f"{zh:.2f}")
        znacka.set("viewBox", vb)
        znacka.set("preserveAspectRatio", "xMidYMid meet")
        g.append(znacka)
        y = y0 + V + 2 + P
        for radek in zalom(jmeno, max_znaku):
            t = ET.SubElement(g, tag("text"), {"x": f"{cx:.2f}", "y": f"{y:.2f}", "font-family": FONT,
                                              "font-size": f"{P:.2f}", "text-anchor": "middle", "fill": "#1b1b1b"})
            t.text = radek
            y += P * 1.25
        if args.soubory:
            t = ET.SubElement(g, tag("text"), {"x": f"{cx:.2f}", "y": f"{y:.2f}", "font-family": FONT,
                                              "font-size": f"{P * 0.7:.2f}", "text-anchor": "middle", "fill": "#888888"})
            t.text = f.name

    ET.ElementTree(doc).write(args.vystup, encoding="utf-8", xml_declaration=True)
    print(f"Hotovo: {args.vystup} ({len(polozky)} značek, {W:.0f} × {H:.0f} mm)")


if __name__ == "__main__":
    main()
