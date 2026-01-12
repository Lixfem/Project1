# facture/urls.py
from django.urls import path
from . import views

app_name = 'facture'

urlpatterns = [
    # Home page
    path('',views.HomeView.as_view(),name='home'),
    # page des parametrages
    #path('settings/',views.settings_view, name='settings'),
    #================== Clients===================================================================================================
    path('clients/ajouter/', views.ClientCreateView.as_view(),name='create-client'),
    path('clients/',views.client_list,name='liste-clients'),
    path('clients/<int:client_id>/',views.client_detail,name='details-clients'), 
    path('clients/<int:client_id>/modifier/',views.client_update,name='update-client'),
    path('clients/<int:client_id>/supprimer/',views.client_delete,name='delete-client'),

    #==================== Produits et Services=========================
    path('ajouter/article/',views.ajouter_article,name='ajouter_element'),
    path('gerer/article/',views.gerer_article,name='gerer-article'),
    path('modifier/article/',views.article_update, name='update-article'),
    path('api/search-produits/', views.search_produits, name='search-produits'),
    path('api/search-services/', views.search_services, name='search-services'),
    path('api/get-prices/', views.get_prices, name='get-prices'),
    #============================= Devis URLs========================================================
    path('devis/', views.devis_list, name='liste-devis'),
    path('devis/create/', views.DevisCreateView.as_view(), name='create-devis'),
    path('liste-attente/', views.devis_list_attente, name='liste-attente'),
    path('devis/<int:devis_id>/edit/', views.DevisEditView.as_view(),name='modifier-devis'),
    #path('devis/<int:devis_id>/supprimer/', views.devis_delete, name='supprimer-devis'),
    path('devis/<int:devis_id>/statut/', views.devis_change_statut, name='changer-statut-devis'),
    path('devis/<int:devis_id>/transformer/', views.DevisTransformView.as_view(), name= 'transformer-devis'),
    path('api/devis/<int:devis_id>/data/', views.get_devis_data,name='get-devis-data'),
    
    #=====================================Documents ==================
    path('document/<int:document_id>/<str:document_type>/', views.detail_document, name='document-detail'),
    path('telecharger-pdf/<str:document_type>/<int:document_id>/', views.telecharger_pdf_document, name='telecharger_pdf_document'),
    path('envoyer-email/<str:document_type>/<int:document_id>/', views.envoyer_document_email, name='envoyer_document_email'),


    #====================Factures=================
    path('facture/create/', views.FactureCreateView.as_view(),name='create-facture'),
    path('factures/',views.facture_list, name='liste-facture'),
    path('facture/impayees/', views.facture_list_impayee, name= 'liste-impaye'),
    path('facture/payees/', views.facture_list_payee, name= 'liste-paye'),
    path('factures/<int:facture_id>/modifier/',views.FacturationEditView.as_view(),name='modifier-facture'),
    path('facture/<int:facture_id>/statut/',views.facture_change_statut,name='facture-change-statut'),

    #=============Reglements===============================
    path('reglements/', views.reglement_list, name='liste-reglements'),
    path('factures/<int:facture_id>/reglements/ajouter', views.reglement_create, name='reglement-create'),
    path('Modes-reglement/', views.mode_reglement_list, name='mode-reglement-list'),
    path('Modes-reglement/ajouter/', views.mode_reglement_create, name='mode-reglement-create'),
    path('mode-reglement/modifier/<int:mode_id>/', views.mode_reglement_update, name='mode-reglement-update'),
    path('mode-reglement/supprimer/<int:mode_id>/', views.mode_reglement_delete, name='mode-reglement-delete'),
    path('mode-reglement/toggle/<int:mode_id>/', views.toggle_mode_reglement, name='toggle-mode-reglement'),
    path('reglement/modifier/<int:pk>/', views.ReglementUpdateView.as_view(), name='modifier-reglement'),
    path('reglement/supprimer/<int:pk>/', views.ReglementDeleteView.as_view(), name='supprimer-reglement'),
    #path('Modes-reglement/<int:mode_id>/modifier/', views.mode
     # API URLs (pour AJAX)
    #path('api/devis/<int:devis_id>/valider/', views.valider_devis, name='api_valider_devis'),
    #path('api/devis/<int:devis_id>/transformer/', views.api_transformer_devis, name='api_transformer_devis'),

    # Page principale des statistiques
    path('statistique',views.statistiques_view,name='stat'),
    
    # API pour récupérer les données de statistiques
    path('statistiques/api/donnees/', views.api_statistiques, name='api_statistiques'),
    
    # KPIs principales pour le tableau de bord
    path('api/kpis/', views.get_kpis_principales, name='kpis_principales'),
    
    
    # Statistiques avancées
    #path('avancees/', views.statistiques_avancees, name='statistiques_avancees'),
    
    # Statistiques admin (réservées aux administrateurs)
    #path('admin/', views.statistiques_admin, name='statistiques_admin'),
]