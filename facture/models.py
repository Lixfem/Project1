from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import date, timedelta,datetime
import uuid

class Client(models.Model):
    SEXE_MASCULIN = 'Masculin'
    SEXE_FEMININ = 'Feminin'
    SEXE_CHOICES = ((SEXE_MASCULIN,'Masculin'),(SEXE_FEMININ,'Féminin'))

    nomClient = models.fields.CharField(max_length=100)
    emailClient = models.fields.CharField(max_length=150)
    telephoneClient = models.fields.CharField(max_length=50)
    adresseClient =  models.fields.CharField(max_length=100)
    ageClient = models.fields.CharField(max_length=50)
    sexClient = models.fields.CharField(max_length=15,choices=SEXE_CHOICES,blank=True)
    villeClient = models.fields.CharField(max_length=50)
    dateCreationClient = models.fields.DateTimeField(auto_now_add=True)
      #Definition des clé primaire 
    clientSaveBy = models.ForeignKey(User, on_delete=models.PROTECT)
    ###########
    def __str__(self):
        return f'{self.nomClient}' 
    
   

class Facturation(models.Model):
    STATUT_PAYE = 1
    STATUT_EN_ATTENTE = 2
    STATUT_ANNULE = 3
    STATUT_CHOICES_FACTURATION = (
       (STATUT_PAYE,'Payé'),
       (STATUT_EN_ATTENTE, 'En Attente'),
       (STATUT_ANNULE, 'Annulée')
    )
        #Definition des clé primaire 
    clientFacture = models.ForeignKey(Client, on_delete=models.PROTECT)
    factureSaveBy = models.ForeignKey(User,on_delete=models.PROTECT)
        ##########################
    totalFacture = models.fields.DecimalField(max_digits=10000,decimal_places=2)

    paid = models.fields.BooleanField(blank=True,default=False)

    dateCreationFacture = models.fields.DateTimeField(auto_now_add=True)
    statutFacture = models.fields.IntegerField(choices=STATUT_CHOICES_FACTURATION,default=STATUT_EN_ATTENTE)
    numeroFacture = models.CharField(max_length=50, unique=True)
    lastUpdateFacture = models.fields.DateTimeField(default=timezone.now)
    commentaireFacture = models.fields.TextField(null=True,blank=True,help_text="Entrer un commentaire sur la facture")
    
    def __str__(self):
        return f"{self.clientFacture.nomClient}_{self.dateCreationFacture}"
    
    @property 
    def get_total(self):
        produits = self.produit_set.all()
        totalFacture = sum(produit.get_total for produit in produits)
        return totalFacture
    @property
    def get_montantService(self):
        services = self.service_set.all()
        return services.montantDuService
    


    def __str__(self):
        return self.numeroFacture
    

class Devis(models.Model):
    STATUT_ATTENTE_DEVIS = 1
    STATUT_ACCEPTE_DEVIS = 2
    STATUT_REFUSE_DEVIS = 3
    STATUT_CHOICE_DEVIS = (
        (STATUT_ATTENTE_DEVIS, 'En Attente'),
        (STATUT_ACCEPTE_DEVIS, 'Accepté'),
        (STATUT_REFUSE_DEVIS, 'Refusé')
    )
        #Definition des clé primaire 
    clientDevis = models.ForeignKey(Client, on_delete=models.PROTECT)
    devisSaveBy = models.ForeignKey(User, on_delete=models.PROTECT)
    ################################
    dateCreationDevis = models.fields.DateTimeField(auto_now_add=True)
    statutDevis = models.fields.IntegerField(choices=STATUT_CHOICE_DEVIS,default=STATUT_ATTENTE_DEVIS)
    numeroDevis = models.fields.CharField(max_length=50, unique=True)
    totalDevis = models.fields.DecimalField(max_digits=100,decimal_places=2)
    lastUpdateDevis = models.fields.DateTimeField(default=timezone.now)
    commentaireDevis = models.fields.TextField(null=True,blank=True,help_text="Entrer un commentaire sur le devis")

    def __str__(self):
        return f"{self.clientDevis.nomClient}_{self.dateCreationDevis}"
    
    @property
    def get_total(self):
        produits = self.produit_set.all()
        totalDevis = sum(produit.get_total for produit in produits )
        return totalDevis
    
    @property
    def get_montantDuService(self):
        services = self.service_set.all()
        return services.montantDuService

class Produit(models.Model):
         #Definition des clé primaire 

     factureProduit = models.ForeignKey(Facturation, on_delete=models.CASCADE)
     devisProduit = models.ForeignKey(Devis, on_delete=models.CASCADE,null=True,blank=True)
     ###################
     nomProduit = models.fields.CharField(max_length= 40) 
     descriptionProduit = models.fields.CharField(max_length=400) 
     prixUnitaireProduit = models.fields.FloatField(max_length=2) 
     quantity = models.fields.IntegerField(default=0)
     total = models.fields.DecimalField(max_digits=100,decimal_places=2,default=0.00)
    
     def __str__(self):
         return f'{self.nomProduit}'
     
     @property
     def get_total(self):
         total = self.quantity * self.prixUnitaireProduit
         

class Service(models.Model):
    nomService = models.fields.CharField(max_length = 60)
    descriptionService = models.fields.CharField(max_length = 400)
    montantDuService = models.fields.DecimalField(max_digits=10, decimal_places=2)
    datePrestationService = models.fields.DateField(blank=True,null=True,auto_now=True)
    #Definition des clé primaire 
    factureService = models.ForeignKey(Facturation,on_delete=models.CASCADE)
    devisService = models.ForeignKey(Devis,on_delete=models.CASCADE, null=True,blank=True)
    #################
    def __str__(self):
        return f'{self.nomService}'
    
    @property
    def get_montantDuService(self):
        return self.montantDuService


