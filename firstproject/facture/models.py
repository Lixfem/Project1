from django.db import models,transaction
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import date, timedelta, datetime
import uuid

class Client(models.Model):
    SEXE_MASCULIN = 'Masculin'
    SEXE_FEMININ = 'Feminin'
    SEXE_CHOICES = ((SEXE_MASCULIN,'Masculin'),(SEXE_FEMININ,'Féminin'))

    nomClient = models.fields.CharField(max_length=100)
    emailClient = models.fields.CharField(max_length=150)
    telephoneClient = models.fields.CharField(max_length=50)
    adresseClient = models.fields.CharField(max_length=100)
    ageClient = models.fields.CharField(max_length=50)
    sexClient = models.fields.CharField(max_length=15,choices=SEXE_CHOICES,blank=True)
    villeClient = models.fields.CharField(max_length=50)
    dateCreationClient = models.fields.DateTimeField(auto_now_add=True)
    # Définition des clé primaire 
    clientSaveBy = models.ForeignKey(User, on_delete=models.PROTECT)
    
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
    # Définition des clé primaire 
    clientFacture = models.ForeignKey(Client, on_delete=models.PROTECT)
    factureSaveBy = models.ForeignKey(User,on_delete=models.PROTECT)
    
    # Lien vers le devis d'origine (nouveau champ)
    devis_origine = models.ForeignKey('Devis', on_delete=models.SET_NULL, 
                                     null=True, blank=True, 
                                     related_name='factures_generees')
    
    totalFacture = models.fields.DecimalField(max_digits=10000,decimal_places=2)
    paid = models.fields.BooleanField(blank=True,default=False)
    dateCreationFacturation = models.fields.DateTimeField(auto_now_add=True)
    statutFacture = models.fields.IntegerField(choices=STATUT_CHOICES_FACTURATION,default=STATUT_EN_ATTENTE)
    numeroFacture = models.CharField(max_length=50, unique=True)
    lastUpdateFacture = models.fields.DateTimeField(default=timezone.now)
    commentaireFacture = models.fields.TextField(null=True,blank=True,help_text="Entrer un commentaire sur la facture")
    
    def __str__(self):
        return f"{self.clientFacture.nomClient}_{self.dateCreationFacturation}"
    
    @property 
    def get_total(self):
        produits = self.produit_set.all()
        totalFacture = sum(produit.get_total for produit in produits)
        return totalFacture
    
    @property
    def get_montantService(self):
        services = self.service_set.all()
        total_services = sum(service.montantDuService for service in services)
        return total_services
    
    def generer_numero_facture(self):
        """Génère automatiquement un numéro de facture unique"""
        with transaction.atomic():
         annee = datetime.now().year
         dernier_numero = Facturation.objects.filter(
            numeroFacture__startswith=f"FAC-{annee}"
         ).count() + 1
         return f"FAC-{annee}-{dernier_numero:05d}"
    
    def save(self, *args, **kwargs):
        if not self.numeroFacture:
            self.numeroFacture = self.generer_numero_facture()
        super().save(*args, **kwargs)

