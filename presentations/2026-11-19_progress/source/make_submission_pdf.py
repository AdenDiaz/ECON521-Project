"""Make the submission PDF from visually validated high-resolution slide renders.

Usage: python make_submission_pdf.py RENDER_DIRECTORY OUTPUT.pdf
The companion PPTX keeps all text, tables and charts editable.
"""
import sys
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image
from pypdf import PdfReader

source=Path(sys.argv[1]);target=Path(sys.argv[2])
slides=[source/f'slide-{i}.png' for i in range(1,13)]
assert all(x.is_file() for x in slides)
assert all(Image.open(x).size==(2560,1440) for x in slides)
c=canvas.Canvas(str(target),pagesize=(960,540),pageCompression=1)
c.setTitle('ECON521 Research Progress: Fan Attendance and Home-Team Performance')
c.setAuthor('Aden Diaz')
c.setSubject('12-slide preliminary research update; source main@51c94a98731180e5be3415892c6846a0590f0250')
for slide in slides:
    c.drawImage(ImageReader(str(slide)),0,0,width=960,height=540)
    c.showPage()
c.save()
assert len(PdfReader(target).pages)==12
print(f'Wrote {target}: 12 pages, 16:9, 192 dpi slide evidence.')
