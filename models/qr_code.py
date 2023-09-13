from PIL import Image
import base64
import qrcode
from io import BytesIO
import os
from models.helpers.log_decorators import log_decorator

@log_decorator
def create_qr_code(link: str) -> str:
    """ Creates a qr code used for sharing decks, uses a faded version of Cephadex logo as background"""
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="#efe8ff")
    image_path = os.path.join('static', 'Cephadex-logo-6.png')
    background = Image.open(image_path)
    background = background.resize(img_qr.size, Image.ANTIALIAS)
    img_qr = img_qr.convert("RGBA")
    img_qr.putalpha(150) 
    background = background.convert("RGBA")
    result = Image.alpha_composite(background, img_qr)
    buffered = BytesIO()
    result.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()