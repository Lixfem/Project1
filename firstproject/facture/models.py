from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta, datetime
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum
from facture.utils import default_validity_date
from encrypted_model_fields.fields import EncryptedCharField
from django.utils.text import slugify
from django.db.models.functions import Coalesce


QUANTIZE_2 = Decimal('0.01')

def arrondi(value):
    """Arrondit proprement à 2 décimales"""
    if value is None:
        return Decimal('0.00')
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)

class Client(models.Model):
    TYPE_INDIVIDU = 'INDIVIDU'
    TYPE_ENTREPRISE = 'ENTREPRISE'
    TYPE_CHOICES = (
        (TYPE_INDIVIDU, 'Individu'),
        (TYPE_ENTREPRISE, 'Entreprise'),
    )
    SEXE_MASCULIN = 'Masculin'
    SEXE_FEMININ = 'Feminin'
    SEXE_CHOICES = (
        (SEXE_MASCULIN, 'Masculin'),
        (SEXE_FEMININ, 'Féminin'),
    )

    client_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_INDIVIDU)
    nom = models.CharField(max_length=100)
    email = models.EmailField(max_length=150,unique=True)
    telephone = models.CharField(max_length=50, blank=True)
    adresse = models.TextField()
    ville = models.CharField(max_length=50, blank=True)
    sexe = models.CharField(max_length=15, choices=SEXE_CHOICES, blank=True)
    company_id_number = models.CharField(max_length=45, blank=True)
    company_iban = EncryptedCharField(max_length=34, blank=True)
    company_bic = EncryptedCharField(max_length=20, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    save_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='clients')
    
    def __str__(self):
        return f"{self.nom} ({self.get_client_type_display()})"

    def clean(self):
        if self.client_type == self.TYPE_INDIVIDU and not self.sexe:
            raise ValidationError("Le sexe est requis pour les clients individuels.")
        elif self.client_type == self.TYPE_ENTREPRISE:
            if  not self.company_id_number:
                raise ValidationError("L'immatriculation est requise pour les entreprises.")
            self.sexe = '' # vide pour entreprises
        

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['telephone']),
            models.Index(fields=['client_type']),
            models.Index(fields=['date_creation']),
        ]
class DevisAlreadyTransformedError(Exception):
    pass
class DevisNotAcceptedError(Exception):
    pass 

