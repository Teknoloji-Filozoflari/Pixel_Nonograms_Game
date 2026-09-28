"""Deterministic offline pixel-art generation with unique-solution verification.

Existing catalog entries are immutable. Only accepted, distinct, solver-verified
drawings are shipped. Run with the project's Python environment from the root.
"""
import json
import random
from collections import Counter
from pathlib import Path
from time import monotonic

from build_catalog_expansion import ICONS, make_puzzle, stamp
from PIL import Image, ImageDraw

from pixel_nonograms.core import Difficulty
from pixel_nonograms.core.compact import compact_puzzle
from pixel_nonograms.services import built_in_puzzles
from pixel_nonograms.solver import SolveStatus, validate_unique_solution

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'src/pixel_nonograms/catalog_extended.json'
COUNTS = {False: (275, 225, 175, 125), True: (100, 50, 25, 25)}
SIZES = (10, 20, 25, 30)
NAMES = ['Sokak Evleri', 'Çiçek Saksısı', 'Orman Silüeti', 'Yelkenli Tekne',
         'Kanat Deseni', 'Kuleler', 'Piksel Galerisi', 'Geometrik Bahçe']
TRANSLATIONS = [
    ['Küçə Evləri', 'Casas de la calle', 'Уличные дома', 'Street Houses'],
    ['Çiçək Dibçəyi', 'Maceta', 'Цветочный горшок', 'Flower Pot'],
    ['Meşə Silueti', 'Silueta del bosque', 'Силуэт леса', 'Forest Silhouette'],
    ['Yelkənli Qayıq', 'Velero', 'Парусник', 'Sailboat'],
    ['Qanad Naxışı', 'Patrón de alas', 'Узор крыльев', 'Wing Pattern'],
    ['Qüllələr', 'Torres', 'Башни', 'Towers'],
    ['Piksel Qalereyası', 'Galería de píxeles', 'Пиксельная галерея', 'Pixel Gallery'],
    ['Həndəsi Bağ', 'Jardín geométrico', 'Геометрический сад', 'Geometric Garden'],
]
PALETTES = [
    ['#D66B45', '#408C79', '#E3B64E'],
    ['#9568AF', '#3B8491', '#E19254'],
    ['#C95870', '#568B53', '#5A78AD'],
    ['#4275A3', '#DB9B3A', '#A25560'],
]


