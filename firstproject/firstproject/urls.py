
from django.contrib import admin
from django.urls import path,include
from django.contrib.auth import  views as auth_views
from facture import views
from register import views as v
from django.conf import settings
from django.conf.urls.static import static

  
urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    path('register/',v.register, name='register'),
    #path('',include('firstproject.urls')),
    path('',include('django.contrib.auth.urls')),
    path('mailfinder/',v.email_finder, name= 'email_finder'),
    path('password_reset_confirm/',auth_views.PasswordChangeView.as_view(
        template_name="registration/password_reset_confirm.html"
    ), name='password_reset_confirm'),
    path('login/',v.LoginView.as_view(), name='login'),
    path('logout/',v.logout_view, name='logout'),
   # path('profile/',v.profile,name='profile'),


   # path('login/',views.login_view,name='login'),
    # Page d'accueil Dashboard
    path('',views.HomeView.as_view(),name='home'),
    # page des parametrages
    #path('settings/',views.settings_view, name='settings'),
    #================== Clients===================================================================================================
    path('clients/ajouter/', views.ClientCreateView.as_view(),name='create-client'),
    path('clients/',views.client_list,name='liste-clients'),
    path('clients/<int:client_id>/',views.client_detail,name='details-clients'), 
    path('clients/<int:client_id>/modifier/',views.client_update,name='update-client'),
    path('clients/<int:client_id>/supprimer/',views.client_delete,name='delete-client'),

    #==================== Produits et Services=================================================================================
    path('ajouter/article/',views.ajouter_article,name='ajouter_element'),
    path('gerer/article/',views.gerer_article,name='gerer-article'),
    path('modifier/article/',views.article_update, name='update-article'),
    path('search-produits/',views.search_produits,name='search-produits'),
    path('search-services/',views.search_services,name='search-services'),

    #============================= Devis URLs========================================================
    path('devis/', views.devis_list, name='liste-devis'),
    path('devis/ajouter/', views.DevisCreateView.as_view(), name='create-devis'),
    path('devis/attente/', views.devis_list_attente, name= 'liste-attente'),
    path('devis/<int:devis_id>/', views.devis_detail, name='devis-details'),
    path('devis/<int:devis_id>/modifier/',views.devis_update,name='modifier-devis'),
    path('devis/<int:devis_id>/transformer/', views.transformer_devis_en_facture, name='transformer-devis'),
    path('devis/<int:devis_id>/envoyer-email/', views.envoyer_devis_email, name='envoyer_devis_email'),
    path('devis/<int:devis_id>/telecharger-pdf/', views.telecharger_pdf_devis, name='telecharger_pdf_devis'),
    path('devis/<int:devis_id>/supprimer/', views.devis_delete, name='supprimer-devis'),
    path('devis/<int:devis_id>/statut/', views.devis_change_statut, name='changer-statut-devis'),
    #path('devis/<int:devis_id>/valider/', views.valider_devis, name='valider_devis'),

    #====================Factures=================
    path('facture/ajouter', views.FactureCreateView.as_view(),name='create-facture'),
    path('factures/',views.facture_list, name='liste-facture'),
    path('facture/impayees/', views.facture_list_impayee, name= 'liste-impaye'),
    path('facture/payees/', views.facture_list_payee, name= 'liste-paye'),
    path('factures/<int:facture_id>/',views.facture_detail,name='details-facture'),
    path('factures/<int:facture_id>/modifier/',views.facture_update,name='modifier-facture'),
    path('factures/<int:facture_id>/supprimer/',views.facture_delete,name='delete-facture'),
    path('facture/<int:facture_id>/statut/',views.facture_change_statut,name='changer-statut-facture'),
    path('factures/<int:facture_id>/envoyer-email/', views.envoyer_facture_email, name='envoyer_facture_email'),
    path('factures/<int:facture_id>/telecharger-pdf/', views.telecharger_pdf_facture, name='telecharger_pdf_facture'),

    #=============Reglements===============================
    path('reglements/', views.reglement_list, name='liste-reglements'),
    path('factures/<int:facture_id>/reglements/ajouter', views.reglement_create, name='ajouter-reglement'),
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

]+ static(settings.MEDIA_URL, document_root= settings.MEDIA_ROOT)




 