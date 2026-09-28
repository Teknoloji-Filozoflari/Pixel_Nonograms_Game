"""Build and verify original pixel-art additions; never run at game startup."""
import json
from pathlib import Path

from PIL import Image, ImageDraw

from pixel_nonograms.core import Difficulty, Puzzle
from pixel_nonograms.solver import SolveStatus, validate_unique_solution

ROOT = Path(__file__).resolve().parents[1]
# Seven-pixel silhouettes, drawn specifically for this collection.
ICONS = [
    ("Mantar", "..###../.#####./#######/##.#.##/..###../..###../.#####."),
    ("Çam Ağacı", "...#.../..###../.#####./..###../#######/...#.../..###.."),
    ("Balık", "...##../#.####./####.##/#######/#.####./...##../......."),
    ("Kedi", "#....#./##..##./######./#.##.#./######./.####../..##..."),
    ("Kupa", "######./##..#.#/##..#.#/##..##./#####../.###.../#######"),
    ("Şemsiye", "..###../.#####./#######/...#.../...#.../.#.#.../.###..."),
    ("Anahtar", ".###.../##.##../##.####/.######/....#.#/....#.#/......."),
    ("Çapa", "..###../..#.#../..###../...#.../#..#..#/##.#.##/.#####."),
    ("Taç", "#..#..#/#.###.#/#######/.#####./.#####./.#####./......."),
    ("Kelebek", "##...##/###.###/#######/.#####./#######/###.###/##...##"),
    ("Mektup", "#######/##...##/#.#.#.#/#..#..#/#.....#/#######/......."),
    ("Şimşek", "...###./..###../.###.../######./..###../.###.../##....."),
    ("Elma", "....#../...#.../.##.##./#######/#######/.#####./..###.."),
    ("Ok", "...#.../...##../#######/#######/#######/...##../...#..."),
    ("Kaktüs", "...#.../#.###../#.###.#/#####.#/.######/..###../.#####."),
    ("Hediye", ".##.##./.#.#.#./#######/###.###/#######/###.###/#######"),
    ("Roket", "...#.../..###../.#####./.##.##./.#####./#######/#.###.#"),
    ("Robot", "...#.../.#####./.#.#.#./.#####./###.###/#.###.#/..#.#.."),
    ("Lokomotif", "#..##../#.####./####.#./######./#######/.##.##./......."),
    ("Kamera", "..###../#######/##...##/#.###.#/#.#.#.#/#.###.#/#######"),
    ("Gitar", "....##./....#../...##../.####../##.###./#...##./.####.."),
    ("Kuş", "..##.../.####../.##.###/######./.#####./..#.#../.##.##."),
    ("Tavşan", ".#..#../.##.##./.#####./.#.#.#./.#####./###.###/.#####."),
    ("Yengeç", "#.....#/.#...#./#######/.#####./#######/.#.#.#./#..#..#"),
    ("Kaplumbağa", "..###../.#####./###.###/#######/.#####./##...##/......."),
    ("Yel Değirmeni", "#.....#/.##.##./..###../#######/..###../.##.##./.#####."),
    ("Fincan", "..#.#../.#.#.../#####../#...#.#/#...###/.###.../#######"),
    ("Dondurma", "..###../.#####./#######/#######/.#####./..###../...#..."),
    ("Pasta", "...#.../...#.../.#####./.#.#.#./#######/#######/#######"),
    ("Telefon", ".#####./.##.##./.#...#./.#...#./.#...#./.##.##./.#####."),
    ("Çanta", "..###../..#.#../.#####./#######/###.###/#######/.#####."),
    ("Saat", "..###../.#####./###.###/###..##/#######/.#####./..###.."),
    ("Pencere", "#######/#..#..#/#..#..#/#######/#..#..#/#..#..#/#######"),
    ("Fener", "..###../..#.#../.#####./.#...#./.#.#.#./.#####./#######"),
]


def stamp(image, pattern, x, y, scale=1, color=1):
    draw = ImageDraw.Draw(image)
    for row, line in enumerate(pattern.split('/')):
        for col, pixel in enumerate(line):
            if pixel == '#':
                draw.rectangle((x+col*scale, y+row*scale,
                                x+(col+1)*scale-1, y+(row+1)*scale-1), fill=color)


