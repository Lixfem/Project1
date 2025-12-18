from django import forms
from .models import Facturation, Produit, Service, Client, Category, Devis, ProduitDevis, ServiceDevis, ProduitFacturation, ServiceFacturation, ModeReglement, Reglement
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
import re


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['client_type', 'nom', 'email', 'telephone', 'adresse', 'ville', 
                  'sexe', 'company_id_number', 'company_iban', 'company_bic']
        widgets = {
            'client_type': forms.Select(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom et prénom du client', 'required': True}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email du client', 'required': True}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro de téléphone du client'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Adresse du client', 'rows': 3}),
            'ville': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ville du client'}),
            'sexe': forms.Select(attrs={'class': 'form-control'}),
            'company_id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Numéro d'identification de l'entreprise"}),
            'company_iban': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "IBAN de l'entreprise"}),
            'company_bic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "BIC de l'entreprise"}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.client_type == Client.TYPE_ENTREPRISE:
            self.fields['sexe'].required = False
            self.fields['company_id_number'].required = True
            self.fields['company_iban'].required = False
            self.fields['company_bic'].required = False
        else:
            self.fields['sexe'].required = False
            self.fields['company_id_number'].required = False
            self.fields['company_iban'].required = False
            self.fields['company_bic'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        client_type = cleaned_data.get('client_type')
        if client_type == Client.TYPE_INDIVIDU and not cleaned_data.get('sexe'):
            self.add_error('sexe', 'Le sexe est requis pour les clients individuels.')
        elif client_type == Client.TYPE_ENTREPRISE and not cleaned_data.get('company_id_number'):
            self.add_error('company_id_number', "L'immatriculation est requise pour les entreprises.")
        return cleaned_data


    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.instance.pk:
            if Client.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Un client avec cet email existe déjà.")
        else:
            if Client.objects.filter(email=email).exists():
                raise forms.ValidationError("Un client avec cet email existe déjà.")
        return email
   


from django import forms
from django.core.exceptions import ValidationError

class FacturationForm(forms.ModelForm):
    # Champ optionnel pour sélectionner un devis
    devis_source = forms.ModelChoiceField(
        queryset=None,  # Sera défini dans __init__
        required=False,
        label="Créer depuis un devis existant (optionnel)",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_devis_source'
        }),
        help_text="Sélectionnez un devis accepté pour pré-remplir la facture"
    )
    
    class Meta:
        model = Facturation
        fields = ['client', 'devis_origine', 'montant_accompte', 'taux_tva', 'statut', 'commentaire']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'devis_origine': forms.HiddenInput(),  # Caché, sera rempli par devis_source
            'montant_accompte': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'taux_tva': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'value': '18.00'
            }),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'commentaire': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            })
        }
    
    def __init__(self, *args, user=None, produit_formset=None, service_formset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.produit_formset = produit_formset
        self.service_formset = service_formset
        
        if user:
            # Filtrer les clients de l'utilisateur
            self.fields['client'].queryset = Client.objects.filter(save_by=user)
            
            # Filtrer les devis acceptés non transformés
            self.fields['devis_source'].queryset = Devis.objects.filter(
                save_by=user,
                statut=Devis.STATUT_ACCEPTE,
                est_transforme_en_facture=False
            ).select_related('client')
            
            # Personnaliser l'affichage des devis
            self.fields['devis_source'].label_from_instance = lambda obj: (
                f"{obj.numero} - {obj.client.nom} - {obj.total_ttc} FCFA"
            )
    
    def clean(self):
        cleaned_data = super().clean()
        devis_source = cleaned_data.get('devis_source')
        client = cleaned_data.get('client')
        
        # Si un devis est sélectionné, vérifier la cohérence
        if devis_source:
            if client and client != devis_source.client:
                raise ValidationError(
                    "Le client sélectionné doit correspondre au client du devis."
                )
            # Copier le devis dans devis_origine
            cleaned_data['devis_origine'] = devis_source
            cleaned_data['client'] = devis_source.client
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save_by = self.user
            instance.save()
        
        return instance
class DevisForm(forms.ModelForm):
    class Meta:
        model = Devis
        fields = ['client', 'statut', 'commentaire', 'taux_tva', 'date_validite']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'commentaire': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'Commentaire sur le devis (optionnel)'
            }),
            'taux_tva': forms.NumberInput(attrs={
                'step': '0.01', 
                'min': '0',
                'class': 'form-control',
                'placeholder': 'Taux de TVA (%) - Par défaut: 18%'
            }),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'date_validite': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }


    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.produit_formset = kwargs.pop('produit_formset', None)
        self.service_formset = kwargs.pop('service_formset', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['client'].queryset = Client.objects.filter(save_by=self.user)
        self.fields['commentaire'].required = False
        self.fields['taux_tva'].required = False
        self.fields['date_validite'].required = False

    def clean(self):
        cleaned_data = super().clean()
        # Vérifier que les formsets contiennent au moins un produit ou service
        if self.produit_formset and self.service_formset:
            produit_valid = any(form.is_valid() and not form.cleaned_data.get('DELETE', False) 
                               for form in self.produit_formset)
            service_valid = any(form.is_valid() and not form.cleaned_data.get('DELETE', False) 
                               for form in self.service_formset)
            if not (produit_valid or service_valid):
                raise forms.ValidationError("Veuillez ajouter au moins un produit ou un service au devis.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.numero:
            instance.numero=instance.generer_numero_devis()
        if self.user and not instance.save_by_id:
            instance.save_by = self.user
        if commit:
            instance.save()
        return instance


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['nom','description']
        widgets ={
            'nom': forms.TextInput(attrs={
                'class':'form-control',
                'placeholder': 'Nom de la catégorie'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Description de la categorie'
            }),
        }
    def __init__(self, *args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['description'].required= False

    def clean_nom(self):
        nom = self.cleaned_data.get('nom')
        if self.instance and self.instance.pk:
            if Category.objects.filter(nom=nom).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(" Cette Catégorie existe déjà")
        else:
            if Category.objects.filter(nom=nom).exists():
                raise forms.ValidationError(" Cette Catégorie existe déjà")
        return nom



class ServiceFacturationForm(forms.ModelForm):
    class Meta:
        model = ServiceFacturation
        fields = ['service', 'date_prestation_service']
        widgets = {
            'service':forms.Select(attrs={'class': 'form-control'}),
            'date_prestation_service': forms.DateInput(attrs={
                'type':'date',
                'class': 'form-control'
            }),
        }
    
    def __init__(self,*args, **kwargs):
        self.devis_origine = kwargs.pop('devis_origine', None)
        super().__init__(*args, **kwargs )
        self.fields['date_prestation_service'].required = False

    def clean(self):
        cleaned_data = super().clean()
        date_prestation_service = cleaned_data.get('date_prestation_service')
        if date_prestation_service and self.devis_origine:
            if date_prestation_service < self.devis_origine.date_validite:
                self.add_error('date_prestation_service','La date de prestation doit être postérieure ou égale à la date de validité du devis.')
        return cleaned_data



class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = ['nom_produit', 'description_produit', 'prix_unitaire_produit', 'category']
        widgets = {
            'nom_produit': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nom du produit'
            }),
            'description_produit': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control', 
                'placeholder': 'Description du produit'
            }),
            'prix_unitaire_produit': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0.01', 
                'step': '0.01',
                'placeholder': 'Prix unitaire'
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.all()
        self.fields['category'].required = False 
        self.fields['description_produit'].required = False

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['nom_service','description_service','montant_du_service']
        widgets = {
            'nom_service':forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nom du service'
            }),
            'description_service':  forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control', 
                'placeholder': 'Description du service'
            }),
            'montant_du_service': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0.01', 
                'step': '0.01',
                'placeholder': 'Montant du service'
            }),
        }


