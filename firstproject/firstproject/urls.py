"""
URL configuration for firstproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from facture import views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('clients/',views.listClient,name='liste-clients'),
    path('clients/<int:id>/',views.detailsClient,name='details-clients'),
    path('clients/add/',views.createClient,name='create-client'),
    path('clients/<int:id>/change/',views.changeClient,name='update-client'),
    path('clients/<int:id>/delete',views.deleteClient,name='delete-client'),
    path('facturation/',views.listfacture, name='liste-facture'),
    path('facturation/<int:id>/',views.detailsFacture,name='details-facture'),
    path('addclient/',views.addClient,name='recup-client'),
]

