"""High-resolution, interface-only equipment map with built-in and uploaded photos."""
from pathlib import Path

from PIL import Image,ImageDraw,ImageFont,ImageOps
from engine import pair_layout
import io,math
NAVY='#12243A';TEAL='#0F766E';INK='#172B45';MUTED='#64748B'
def font(size,bold=False):
    for path in ['/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf','/usr/share/fonts/truetype/liberation2/LiberationSans'+('-Bold' if bold else '-Regular')+'.ttf']:
        try:return ImageFont.truetype(path,size)
        except OSError:pass
    return ImageFont.load_default(size=size)
def equipment_illustration(kind):
    """Generic schematic, not a photograph or exact model representation."""
    art=Image.new('RGB',(128,132),'#EEF3F8');p=ImageDraw.Draw(art)
    k=kind.lower()
    if 'instron' in k or 'zwick' in k:
        p.rounded_rectangle((24,110,106,125),radius=4,fill='#334155')
        p.rectangle((30,14,39,111),fill='#64748B');p.rectangle((93,14,102,111),fill='#64748B')
        p.rounded_rectangle((24,8,108,25),radius=3,fill='#1D4ED8')
        p.rectangle((42,61,92,68),fill='#475569');p.rectangle((42,86,92,91),fill='#475569')
        p.line((66,68,66,86),fill='#D97706',width=4)
        p.rounded_rectangle((3,44,25,77),radius=3,fill='#0F766E')
        p.rectangle((7,49,21,63),fill='#CFFAFE')
    elif 'fatm' in k or 'ibm' in k:
        p.rounded_rectangle((8,19,121,120),radius=6,fill='#CBD5E1',outline='#475569',width=3)
        p.rectangle((16,28,112,87),fill='#94A3B8');p.rectangle((23,34,104,81),fill='#E0F2FE')
        for x in (30,58,86):p.line((x,35,x,80),fill='#64748B',width=3)
        p.rectangle((23,94,106,110),fill='#334155')
        for x in (31,53,75):p.ellipse((x,99,x+8,107),fill='#22C55E')
    else:
        p.rounded_rectangle((16,22,112,114),radius=8,fill='#CBD5E1',outline='#475569',width=3)
        p.rounded_rectangle((30,34,98,82),radius=4,fill='#E0F2FE')
        p.rectangle((36,92,92,99),fill='#64748B')
    return art

def equipment_thumbnail(kind, uploaded=None):
    default_photos = {
        'instron': 'instron.png',
        'fatm': 'fatm.png',
        'zwick': 'zwick.png',
    }
    filename = default_photos.get(kind.strip().casefold())
    bundled = Path(__file__).with_name('equipment_photos') / filename if filename else None
    for source in (io.BytesIO(uploaded) if uploaded else None, bundled):
        if source is None:
            continue
        try:
            with Image.open(source) as photo:
                thumbnail = ImageOps.contain(ImageOps.exif_transpose(photo).convert('RGBA'), (128, 132))
                background = Image.new('RGB', thumbnail.size, 'white')
                background.paste(thumbnail, mask=thumbnail.getchannel('A'))
                return background
        except (OSError, ValueError, Image.DecompressionBombError):
            continue
    return equipment_illustration(kind)


CORE = '#2454B8'
CROSS = '#A65308'
WITHIN = '#52647B'
WASH = {CORE: '#E7EFFF', CROSS: '#FFF0DE', WITHIN: '#E9EFF5'}


def fit_label(draw, text, face, max_width):
    if draw.textlength(text, font=face) <= max_width:
        return text
    while text and draw.textlength(text + '…', font=face) > max_width:
        text = text[:-1]
    return text + '…'


def draw_route(draw, points, color):
    draw.line(points, fill=color, width=3, joint='curve')
    x, y = points[-1]
    previous_x, previous_y = points[-2]
    angle = math.atan2(y - previous_y, x - previous_x)
    draw.polygon([(x, y), *[(x - 12 * math.cos(angle + offset),
                            y - 12 * math.sin(angle + offset)) for offset in (-.45, .45)]],
                 fill=color)