class ProduitDevisForm(forms.ModelForm):
    nom_produit = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control produit-search',
            'placeholder': 'Rechercher un produit',
            'autocomplete': 'off'
        })
    )
    description_produit = forms.CharField(
        required=False,
         widget=forms.Textarea(attrs={ 
        'class': 'form-control produit-search',
        'rows': 2,
        'placeholder': 'Description du produit', 'readonly': 'readonly'
          })
    )
    prix_unitaire_produit = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'})
    )
    category = forms.CharField(
        #queryset=Category.objects.all(),
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control','readonly': 'readonly'})
    )

    class Meta:
        model = ProduitDevis
        fields = ['produit', 'quantite', 'remise']
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control',
                                                  'min': '0',
                                                  'step': '1',
                                                  'placeholder': 'Quantité'}), 
            'remise': forms.NumberInput(attrs={'class': 'form-control',
                                              'min': '0',
                                              'max': '100',
                                              'step': '0.01',
                                             'value':'0' }) 
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pré-remplir les champs depuis le produit existant
        if self.instance and self.instance.pk and self.instance.produit:
            self.initial['nom_produit'] = self.instance.produit.nom_produit
            self.initial['description_produit'] = self.instance.produit.description_produit
            self.initial['prix_unitaire_produit'] = self.instance.produit.prix_unitaire_produit
            if hasattr(self.instance.produit, 'category'):
                self.initial['category'] = self.instance.produit.category

    def clean(self):
        cleaned_data = super().clean()
        produit = cleaned_data.get('produit')
        quantite = cleaned_data.get('quantite')
        remise = cleaned_data.get('remise')
        if produit and quantite is not None:
            if quantite < 0:
                self.add_error('quantite', "La quantité ne peut pas être négative.")
            if remise is not None and (remise < 0 or remise > 100):
                self.add_error('remise', "La remise doit être comprise entre 0 et 100%.")
        return cleaned_data

