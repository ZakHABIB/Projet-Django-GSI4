import json

from django.test import Client, TestCase

from .models import DHT11, Mesure, Piece


class DHT11ApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_add_last_and_all_endpoints(self):
        response = self.client.post(
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

    def test_legacy_mesure_endpoint_also_records_dht11(self):
        response = self.client.post(
            '/api/mesure/',
            data=json.dumps({'temperature': 21.5, 'humidite': 55}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DHT11.objects.count(), 1)
        self.assertEqual(Mesure.objects.count(), 1)