class Devis(models.Model):
    STATUT_ATTENTE = 1
    STATUT_ACCEPTE = 2
    STATUT_REFUSE = 3
    STATUT_TRANSFORME_FACTURE = 4
    STATUT_CHOICES = (
        (STATUT_ATTENTE, 'En Attente'),
        (STATUT_ACCEPTE, 'Accepté'),
        (STATUT_REFUSE, 'Refusé'),
        (STATUT_TRANSFORME_FACTURE, 'Transformé en facture'),
    )

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='devis')
    save_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='devis')
    date_creation = models.DateTimeField(auto_now_add=True)
    statut = models.IntegerField(choices=STATUT_CHOICES, default=STATUT_ATTENTE)
    numero = models.CharField(max_length=50, unique=True)
    last_update = models.DateTimeField(default=timezone.now)
    commentaire = models.TextField(null=True, blank=True, help_text="Entrer un commentaire sur le devis")
    net_a_payer = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=Decimal('18.00'))
    total_net_ht = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_tva = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    date_validite = models.DateField(default=default_validity_date)
    est_transforme_en_facture = models.BooleanField(default=False)
    date_transformation = models.DateTimeField(null=True, blank=True)
    produits = models.ManyToManyField('Produit', through='ProduitDevis', related_name='devis')
    services = models.ManyToManyField('Service', through='ServiceDevis', related_name='devis')

    def __str__(self):
        return f"Devis {self.numero} - {self.client.nom}"

    def get_total(self):
        """Calcule le total des produits avec remises"""
        if not hasattr(self, '_cached_total'):
            self._cached_total = sum(
                item.total for item in self.produitdevis_set.all()
            )
        return self._cached_total

    def get_montant_service(self):
        """Calcule le total des services"""
        if not hasattr(self, '_cached_service_total'):
            self._cached_service_total = sum(
                item.service.montant_du_service for item in self.servicedevis_set.all()
            )
        return self._cached_service_total

    def generer_numero_devis(self):
        """Génère un numéro de devis unique"""
        with transaction.atomic():
            annee = timezone.now().year
            dernier = Devis.objects.filter(
                numero__startswith=f"DEV-{annee}"
            ).select_for_update().order_by('-numero').first()
            
            if dernier:
                dernier_num = int(dernier.numero.split('-')[-1])
                nouveau_num = dernier_num + 1
            else:
                nouveau_num = 1
            return f"DEV-{annee}-{nouveau_num:05d}"
    
    def recalculer_totaux(self):
        """
        Recalcule et SAUVEGARDE tous les totaux du devis.
        Cette méthode doit être appelée après modification des produits/services.
        """
        # Invalider le cache
        if hasattr(self, '_cached_total'):
            del self._cached_total
        if hasattr(self, '_cached_service_total'):
            del self._cached_service_total
        
        # Recalculer les totaux
        self.total_net_ht = self.get_total() + self.get_montant_service()
        taux_tva = self.taux_tva if self.taux_tva is not None else Decimal('18.00')
        self.total_tva = self.total_net_ht * (taux_tva / Decimal('100.00'))
        self.total_ttc = self.total_net_ht + self.total_tva
        self.net_a_payer = self.total_ttc
        
        # Sauvegarder uniquement les champs de totaux
        self.save(update_fields=['total_net_ht', 'total_tva', 'total_ttc', 'net_a_payer'])

    def save(self, *args, **kwargs):
        """
        Sauvegarde le devis et génère un numéro si nécessaire.
        Note: Ne recalcule PAS les totaux automatiquement pour éviter les boucles infinies.
        """
        if not self.numero:
            self.numero = self.generer_numero_devis()
        
        super().save(*args, **kwargs)

    def ajouter_produits(self, produits, quantites, remises=None):
        """Ajoute des produits au devis"""
        if remises is None:
            remises = [Decimal('0.00')] * len(produits)
        
        for produit, quantite, remise in zip(produits, quantites, remises):
            if not ProduitDevis.objects.filter(devis=self, produit=produit).exists():
                ProduitDevis.objects.create(
                    devis=self,
                    produit=produit,
                    quantite=quantite,
                    remise=remise
                )
        
        # Recalculer les totaux après ajout
        self.recalculer_totaux()

    def ajouter_services(self, services, dates_prestation=None):
        """Ajoute des services au devis avec leurs dates de prestation (optionnel)"""
        if dates_prestation is None:
            dates_prestation = [None] * len(services)
        
        for service, date_prestation in zip(services, dates_prestation):
            if not ServiceDevis.objects.filter(devis=self, service=service).exists():
                ServiceDevis.objects.create(
                    devis=self,
                    service=service,
                    date_prestation_service=date_prestation
                )
        
        # Recalculer les totaux après ajout
        self.recalculer_totaux()

    def transformer_en_facture(self, user):
        """Transforme le devis en facture"""
        if self.est_transforme_en_facture:
            raise DevisAlreadyTransformedError("Ce devis a déjà été transformé en facture")
        if self.statut != self.STATUT_ACCEPTE:
            raise DevisNotAcceptedError("Seul un devis accepté peut être transformé en facture")

        with transaction.atomic():
            facture = Facturation.objects.create(
                client=self.client,
                save_by=user,
                devis_origine=self,
                statut=Facturation.STATUT_EN_ATTENTE,
                commentaire=f"Facture générée depuis le devis {self.numero}\n{self.commentaire or ''}",
                taux_tva=self.taux_tva,
                total_net_ht=self.total_net_ht,
                total_tva=self.total_tva,
                total_ttc=self.total_ttc,
                net_a_payer=self.net_a_payer
            )
            
            # Copie des produits
            for produit_devis in self.produitdevis_set.all():
                ProduitFacturation.objects.create(
                    facture=facture,
                    produit=produit_devis.produit,
                    quantite=produit_devis.quantite,
                    remise=produit_devis.remise,
                    total=produit_devis.total
                )
            
            # Copie des services 
            for service_devis in self.servicedevis_set.all():
                ServiceFacturation.objects.create(
                    facture=facture,
                    service=service_devis.service,
                    date_prestation_service=service_devis.date_prestation_service
                )

            # Mise à jour du devis 
            self.est_transforme_en_facture = True
            self.statut = self.STATUT_TRANSFORME_FACTURE
            self.date_transformation = timezone.now()
            self.last_update = timezone.now()
            self.save()
            
            return facture

    def peut_etre_transforme(self):
        """Vérifie si le devis peut être transformé en facture"""
        return self.statut == self.STATUT_ACCEPTE and not self.est_transforme_en_facture

    class Meta:
        indexes = [
            models.Index(fields=['numero']),
            models.Index(fields=['date_creation']),
            models.Index(fields=['statut']),
            models.Index(fields=['client', 'statut']),
            models.Index(fields=['-date_validite']),
            models.Index(fields=['-date_creation']),
        ]
        verbose_name = "Devis"
        verbose_name_plural = "Devis"