# Definition des formsets pour devis
ProduitDevisFormset = inlineformset_factory(
    Devis, ProduitDevis, form=ProduitDevisForm, fields=('produit',
    'quantite','remise'), extra=1, can_delete=True
)

class ServiceDevisForm(forms.ModelForm):
    nom_service = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du service'})
    )
    description_service = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Description','readonly': 'readonly'})
    )
    montant_du_service = forms.DecimalField(
        required=True,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01','readonly': 'readonly'})
    )
    date_prestation_service = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = ServiceDevis
        fields = ['service', 'date_prestation_service']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.service_id:
            self.fields['nom_service'].initial = self.instance.service.nom_service
            self.fields['description_service'].initial = self.instance.service.description_service
            self.fields['montant_du_service'].initial = self.instance.service.montant_du_service
            self.fields['date_prestation_service'].initial = self.instance.date_prestation_service

    def clean(self):
        cleaned_data = super().clean()
        nom_service = cleaned_data.get('nom_service')
        if nom_service:
            try:
                service = Service.objects.get(nom_service=nom_service)
                cleaned_data['service'] = service
            except Service.DoesNotExist:
                self.add_error('nom_service', f"Le service '{nom_service} n'existe pas. Veuillez le créer d'abord.")
        return cleaned_data

ServiceDevisFormset = inlineformset_factory(
    Devis,
    ServiceDevis,
    form=ServiceDevisForm,
    fields=('service', 'date_prestation_service', 'nom_service', 
            'description_service', 'montant_du_service'),
    extra=1,can_delete=True
)

# Formsets pour Facturation
class ProduitFacturationForm(forms.ModelForm):
    nom_produit = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control produit-search',
            'placeholder': 'Rechercher un produit',
            'autocomplete': 'off'
        })
    )
    description_produit = forms.CharField(
        required=False,
         widget=forms.Textarea(attrs={ 
        'class': 'form-control produit-search',
        'rows': 2,
        'placeholder': 'Description du produit', 'readonly': 'readonly'
          })
    )
    prix_unitaire_produit = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'})
    )
    category = forms.CharField(
        #queryset=Category.objects.all(),
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control','readonly': 'readonly'})
    )

    class Meta:
        model = ProduitFacturation
        fields = ['produit', 'quantite', 'remise']
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control',
                                                  'min': '0',
                                                  'step': '1',
                                                  'placeholder': 'Quantité'}), 
            'remise': forms.NumberInput(attrs={'class': 'form-control',
                                              'min': '0',
                                              'max': '100',
                                              'step': '0.01',
                                             'value':'0' }) 
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pré-remplir les champs depuis le produit existant
        if self.instance and self.instance.pk and self.instance.produit:
            self.initial['nom_produit'] = self.instance.produit.nom_produit
            self.initial['description_produit'] = self.instance.produit.description_produit
            self.initial['prix_unitaire_produit'] = self.instance.produit.prix_unitaire_produit
            if hasattr(self.instance.produit, 'category'):
                self.initial['category'] = self.instance.produit.category

    def clean(self):
        cleaned_data = super().clean()
        produit = cleaned_data.get('produit')
        quantite = cleaned_data.get('quantite')
        remise = cleaned_data.get('remise')
        if produit and quantite is not None:
            if quantite < 0:
                self.add_error('quantite', "La quantité ne peut pas être négative.")
            if remise is not None and (remise < 0 or remise > 100):
                self.add_error('remise', "La remise doit être comprise entre 0 et 100%.")
        return cleaned_data


ProduitFacturationFormset = inlineformset_factory(
    Facturation, ProduitFacturation, 
    form=ProduitFacturationForm, 
    fields=('produit','quantite','remise'), 
    extra=1, can_delete=True
)


