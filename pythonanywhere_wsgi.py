import os
import sys

USERNAME = 'VOTRE_USER'
PROJECT_PATH = f'/home/{USERNAME}/projet-iot-django-main'

if PROJECT_PATH not in sys.path:
    sys.path.insert(0, PROJECT_PATH)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DJANGO_DEBUG'] = 'False'
os.environ['DJANGO_ALLOWED_HOSTS'] = f'{USERNAME}.pythonanywhere.com'
os.environ['DJANGO_CSRF_TRUSTED_ORIGINS'] = f'https://{USERNAME}.pythonanywhere.com'

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
