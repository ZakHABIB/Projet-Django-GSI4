# Deploiement PythonAnywhere

Ce projet est pret pour PythonAnywhere avec Django, SQLite et l'API ESP8266.

## 1. Envoyer le projet sur PythonAnywhere

Option simple: compresser ce dossier puis l'envoyer dans l'onglet **Files** de PythonAnywhere.

Option Git:

```bash
git clone https://github.com/votre-compte/projet-iot-django-main.git
cd projet-iot-django-main
```

Le dossier important est celui qui contient `manage.py`.

## 2. Creer l'environnement Python

Dans une console Bash PythonAnywhere:

```bash
cd ~/projet-iot-django-main
mkvirtualenv --python=/usr/bin/python3.10 projet-iot-env
pip install -r requirements.txt
```

## 3. Initialiser la base de donnees

SQLite suffit pour ce TP. La base sera creee dans `db.sqlite3`.

```bash
cd ~/projet-iot-django-main
python manage.py migrate
python manage.py createsuperuser
```

## 4. Configurer l'application Web

Dans l'onglet **Web** de PythonAnywhere:

- Add a new web app
- Choisir **Manual configuration**
- Choisir la meme version Python que le virtualenv
- Virtualenv: `/home/VOTRE_USER/.virtualenvs/projet-iot-env`
- Source code: `/home/VOTRE_USER/projet-iot-django-main`
- Working directory: `/home/VOTRE_USER/projet-iot-django-main`

## 5. Configurer le fichier WSGI

Dans le fichier WSGI indique par PythonAnywhere, remplacer `VOTRE_USER`:

```python
import os
import sys

path = '/home/VOTRE_USER/projet-iot-django-main'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DJANGO_DEBUG'] = 'False'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'VOTRE_USER.pythonanywhere.com'
os.environ['DJANGO_CSRF_TRUSTED_ORIGINS'] = 'https://VOTRE_USER.pythonanywhere.com'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Puis cliquer sur **Reload** dans l'onglet Web.

## 6. Fichiers statiques

Dans une console Bash:

```bash
cd ~/projet-iot-django-main
python manage.py collectstatic --noinput
```

Dans l'onglet **Web**, section **Static files**:

- URL: `/static/`
- Directory: `/home/VOTRE_USER/projet-iot-django-main/staticfiles`

## 7. Tester l'API

Remplacer `VOTRE_USER`:

```bash
curl -X POST https://VOTRE_USER.pythonanywhere.com/api/add/ -H "Content-Type: application/json" -d '{"temperature":25,"humidite":60}'
curl https://VOTRE_USER.pythonanywhere.com/api/last/
curl https://VOTRE_USER.pythonanywhere.com/api/all/
```

## 8. Lier l'ESP8266

Ouvrir:

```text
arduino/projet_iot_esp8266/projet_iot_esp8266.ino
```

Modifier:

```cpp
const char* ssid = "NOM_WIFI";
const char* password = "MOT_DE_PASSE_WIFI";
String serverName = "https://VOTRE_USER.pythonanywhere.com/api/add/";
```

Bibliotheques Arduino necessaires:

- ESP8266 board package
- DHT sensor library
- Adafruit Unified Sensor

Ensuite televerser le sketch vers l'ESP8266 et ouvrir le moniteur serie a `115200`.
