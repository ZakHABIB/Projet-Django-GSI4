from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import DHT11, Mesure, Piece
from .serializers import DHT11Serializer


def sync_mesure_from_dht11(dht11):
    piece, _ = Piece.objects.get_or_create(nom='DHT11')
    Mesure.objects.create(
        piece=piece,
        temperature=dht11.temperature,
        humidite=dht11.humidite,
        timestamp=dht11.date,
    )


@api_view(['GET'])
def liste_mesures(request):
    mesures = DHT11.objects.all().order_by('-date')
    serializer = DHT11Serializer(mesures, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def derniere_mesure(request):
    mesure = DHT11.objects.order_by('-date').first()
    if mesure is None:
        return Response({'message': 'Aucune donnee'})
    serializer = DHT11Serializer(mesure)
    return Response(serializer.data)


class AjouterMesure(generics.CreateAPIView):
    queryset = DHT11.objects.all()
    serializer_class = DHT11Serializer

    def perform_create(self, serializer):
        dht11 = serializer.save()
        sync_mesure_from_dht11(dht11)
