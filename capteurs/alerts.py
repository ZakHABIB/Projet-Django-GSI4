import logging
import json

import requests
from django.conf import settings
from django.core.mail import send_mail

from .models import AlertSettings

logger = logging.getLogger(__name__)


def _format_value(value, unit):
    if value is None:
        return f'--{unit}'
    return f'{value:.1f}{unit}'


def get_temperature_threshold():
    return AlertSettings.load(settings.TEMPERATURE_ALERT_THRESHOLD).temperature_threshold


def should_send_temperature_alert(current_temperature, previous_temperature=None):
    if current_temperature is None:
        return False

    threshold = get_temperature_threshold()
    if current_temperature < threshold:
        return False

    return previous_temperature is None or previous_temperature < threshold


def build_temperature_ai_report(mesure, previous_mesure=None):
    current = mesure.temperature
    previous = previous_mesure.temperature if previous_mesure else None
    humidity = mesure.humidite
    threshold = get_temperature_threshold()

    if current is None:
        return {
            'title': 'Analyse IA indisponible',
            'trend': 'Aucune temperature exploitable pour cette mesure.',
            'suggestion': 'Verifier le capteur et relancer une mesure.',
        }

    if previous is None:
        trend = 'Premiere mesure exploitable pour cette zone.'
        delta_text = 'variation non disponible'
    else:
        delta = current - previous
        delta_text = f'{delta:+.1f} C'
        if delta >= 1:
            trend = f'Hausse rapide de la temperature ({delta_text}).'
        elif delta <= -1:
            trend = f'Baisse notable de la temperature ({delta_text}).'
        else:
            trend = f'Temperature globalement stable ({delta_text}).'

    if current >= threshold + 4:
        suggestion = (
            'Action urgente: verifier climatisation, portes du bloc, flux d air '
            'et presence de sources de chaleur.'
        )
    elif current >= threshold:
        suggestion = (
            'Surveillance renforcee: controler la climatisation et limiter les ouvertures '
            'jusqu au retour sous le seuil.'
        )
    elif humidity is not None and humidity >= 70:
        suggestion = 'Humidite elevee: verifier ventilation et renouvellement d air.'
    else:
        suggestion = 'Situation acceptable: continuer la surveillance automatique.'

    return {
        'title': 'Agent IA - analyse environnement clinique',
        'trend': trend,
        'suggestion': suggestion,
        'delta': delta_text,
    }


def build_temperature_alert_message(mesure, previous_mesure=None):
    ai_report = build_temperature_ai_report(mesure, previous_mesure)
    return (
        f"Alerte IoT clinique: temperature seuil depassee dans {mesure.piece.nom}. "
        f"Temperature: {_format_value(mesure.temperature, ' C')}. "
        f"Seuil: {get_temperature_threshold():.1f} C. "
        f"Humidite: {_format_value(mesure.humidite, '%')}.\n"
        f"{ai_report['title']}\n"
        f"Variation: {ai_report['trend']}\n"
        f"Suggestion: {ai_report['suggestion']}"
    )


def send_telegram_alert(message):
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return False

    try:
        response = requests.post(
            f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage',
            data={
                'chat_id': settings.TELEGRAM_CHAT_ID,
                'text': message,
            },
            timeout=10,
        )
        response.raise_for_status()
        logger.info('Alerte envoyee avec Telegram.')
        return True
    except Exception:
        logger.exception('Erreur pendant l envoi de l alerte Telegram.')
        return False


def send_email_alert(message):
    recipients = settings.ALERT_EMAIL_TO
    if not recipients:
        return False

    try:
        send_mail(
            subject='Alerte temperature clinique IoT',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        logger.info('Alerte envoyee par email.')
        return True
    except Exception:
        logger.exception('Erreur pendant l envoi de l alerte email.')
        return False


def build_twilio_content_variables(mesure):
    return json.dumps({
        '1': mesure.piece.nom,
        '2': _format_value(mesure.temperature, ' C'),
    })


def send_twilio_whatsapp(message, mesure=None):
    if not all([
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN,
        settings.TWILIO_WHATSAPP_FROM,
    ]):
        return False

    data = {
        'From': settings.TWILIO_WHATSAPP_FROM,
        'To': f'whatsapp:{settings.WHATSAPP_PHONE}',
    }

    if settings.TWILIO_CONTENT_SID:
        data['ContentSid'] = settings.TWILIO_CONTENT_SID
        if mesure is not None:
            data['ContentVariables'] = build_twilio_content_variables(mesure)
    else:
        data['Body'] = message

    try:
        response = requests.post(
            (
                'https://api.twilio.com/2010-04-01/Accounts/'
                f'{settings.TWILIO_ACCOUNT_SID}/Messages.json'
            ),
            data=data,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            timeout=10,
        )
        response.raise_for_status()
        logger.info('Alerte WhatsApp envoyee avec Twilio.')
        return True
    except Exception:
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

    message = build_temperature_alert_message(mesure, previous_mesure)

    try:
        sent = False
        if send_telegram_alert(message):
            sent = True

        if send_email_alert(message):
            sent = True

        if send_twilio_whatsapp(message, mesure):
            sent = True

        if send_callmebot_whatsapp(message):
            sent = True

        if not sent:
            logger.warning('Alerte ignoree: aucun fournisseur de notification configure.')
        return sent
    except Exception:
        logger.exception('Erreur inattendue pendant le traitement de l alerte.')
        return False
