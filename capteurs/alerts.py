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


def send_temperature_alert(mesure, previous_mesure=None):
    previous_temperature = previous_mesure.temperature if previous_mesure else None
    if not should_send_temperature_alert(mesure.temperature, previous_temperature):
        return False

    api_key = settings.CALLMEBOT_API_KEY
    if not api_key or api_key == 'VOTRE_CLE_API':
        logger.warning('Alerte WhatsApp ignoree: CALLMEBOT_API_KEY non configuree.')
        return False

    message = (
        f"Alerte IoT: temperature seuil depassee dans {mesure.piece.nom}. "
        f"Temperature: {_format_value(mesure.temperature, ' C')}. "
        f"Seuil: {settings.TEMPERATURE_ALERT_THRESHOLD:.1f} C. "
        f"Humidite: {_format_value(mesure.humidite, '%')}."
    )

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
        logger.info('Alerte WhatsApp envoyee pour la mesure %s.', mesure.id)
        return True
    except requests.RequestException:
        logger.exception('Erreur pendant l envoi de l alerte WhatsApp.')
        return False
