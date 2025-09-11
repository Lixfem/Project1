
from django.contrib import admin
from django.urls import path
from facture import views
  
urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    # Page d'accueil
    path('',views.HomeView.as_view(),name='home'),

    # Clients
    path('addCustomer/', views.addCustomerView.as_view(),name='create-client'),
    path('clients/',views.listClient,name='liste-clients'),
    path('clients/<int:id>/',views.detailsClient,name='details-clients'),
    path('clients/<int:id>/change/',views.changeClient,name='update-client'),
    path('clients/<int:id>/delete',views.deleteClient,name='delete-client'),
    #path('clients/add/',views.createClient,name='create-client'),
    #path('addclient/',views.addClient,name='recup-client'),

    # Devis URLs
    path('listdevis/', views.liste_devis, name='liste-devis'),
    path('addDevis/',views.addDevisView.as_view(),name='create-devis'),
    path('devis/<int:devis_id>/', views.details_devis, name='devis-detail'),
    path('devis/<int:devis_id>/valider/', views.valider_devis, name='valider_devis'),
    path('devis/<int:devis_id>/transformer/', views.transformer_devis_en_facture, name='transformer_devis'),
    path('devis/<int:devis_id>/envoyer-email/', views.envoyer_devis_email, name='envoyer_devis_email'),
    path('devis/<int:devis_id>/telecharger-pdf/', views.telecharger_pdf_devis, name='telecharger_pdf_devis'),

    #Factures
    path('addFacture/', views.addFactureView.as_view(),name='create-facture'),
    path('facturation/',views.listfacture, name='liste-facture'),
    path('facturation/<int:facture_id>/',views.detailsFacture,name='details-facture'),
    path('facturation/<int:facture_id>/modifier/',views.modifier_facture,name='modifier-facture'),
    path('factures/<int:facture_id>/envoyer-email/', views.envoyer_facture_email, name='envoyer_facture_email'),
    path('factures/<int:facture_id>/telecharger-pdf/', views.telecharger_pdf_facture, name='telecharger_pdf_facture'),

    #path('home/', views.dashboard, name='index'),

     # API URLs (pour AJAX)
    path('api/devis/<int:devis_id>/valider/', views.valider_devis, name='api_valider_devis'),
    #path('api/devis/<int:devis_id>/transformer/', views.api_transformer_devis, name='api_transformer_devis'),

]




 