from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
import logging
import logging.handlers


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

SEND_GRID_KEY = os.environ.get("SEND_GRID_KEY")

def send_email( recipients, first_name, template_name,
                subject = None, text_body = None,
                html_body = None, sender = None, payload = None):
    
    email_template = {
        'deck_ready': 'd-29696fa7e9e84eb7a81d04491e24e212',
        'welcome': 'd-35f9b384cd83460eac6601895e36a645',
        'upgrade': 'd-58efdfc3c4f14794ab83629b10d2f1b0',
    }
    message = Mail(
        from_email='cephadex@cephadex.com',
        to_emails=recipients,
        subject=subject,
        html_content=html_body)
    message.template_id = email_template[template_name]
    message.dynamic_template_data = {
        'First_Name': first_name,
        'Sender_Name': 'Cephadex Limited',
        'Sender_Address': 'UNIT 4 FIRST FLOOR, 84 STRAND STREET',
        'Sender_City': 'SKERRIES',
        'Sender_County': 'DUBLIN',
        'Sender_Postcode': 'K34 VW93',
    }
    try:
        sg = SendGridAPIClient(SEND_GRID_KEY)
        response = sg.send(message)
        print(response.status_code)
    except Exception as e:
        logging.error("Error sending email %s", e)
        print(e.message)