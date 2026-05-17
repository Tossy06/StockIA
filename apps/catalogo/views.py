from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def lista_view(request):
    return render(request, "catalogo/lista.html")