class Devis(models.Model):
    STATUT_ATTENTE_DEVIS = 1
    STATUT_ACCEPTE_DEVIS = 2
    STATUT_REFUSE_DEVIS = 3
    STATUT_TRANSFORME_FACTURE = 4  # Nouveau statut
    STATUT_CHOICE_DEVIS = (
        (STATUT_ATTENTE_DEVIS, 'En Attente'),
        (STATUT_ACCEPTE_DEVIS, 'Accepté'),
        (STATUT_REFUSE_DEVIS, 'Refusé'),
        (STATUT_TRANSFORME_FACTURE, 'Transformé en facture')  # Nouveau statut
    )
    # Définition des clé primaire 
    clientDevis = models.ForeignKey(Client, on_delete=models.PROTECT)
    devisSaveBy = models.ForeignKey(User, on_delete=models.PROTECT)
    
    dateCreationDevis = models.fields.DateTimeField(auto_now_add=True)
    statutDevis = models.fields.IntegerField(choices=STATUT_CHOICE_DEVIS,default=STATUT_ATTENTE_DEVIS)
    numeroDevis = models.fields.CharField(max_length=50, unique=True)
    totalDevis = models.fields.DecimalField(max_digits=100,decimal_places=2)
    lastUpdateDevis = models.fields.DateTimeField(default=timezone.now)
    commentaireDevis = models.fields.TextField(null=True,blank=True,help_text="Entrer un commentaire sur le devis")
    
    # Nouveau champ pour savoir si le devis a été transformé en facture
    est_transforme_en_facture = models.BooleanField(default=False)
    date_transformation = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.clientDevis.nomClient}_{self.dateCreationDevis}"
    
    @property
    def get_total(self):
        produits = self.produit_set.all()
        totalDevis = sum(produit.get_total for produit in produits)
        return totalDevis
    
    @property
    def get_montantDuService(self):
        services = self.service_set.all()
        total_services = sum(service.montantDuService for service in services)
        return total_services
    
    def generer_numero_devis(self):
        """Génère automatiquement un numéro de devis unique"""
        with transaction.atomic():
          annee = datetime.now().year
          dernier_numero = Devis.objects.filter(
            numeroDevis__startswith=f"DEV-{annee}"
          ).count() + 1
          return f"DEV-{annee}-{dernier_numero:05d}"
    
    def save(self, *args, **kwargs):
        if not self.numeroDevis:
            self.numeroDevis = self.generer_numero_devis()
        super().save(*args, **kwargs)
    
    def transformer_en_facture(self, user):
        """
        Transforme le devis en facture
        Args:
            user: L'utilisateur qui effectue la transformation
        Returns:
            Facturation: La facture créée
        """
        from django.db import transaction
        
        # Vérifier si le devis n'est pas déjà transformé
        if self.est_transforme_en_facture:
            raise ValueError("Ce devis a déjà été transformé en facture")
        
        # Vérifier que le devis est accepté
        if self.statutDevis != self.STATUT_ACCEPTE_DEVIS:
            raise ValueError("Seul un devis accepté peut être transformé en facture")
        
        with transaction.atomic():
            # Créer la facture
            facture = Facturation.objects.create(
                clientFacture=self.clientDevis,
                factureSaveBy=user,
                devis_origine=self,
                totalFacture=self.totalDevis,
                paid=False,
                statutFacture=Facturation.STATUT_EN_ATTENTE,
                commentaireFacture=f"Facture générée depuis le devis {self.numeroDevis}\n{self.commentaireDevis or ''}"
            )
            
            # Copier tous les produits du devis vers la facture
            for produit in self.produit_set.all():
                Produit.objects.create(
                    factureProduit=facture,
                    nomProduit=produit.nomProduit,
                    descriptionProduit=produit.descriptionProduit,
                    prixUnitaireProduit=produit.prixUnitaireProduit,
                    quantity=produit.quantity,
                    total=produit.total
                )
            
            # Copier tous les services du devis vers la facture
            for service in self.service_set.all():
                Service.objects.create(
                    factureService=facture,
                    nomService=service.nomService,
                    descriptionService=service.descriptionService,
                    montantDuService=service.montantDuService,
                    datePrestationService=service.datePrestationService
                )
            
            # Mettre à jour le statut du devis
            self.statutDevis = self.STATUT_TRANSFORME_FACTURE
            self.est_transforme_en_facture = True
            self.date_transformation = timezone.now()
            self.lastUpdateDevis = timezone.now()
            self.save()
            
            return facture
    
    def peut_etre_transforme(self):
        """Vérifie si le devis peut être transformé en facture"""
        return (
            self.statutDevis == self.STATUT_ACCEPTE_DEVIS and 
            not self.est_transforme_en_facture
        )

class Produit(models.Model):
    # Définition des clé primaire 
    factureProduit = models.ForeignKey(Facturation, on_delete=models.CASCADE, null=True, blank=True)
    devisProduit = models.ForeignKey(Devis, on_delete=models.CASCADE, null=True, blank=True)
    
    nomProduit = models.fields.CharField(max_length=40) 
    descriptionProduit = models.fields.CharField(max_length=400) 
    prixUnitaireProduit = models.fields.FloatField(max_length=2) 
    quantity = models.fields.IntegerField(default=0)
    total = models.fields.DecimalField(max_digits=100,decimal_places=2,default=0.00)
    
    def __str__(self):
        return f'{self.nomProduit}'
    
    @property
    def get_total(self):
        return Decimal(str(self.quantity * self.prixUnitaireProduit))
    
    def save(self, *args, **kwargs):
        self.total = self.get_total
        super().save(*args, **kwargs)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(factureProduit__isnull=False, devisProduit__isnull=True) |
                    models.Q(factureProduit__isnull=True, devisProduit__isnull=False)
                ),
                name='produit_facture_ou_devis'
            )
        ]

class Service(models.Model):
    nomService = models.fields.CharField(max_length=60)
    descriptionService = models.fields.CharField(max_length=400)
    montantDuService = models.fields.DecimalField(max_digits=10, decimal_places=2)
    datePrestationService = models.fields.DateField(blank=True,null=True,auto_now=True)
    
    # Définition des clé primaire 
    factureService = models.ForeignKey(Facturation,on_delete=models.CASCADE, null=True, blank=True)
    devisService = models.ForeignKey(Devis,on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return f'{self.nomService}'
    
    @property
    def get_montantDuService(self):
        return self.montantDuService
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(factureService__isnull=False, devisService__isnull=True) |
                    models.Q(factureService__isnull=True, devisService__isnull=False)
                ),
                name='service_facture_ou_devis'
            )
        ]