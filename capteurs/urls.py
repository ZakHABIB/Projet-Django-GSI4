from django.urls import path

from . import views
from .api import AjouterMesure, derniere_mesure, liste_mesures

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('export-pdf/', views.export_pdf, name='export_pdf'),
    path('export-excel/', views.export_excel, name='export_excel'),
    path('api/all/', liste_mesures, name='liste_mesures'),
    path('api/last/', derniere_mesure, name='derniere_mesure'),
    path('api/add', AjouterMesure.as_view(), name='ajouter_mesure_no_slash'),
    path('api/add/', AjouterMesure.as_view(), name='ajouter_mesure'),
    path('api/mesure', views.recevoir_mesure, name='recevoir_mesure_no_slash'),
    path('api/mesure/', views.recevoir_mesure, name='recevoir_mesure'),
]
