import json

from django.test import Client, TestCase

from .models import DHT11, Mesure, Piece


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
