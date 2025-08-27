
from django.contrib import admin
from django.urls import path
from facture import views



    


urlpatterns = [
    path('admin/', admin.site.urls),
    path('',views.HomeView.as_view(),name='home'),
    path('addCustomer/', views.addCustomerView.as_view(),name='create-client'),
    path('clients/',views.listClient,name='liste-clients'),
    path('clients/<int:id>/',views.detailsClient,name='details-clients'),
    #path('clients/add/',views.createClient,name='create-client'),
    path('clients/<int:id>/change/',views.changeClient,name='update-client'),
    path('clients/<int:id>/delete',views.deleteClient,name='delete-client'),
    path('facturation/',views.listfacture, name='liste-facture'),
    path('facturation/<int:id>/',views.detailsFacture,name='details-facture'),
    path('addclient/',views.addClient,name='recup-client'),
    #path('home/', views.dashboard, name='index'),
]