def artwork(size, family, seed, colored):
    rng = random.Random(seed)
    image = Image.new('L', (size, size))
    d = ImageDraw.Draw(image)
    def color(n):
        return 1 + n % 3 if colored else 1
    baseline = size - 2
    if family in (0, 5):
        # Different roof heights, façades, doors and window arrangements.
        x = 0
        while x < size:
            width = min(rng.randint(3, max(4, size // 3)), size-x)
            top = rng.randint(1, max(2, size // 2))
            if width >= 3:
                d.rectangle((x, top+1, x+width-1, baseline), fill=color(x))
                if family == 0:
                    d.polygon([(x, top+1), (x+width//2, max(0, top-2)),
                               (x+width-1, top+1)], fill=color(x+1))
                else:
                    for xx in range(x, x+width, 2):
                        d.point((xx, top), fill=color(x))
                for yy in range(top+3, baseline-1, 3):
                    for xx in range(x+1, x+width-1, 2):
                        if rng.random() < .8:
                            d.point((xx, yy), fill=0)
                door = x+rng.randrange(1, width-1)
                d.line((door, baseline-1, door, baseline), fill=0)
            x += width + (1 if rng.random() < .3 else 0)
        d.line((0, size-1, size-1, size-1), fill=color(2))
    elif family == 1:
        cx = size//2
        pot_top = size*2//3
        d.polygon([(cx-size//3, pot_top), (cx+size//3, pot_top),
                   (cx+size//4, size-1), (cx-size//4, size-1)], fill=color(0))
        for _ in range(rng.randint(2, 4)):
            fx, fy = rng.randint(1, size-2), rng.randint(1, max(2, pot_top-2))
            radius = rng.randint(1, max(1, size//8))
            d.line((cx, pot_top, fx, fy), fill=color(1), width=max(1, size//12))
            d.ellipse((max(0,fx-radius), max(0,fy-radius), min(size-1,fx+radius),
                       min(pot_top-1,fy+radius)), fill=color(2))
            d.point((fx,fy), fill=color(0) if colored else 0)
        d.line((cx-size//3, pot_top, cx+size//3, pot_top), fill=color(2))
    elif family == 2:
        for cx in range(1, size, max(3, size//4)):
            top = rng.randint(0, size//3)
            spread = rng.randint(2, max(2, size//4))
            d.line((cx, top, cx, size-1), fill=color(0))
            for cy in range(top+2, size-2, max(2, size//7)):
                d.polygon([(cx, max(top,cy-3)), (max(0,cx-spread),cy),
                           (min(size-1,cx+spread),cy)], fill=color(cx))
        d.line((0,size-1,size-1,size-1), fill=color(1))
    elif family == 3:
        mast = rng.randint(size//3, size*2//3)
        deck = size-3
        top = rng.randint(0, max(1,size//5))
        d.line((mast, top, mast, deck), fill=color(0))
        d.polygon([(mast-1,top+1), (rng.randint(0,max(0,mast//3)),deck-1),
                   (mast-1,deck-1)], fill=color(1))
        d.polygon([(mast+1,top+2),(size-1,deck-1),(mast+1,deck-1)],fill=color(2))
        d.polygon([(0,deck),(size-1,deck),(size-3,size-1),(2,size-1)],fill=color(0))
        if size > 10:
            for x in range(3,size-3,3):
                d.point((x,deck+1),fill=0)
    elif family == 4:
        center = (size-1)/2
        widths = [rng.randint(1,max(2,size//2-1)) for _ in range((size+1)//2)]
        for y in range(size):
            reach = widths[min(y,size-1-y)]
            for x in range(size):
                dist = abs(x-center)
                if dist <= reach:
                    image.putpixel((x,y),color(y//max(1,size//3)))
                if 1.5 < dist < reach-1 and y % 3 == 1:
                    image.putpixel((x,y),0)
        d.rectangle((size//2-1,1,size//2,size-2),fill=color(2))
    elif family == 6:
        # Pixel-art exhibits, each composed of different original motifs.
        if size == 10:
            _, pattern = rng.choice(ICONS)
            stamp(image, pattern, rng.randint(0,2), rng.randint(0,2), color=color(seed))
            d.line((0,9,9,9),fill=color(1))
            if rng.random() < .5:
                d.line((9,0,9,9),fill=color(2))
        else:
            tiles = 2 if size < 30 else 3
            stride = size//tiles
            for ty in range(tiles):
                for tx in range(tiles):
                    _, pattern = rng.choice(ICONS)
                    stamp(image,pattern,tx*stride+1,ty*stride+1,color=color(tx+ty))
            for p in range(0,size,stride):
                d.line((0,p,size-1,p),fill=color(p))
                d.line((p,0,p,size-1),fill=color(p+1))
            d.line((0,size-1,size-1,size-1),fill=color(2))
            d.line((size-1,0,size-1,size-1),fill=color(1))
    else:
        # Woven geometric panels, with individually varied symmetrical bands.
        for y in range(size):
            band = rng.randint(1, max(2,size//3))
            for x in range(size):
                if min(x,size-1-x) <= band or abs(x-size//2) <= y % 3:
                    image.putpixel((x,y),color(y//3))
        for y in range(0,size,5):
            d.line((0,y,size-1,y),fill=color(y))
    return image


def main():
    started = monotonic()
    originals = [p for p in built_in_puzzles() if not p.id.startswith('extended-')]
    records = json.loads(TARGET.read_text(encoding='utf-8')) if TARGET.exists() else []
    puzzles = originals + [make_puzzle(r) for r in records]
    counts = Counter((p.difficulty, p.is_colored) for p in puzzles)
    seen = {compact_puzzle(p)[0].solution for p in puzzles}
    accepted = 0
    for group,difficulty in enumerate(Difficulty):
        for colored in (False,True):
            goal = COUNTS[colored][group]
            attempt = 0
            while counts[difficulty,colored] < goal:
                if attempt >= 50000:
                    raise RuntimeError(f'Insufficient accepted drawings: {difficulty}, {colored}')
                family = attempt % len(NAMES)
                seed = 20260928 + group*1000000 + int(colored)*100000 + attempt
                image = artwork(SIZES[group],family,seed,colored)
                attempt += 1
                serial = counts[difficulty,colored]+1
                record = dict(id=f'extended-{difficulty.value}-{"color" if colored else "mono"}-{serial:03}',
                              title=f'{NAMES[family]} · {group+1}{int(colored)}{serial:03}',
                              difficulty=difficulty.value,
                              palette=PALETTES[seed % len(PALETTES)] if colored else ['#29343B'],
                              rows=[''.join(str(image.getpixel((x,y))) for x in range(image.width))
                                    for y in range(image.height)])
                puzzle = make_puzzle(record)
                compact = compact_puzzle(puzzle)[0]
                if compact.solution in seen or min(compact.width,compact.height) < SIZES[group]*.65:
                    continue
                density = sum(c != 0 for row in puzzle.solution for c in row)/(puzzle.width*puzzle.height)
                if not .2 <= density <= .85:
                    continue
                if colored and len({c for row in puzzle.solution for c in row if c}) < 2:
                    continue
                result = validate_unique_solution(puzzle,timeout_seconds=.4)
                if result.status != SolveStatus.SOLVED or result.solution != puzzle.solution:
                    continue
                compact_result = validate_unique_solution(compact,timeout_seconds=.4)
                if compact_result.status != SolveStatus.SOLVED or compact_result.solution != compact.solution:
                    continue
                record['verification'] = 'unique'
                records.append(record)
                counts[difficulty,colored] += 1
                seen.add(compact.solution)
                accepted += 1
                if accepted % 20 == 0:
                    TARGET.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    print(f'{len(records)} additions; {difficulty.value} {"color" if colored else "mono"}: '
                          f'{counts[difficulty,colored]}/{goal}; {monotonic()-started:.1f}s',flush=True)
            TARGET.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(f'COMPLETE {difficulty.value} colored={colored}: {goal}; attempts={attempt}',flush=True)
    translations_path = ROOT/'src/pixel_nonograms/translations.json'
    translations = json.loads(translations_path.read_text(encoding='utf-8'))
    translations.update(dict(zip(NAMES,TRANSLATIONS)))
    translations_path.write_text(json.dumps(translations,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'DONE: {len(records)} additions; {len(originals)+len(records)} total; {monotonic()-started:.1f}s',flush=True)


if __name__ == '__main__':
    main()
