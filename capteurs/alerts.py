import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _format_value(value, unit):
    if value is None:
        return f'--{unit}'
    return f'{value:.1f}{unit}'


def should_send_temperature_alert(current_temperature, previous_temperature=None):
    if current_temperature is None:
        return False

    threshold = settings.TEMPERATURE_ALERT_THRESHOLD
    if current_temperature < threshold:
        return False

    return previous_temperature is None or previous_temperature < threshold


def build_temperature_alert_message(mesure):
    return (
        f"Alerte IoT: temperature seuil depassee dans {mesure.piece.nom}. "
        f"Temperature: {_format_value(mesure.temperature, ' C')}. "
        f"Seuil: {settings.TEMPERATURE_ALERT_THRESHOLD:.1f} C. "
        f"Humidite: {_format_value(mesure.humidite, '%')}."
    )


def send_twilio_whatsapp(message):
    if not all([
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN,
        settings.TWILIO_WHATSAPP_FROM,
    ]):
        return False

    try:
        response = requests.post(
            (
                'https://api.twilio.com/2010-04-01/Accounts/'
                f'{settings.TWILIO_ACCOUNT_SID}/Messages.json'
            ),
            data={
                'Body': message,
                'From': settings.TWILIO_WHATSAPP_FROM,
                'To': f'whatsapp:{settings.WHATSAPP_PHONE}',
            },
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            timeout=10,
        )
        response.raise_for_status()
        logger.info('Alerte WhatsApp envoyee avec Twilio.')
        return True
    except requests.RequestException:
        logger.exception('Erreur pendant l envoi de l alerte WhatsApp avec Twilio.')
        return False


def send_callmebot_whatsapp(message):
    api_key = settings.CALLMEBOT_API_KEY
    if not api_key or api_key == 'VOTRE_CLE_API':
        return False

    try:
        response = requests.get(
            settings.CALLMEBOT_WHATSAPP_URL,
            params={
                'phone': settings.WHATSAPP_PHONE,
                'text': message,
                'apikey': api_key,
            },
            timeout=10,
        )
        response.raise_for_status()
        logger.info('Alerte WhatsApp envoyee avec CallMeBot.')
        return True
    except requests.RequestException:
        logger.exception('Erreur pendant l envoi de l alerte WhatsApp avec CallMeBot.')
        return False


def send_temperature_alert(mesure, previous_mesure=None):
    previous_temperature = previous_mesure.temperature if previous_mesure else None
    if not should_send_temperature_alert(mesure.temperature, previous_temperature):
        return False

    message = build_temperature_alert_message(mesure)

    if send_twilio_whatsapp(message):
        return True

    if send_callmebot_whatsapp(message):
        return True

    logger.warning('Alerte WhatsApp ignoree: aucun fournisseur WhatsApp configure.')
    return False