# Constantes pour arrondi propre

class Facturation(models.Model):
    STATUT_PAYE = 1
    STATUT_EN_ATTENTE = 2
    STATUT_ANNULE = 3
    STATUT_CHOICES = (
        (STATUT_PAYE, 'Payé'),
        (STATUT_EN_ATTENTE, 'En Attente'),
        (STATUT_ANNULE, 'Annulée'),
    )
    
    client = models.ForeignKey(Client, on_delete=models.PROTECT) 
    devis_origine = models.OneToOneField(
        Devis, 
        on_delete=models.PROTECT, 
        null=True,  # Changé pour permettre None temporairement
        blank=True, 
        related_name='facture_generee'
    )
    save_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='factures')
    montant_accompte = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00, 
        validators=[MinValueValidator(0)]
    )
    #solde_du = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    date_creation = models.DateTimeField(auto_now_add=True)
    statut = models.IntegerField(choices=STATUT_CHOICES, default=STATUT_EN_ATTENTE)
    numero = models.CharField(max_length=50, unique=True)
    last_update = models.DateTimeField(default=timezone.now)
    commentaire = models.TextField(null=True, blank=True, help_text="Entrer un commentaire sur la facture")
    net_a_payer = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    taux_tva = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        default=Decimal('18.00')
    )
    total_tva = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_net_ht = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    produits = models.ManyToManyField('Produit', through='ProduitFacturation', related_name='factures')
    services = models.ManyToManyField('Service', through='ServiceFacturation', related_name='factures')

    def __str__(self):
        return f"Facture {self.numero} - {self.client.nom}"

    def get_total(self):
        """Calcule le total des produits avec remises"""
        if not self.pk:
            return Decimal('0.00')
        return sum(item.get_total() for item in self.produitfacturation_set.all())

    def get_montant_service(self):
        """Calcule le total des services"""
        if not self.pk:
            return Decimal('0.00')
        return sum(item.service.montant_du_service for item in self.servicefacturation_set.all())

    def generer_numero_facture(self):
        """Génère un numéro de facture unique"""
        with transaction.atomic():
            annee = timezone.now().year
            dernier = Facturation.objects.filter(
                numero__startswith=f"FAC-{annee}"
            ).select_for_update().order_by('-numero').first()
            
            if dernier:
                dernier_num = int(dernier.numero.split('-')[-1])
                nouveau_num = dernier_num + 1
            else:
                nouveau_num = 1
            return f"FAC-{annee}-{nouveau_num:05d}"
    
    def clean(self):
        """Validation personnalisée"""
        if self.devis_origine is None:
            raise ValidationError("Une facture doit être associée à un devis existant.")
        if self.devis_origine.est_transforme_en_facture and self.pk is None:
            # Vérifier seulement à la création, pas à la modification
            raise ValidationError("Le devis associé a déjà été transformé en facture.")
        if self.montant_accompte > self.net_a_payer:
            raise ValidationError("L'accompte ne peut pas être supérieur au net à payer.")
        
    @property
    def solde_du(self):
        """Solde dû calculé en temps réel – toujours juste, jamais obsolète"""
        if not self.pk:
            return Decimal('0.00')

        total_reglements = self.reglement_set.aggregate(
            total=Coalesce(Sum('montant_reglement'), Decimal('0.00'))
        )['total']

        solde = self.net_a_payer - self.montant_accompte - total_reglements
        return max(Decimal('0.00'), solde)  # solde jamais négatif

    def recalculer_totaux(self):
        """
        Recalcule et sauvegarde tous les totaux avec arrondi propre à 2 décimales.
        """
        if not self.pk:
            return  # impossible de calculer sans ID

        # 1. Calcul des totaux de base
        total_produits = self.get_total()
        total_services = self.get_montant_service()
        self.total_net_ht = arrondi(total_produits + total_services)

        # 2. TVA
        taux_tva = self.taux_tva if self.taux_tva is not None else Decimal('18.00')
        self.total_tva = arrondi(self.total_net_ht * (taux_tva / Decimal('100')))

        # 3. TTC et net à payer
        self.total_ttc = arrondi(self.total_net_ht + self.total_tva)
        self.net_a_payer = self.total_ttc  # identique

    
        if self.solde_du <= 0:
            self.statut = self.STATUT_PAYE
        else:
            self.statut = self.STATUT_EN_ATTENTE# au cas où on rembourse trop

        # 6. Sauvegarde uniquement les champs modifiés
        self.save(update_fields=[
            'total_net_ht', 'total_tva', 'total_ttc',
            'net_a_payer', 'statut'
        ])
    def save(self, *args, **kwargs):
        """
        Sauvegarde la facture et génère un numéro si nécessaire.
        Note: Ne recalcule PAS les totaux automatiquement pour éviter les erreurs.
        """
        # Générer le numéro si nécessaire
        if not self.numero:
            self.numero = self.generer_numero_facture()
        
        # Validation seulement si ce n'est pas un update partiel
        if 'update_fields' not in kwargs:
            self.full_clean()
        
        super().save(*args, **kwargs)
        # Recalcule uniquement si on touche à des champs qui impactent le solde
        
    class Meta:
        indexes = [
            models.Index(fields=['numero']),
            models.Index(fields=['date_creation']),
            models.Index(fields=['statut']),
            models.Index(fields=['client', 'statut']),
            models.Index(fields=['-date_creation']),
        ]
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
class Category(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    date_creation = models.DateField(auto_now_add=True)
    

    def __str__(self):
        return self.nom
    
    def save(self,*args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)
        super().save(*args, **kwargs)


    class Meta:
        verbose_name_plural = "categories"
        verbose_name = "categorie"

class Produit(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=False, blank=True, related_name='produits')
    nom_produit = models.CharField(max_length=40, unique=True)
    description_produit = models.CharField(max_length=400)
    prix_unitaire_produit = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.nom_produit
    
    def clean(self):
        if self.prix_unitaire_produit<0:
            raise ValidationError("Le prix ne peut être en dessous de 0 ")
        
    def save(self):
        self.full_clean()
        return super().save()


    
   
    class Meta:
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['nom_produit']),
        ]
