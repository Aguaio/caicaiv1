from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.cache import never_cache
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from .models import AdminUser, Categoria, Producto, Pedido, DetallePedido, Cliente, HistorialCliente
from .decorators import admin_required

from django.db import transaction
from django.views.decorators.csrf import csrf_protect
from decimal import Decimal, InvalidOperation

from django.views.decorators.http import require_POST

from django.http import JsonResponse  

from collections import defaultdict

from django.utils.functional import cached_property


User = get_user_model()

# ------------------- PÁGINAS PÚBLICAS -------------------

def home(request):
    return render(request, 'core/home.html')

def _cart_count(request):
    carrito = request.session.get('carrito', {})
    return sum(int(q) for q in carrito.values())


def catalogo(request):
    query = request.GET.get('q')
    categoria_id = request.GET.get('categoria')

    productos = Producto.objects.all()
    categorias = Categoria.objects.all()

    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)
    if query:
        productos = productos.filter(Q(nombre__icontains=query) | Q(descripcion__icontains=query))

    return render(request, 'core/catalogo.html', {
        'productos': productos,
        'categorias': categorias,
        'categoria_id': categoria_id,
        'query': query,
        'cart_count': _cart_count(request),
    })


# ------------------- LOGIN UNIFICADO -------------------

@never_cache
@csrf_protect
def login_unificado(request):
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = (request.POST.get('password') or '').strip()

        user = authenticate(request, username=username, password=password)
        if user:
            if getattr(user, 'bloqueado', False):
                messages.error(request, 'Tu cuenta está bloqueada. Contacta con el administrador.')
                return redirect('login_unificado')
            login(request, user)
            request.session['cliente_id'] = user.id
            return redirect('catalogo')

        admin = AdminUser.objects.filter(username=username).first()
        if admin and admin.check_password(password):
            request.session['admin_id'] = admin.id
            return redirect('admin_dashboard')

        messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'core/login.html')


def logout_unificado(request):
    logout(request)
    request.session.flush()
    return redirect('login_unificado')

# ------------------- REGISTRO CLIENTE -------------------

@csrf_protect
def registro_cliente(request):
    if request.method == 'POST':
        username = request.POST.get('username').strip()
        password = request.POST.get('password').strip()
        correo = request.POST.get('correo').strip()
        direccion = request.POST.get('direccion').strip()
        telefono = request.POST.get('telefono').strip()

        if not username or not password or not correo:
            messages.error(request, 'Todos los campos obligatorios deben estar completos.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Ese nombre de usuario ya existe.')
        elif User.objects.filter(email=correo).exists():
            messages.error(request, 'Ese correo ya está registrado.')
        else:
            user = User.objects.create_user(
                username=username,
                password=password,
                email=correo,
                direccion=direccion,
                telefono=telefono
            )
            login(request, user)
            messages.success(request, 'Cuenta creada exitosamente.')
            return redirect('catalogo')
    return render(request, 'core/registro_cliente.html')


# ------------------- PERFIL CLIENTE -------------------

