from django.contrib import admin

from facture.models import *

class ClientAdmin(admin.ModelAdmin):
    list_display = ('nomClient','adresseClient','telephoneClient','emailClient','sexClient','ageClient','villeClient','dateCreationClient')
    

class FacturationAdmin(admin.ModelAdmin):
    list_display = ('dateCreationFacture','statutFacture','numeroFacture','paid','totalFacture','lastUpdateFacture','commentaireFacture')     
      

class DevisAdmin(admin.ModelAdmin):
    list_display = ('dateCreationDevis','statutDevis','numeroDevis','totalDevis','lastUpdateDevis','commentaireDevis')

class ProduitAdmin(admin.ModelAdmin):
    list_display = ('nomProduit','descriptionProduit','prixUnitaireProduit','quantity','total')

class ServiceAdmin(admin.ModelAdmin):
    list_display = ('nomService','descriptionService','montantDuService','datePrestationService')
    

admin.site.register(Client,ClientAdmin)
admin.site.register(Facturation,FacturationAdmin)
admin.site.register(Devis,DevisAdmin)
admin.site.register(Produit,ProduitAdmin)
admin.site.register(Service,ServiceAdmin)

