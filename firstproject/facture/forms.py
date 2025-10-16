from django import forms
from .models import Facturation, Produit, Service, Client, Category, Devis
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['client_type', 'nom', 'email', 'telephone', 'adresse', 'ville', 
                  'sexe', 'company_id_number', 'company_iban', 'company_bic']
        widgets = {
            'client_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom et prénom du client',
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email du client',
                'required': True
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de téléphone du client'
            }),
            'sexe': forms.Select(attrs={
                'class': 'form-control'
            }),
            'adresse': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Adresse du client',
                'rows': 3
            }),
            'ville': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ville du client'
            }),
            'company_id_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Numéro d'identification de l'entreprise"
            }),
            'company_iban': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "IBAN de l'entreprise"
            }),
            'company_bic': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "BIC de l'entreprise"
            })
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Exclure l'instance actuelle lors de la modification
        if self.instance and self.instance.pk:
            if Client.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Un client avec cet email existe déjà.")
        else:
            if Client.objects.filter(email=email).exists():
                raise forms.ValidationError("Un client avec cet email existe déjà.")
        return email
    
   


class FacturationForm(forms.ModelForm):
    class Meta:
        model = Facturation
        fields = ['client', 'montant_accompte', 'statut', 'commentaire', 'taux_tva']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'montant_accompte': forms.NumberInput(attrs={
                'step': '0.01', 
                'min': '0',
                'class': 'form-control'
            }),
            'commentaire': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'Commentaire sur la facture (optionnel)'
            }),
            'taux_tva': forms.NumberInput(attrs={
                'step': '0.01', 
                'min': '0',
                'class': 'form-control',
                'placeholder': 'Taux de TVA (%) - Par défaut: 18%'
            }),
            'statut': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['client'].queryset = Client.objects.all()
        self.fields['commentaire'].required = False
        self.fields['tva_rate'].required = False
        self.fields['montant_accompte'].required = False

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user and not instance.save_by_id:
            instance.save_by = self.user
        if commit:
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
        super().__init__(*args, **kwargs)
        self.fields['client'].queryset = Client.objects.all()
        self.fields['commentaire'].required = False
        self.fields['tva_rate'].required = False
        self.fields['date_validite'].required = False

    def save(self, commit=True):
        instance = super().save(commit=False)
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
        self.fields['quantity'].required = False
        self.fields['description_produit'].required = False


# Forme specialise pour les produits dans les devis/factures
# class ProduitInlineForm(ProduitForm):
#     produit_existant = forms.ModelChoiceField(
#         queryset= Produit.objects.all(),
#         required=False,
#         widget= forms.Select(attrs={
#             'class': 'form-control produit-existant-select',
#         }),
#         label="Sélectionner un produit existant."
#     )

#     class Meta(ProduitForm.Meta):
#         fields =['produit_existant','nom_produit','description_produit','quantity','prix_unitaire_produit','category']
    
#     def clean(self):
#         cleaned_data = super().clean()
#         produit_existant = cleaned_data.get('produit_existant')
#         nom_produit = cleaned_data.get('nom_produit')

#         if not produit_existant and not nom_produit:
#             raise forms.ValidationError("Vous devez Sélectionner un produit existant ou entrer un nouveau produit ")



# Formsets pour Facturation
# ProduitFactureFormset = inlineformset_factory(
#     Facturation,
#     Produit,
#     form=ProduitForm,
#     fk_name='facture_produit',
#     fields=['nom_produit', 'description_produit', 'quantity', 'prix_unitaire_produit', 'category'],
#     extra=1,
#     can_delete=True
# )

# # Formsets pour Devis
# ProduitDevisFormset = inlineformset_factory(
#     Devis,
#     Produit,
#     form=ProduitForm,
#     fk_name='devis_produit',
#     fields=['nom_produit', 'description_produit', 'quantity', 'prix_unitaire_produit', 'category'],
#     extra=1,
#     can_delete=True
# )


# class ServiceForm(forms.ModelForm):
#     class Meta:
#         model = Service
#         fields = ['nom_service', 'description_service', 'montant_du_service', 'date_prestation_service']
#         widgets = {
#             'nom_service': forms.TextInput(attrs={
#                 'class': 'form-control',
#                 'placeholder': 'Nom du service'
#             }),
#             'description_service': forms.Textarea(attrs={
#                 'rows': 3,
#                 'class': 'form-control',
#                 'placeholder': 'Description du service'
#             }),
#             'montant_du_service': forms.NumberInput(attrs={
#                 'class': 'form-control', 
#                 'min': '0.01', 
#                 'step': '0.01',
#                 'placeholder': 'Montant du service'
#             }),
#             'date_prestation_service': forms.DateInput(attrs={
#                 'type': 'date', 
#                 'class': 'form-control'
#             }),
#         }
    
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields['description_service'].required = False
#         self.fields['date_prestation_service'].required = False


# # Formsets pour Services
# ServiceFactureFormset = inlineformset_factory(
#     Facturation,
#     Service,
#     form=ServiceForm,
#     fk_name='facture_service',
#     fields=['nom_service', 'description_service', 'montant_du_service', 'date_prestation_service'],
#     extra=1,
#     can_delete=True    
# )

# ServiceDevisFormset = inlineformset_factory(
#     Devis,
#     Service,
#     form=ServiceForm,
#     fk_name='devis_service',
#     fields=['nom_service', 'description_service', 'montant_du_service', 'date_prestation_service'],
#     extra=1,
#     can_delete=True    
# )