@login_required
def editar_perfil(request):
    user = request.user

    if request.method == 'POST':
        email = request.POST.get('correo', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        telefono = request.POST.get('telefono', '').strip()

        if not email:
            messages.error(request, 'El correo no puede estar vacío.')
        elif User.objects.exclude(id=user.id).filter(email=email).exists():
            messages.error(request, 'Ese correo ya está en uso.')
        else:
            user.email = email
            user.direccion = direccion
            user.telefono = telefono
            user.save()
            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('editar_perfil')

    return render(request, 'core/editar_perfil.html', {'user': user})


# ------------------- PANEL ADMIN -------------------

@admin_required
@never_cache
def admin_dashboard(request):
    return render(request, 'core/admin_dashboard.html')


# ----- CRUD Categorías -----

@admin_required
def categorias_list(request):
    categorias = Categoria.objects.all()
    return render(request, 'core/categorias_list.html', {'categorias': categorias})


@admin_required
def categoria_create(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre').strip()
        if not nombre:
            messages.error(request, 'El nombre no puede estar vacío.')
        elif Categoria.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, 'Ya existe una categoría con ese nombre.')
        else:
            Categoria.objects.create(nombre=nombre)
            messages.success(request, 'Categoría creada correctamente.')
            return redirect('categorias_list')
    return render(request, 'core/categoria_form.html')


@admin_required
def categoria_edit(request, id):
    categoria = get_object_or_404(Categoria, id=id)
    if request.method == 'POST':
        nombre = request.POST.get('nombre').strip()
        if not nombre:
            messages.error(request, 'El nombre no puede estar vacío.')
        elif Categoria.objects.exclude(id=id).filter(nombre__iexact=nombre).exists():
            messages.error(request, 'Ya existe una categoría con ese nombre.')
        else:
            categoria.nombre = nombre
            categoria.save()
            messages.success(request, 'Categoría actualizada correctamente.')
            return redirect('categorias_list')
    return render(request, 'core/categoria_form.html', {'categoria': categoria})


@admin_required
@csrf_protect
def categoria_delete(request, id):
    if request.method != 'POST':
        messages.error(request, 'Operación no permitida.')
        return redirect('categorias_list')
    Categoria.objects.filter(id=id).delete()
    messages.success(request, 'Categoría eliminada correctamente.')
    return redirect('categorias_list')


# ----- CLIENTES ADMIN -----

@admin_required
def clientes_list(request):
    clientes = Cliente.objects.all().order_by('username')
    nombres = list(clientes.values_list('username', flat=True))
    historial_qs = HistorialCliente.objects.filter(nombre__in=nombres).order_by('-fecha')
    historial_por_cliente = defaultdict(list)
    for h in historial_qs:
        historial_por_cliente[h.nombre].append(h)
    resumen = []
    for c in clientes:
        lst = historial_por_cliente.get(c.username, [])
        last = lst[0] if lst else None
        resumen.append({
            'username': c.username,
            'correo': c.email,
            'accion': last.accion if last else '—',
            'fecha': last.fecha if last else None,
            'tiene_historial': bool(lst),
        })

    return render(request, 'core/clientes_list.html', {
        'clientes': clientes,
        'resumen': resumen,
        'historial_por_cliente': historial_por_cliente,
    })


@admin_required
@require_POST
@csrf_protect
def cliente_bloquear(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    cliente.bloqueado = True
    cliente.save()
    HistorialCliente.objects.create(nombre=cliente.username, correo=cliente.email, accion='bloqueado')
    messages.error(request, f'Cliente {cliente.username} bloqueado.')
    return redirect('clientes_list')


@admin_required
@require_POST
@csrf_protect
def cliente_desbloquear(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    cliente.bloqueado = False
    cliente.save()
    HistorialCliente.objects.create(nombre=cliente.username, correo=cliente.email, accion='desbloqueado')
    messages.success(request, f'Cliente {cliente.username} desbloqueado.')
    return redirect('clientes_list')



# ------------------- PRODUCTOS -------------------

@admin_required
def productos_list(request):
    productos = Producto.objects.all()
    return render(request, 'core/productos_list.html', {'productos': productos})


@admin_required
@csrf_protect
def producto_create(request):
    categorias = Categoria.objects.all()
    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        descripcion = (request.POST.get('descripcion') or '').strip()
        precio_raw = request.POST.get('precio')
        stock_raw = request.POST.get('stock')
        categoria_id = request.POST.get('categoria')
        imagen = request.FILES.get('imagen')

        if not nombre or precio_raw is None or stock_raw is None or not categoria_id:
            messages.error(request, 'Todos los campos obligatorios deben completarse.')
        else:
            try:
                precio = Decimal(precio_raw)
                stock = int(stock_raw)
                if precio < 0 or stock < 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                messages.error(request, 'Precio o stock inválidos.')
                return render(request, 'core/producto_form.html', {'categorias': categorias})

            categoria = get_object_or_404(Categoria, id=categoria_id)
            Producto.objects.create(
                nombre=nombre,
                descripcion=descripcion,
                precio=precio,
                stock=stock,
                categoria=categoria,
                imagen=imagen
            )
            messages.success(request, 'Producto creado correctamente.')
            return redirect('productos_list')
    return render(request, 'core/producto_form.html', {'categorias': categorias})


@admin_required
@csrf_protect
def producto_edit(request, id):
    producto = get_object_or_404(Producto, id=id)
    categorias = Categoria.objects.all()
    if request.method == 'POST':
        producto.nombre = (request.POST.get('nombre') or '').strip()
        producto.descripcion = (request.POST.get('descripcion') or '').strip()
        try:
            producto.precio = Decimal(request.POST.get('precio'))
            producto.stock = int(request.POST.get('stock'))
            if producto.precio < 0 or producto.stock < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            messages.error(request, 'Precio o stock inválidos.')
            return render(request, 'core/producto_form.html', {'producto': producto, 'categorias': categorias})

        producto.categoria_id = request.POST.get('categoria')
        if request.FILES.get('imagen'):
            producto.imagen = request.FILES.get('imagen')
        producto.save()
        messages.success(request, 'Producto actualizado correctamente.')
        return redirect('productos_list')
    return render(request, 'core/producto_form.html', {'producto': producto, 'categorias': categorias})


@admin_required
@csrf_protect
def producto_delete(request, id):
    if request.method != 'POST':
        messages.error(request, 'Operación no permitida.')
        return redirect('productos_list')
    Producto.objects.filter(id=id).delete()
    messages.success(request, 'Producto eliminado correctamente.')
    return redirect('productos_list')


# ------------------- PEDIDOS -------------------

@admin_required
def pedidos_list(request):
    pedidos = list(Pedido.objects.all().order_by('-fecha'))

    # Colecta identificadores presentes en la tabla de pedidos
    usernames = {p.nombre_cliente for p in pedidos if p.nombre_cliente}
    correos = {p.correo for p in pedidos if p.correo}

    # Trae clientes que coincidan por username o email
    clientes = Cliente.objects.filter(Q(username__in=usernames) | Q(email__in=correos)) \
                              .values('username', 'email', 'bloqueado')

    # Índices para lookup rápido
    block_by_user = {c['username']: c['bloqueado'] for c in clientes}
    block_by_mail = {c['email']: c['bloqueado'] for c in clientes}

    # Anexa flag al objeto pedido
    for p in pedidos:
        p.bloqueado = bool(block_by_user.get(p.nombre_cliente) or block_by_mail.get(p.correo))

    return render(request, 'core/pedidos_list.html', {'pedidos': pedidos})

@admin_required
def pedido_detalle(request, id):
    pedido = get_object_or_404(Pedido, id=id)
    detalles = pedido.detalles.all()

    # Determina si el cliente está bloqueado
    bloqueado = Cliente.objects.filter(
        username=pedido.nombre_cliente
    ).values_list('bloqueado', flat=True).first() or False

    if request.method == 'POST':
        pedido.estado = request.POST.get('estado')
        pedido.save()
        messages.success(request, 'Estado actualizado.')
        return redirect('pedidos_list')

    return render(request, 'core/pedido_detalle.html', {
        'pedido': pedido,
        'detalles': detalles,
        'bloqueado': bloqueado
    })

# ------------------- CARRITO -------------------

@require_POST
@csrf_protect
def agregar_al_carrito(request, id):
    if request.user.is_authenticated and getattr(request.user, 'bloqueado', False):
        return JsonResponse({'ok': False, 'error': 'bloqueado'}, status=403)
    
    carrito = request.session.get('carrito', {})
    try:
        cantidad = int(request.POST.get('cantidad', 1))
        if cantidad < 1:
            cantidad = 1
    except ValueError:
        cantidad = 1

    key = str(id)
    carrito[key] = carrito.get(key, 0) + cantidad
    request.session['carrito'] = carrito
    count = _cart_count(request)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('accept', '').find('application/json') != -1:
        return JsonResponse({'ok': True, 'count': count})

    return redirect('ver_carrito')


@require_POST
@csrf_protect
def eliminar_del_carrito(request, id):
    carrito = request.session.get('carrito', {})
    if str(id) in carrito:
        del carrito[str(id)]
        request.session['carrito'] = carrito
    return redirect('ver_carrito')


def ver_carrito(request):
    carrito = request.session.get('carrito', {})
    productos = []
    total = Decimal(0)

    for id, cantidad in carrito.items():
        producto = Producto.objects.get(id=id)
        subtotal = producto.precio * cantidad
        total += subtotal
        productos.append({'id': producto.id, 'nombre': producto.nombre, 'precio': producto.precio, 'cantidad': cantidad, 'subtotal': subtotal})

    return render(request, 'core/carrito.html', {'productos': productos, 'total': total, 'cart_count': _cart_count(request)})


@login_required
@csrf_protect
def confirmar_pedido(request):
    if request.user.bloqueado:
        messages.error(request, 'Tu cuenta está bloqueada. No puedes realizar pedidos.')
        return redirect('catalogo')

    carrito = request.session.get('carrito', {})
    if not carrito:
        messages.error(request, 'Tu carrito está vacío.')
        return redirect('catalogo')

    if request.method == 'POST':
        with transaction.atomic():
            # Verificación previa de stock con bloqueo de fila
            faltantes = []
            productos_seleccionados = {}
            for pid, cantidad in carrito.items():
                prod = Producto.objects.select_for_update().get(id=pid)
                if prod.stock < cantidad:
                    faltantes.append((prod.nombre, prod.stock, cantidad))
                productos_seleccionados[pid] = prod

            if faltantes:
                msg = 'Sin stock suficiente: ' + ', '.join([f'{n} (disp: {d}, solicitado: {c})' for n, d, c in faltantes])
                messages.error(request, msg)
                return redirect('ver_carrito')

            cliente = request.user
            pedido = Pedido.objects.create(
                nombre_cliente=cliente.username,
                correo=cliente.email,
                direccion=cliente.direccion or 'Sin dirección',
                total=Decimal('0')
            )

            total = Decimal('0')
            for pid, cantidad in carrito.items():
                prod = productos_seleccionados[pid]
                subtotal = prod.precio * cantidad
                total += subtotal
                DetallePedido.objects.create(pedido=pedido, producto=prod, cantidad=cantidad, subtotal=subtotal)
                prod.stock -= cantidad
                prod.save()

            pedido.total = total
            pedido.save()

        request.session['carrito'] = {}
        messages.success(request, 'Pedido confirmado correctamente.')
        return render(request, 'core/pedido_confirmado.html', {'pedido': pedido})

    return render(request, 'core/confirmar_pedido.html')


@login_required
def mis_pedidos(request):
    pedidos = Pedido.objects.filter(nombre_cliente=request.user.username).order_by('-fecha')
    return render(request, 'core/mis_pedidos.html', {'pedidos': pedidos, 'cart_count': _cart_count(request)})