class ProduitDevis(models.Model):
    devis = models.ForeignKey(Devis, on_delete=models.CASCADE, related_name='produitdevis_set')
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='produitdevis_set')
    quantite = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    remise = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00, 
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    # Option 1: Rendre le champ nullable temporairement
    total = models.DecimalField(
        max_digits=15,  # Augmenté pour éviter les dépassements
        decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,  # Permet le champ vide dans les forms
        null=True    # Permet NULL dans la base de données
    )

    def get_total(self):
        """Calcule le total avec remise"""
        if self.produit and self.quantite is not None:
            prix_unitaire = Decimal(str(self.produit.prix_unitaire_produit))
            quantite = Decimal(str(self.quantite))
            remise = Decimal(str(self.remise))
            
            self.total = quantite * prix_unitaire * (Decimal('1.00') - remise / Decimal('100.00'))
            return self.total
        return Decimal('0.00')
    
    def save(self, *args, **kwargs):
        """Calcule automatiquement le total avant la sauvegarde"""
        # Calculer le total avant de sauvegarder
        self.get_total()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.produit.nom_produit} x {self.quantite} = {self.total} FCFA"

    class Meta:
        verbose_name = "Produit du devis"
        verbose_name_plural = "Produits du devis"

class Service(models.Model):
    nom_service = models.CharField(max_length=60,unique=True)
    description_service = models.CharField(max_length=400)
    montant_du_service = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    def __str__(self):
        return self.nom_service

    def save(self, *args, **kwargs):
        #self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['nom_service']),
        ]