class ServiceFacturationForm(forms.ModelForm):
    nom_service = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du service'})
    )
    description_service = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Description','readonly': 'readonly'})
    )
    montant_du_service = forms.DecimalField(
        required=True,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01','readonly': 'readonly'})
    )
    date_prestation_service = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = ServiceFacturation
        fields = ['service', 'date_prestation_service']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.service_id:
            self.fields['nom_service'].initial = self.instance.service.nom_service
            self.fields['description_service'].initial = self.instance.service.description_service
            self.fields['montant_du_service'].initial = self.instance.service.montant_du_service
            self.fields['date_prestation_service'].initial = self.instance.date_prestation_service

    def clean(self):
        cleaned_data = super().clean()
        nom_service = cleaned_data.get('nom_service')
        if nom_service:
            try:
                service = Service.objects.get(nom_service=nom_service)
                cleaned_data['service'] = service
            except Service.DoesNotExist:
                self.add_error('nom_service', f"Le service '{nom_service} n'existe pas. Veuillez le créer d'abord.")
        return cleaned_data

ServiceFacturationFormset = inlineformset_factory(
    Facturation, ServiceFacturation, form=ServiceFacturationForm, extra=1
)

class ModeReglementForm(forms.ModelForm):
    class Meta :
        model = ModeReglement
        fields = ['nom','description','est_actif']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du mode de règlement'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description du mode de règlement (optionnel)'
            }),
            'est_actif': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['est_actif'].initial = True # Actif par defaut


from decimal import Decimal, ROUND_HALF_UP
from django import forms
from django.core.exceptions import ValidationError
from .models import Reglement, Facturation, Client, ModeReglement
import re

class ReglementForm(forms.ModelForm):
    montant_reglement = forms.CharField(
        label="Montant du règlement",
        widget=forms.TextInput(attrs={
            'class': 'form-control montant-input',
            'placeholder': '0'
        })
    )

    class Meta:
        model = Reglement
        fields = ['client', 'facture', 'mode_reglement', 'montant_reglement']
        widgets = {
            'client': forms.HiddenInput(),
            'facture': forms.HiddenInput(),
            'mode_reglement': forms.Select(attrs={'class': 'form-control'}),
        }

    # --------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        # 1. Récupérer la facture passée depuis la vue
        self.facture = kwargs.pop('facture', None)          # <-- pop avant super()
        super().__init__(*args, **kwargs)

        # 2. Pré-remplir les champs cachés
        if self.facture:
            self.fields['client'].initial = self.facture.client
            self.fields['facture'].initial = self.facture
            # on rend les champs cachés non-requéris (ils seront remplis par le formulaire)
            self.fields['client'].required = False
            self.fields['facture'].required = False

        # 3. Si on édite un règlement existant → garder les valeurs actuelles
        if self.instance.pk:
            self.fields['client'].initial = self.instance.client
            self.fields['facture'].initial = self.instance.facture

    # --------------------------------------------------------------
    def clean_montant_reglement(self):
        montant_str = self.cleaned_data.get('montant_reglement')
        if not montant_str:
            raise ValidationError("Le montant est requis.")

        # Nettoyage du texte saisi (ex: 1 234,56 → 1234.56)
        montant_str = re.sub(r'[^\d,.]', '', str(montant_str)).replace(',', '.')

        try:
            montant = Decimal(montant_str)
        except Exception:
            raise ValidationError("Format de montant invalide.")

        if montant <= 0:
            raise ValidationError("Le montant doit être positif.")

        return montant.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # --------------------------------------------------------------
    def clean(self):
        cleaned_data = super().clean()
        montant_nouveau = cleaned_data.get('montant_reglement')
        if not montant_nouveau:
            return cleaned_data

        # On a besoin d’une facture pour la validation
        facture = self.facture or cleaned_data.get('facture')

        if not facture:
            # Si pas de facture (cas rare), on essaie avec l'instance
            facture = getattr(self.instance, 'facture', None)

        if not facture:
            return cleaned_data

        # Montant actuel (0 pour création)
        ancien_montant = self.instance.montant_reglement if self.instance.pk else Decimal('0')

        solde_actuel = facture.solde_du
        max_autorise = solde_actuel + ancien_montant

        if montant_nouveau > max_autorise:
            raise ValidationError(
                f"Le montant ne peut pas dépasser {max_autorise:,.0f} FCFA "
                f"(solde disponible après annulation du règlement actuel)."
            )
        return cleaned_data