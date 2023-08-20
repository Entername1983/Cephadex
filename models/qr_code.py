from PIL import Image
import base64
import qrcode
from io import BytesIO



def create_qr_code(link):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="#efe8ff")

    # Load your background image
    background = Image.open("static\Cephadex-logo-6.png")

    # Make background image the same size as the QR code
    background = background.resize(img_qr.size, Image.ANTIALIAS)

    # Convert images to RGBA to ensure compatibility
    img_qr = img_qr.convert("RGBA")

    # Apply transparency to QR code (0 to 255, 255 being fully opaque)
    img_qr.putalpha(150) 

    background = background.convert("RGBA")

    # Composite the QR code onto the background
    result = Image.alpha_composite(background, img_qr)

    # Save the result to a BytesIO object
    buffered = BytesIO()
    result.save(buffered, format="PNG")

    return base64.b64encode(buffered.getvalue()).decode()