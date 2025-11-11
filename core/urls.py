from django.urls import path
from . import views

urlpatterns = [
    # Página principal
    path('', views.home, name='home'),

    # Catálogo y compras
    path('catalogo/', views.catalogo, name='catalogo'),
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/agregar/<int:id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/eliminar/<int:id>/', views.eliminar_del_carrito, name='eliminar_del_carrito'),
    path('pedido/confirmar/', views.confirmar_pedido, name='confirmar_pedido'),
    path('mis-pedidos/', views.mis_pedidos, name='mis_pedidos'),

    # Registro y login unificados
    path('registro/', views.registro_cliente, name='registro_cliente'),
    path('login/', views.login_unificado, name='login_unificado'),
    path('logout/', views.logout_unificado, name='logout_unificado'),

    # Panel del administrador
    path('panel/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('panel/categorias/', views.categorias_list, name='categorias_list'),
    path('panel/categorias/nueva/', views.categoria_create, name='categoria_create'),
    path('panel/categorias/editar/<int:id>/', views.categoria_edit, name='categoria_edit'),
    path('panel/categorias/eliminar/<int:id>/', views.categoria_delete, name='categoria_delete'),
    path('panel/productos/', views.productos_list, name='productos_list'),
    path('panel/productos/nuevo/', views.producto_create, name='producto_create'),
    path('panel/productos/editar/<int:id>/', views.producto_edit, name='producto_edit'),
    path('panel/productos/eliminar/<int:id>/', views.producto_delete, name='producto_delete'),
    path('panel/pedidos/', views.pedidos_list, name='pedidos_list'),
    path('panel/pedidos/<int:id>/', views.pedido_detalle, name='pedido_detalle'),

    # CLIENTE
    path('perfil/', views.editar_perfil, name='editar_perfil'),
    
    # ADMIN CLIENTES
    path('panel/clientes/', views.clientes_list, name='clientes_list'),
    path('panel/clientes/bloquear/<int:id>/', views.cliente_bloquear, name='cliente_bloquear'),
    path('panel/clientes/desbloquear/<int:id>/', views.cliente_desbloquear, name='cliente_desbloquear'),

]
