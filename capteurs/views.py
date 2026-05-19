import json
import logging
import csv
from datetime import datetime, timedelta

from django.db.models import Avg, Max, Min
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .api import sync_mesure_from_dht11
from .models import DHT11, Mesure, Piece

logger = logging.getLogger(__name__)

PIECE_DISPLAY_NAMES = {
    'DHT11': 'BLOC 1',
    'Salon': 'BLOC OPERATOIRE',
    'Cuisine': 'BLOC REANIMATION',
}


def _display_piece_name(piece):
    return PIECE_DISPLAY_NAMES.get(piece.nom, piece.nom)


def _parse_filter_date(value, end_of_day=False):
    if not value:
        return None

    try:
        parsed = datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        return None

    if end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return timezone.make_aware(parsed)


def _filtered_measure_queryset(request):
    date_debut = request.GET.get('date_debut', '').strip()
    date_fin = request.GET.get('date_fin', '').strip()
    piece_id = request.GET.get('piece', '').strip()

    queryset = Mesure.objects.select_related('piece').all()

    start = _parse_filter_date(date_debut)
    end = _parse_filter_date(date_fin, end_of_day=True)

    if start:
        queryset = queryset.filter(timestamp__gte=start)
    if end:
        queryset = queryset.filter(timestamp__lte=end)
    if piece_id:
        queryset = queryset.filter(piece_id=piece_id)

    filters = {
        'date_debut': date_debut,
        'date_fin': date_fin,
        'piece': piece_id,
    }
    return queryset, filters


def _sample_for_chart(mesures, limit=60):
    if len(mesures) <= limit:
        return mesures

    step = max(1, len(mesures) // limit)
    sampled = mesures[::step]
    return sampled[-limit:]


def dashboard(request):
    pieces = Piece.objects.all().order_by('nom')
    for piece in pieces:
        piece.display_nom = _display_piece_name(piece)

    mesures_filtrees, filters = _filtered_measure_queryset(request)

    dernieres_mesures = []
    for piece in pieces:
        derniere = Mesure.objects.filter(piece=piece).order_by('-timestamp').first()
        if derniere:
            dernieres_mesures.append({
                'piece': piece,
                'piece_display': _display_piece_name(piece),
                'temperature': derniere.temperature,
                'humidite': derniere.humidite,
                'timestamp': derniere.timestamp,
            })

    if not any(filters.values()):
        periode_stats = mesures_filtrees.filter(timestamp__gte=timezone.now() - timedelta(hours=24))
    else:
        periode_stats = mesures_filtrees

    stats = periode_stats.aggregate(
        temp_moy=Avg('temperature'),
        temp_max=Max('temperature'),
        temp_min=Min('temperature'),
        hum_moy=Avg('humidite'),
        hum_max=Max('humidite'),
        hum_min=Min('humidite'),
    )

    chart_mesures = _sample_for_chart(list(periode_stats.order_by('timestamp')))
    chart_labels = [mesure.timestamp.strftime('%d/%m %H:%M') for mesure in chart_mesures]
    chart_categories = [mesure.timestamp.isoformat() for mesure in chart_mesures]
    chart_temperature = [mesure.temperature for mesure in chart_mesures]
    chart_humidite = [mesure.humidite for mesure in chart_mesures]

    mesures_recentes = list(periode_stats.order_by('-timestamp')[:25])
    for mesure in mesures_recentes:
        mesure.piece_display = _display_piece_name(mesure.piece)

    derniere_mesure_globale = Mesure.objects.select_related('piece').order_by('-timestamp').first()
    if derniere_mesure_globale:
        derniere_mesure_globale.piece_display = _display_piece_name(derniere_mesure_globale.piece)

    context = {
        'pieces': pieces,
        'filters': filters,
        'dernieres_mesures': dernieres_mesures,
        'mesures_recentes': mesures_recentes,
        'derniere_mesure_globale': derniere_mesure_globale,
        'stats': stats,
        'total_mesures': Mesure.objects.count(),
        'filtered_total': periode_stats.count(),
        'chart_labels': chart_labels,
        'chart_labels_json': json.dumps(chart_labels),
        'chart_categories_json': json.dumps(chart_categories),
        'chart_temperature_json': json.dumps(chart_temperature),
        'chart_humidite_json': json.dumps(chart_humidite),
        'query_string': request.GET.urlencode(),
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


def export_excel(request):
    mesures, filters = _filtered_measure_queryset(request)
    if not any(filters.values()):
        mesures = mesures.filter(timestamp__gte=timezone.now() - timedelta(hours=24))

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="mesures-iot.csv"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Piece',
        'Temperature (C)',
        'Humidite (%)',
        'Date',
        'Heure',
    ])

    for mesure in mesures.order_by('-timestamp'):
        local_time = timezone.localtime(mesure.timestamp)
        writer.writerow([
            _display_piece_name(mesure.piece),
            _format_stat(mesure.temperature),
            _format_stat(mesure.humidite),
            local_time.strftime('%d/%m/%Y'),
            local_time.strftime('%H:%M:%S'),
        ])

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
        dht11.piece_nom = data.get('piece') or 'DHT11'
        mesure = sync_mesure_from_dht11(dht11)

        return JsonResponse({'status': 'ok', 'id': dht11.id, 'mesure_id': mesure.id})
    except Exception as exc:
        logger.exception('Erreur pendant la reception de la mesure')
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
