from django.db import models
from django.utils import timezone


class Piece(models.Model):
    nom = models.CharField(max_length=50)

    def __str__(self):
        return self.nom


class Mesure(models.Model):
    piece = models.ForeignKey(Piece, on_delete=models.CASCADE)
    temperature = models.FloatField(null=True, blank=True)
    humidite = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.piece} - {self.temperature} C"

    class Meta:
        ordering = ['-timestamp']


class DHT11(models.Model):
    temperature = models.FloatField()
    humidite = models.FloatField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"T={self.temperature} H={self.humidite}"

    class Meta:
        ordering = ['-date']


class AlertSettings(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    temperature_threshold = models.FloatField(default=26)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls, default_threshold=26):
        settings_obj, _created = cls.objects.get_or_create(
            singleton_key=1,
            defaults={'temperature_threshold': default_threshold},
        )
        return settings_obj

    def __str__(self):
        return f"Seuil temperature: {self.temperature_threshold} C"
