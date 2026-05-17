from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from . import services


@login_required
def dashboard_view(request):
    resumen = services.obtener_resumen_dashboard()
    return render(request, "inventario/dashboard.html", {"resumen": resumen})
