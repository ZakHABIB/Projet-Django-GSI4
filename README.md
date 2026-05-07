# projet-iot-django

Application Django de monitoring IoT pour capteur DHT11 avec ESP8266.

## Fonctionnalites du TP

- Enregistrer les mesures de temperature et d'humidite dans SQLite.
- Afficher les dernieres mesures dans un dashboard web.
- Fournir une API REST pour l'ESP8266.
- Consulter les mesures dans l'interface d'administration Django.

## Routes principales

- Dashboard web: `http://127.0.0.1:8000/`
- Admin Django: `http://127.0.0.1:8000/admin/`
- Toutes les mesures: `GET /api/all/`
- Derniere mesure: `GET /api/last/`
- Ajouter une mesure: `POST /api/add/`

Exemple de test:

```bash
curl -X POST http://127.0.0.1:8000/api/add/ -H "Content-Type: application/json" -d "{\"temperature\":25,\"humidite\":60}"
```

## PythonAnywhere et ESP8266

- Guide de deploiement: `docs/PYTHONANYWHERE.md`
- Sketch Arduino ESP8266: `arduino/projet_iot_esp8266/projet_iot_esp8266.ino`

## Lancer le projet

```bash
venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```
