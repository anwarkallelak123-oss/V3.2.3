"""Shared branding for the app and report pages."""
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader

LOGO_PATH = Path(__file__).with_name('shl_medical_logo.png')
VARIANCE_COLORS = {
    'No evidence of unequal variances': ('#dcfce7', '#14532d'),
    'Evidence of unequal variances': ('#fee2e2', '#7f1d1d'),
    'Unavailable': ('#e5e7eb', '#374151'),
}


with Image.open(LOGO_PATH) as logo:
    visible_logo = ImageReader(logo.crop(logo.getchannel('A').getbbox()))
    logo_width, logo_height = visible_logo.getSize()


def draw_report_logo(canvas, doc):
    inset = 24
    height = 16
    width = height * logo_width / logo_height
    canvas.drawImage(visible_logo, inset, doc.pagesize[1] - inset - height,
                     width=width, height=height, mask='auto')
