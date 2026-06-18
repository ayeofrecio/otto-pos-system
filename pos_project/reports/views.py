"""
reports/views.py

Thin views — all data assembly is delegated to service modules.
WeasyPrint renders HTML templates to PDF and streams the response.
"""

from django.http import HttpResponse, Http404
from django.utils import timezone
from django.contrib.auth.decorators import login_required

# from weasyprint import HTML

from users.models import POSSession
from .services.series_report import build_series_report

from .pdf.series_pdf import build_series_pdf
 
# ---------------------------------------------------------------------------
# Allowed paper sizes — maps query param → CSS @page token
# ---------------------------------------------------------------------------
# PAPER_SIZES = {
#     "a4":     "a4",
#     "long":   "long",     # 13in × 8.5in (legal)
#     "letter": "letter",
# }
VALID_PAPERS = {"a4", "letter", "long"}


DEFAULT_PAPER = "a4"


# ---------------------------------------------------------------------------
# Series Report
# ---------------------------------------------------------------------------

# @login_required
# def series_report(request):
#     """
#     GET /reports/series/?session_id=<id>&paper=<a4|long|letter>

#     Generates and streams a PDF Series Sales Report for the given session.
#     All transactions linked to the session are included, with void-type
#     transactions excluded.
#     """

#     # -- Validate session_id param --
#     session_id = request.GET.get("session_id", "").strip()
#     if not session_id or not session_id.isdigit():
#         raise Http404("A valid session_id is required.")

#     # -- Validate paper param --
#     paper = PAPER_SIZES.get(request.GET.get("paper", "").lower(), DEFAULT_PAPER)

#     # -- Build report data --
#     try:
#         context = build_series_report(int(session_id))
#     except POSSession.DoesNotExist:
#         raise Http404(f"Session {session_id} not found.")
#     except Exception as exc:
#         # Surface config errors (missing TerminalConfiguration, etc.) clearly
#         raise Http404(str(exc))

#     # -- Inject template-only values --
#     context["paper"] = paper
#     context["now"] = timezone.now()

#     # -- Render HTML → PDF --
#     html_string = render_to_string("reports/series_report.html", context, request=request)
#     pdf_bytes = HTML(
#         string=html_string,
#         base_url=request.build_absolute_uri("/"),
#     ).write_pdf()

#     # -- Build filename: series_<store>_<terminal>_<date>.pdf --
#     filename = (
#         f"series_{context['store_id']}"
#         f"_{context['terminal_id']}"
#         f"_{context['business_date']}.pdf"
#     )

#     response = HttpResponse(pdf_bytes, content_type="application/pdf")
#     response["Content-Disposition"] = f'inline; filename="{filename}"'
#     return response




@login_required
def series_report(request):
    """
    GET /reports/series/?session_id=<id>&paper=<a4|letter|long>
 
    Generates and streams a PDF Series Sales Report for the given session.
    Void transactions are excluded automatically by the service layer.
    """
 
    # -- Validate session_id --
    session_id = request.GET.get("session_id", "").strip()
    if not session_id or not session_id.isdigit():
        raise Http404("A valid session_id is required.")
 
    # -- Validate paper --
    paper = request.GET.get("paper", DEFAULT_PAPER).strip().lower()
    if paper not in VALID_PAPERS:
        paper = DEFAULT_PAPER
 
    # -- Build report data --
    try:
        ctx = build_series_report(int(session_id))
    except POSSession.DoesNotExist:
        raise Http404(f"Session {session_id} not found.")
    except Exception as exc:
        raise Http404(str(exc))
 
    # -- Render PDF --
    pdf_bytes = build_series_pdf(ctx, paper=paper)
 
    # -- Filename: series_<store>_<terminal>_<date>.pdf --
    filename = (
        f"series_{ctx['store_id']}"
        f"_{ctx['terminal_id']}"
        f"_{ctx['business_date']}.pdf"
    )
 
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response