def artwork(group, index):
    size = (10, 20, 25, 30)[group]
    image = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(image)
    if group == 0:
        name, pattern = ICONS[index]
        stamp(image, pattern, 1, 1)
    elif group == 1:
        name, pattern = ICONS[16+index]
        stamp(image, pattern, 3, 2, 2)
        # A small plinth visually grounds each detailed object.
        draw.rectangle((2, 17, 17, 18), fill=1)
        draw.line((9, 15, 9, 17), fill=1)
    elif group == 2:
        places = ["Orman Evi", "Liman", "Dağ Kampı", "Uzay Üssü", "Köy Meydanı",
                  "Tren İstasyonu", "Sahil", "Gece Bahçesi", "Kış Kulübesi",
                  "Göl Kıyısı", "Müzik Sokağı", "Çiçek Pazarı", "Çöl Yolu",
                  "Denizaltı", "Kahve Molası", "Doğum Günü", "Oyuncakçı", "Saat Kulesi"]
        name = places[index]
        motif = [1, 7, 4, 16, 25, 18, 2, 13, 0, 24, 20, 12, 14, 23, 26, 28, 17, 31][index]
        stamp(image, ICONS[motif][1], 9, 8, 2)
        # Skyline, foreground and a different moon position for each scene.
        draw.ellipse((2, 1+(index%3), 7, 6+(index%3)), fill=1)
        draw.polygon([(0, 18), (4, 9 + index%5), (8, 18)], fill=1)
        draw.line((0, 22, 24, 22), fill=1)
        draw.line((0, 24, 24, 24), fill=1)
        draw.line((5, 18, 5, 22), fill=1)
    else:
        names = ["Selçuklu Yıldızı", "Dokuma", "Baklava Deseni", "Gül Penceresi",
                 "Labirent", "Çini", "Pusula", "Kristal", "Sarmal",
                 "Kilim", "Petek", "Dalga", "Yaprak Deseni", "Vitray",
                 "Kar Tanesi", "Kemer", "Dama Bahçesi", "Güneş Motifi"]
        name = names[index]
        # Distinct geometric panels with strong clue anchors at their seams.
        for y in range(size):
            for x in range(size):
                u, v = x % 10, y % 10
                dx, dy = abs(u-4.5), abs(v-4.5)
                modes = [
                    dx+dy <= 4 or (dx <= 1 and dy <= 4),
                    (u < 3) != (v < 3),
                    2 <= dx+dy <= 5,
                    dx*dx+dy*dy <= 14 and (dx >= 1 or dy >= 1),
                    (u in (2, 7) and v >= 2) or (v == 2 and u >= 2),
                    (dx <= 2 and dy <= 2) or dx+dy >= 8,
                    dx+dy <= 5 and (dx <= 1.5 or dy <= 1.5),
                    dx+dy <= 5 and dx >= 1,
                    (u <= 6 and v == 2) or (u == 6 and 2 <= v <= 7) or
                    (v == 7 and 2 <= u <= 6) or (u == 2 and 4 <= v <= 7),
                    abs(u-v) <= 1 or abs(u+v-9) <= 1,
                    (v in (1, 8) and 2 <= u <= 7) or (u in (1, 8) and 2 <= v <= 7),
                    (u+v) % 10 < 4,
                    dx+dy <= 5 and u >= v,
                    (u < 5 and v < 5) or (u >= 5 and v >= 5),
                    dx == dy or dx <= 0.5 or dy <= 0.5,
                    dx*dx+(v-6)**2 <= 16 and (v < 4 or dx >= 2),
                    (u//3 + v//3) % 2 == 0,
                    dx*dx+dy*dy <= 7 or (dx <= 0.5 or dy <= 0.5),
                ]
                if x in (0, 10, 20, 29) or y in (0, 10, 20, 29) or modes[index]:
                    image.putpixel((x, y), 1)
    return name, image


def make_puzzle(record):
    return Puzzle(id=record['id'], title=record['title'], author='Pixel Nonograms',
                  description='Özgün piksel çizimi', width=len(record['rows'][0]),
                  height=len(record['rows']), difficulty=Difficulty(record['difficulty']),
                  tags=(), palette=tuple(record['palette']),
                  solution=tuple(tuple(int(c) for c in row) for row in record['rows']))


def main():
    records = []
    for group, difficulty in enumerate(Difficulty):
        for index in range(16 if group == 0 else 18):
            name, image = artwork(group, index)
            colored = index < (4, 5, 5, 4)[group]
            palette = ['#29343B']
            if colored:
                palette = ['#D66B45', '#408C79', '#E3B64E']
                for y in range(image.height):
                    for x in range(image.width):
                        if image.getpixel((x, y)):
                            image.putpixel((x, y), 1 + ((y//max(1,image.height//3)) % 3))
            record = dict(id=f'collection-{difficulty.value}-{index+1:02}', title=name,
                          difficulty=difficulty.value, palette=palette)
            # Resolve ambiguous clues with minimal, deterministic connecting pixels.
            # These edits happen only here; shipped artwork and IDs remain immutable.
            for repair in range(65):
                record['rows'] = [''.join(str(image.getpixel((x, y))) for x in range(image.width))
                                  for y in range(image.height)]
                puzzle = make_puzzle(record)
                result = validate_unique_solution(puzzle, timeout_seconds=3)
                if result.status == SolveStatus.SOLVED:
                    assert result.solution == puzzle.solution
                    break
                if result.status == SolveStatus.UNKNOWN_LIMIT:
                    # Add a structural seam to bound complex line possibilities.
                    y = (repair*7+3) % image.height
                    ImageDraw.Draw(image).line((0,y,image.width-1,y),fill=1)
                else:
                    alternate = result.alternate_solution
                    if alternate == puzzle.solution:
                        alternate = result.solution
                    candidates = [(x,y) for y in range(image.height) for x in range(image.width)
                                  if alternate[y][x] != puzzle.solution[y][x] and not image.getpixel((x,y))]
                    if not candidates:
                        raise RuntimeError((name, result.status))
                    x,y = min(candidates, key=lambda p: (
                        -sum(image.getpixel((xx,yy)) > 0 for xx,yy in
                             ((p[0]-1,p[1]),(p[0]+1,p[1]),(p[0],p[1]-1),(p[0],p[1]+1))
                             if 0 <= xx < image.width and 0 <= yy < image.height), p[1],p[0]))
                    image.putpixel((x,y), 1)
            else:
                raise RuntimeError(f'Could not validate {name}')
            record['repairs'] = repair
            records.append(record)
            print(record['id'], name, repair, flush=True)
    target = ROOT/'src/pixel_nonograms/catalog_expansion.json'
    target.write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
