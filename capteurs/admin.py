from django.contrib import admin

from .models import DHT11, Mesure, Piece


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    list_display = ['nom']


@admin.register(Mesure)
class MesureAdmin(admin.ModelAdmin):
    list_display = ['piece', 'temperature', 'humidite', 'timestamp']
    list_filter = ['piece', 'timestamp']


@admin.register(DHT11)
class DHT11Admin(admin.ModelAdmin):
    list_display = ['temperature', 'humidite', 'date']
    list_filter = ['date']
