from rest_framework import serializers

from .models import DHT11


class DHT11Serializer(serializers.ModelSerializer):
    piece = serializers.CharField(required=False, write_only=True, default='DHT11')

    class Meta:
        model = DHT11
        fields = ['temperature', 'humidite', 'date', 'piece']
        read_only_fields = ['date']

    def create(self, validated_data):
        piece = validated_data.pop('piece', 'DHT11')
        instance = super().create(validated_data)
        instance.piece_nom = piece
        return instance
