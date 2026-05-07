import json
import logging
from datetime import datetime, timedelta

from django.db.models import Avg, Max, Min
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .api import sync_mesure_from_dht11
from .models import DHT11, Mesure, Piece

logger = logging.getLogger(__name__)


def dashboard(request):
    pieces = Piece.objects.all()

    dernieres_mesures = []
    for piece in pieces:
        derniere = Mesure.objects.filter(piece=piece).order_by('-timestamp').first()
        if derniere:
            dernieres_mesures.append({
                'piece': piece,
                'temperature': derniere.temperature,
                'humidite': derniere.humidite,
                'timestamp': derniere.timestamp,
            })

    hier = timezone.now() - timedelta(hours=24)
    stats = Mesure.objects.filter(timestamp__gte=hier).aggregate(
        temp_moy=Avg('temperature'),
        temp_max=Max('temperature'),
        temp_min=Min('temperature'),
        hum_moy=Avg('humidite'),
    )

    mesures_24h = Mesure.objects.filter(timestamp__gte=hier).order_by('timestamp')
    chart_labels = []
    chart_data = []

    for compteur, mesure in enumerate(mesures_24h):
        if compteur % 6 == 0:
            chart_labels.append(mesure.timestamp.strftime('%H:%M'))
            chart_data.append(mesure.temperature)

    if len(chart_labels) > 12:
        chart_labels = chart_labels[-12:]
        chart_data = chart_data[-12:]

    context = {
        'dernieres_mesures': dernieres_mesures,
        'stats': stats,
        'total_mesures': Mesure.objects.count(),
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    }

    return render(request, 'capteurs/dashboard.html', context)


def _stats_24h():
    hier = timezone.now() - timedelta(hours=24)
    return Mesure.objects.filter(timestamp__gte=hier).aggregate(
        temp_moy=Avg('temperature'),
        temp_max=Max('temperature'),
        temp_min=Min('temperature'),
        hum_moy=Avg('humidite'),
    )


def _format_stat(value):
    return f'{value:.1f}' if value is not None else '--'


def _plain_pdf(lines):
    """Create a small valid PDF without external dependencies."""
    escaped_lines = [
        line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        for line in lines
    ]
    text_commands = ['BT', '/F1 12 Tf', '50 790 Td', '16 TL']
    for index, line in enumerate(escaped_lines):
        if index:
            text_commands.append('T*')
        text_commands.append(f'({line}) Tj')
    text_commands.append('ET')
    stream = '\n'.join(text_commands).encode('latin-1', errors='replace')

    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
        b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream',
    ]

    pdf = bytearray(b'%PDF-1.4\n')
    offsets = []
    for number, content in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f'{number} 0 obj\n'.encode())
        pdf.extend(content)
        pdf.extend(b'\nendobj\n')

    xref_offset = len(pdf)
    pdf.extend(f'xref\n0 {len(objects) + 1}\n'.encode())
    pdf.extend(b'0000000000 65535 f \n')
    for offset in offsets:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode())
    pdf.extend(
        f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
        f'startxref\n{xref_offset}\n%%EOF\n'.encode()
    )
    return bytes(pdf)


def export_pdf(request):
    stats = _stats_24h()
    lines = [
        'Rapport IoT Dashboard',
        f'Genere le: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        '',
        'Statistiques des dernieres 24h',
        f'Temperature moyenne: {_format_stat(stats["temp_moy"])} C',
        f'Temperature max: {_format_stat(stats["temp_max"])} C',
        f'Temperature min: {_format_stat(stats["temp_min"])} C',
        f'Humidite moyenne: {_format_stat(stats["hum_moy"])} %',
    ]

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        import io

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        pdf.setFont('Helvetica-Bold', 20)
        pdf.drawString(50, height - 50, lines[0])

        pdf.setFont('Helvetica', 12)
        y = height - 80
        for line in lines[1:]:
            pdf.drawString(50, y, line)
            y -= 20

        pdf.showPage()
        pdf.save()
        content = buffer.getvalue()
    except ImportError:
        content = _plain_pdf(lines)
    except Exception:
        logger.exception('Erreur pendant la generation du PDF')
        return HttpResponse('Erreur pendant la generation du PDF.', status=500)

    response = HttpResponse(content, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="rapport-iot.pdf"'
    return response


@csrf_exempt
def recevoir_mesure(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Methode non autorisee'}, status=405)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON invalide'}, status=400)

    try:
        dht11 = DHT11.objects.create(
            temperature=data.get('temperature'),
            humidite=data.get('humidite'),
        )
        sync_mesure_from_dht11(dht11)

        piece_nom = data.get('piece')
        if not piece_nom or piece_nom == 'DHT11':
            return JsonResponse({'status': 'ok', 'id': dht11.id})

        piece, _ = Piece.objects.get_or_create(nom=piece_nom)

        mesure = Mesure.objects.create(
            piece=piece,
            temperature=data.get('temperature'),
            humidite=data.get('humidite'),
            timestamp=timezone.now(),
        )

        return JsonResponse({'status': 'ok', 'id': dht11.id, 'mesure_id': mesure.id})
    except Exception as exc:
        logger.exception('Erreur pendant la reception de la mesure')
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