def render_layout(equipment, photos=None, ou_label='Origin Unit (OU)', ru_label='Receiving Unit (RU)',
                  study='Unique equipment comparisons', selected=None):
    photos = photos or {}
    by_site = {site: [machine for machine in equipment if machine['site'] == site] for site in ('OU', 'RU')}
    pairs = selected if selected is not None else [
        {**pair, 'et': f'ET{i}'} for i, pair in enumerate(pair_layout(equipment), 1)
    ]
    site_by_id = {machine['id']: site for site, machines in by_site.items() for machine in machines}
    pairs = [pair for pair in pairs if pair['reference'] in site_by_id and pair['test'] in site_by_id]
    within = {site: [pair for pair in pairs if site_by_id[pair['reference']] == site_by_id[pair['test']] == site]
              for site in by_site}
    card_width, card_height, step, top = 305, 132, 214, 166
    gutter = {site: 54 + 34 * len(routes) if len(routes) > 1 else 76 if routes else 54
              for site, routes in within.items()}
    cross_site = [pair for pair in pairs if site_by_id[pair['reference']] != site_by_id[pair['test']]]
    gap = max(550, 24 * len(cross_site))
    left = gutter['OU']
    right = left + card_width + gap
    width = right + card_width + gutter['RU']
    height = top + (max(1, *(len(items) for items in by_site.values())) - 1) * step + card_height + 80
    image = Image.new('RGB', (width, height), '#F2F6FA')
    draw = ImageDraw.Draw(image)
    title_font, name_font, small_font = font(30, True), font(20, True), font(16)
    draw.rounded_rectangle((14, 14, width - 14, height - 14), radius=20, fill='#FFFFFF', outline='#D9E4EE', width=2)
    draw.text((36, 35), fit_label(draw, study, title_font, width - 72), fill=NAVY, font=title_font)
    draw.text((36, 77), f'{len(equipment)} machines · {len(pairs)} comparisons · Reference → Test',
              fill=MUTED, font=small_font)

    positions = {}
    for site, label, x in [('OU', ou_label, left), ('RU', ru_label, right)]:
        draw.rounded_rectangle((x, 112, x + card_width, 151), radius=8,
                               fill='#E7EFFF' if site == 'OU' else '#E1F3F0')
        draw.text((x + card_width / 2, 131), fit_label(draw, label, name_font, card_width - 20),
                  fill=CORE if site == 'OU' else TEAL, font=name_font, anchor='mm')
        for row, machine in enumerate(by_site[site]):
            positions[machine['id']] = (x, top + row * step)

    # Separate ports keep multiple links from merging at the equipment card.
    ports = {}
    for machine, (x, y) in positions.items():
        incident = []
        for index, pair in enumerate(cross_site):
            ref, test = pair['reference'], pair['test']
            if machine in (ref, test):
                other = test if machine == ref else ref
                incident.append((pair['kind'] != 'Core', positions[other][1], index))
        count = len(incident)
        spacing = min(18, (card_height - 22) / max(1, count - 1))
        for rank, (_, _, index) in enumerate(sorted(incident)):
            ports[machine, index] = (x + card_width if x == left else x,
                                     y + card_height / 2 + (rank - (count - 1) / 2) * spacing)

    labels = []
    routes = []
    for index, pair in enumerate(cross_site):
        x1, y1 = ports[pair['reference'], index]
        x2, y2 = ports[pair['test'], index]
        lead = (x2 - x1) * .15
        color = CORE if pair['kind'] == 'Core' else CROSS
        points = [(x1, y1), (x1 + lead, y1), (x2 - lead, y2), (x2, y2)]
        routes.append((points, color))
        # Stagger labels on opposing routes so the center crossing remains clear.
        start, end = sorted(points[1:3])
        labels.append((pair['et'], color, start, end))

    for site, comparisons in within.items():
        x = left if site == 'OU' else right
        for index, pair in enumerate(comparisons):
            _, y1 = positions[pair['reference']]
            _, y2 = positions[pair['test']]
            if len(comparisons) == 1 and abs(y1 - y2) == step:
                center = x + card_width / 2
                start = (center, y1 + card_height if y1 < y2 else y1)
                end = (center, y2 if y1 < y2 else y2 + card_height)
                points = [start, end]
            else:
                edge = x if site == 'OU' else x + card_width
                lane = edge + (-1 if site == 'OU' else 1) * (34 + index * 34)
                start = (lane, y1 + card_height / 2)
                end = (lane, y2 + card_height / 2)
                points = [(edge, start[1]), start, end, (edge, end[1])]
            routes.append((points, WITHIN))
            labels.append((pair['et'], WITHIN, start, end))

    for points, color in routes:
        draw_route(draw, points, color)

    for site, machines in by_site.items():
        for machine in machines:
            x, y = positions[machine['id']]
            draw.rounded_rectangle((x, y, x + card_width, y + card_height),
                                   radius=12, fill='white', outline='#CDDCE8', width=2)
            draw.rounded_rectangle((x + 12, y + 11, x + 112, y + 121), radius=9, fill='#F1F5F9')
            photo = ImageOps.contain(equipment_thumbnail(machine['type'], photos.get(machine['id'])), (94, 106))
            image.paste(photo, (x + 62 - photo.width // 2, y + 66 - photo.height // 2))
            draw.text((x + 126, y + 43), fit_label(draw, machine['id'], name_font, card_width - 137),
                      font=name_font, fill=INK)
            draw.text((x + 126, y + 76), fit_label(draw, machine['type'], small_font, card_width - 137),
                      font=small_font, fill=MUTED)

    label_font = font(16, True)
    placed = []
    for text, color, start, end in labels:
        half_width = max(26, draw.textlength(text, font=label_font) / 2 + 9)
        fractions = (.28, .70, .43, .55, .12, .85) if color == CROSS else (.50, .28, .72, .12, .88)
        for fraction in fractions:
            cx = start[0] + (end[0] - start[0]) * fraction
            cy = start[1] + (end[1] - start[1]) * fraction
            box = (cx - half_width, cy - 14, cx + half_width, cy + 14)
            if all(box[2] + 4 < old[0] or old[2] + 4 < box[0]
                   or box[3] + 4 < old[1] or old[3] + 4 < box[1] for old in placed):
                break
        placed.append(box)
        draw.rounded_rectangle(box, radius=6, fill=WASH[color], outline=color, width=1)
        draw.text((cx, cy), text, font=label_font, fill=color, anchor='mm')

    x = 36
    for caption, color in [('Core transfer', CORE), ('Cross transfer', CROSS), ('Within site', WITHIN)]:
        y = height - 44
        draw.line((x, y, x + 24, y), fill=color, width=3)
        draw.text((x + 34, y), caption, fill=INK, font=small_font, anchor='lm')
        x += 34 + int(draw.textlength(caption, font=small_font)) + 28

    out = io.BytesIO()
    image.resize((width * 2, height * 2), Image.Resampling.LANCZOS).save(out, format='PNG', dpi=(300, 300))
    return out.getvalue()
