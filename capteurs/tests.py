import json
from unittest.mock import patch

import requests
from django.test import Client, TestCase, override_settings

from .models import AlertSettings, DHT11, Mesure, Piece


class DHT11ApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_add_last_and_all_endpoints(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            '/api/add/',
            data=json.dumps({'temperature': 25, 'humidite': 60}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DHT11.objects.count(), 1)
        self.assertEqual(Mesure.objects.count(), 1)
        self.assertTrue(Piece.objects.filter(nom='DHT11').exists())

        last_response = self.client.get('/api/last/')
        self.assertEqual(last_response.status_code, 200)
        self.assertEqual(last_response.json()['temperature'], 25.0)

        all_response = self.client.get('/api/all/')
        self.assertEqual(all_response.status_code, 200)
        self.assertEqual(len(all_response.json()), 1)

    def test_add_endpoint_accepts_url_without_trailing_slash(self):
        response = self.client.post(
            '/api/add',
            data=json.dumps({'temperature': 26, 'humidite': 61}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DHT11.objects.count(), 1)

    def test_add_endpoint_uses_piece_from_esp8266_payload(self):
        response = self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'Salon', 'temperature': 24, 'humidite': 58}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Piece.objects.filter(nom='Salon').exists())
        self.assertEqual(Mesure.objects.get().piece.nom, 'Salon')

    def test_legacy_mesure_endpoint_also_records_dht11(self):
        response = self.client.post(
            '/api/mesure/',
            data=json.dumps({'temperature': 21.5, 'humidite': 55}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DHT11.objects.count(), 1)
        self.assertEqual(Mesure.objects.count(), 1)

    def test_dashboard_filters_and_excel_export(self):
        salon = Piece.objects.create(nom='Salon')
        cuisine = Piece.objects.create(nom='Cuisine')
        Mesure.objects.create(piece=salon, temperature=31, humidite=55)
        Mesure.objects.create(piece=cuisine, temperature=22, humidite=60)

        dashboard_response = self.client.get('/', {'piece': salon.id})
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, 'Registre des mesures')
        self.assertContains(dashboard_response, '1 resultats')

        export_response = self.client.get('/export-excel/', {'piece': salon.id})
        self.assertEqual(export_response.status_code, 200)
        self.assertIn('text/csv', export_response['Content-Type'])
        content = export_response.content.decode('utf-8-sig')
        self.assertIn('BLOC OPERATOIRE', content)
        self.assertNotIn('BLOC REANIMATION', content)

    def test_user_can_update_temperature_alert_threshold(self):
        response = self.client.post(
            '/settings/alert-threshold/',
            data={'temperature_threshold': '24.5'},
            HTTP_REFERER='/',
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AlertSettings.load().temperature_threshold, 24.5)

        dashboard_response = self.client.get('/')
        self.assertContains(dashboard_response, 'Seuil 24,5')

    @override_settings(
        TELEGRAM_BOT_TOKEN='telegram-token',
        TELEGRAM_CHAT_ID='123456',
        ALERT_EMAIL_TO=[],
        TWILIO_ACCOUNT_SID='',
        TWILIO_AUTH_TOKEN='',
        TWILIO_WHATSAPP_FROM='',
        CALLMEBOT_API_KEY='VOTRE_CLE_API',
        TEMPERATURE_ALERT_THRESHOLD=26,
    )
    @patch('capteurs.alerts.requests.post')
    def test_saved_threshold_is_used_by_alert_agent(self, mock_post):
        alert_settings = AlertSettings.load()
        alert_settings.temperature_threshold = 24
        alert_settings.save()
        mock_post.return_value.raise_for_status.return_value = None

        self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'BlocSeuil', 'temperature': 23, 'humidite': 50}),
            content_type='application/json',
        )
        self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'BlocSeuil', 'temperature': 25, 'humidite': 50}),
            content_type='application/json',
        )

        self.assertTrue(mock_post.called)
        self.assertIn('Seuil: 24.0 C', mock_post.call_args.kwargs['data']['text'])

    @override_settings(
        TELEGRAM_BOT_TOKEN='telegram-token',
        TELEGRAM_CHAT_ID='123456',
        ALERT_EMAIL_TO=[],
        TWILIO_ACCOUNT_SID='',
        TWILIO_AUTH_TOKEN='',
        TWILIO_WHATSAPP_FROM='',
        CALLMEBOT_API_KEY='VOTRE_CLE_API',
        TEMPERATURE_ALERT_THRESHOLD=30,
    )
    @patch('capteurs.alerts.requests.post')
    def test_telegram_alert_is_sent_when_temperature_crosses_threshold(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None

        self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'Salon', 'temperature': 29, 'humidite': 50}),
            content_type='application/json',
        )
        self.assertFalse(mock_post.called)

        response = self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'Salon', 'temperature': 31, 'humidite': 52}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://api.telegram.org/bottelegram-token/sendMessage')
        self.assertEqual(kwargs['data']['chat_id'], '123456')
        self.assertIn('Salon', kwargs['data']['text'])
        self.assertIn('31.0 C', kwargs['data']['text'])
        self.assertIn('Agent IA', kwargs['data']['text'])

    @override_settings(
        TELEGRAM_BOT_TOKEN='',
        TELEGRAM_CHAT_ID='',
        ALERT_EMAIL_TO=['admin@example.com'],
        DEFAULT_FROM_EMAIL='iot@example.com',
        TWILIO_ACCOUNT_SID='',
        TWILIO_AUTH_TOKEN='',
        TWILIO_WHATSAPP_FROM='',
        CALLMEBOT_API_KEY='VOTRE_CLE_API',
        TEMPERATURE_ALERT_THRESHOLD=26,
    )
    @patch('capteurs.alerts.send_mail')
    def test_email_alert_is_sent_when_temperature_crosses_threshold(self, mock_send_mail):
        mock_send_mail.return_value = 1

        self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'BlocTest', 'temperature': 25, 'humidite': 50}),
            content_type='application/json',
        )
        self.assertFalse(mock_send_mail.called)

        response = self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'BlocTest', 'temperature': 27, 'humidite': 52}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        mock_send_mail.assert_called_once()
        kwargs = mock_send_mail.call_args.kwargs
        self.assertEqual(kwargs['recipient_list'], ['admin@example.com'])
        self.assertIn('27.0 C', kwargs['message'])
        self.assertIn('Suggestion:', kwargs['message'])

    @override_settings(
        ALERT_EMAIL_TO=[],
        TWILIO_ACCOUNT_SID='',
        TWILIO_AUTH_TOKEN='',
        TWILIO_WHATSAPP_FROM='',
        CALLMEBOT_API_KEY='test-key',
        WHATSAPP_PHONE='+212706199603',
        TEMPERATURE_ALERT_THRESHOLD=30,
    )
    @patch('capteurs.alerts.requests.get')
    def test_whatsapp_alert_is_sent_when_temperature_crosses_threshold(self, mock_get):
        mock_get.return_value.raise_for_status.return_value = None

        self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'Salon', 'temperature': 29, 'humidite': 50}),
            content_type='application/json',
        )
        self.assertFalse(mock_get.called)

        response = self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'Salon', 'temperature': 31, 'humidite': 52}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(mock_get.call_count, 1)
        params = mock_get.call_args.kwargs['params']
        self.assertEqual(params['phone'], '+212706199603')
        self.assertIn('Salon', params['text'])
        self.assertIn('31.0 C', params['text'])

    @override_settings(
        ALERT_EMAIL_TO=[],
        TWILIO_ACCOUNT_SID='',
        TWILIO_AUTH_TOKEN='',
        TWILIO_WHATSAPP_FROM='',
        CALLMEBOT_API_KEY='test-key',
        TEMPERATURE_ALERT_THRESHOLD=30,
    )
    @patch('capteurs.alerts.requests.get')
    def test_whatsapp_alert_is_not_repeated_while_temperature_stays_high(self, mock_get):
        mock_get.return_value.raise_for_status.return_value = None

        self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'Salon', 'temperature': 31, 'humidite': 52}),
            content_type='application/json',
        )
        self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'Salon', 'temperature': 32, 'humidite': 53}),
            content_type='application/json',
        )

        self.assertEqual(mock_get.call_count, 1)

    @override_settings(
        ALERT_EMAIL_TO=[],
        TWILIO_ACCOUNT_SID='AC123',
        TWILIO_AUTH_TOKEN='token',
        TWILIO_WHATSAPP_FROM='whatsapp:+14155238886',
        WHATSAPP_PHONE='+212706199603',
        TEMPERATURE_ALERT_THRESHOLD=30,
        CALLMEBOT_API_KEY='VOTRE_CLE_API',
    )
    @patch('capteurs.alerts.requests.post')
    def test_twilio_whatsapp_alert_is_sent_when_configured(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None

        response = self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'Salon', 'temperature': 31, 'humidite': 52}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        mock_post.assert_called_once()
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs['auth'], ('AC123', 'token'))
        self.assertEqual(kwargs['data']['From'], 'whatsapp:+14155238886')
        self.assertEqual(kwargs['data']['To'], 'whatsapp:+212706199603')
        self.assertIn('Salon', kwargs['data']['Body'])

    @override_settings(
        ALERT_EMAIL_TO=[],
        TWILIO_ACCOUNT_SID='AC123',
        TWILIO_AUTH_TOKEN='token',
        TWILIO_WHATSAPP_FROM='whatsapp:+14155238886',
        TWILIO_CONTENT_SID='HX123',
        WHATSAPP_PHONE='+212706199603',
        TEMPERATURE_ALERT_THRESHOLD=30,
        CALLMEBOT_API_KEY='VOTRE_CLE_API',
    )
    @patch('capteurs.alerts.requests.post')
    def test_twilio_content_template_is_used_when_configured(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None

        response = self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'Salon', 'temperature': 31, 'humidite': 52}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        data = mock_post.call_args.kwargs['data']
        self.assertEqual(data['ContentSid'], 'HX123')
        self.assertIn('ContentVariables', data)
        self.assertNotIn('Body', data)

    @override_settings(
        ALERT_EMAIL_TO=[],
        TWILIO_ACCOUNT_SID='AC123',
        TWILIO_AUTH_TOKEN='token',
        TWILIO_WHATSAPP_FROM='whatsapp:+14155238886',
        WHATSAPP_PHONE='+212706199603',
        TEMPERATURE_ALERT_THRESHOLD=30,
        CALLMEBOT_API_KEY='VOTRE_CLE_API',
    )
    @patch('capteurs.alerts.requests.post')
    def test_twilio_error_does_not_block_measure_recording(self, mock_post):
        mock_post.side_effect = requests.RequestException('Twilio unavailable')

        response = self.client.post(
            '/api/add/',
            data=json.dumps({'piece': 'Salon', 'temperature': 31, 'humidite': 52}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DHT11.objects.count(), 1)
        self.assertEqual(Mesure.objects.count(), 1)
