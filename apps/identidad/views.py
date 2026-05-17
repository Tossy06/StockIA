from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from cryptography.fernet import Fernet
from .models import PerfilTendero


def login_view(request):
    if request.user.is_authenticated:
        return redirect("inventario:dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("inventario:dashboard")
        messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "identidad/login.html")


def logout_view(request):
    logout(request)
    return redirect("identidad:login")


def registro_view(request):
    if request.user.is_authenticated:
        return redirect("inventario:dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 != password2:
            messages.error(request, "Las contraseñas no coinciden.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Ese nombre de usuario ya está en uso.")
        else:
            user = User.objects.create_user(username=username, password=password1)
            PerfilTendero.objects.create(usuario=user)
            login(request, user)
            return redirect("inventario:dashboard")

    return render(request, "identidad/registro.html")


@login_required
def configuracion_view(request):
    perfil, _ = PerfilTendero.objects.get_or_create(usuario=request.user)
    fernet = Fernet(settings.FERNET_KEY)

    if request.method == "POST":
        proveedor = request.POST.get("proveedor", "").strip()
        api_key = request.POST.get("api_key", "").strip()

        if proveedor and proveedor in PerfilTendero.Proveedor.values:
            perfil.proveedor = proveedor
            perfil.save()

        if api_key:
            perfil.guardar_api_key(api_key, fernet)

        messages.success(request, "Configuración guardada.")
        return redirect("identidad:configuracion")

    return render(request, "identidad/configuracion.html", {"perfil": perfil})
