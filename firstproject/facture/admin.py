from django.contrib import admin

from facture.models import *

class ClientAdmin(admin.ModelAdmin):
    list_display = ('nom','adresse','telephone','email','sexe','ville','date_creation')
    

class FacturationAdmin(admin.ModelAdmin):
    list_display = ('date_creation','statut','numero','total_ttc','last_update','commentaire')     
      

class DevisAdmin(admin.ModelAdmin):
    list_display = ('date_creation','statut','numero','total_ttc','last_update','commentaire')

class ProduitAdmin(admin.ModelAdmin):
    list_display = ('nom_produit','description_produit','prix_unitaire_produit')

class ServiceAdmin(admin.ModelAdmin):
    list_display = ('nom_service','description_service','montant_du_service')
    

    
admin.site.register(Client,ClientAdmin)
admin.site.register(Facturation,FacturationAdmin)
admin.site.register(Devis,DevisAdmin)
admin.site.register(Produit,ProduitAdmin)
admin.site.register(Service,ServiceAdmin)