class ServiceDevis(models.Model):
    devis = models.ForeignKey(Devis, on_delete=models.CASCADE, related_name='servicedevis_set')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='servicedevis_set')
    date_prestation_service = models.DateField(null=True, blank=True)

    
    def save(self):
        #self.full_clean()
        return super().save()

class ProduitFacturation(models.Model):
    facture = models.ForeignKey(Facturation, on_delete=models.CASCADE, related_name='produitfacturation_set')
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='produitfacturation_set')
    quantite = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    remise = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, validators=[MinValueValidator(0), MaxValueValidator(100)])
    total = models.DecimalField(
        max_digits=15,  # Augmenté pour éviter les dépassements
        decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,  # Permet le champ vide dans les forms 
        null=True    # Permet NULL dans la base de données
    )
    def get_total(self):
        """Calcule le total avec remise"""
        if self.produit and self.quantite is not None:
            prix_unitaire = Decimal(str(self.produit.prix_unitaire_produit))
            quantite = Decimal(str(self.quantite))
            remise = Decimal(str(self.remise))
            
            self.total = quantite * prix_unitaire * (Decimal('1.00') - remise / Decimal('100.00'))
            return self.total
        return Decimal('0.00')
       
    def save(self, *args, **kwargs):
        self.total = self.get_total()
        super().save(*args, **kwargs)

class ServiceFacturation(models.Model):
    facture = models.ForeignKey(Facturation, on_delete=models.CASCADE, related_name='servicefacturation_set')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='servicefacturation_set')
    date_prestation_service = models.DateField(null=True, blank=True)

    def clean(self):
        pass

    def save(self,*args, **kwargs):
        
        return super().save(*args, **kwargs)

class ModeReglement(models.Model):
    nom = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    est_actif = models.BooleanField(default=True, help_text="Indique si ce mode de règlement est disponible pour une utilisation.")
    date_creation = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.nom

    # AJOUTE ÇA :
    def get_badge_class(self):
        return 'bg-success text-white' if self.est_actif else 'bg-warning text-dark'
    class Meta:
        verbose_name = "Mode de règlement"
        verbose_name_plural = "Modes de règlement"

        # models.py


    
class Reglement(models.Model):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='reglements')
    facture = models.ForeignKey(Facturation, on_delete=models.PROTECT, related_name='reglement_set')
    date_reglement = models.DateField(auto_now_add=True)
    montant_reglement = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    mode_reglement = models.ForeignKey(ModeReglement, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'est_actif': True})
    

    def __str__(self):
        return f"Règlement {self.facture.numero} - {self.client.nom}"
    
   # models.py → Reglement
    def clean(self):
        if self.montant_reglement <= 0:
            raise ValidationError("Le montant doit être positif.")

        # On force le recalcul du solde juste avant la validation
        self.facture.recalculer_totaux()

        if self.montant_reglement > self.facture.solde_du:
            raise ValidationError(
                f"Le montant ({self.montant_reglement} FCFA) dépasse le solde dû "
                f"de {self.facture.solde_du} FCFA."
            )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.facture.recalculer_totaux()

    class Meta:
        indexes = [
            models.Index(fields=['facture']),
            models.Index(fields=['client']),
            models.Index(fields=['date_reglement']),
            models.Index(fields=['facture', 'date_reglement']),
        ]