from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
from models.helpers.log_decorators import log_decorator, subrollover_log_decorator
import logging


logger = logging.getLogger("subrollover")
@log_decorator
def send_email( recipients, first_name, template_name,
                subject = None, text_body = None,
                html_body = None, sender = None, payload = None, link = None, api_key = None):
    SEND_GRID_KEY = os.environ.get("SEND_GRID_KEY")

    if SEND_GRID_KEY is None:
        SEND_GRID_KEY = api_key
    email_template = {
        'deck_ready': 'd-29696fa7e9e84eb7a81d04491e24e212',
        'welcome': 'd-35f9b384cd83460eac6601895e36a645',
        'upgrade': 'd-58efdfc3c4f14794ab83629b10d2f1b0',
        'deck_shared': 'd-b878423ea0304bd2a70c21cbe9129b75',
        'test_shared': 'd-0b0b6b0b0b0b0b0b0b0b0b0b0b0b0b0b',
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
        'link': link,
    }
    try:
        sg = SendGridAPIClient(SEND_GRID_KEY)
        sg.send(message)
    except Exception as e:
        logger.error(f"Failed to send email {template_name}: {e}")

@subrollover_log_decorator
def send_email_report(recipient, body, api_key = None):
    SEND_GRID_KEY = os.environ.get("SEND_GRID_KEY")
    if SEND_GRID_KEY is None:
        SEND_GRID_KEY = api_key
    message = Mail(
        from_email='cephadex@cephadex.com',
        to_emails=recipient,
        subject = 'Cephadex daily report',
        plain_text_content = body)
    try: 
        sg = SendGridAPIClient(SEND_GRID_KEY)
        sg.send(message)
    except Exception as e:
        logger.error(f"Failed to send daily report email: {e}")