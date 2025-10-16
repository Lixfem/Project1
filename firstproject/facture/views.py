from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import HttpResponse, JsonResponse
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.views import View
from django.db import transaction, IntegrityError
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from facture.forms import *
from .models import *
from django.db.models import Sum, Count, Q, Avg
from django.db.models.functions import TruncMonth, TruncYear
import json
from django.views.decorators.http import require_POST
from functools import wraps
from utils import paginate_queryset
import logging
# Packages pour la vue pdf
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
import logging
from django.core.exceptions import ValidationError 

logger = logging.getLogger(__name__)




# @login_required
# def settings_view(request):
#     """Vue pour gérer les paramètres de l'entreprise"""
#     profile, created = CompanyProfile.objects.get_or_create(user=request.user)

#     if request.method == 'POST':
#         data = request.POST
#         profile.company_name = data.get('companyName')
#         profile.company_address = data.get('companyAddress')
#         profile.company_phone = data.get('companyPhone')
#         profile.company_email = data.get('companyEmail')
#         profile.company_siret = data.get('companySiret')
#         profile.company_logo = data.get('companyLogo')
#         profile.payment_terms = data.get('paymentTerms')
#         profile.company_iban = data.get('companyIban')
#         profile.company_bic = data.get('companyBic')
#         profile.vat_rates = json.loads(data.get('vatRates', '[]'))
#         profile.save()
#         return JsonResponse({'status': 'success', 'message': 'Paramètres enregistrés avec succès !'})

#     return render(request, 'facture/settings.html', {'profile': profile})


@method_decorator(login_required, name='dispatch')
class HomeView(View):
    template_name = 'facture/index.html'

    def get(self, request, *args, **kwargs):
        # Factures avec les bons noms de champs
        factures = Facturation.objects.select_related('client', 'save_by').all()
        devis = Devis.objects.select_related('client', 'save_by').all()

        # Dashboard statistics
        total_factures_payees = Facturation.objects.filter(
            statut=Facturation.STATUT_PAYE
        ).aggregate(total=Sum('total_ttc'))['total'] or 0

        total_factures_en_attente = Facturation.objects.filter(
            statut=Facturation.STATUT_EN_ATTENTE
        ).aggregate(total=Sum('total_ttc'))['total'] or 0

        total_devis_en_cours = Devis.objects.filter(
            statut__in=[Devis.STATUT_ATTENTE, Devis.STATUT_ACCEPTE],
            est_transforme_en_facture=False
        ).aggregate(total=Sum('total_ttc'))['total'] or 0

        nombre_clients_actifs = Client.objects.filter(
            Q(facturation__isnull=False) | Q(devis__isnull=False)
        ).distinct().count()
        
        dernieres_factures = Facturation.objects.select_related('client').order_by('-date_creation')[:5]
        derniers_devis = Devis.objects.select_related('client').order_by('-date_creation')[:5]

        context = {
            'factures': factures,
            'devis': devis,
            'total_factures_payees': total_factures_payees,
            'total_factures_en_attente': total_factures_en_attente,
            'total_devis_en_cours': total_devis_en_cours,
            'nombre_clients_actifs': nombre_clients_actifs,
            'dernieres_factures': dernieres_factures,
            'derniers_devis': derniers_devis

        }
        return render(request, self.template_name, context)


# =============================VUES CLIENTS=============================
@method_decorator(login_required, name='dispatch')
class ClientCreateView(View):
    """" Creer un nouveau client avec le formulaire django"""
    template_name = 'facture/ajouterClient.html'

    def get(self, request, *args, **kwargs):
        form = ClientForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.save_by = request.user
            client.save()
            messages.success(request, f'Client{client.nom} ajouté avec succès')
            return redirect('liste-clients')
        return render(request, self.template_name, {'form': form})


@login_required
def client_list(request):
    """Liste des clients"""
    clients = Client.objects.all().order_by('-date_creation')
    return render(request, 'facture/listClient.html', {"clients": clients})


@login_required
def client_detail(request, client_id):
    """Détails d'un client"""
    client = get_object_or_404(Client, id=client_id)
    factures = Facturation.objects.filter(client=client).order_by('-date_creation')
    devis_lists = Devis.objects.filter(client=client).order_by('-date_creation')

    context = {
        'client': client,
        'factures': factures,
        'devis_lists': devis_lists
    }
    return render(request, 'facture/detailsClient.html', context)


@login_required
def client_update(request, client_id):
    """Modification d'un client"""
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            return redirect('details-clients', client.id)
    else:
        form = ClientForm(instance=client)
    return render(request, 'facture/client_update.html', {'form': form, 'client': client})


@login_required
def client_delete(request, client_id):
    """Suppression d'un client"""
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        client.delete()
        return redirect('liste-clients')
    return render(request, 'facture/client_delete.html', {'client': client})

#============================VUES FACTURES=============================

@method_decorator(login_required, name='dispatch')
class FactureCreateView(View):
    """ Creer une nouvelle facture avec le formulaire django """

    template_name = 'facture/add_facture.html'


    def get(self, request, *args, **kwargs):
        form = FacturationForm(user=request.user)
        produit_formset = ProduitFactureFormset()
        service_formset = ServiceFactureFormset()
        context = { 'form': form, 'produit_formset': produit_formset,
                    'service_formset': service_formset}
        return render(request, self.template_name,context)
    
    
    def post(self, request, *args, **kwargs):
        form = FacturationForm(request.POST, user=request.user)
        produit_formset = ProduitFactureFormset(request.POST)
        service_formset = ServiceFactureFormset(request.POST)

        if form.is_valid() and produit_formset.is_valid() and service_formset.is_valid():
            try:
                with transaction.atomic():
                    facture = form.save() # 

                    produits = produit_formset.save(commit=False)
                    for produit in produits:
                        produit.facture_produit = facture
                        produit.save()
                    
                    for obj in produit_formset.deleted_objects:
                        obj.delete()

                    services = service_formset.save(commit=False)
                    for service in services:
                        service.facture_service = facture
                        service.save()

                    for obj in service_formset.deleted_objects:
                        obj.delete() 
                
                facture.recalculer_totaux()

                messages.success(request, f'Facture {facture.numero}créée avec succès' )
                return redirect('details-facture', facture_id=facture.id)
            except Exception as e:
                messages.error(request,f'Erreur lors de la création: {str(e)}')

        context = {'form':form,'produit_formset':produit_formset,
                   'service_formset':service_formset}
        return render(request, self.template_name, context)
    

@login_required
def facture_list(request):
    """Liste des factures"""
    factures = Facturation.objects.select_related('client','save_by').order_by('-date_creation')
    context = {'factures': factures ,'factures':paginate_queryset, 'statuts': Facturation.STATUT_CHOICES }
    return render(request, 'facture/listeFacture.html', context)

@login_required
def facture_detail(request, facture_id):
    """Détails d'une facture"""
    facture = get_object_or_404(Facturation.objects.select_related('client','save_by','devis_origine'), id=facture_id)
    produits = facture.produits.all()
    services = facture.services.all()
    reglements = facture.reglement_set.all().order_by('-date_reglement')
    context = { 'facture': facture, 'produits':produits, 'services':services,
              'reglements':reglements
            }
    return render(request, 'facture/details_devis_facture.html', context)

@login_required
def facture_update(request, facture_id):
    """Modifier une facture"""
    facture = get_object_or_404(Facturation, id=facture_id)

    if  request.method =='POST':
        form = FacturationForm(request.POST,instance=facture, user=request.user)
        produit_formset =ProduitFactureFormset(request.POST, instance=facture)
        service_formset = ServiceFactureFormset(request.POST, instance=facture)

        if form.is_valid() and produit_formset.is_valid() and service_formset.is_valid():
            try :
                with transaction.atomic():
                    facture = form.save()
                    produit_formset.save()
                    service_formset.save()

                    facture.recalculer_totaux()

                    messages.success(request, 'Facture modifiée avec succès')
                    return redirect('details-facture', facture_id=facture.id)
            except Exception as e :
                messages.error(request, f'Erreur : {str(e)}') 
        else :
            form = FacturationForm(instance = facture, user=request.user)
            produit_formset = ProduitFactureFormset(instance=facture)
            service_formset = ServiceFactureFormset(instance=facture)
        context = {
            'form': form,
            'produits_formset': produit_formset,
            'service_formset': service_formset,
            'facture': facture
        }  

    return render(request, 'facture/update_facture.html', context)

@login_required
def facture_delete(request, facture_id):
    """Supprimer une facture"""
    facture = get_object_or_404(Facturation,id= facture_id)
    if request.method == 'POST':
        numero = facture.numero
        facture.delete()
        messages.success(request,f' Facture {numero} supprimée avec succès ')
        return redirect('liste-facture')
    return render(request, 'facture/facture_delete.html',{'facture':facture})

@login_required
def facture_change_statut(request, facture_id):
    """ Changer le statut de la facture (AJAX)"""
    if request.method == 'POST':
        facture = get_object_or_404(Facturation, id=facture_id)
        nouveau_statut = int(request.POST.get('statut'))
    
        if nouveau_statut in [Facturation.STATUT_PAYE,Facturation.STATUT_EN_ATTENTE,Facturation.STATUT_ANNULE]:
            facture.statut = nouveau_statut
            facture.last_update = timezone.now()
            facture.save

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' :
                return JsonResponse({
                    'success': True,
                    'message': 'Statut modifié avec succès'
                })
            messages.success(request, 'Statut modifié avec succès')

        else:
            if request.headers.get('X-Reqested-With') == 'XMLHttpReqest':
                return JsonResponse({
                    'success': False,

                    'message': 'Statut modifié avec succès'
                })
        messages.success(request, 'Statut invalide')
    
    return redirect('details-facture', facture_id = facture_id)
 

#===========================================VUES DEVIS =============================================
 
@method_decorator(login_required, name='dispatch')
class DevisCreateView(View):
    """ Creer un nouveau devis avec formset"""
    template_name = 'facture/add_devis.html'
 
    def get(self, request, *args, **kwargs):
        form = DevisForm(user=request.user)
        produit_formset = ProduitDevisFormset(prefix='produits')
        service_formset = ServiceDevisFormset(prefix='services')

        context = {
            'form': form,
            'produit_formset': produit_formset,
            'service_formset': service_formset,
        }
        return render(request, self.template_name,context)

    def post(self, request, *args, **kwargs):
        form = DevisForm(request.POST, user=request.user)
        produit_formset = ProduitDevisFormset(request.POST)
        service_formset = ServiceDevisFormset(request.POST)

        if form.is_valid() and produit_formset.is_valid() and service_formset.is_valid():

            try:
                with transaction.atomic():
                    devis = form.save()

                    produits = produit_formset.save(commit=False)
                    for produit in produits:
                        produit.devis_produit = devis
                        produit.save()
                    
                    for obj in produit_formset.deleted_objects:
                        obj.delete()
                    
                    services = service_formset.save(commit=False)
                    
                    for service in services:
                        service.devis_service = devis
                        service.save()
                    
                    for obj in service_formset.deleted_objects:
                        obj.delete()
                    messages.success(request,f'Devis {devis.numero} créé avec succès !')

                    return redirect('devis-details', devis_id= devis.id)
            except(IntegrityError,ValidationError)as e :
                messages.error(request,f'Erreur lors de la création : {str(e)}')
        context = {
            'form': form,
            'produit_formset': produit_formset,
            'service_formset': service_formset,
        }
        
        return render(request, self.template_name,context)

@login_required
def devis_list(request):
    """Liste des devis"""
    devis_list = Devis.objects.select_related('client','save_by').order_by('-date_creation')
    context ={'devis_list':devis_list,'devis_list':paginate_queryset}
    return render(request, 'facture/liste_devis.html', context)

 
@login_required
def devis_detail(request, devis_id):
    """Détails d'un devis"""
    devis = get_object_or_404(Devis.objects.select_related('client', 'save_by'), id=devis_id)
    produits = devis.produits.all()
    services = devis.services.all()

    context = {
        'devis':devis,
        'produits': produits,
        'services': services,
        'peut_transformer':devis.peut_etre_transforme()
    }
    return render(request, 'facture/details_devis_facture.html', context)

@login_required
def devis_update(request, devis_id):
    """Modifier un devis"""
    devis = get_object_or_404(Devis, id=devis_id)
    if request.method == 'POST':
        form = DevisForm(request.POST, instance= devis, user= request.user)
        produit_formset = ProduitDevisFormset(request.POST, instance=devis)
        service_formset = ServiceDevisFormset(request.POST, instance=devis)

        if form.is_valid() and produit_formset.is_valid() and service_formset.is_valid():
            try:
                with transaction.atomic():
                    devis = form.save()
                    produit_formset.save()
                    service_formset.save()

                    messages.success(request, 'Devis modifié avec succès ')
                    return redirect('devis-detail',devis_id=devis.id)
            
            except Exception as e :
                messages.error(request,f'Erreur : {str(e)}')
    
    else :
        form = DevisForm(instance= devis, user= request.user)
        produit_formset = ProduitDevisFormset(instance=devis, user= request.user)
        service_formset = ServiceDevisFormset(instance=devis, user=request.user)

    context = {
        'form': form,
        'produit_formset': produit_formset,
        'service_formset': service_formset,
        'devis': devis
    }         

    return render(request, 'facture/update_devis.html', context)

def devis_delete(request,devis_id):
    """ Supprimer un devis"""
    devis = get_object_or_404(devis, id= devis_id)

    if request.method == 'POST':
        numero = devis.numero
        devis.delete()
        messages.success(request, f'Devis {numero} supprimé avce succès')
        return redirect('liste-devis')

    return render(request, 'facture/devis_delete.html',{'devis':devis}) 

@login_required
def devis_change_statut(request, devis_id):
    """Changer le statut d'un devis"""

    if request.method == "POST":
        devis = get_object_or_404(Devis, id=devis_id)
        nouveau_statut = int(request.POST.get('statut'))

        if nouveau_statut in [s[0] for s in Devis.STATUT_CHOICES]:
            devis.statut = nouveau_statut
            devis.last_update = timezone.now()
            devis.save() 

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Statut modifié avec succès '
                })
            messages.success(request,'Statut modifié avec succès')
        else:
            messages.error(request, 'Statut invalide')
    
    return redirect('devis-detail', devis_id=devis_id)
            

@login_required
def transformer_devis_en_facture(request, devis_id):
    """Transformer un devis en facture"""
    devis = get_object_or_404(Devis, id=devis_id)
    
    if request.method == 'POST':
        try:
            if not devis.peut_etre_transforme():
                messages.error(request, "Ce devis ne peut pas être transformé en facture.")
                return redirect('devis-detail', devis_id=devis_id)
            
            with transaction.atomic():
                facture = devis.transformer_en_facture(request.user)
                messages.success(request, f"Le devis {devis.numero} a été transformé en facture {facture.numero} avec succès.")
                return redirect('details-facture', facture_id=facture.id)

            
            if request.POST.get('envoyer_email'):
                envoyer_facture_email(request, facture.id)
            
            return redirect('details-facture', facture_id=facture.id)
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la transformation : {str(e)}")
            return redirect('devis-detail', devis_id=devis_id)
    
    context = {
        'devis': devis,
        'peut_transformer': devis.peut_etre_transforme()
    }
    return render(request, 'facture/transformer_devis_to_facture.html', context)


# ======================================Vues REGLEMENTS =========================
@login_required

def reglement_create(request,facture_id):
    """Ajouter un reglement a une facture"""

    facture = get_object_or_404(Facturation, id=facture_id)

    if request.method == 'POST':
        montant = request.POST.get('montant_reglement')
        mode_reglement_id = request.POST.get('mode_reglement')

        try:
            montant = Decimal(montant)
            mode_reglement = get_object_or_404(ModeReglement, id= mode_reglement_id)
            # Verifier que le montant ne depasse pas le solde du 

            if montant > facture.solde_du:
                messages.error(request, f"Le montant du règlement ({montant}) dépasse le solde dû ({facture.solde_du})")
                return redirect('details-facture', facture_id=facture.id) 
            
            with transaction.atomic():
                reglement = Reglement.objects.create(
                    client = facture.client,
                    facture = facture,
                    montant_reglement = montant,
                    mode_reglement = mode_reglement
                )
                messages.success(request,f'Règlement de {montant} FCFA enregistré avec succès')
                return redirect('details-facture', facture_id = facture.id)
        
        except Exception as e :
            messages.error(request, f'Erreur de l\'enregistrement du règlement : {str(e)} ')
    
    modes_reglement = ModeReglement.objects.filter(est_actif=True)
    context = {
        'facture': facture,
        'modes_reglement': modes_reglement
    }
    return render(request,'facture/add_reglement.html', context)

@login_required
def reglement_list(request):
    """Liste de tout les reglements"""
    reglements = Reglement.objects.select_related('client','facture','mode_reglement')

    total_reglements = reglements.aggregate(total=Sum('montant_reglement'))['total'] or 0

    context ={
        'reglements': reglements,
        'total_reglements': total_reglements
    }
    return render(request,'facture/liste_reglements.html', context)

#=========================VUES PRODUITS ET SERVICES =========================== 
@login_required
def ajouter_article(request):
    """Vue pour ajouter un produit ou un service et une categorie"""
    produit_form = ProduitForm()
    service_form = ServiceForm()
    category_form = CategoryForm()
    if request.method == 'POST':
        type_element = request.POST.get('type_element')
        logger.debug(f"Type element:{type_element}")
        logger.debug(f"POST data: {request.POST}")
        
        if type_element == 'produit':
            produit_form = ProduitForm(request.POST)
            if produit_form.is_valid():
                produit_form.save()
                messages.success(request,"Produits ajoutés avec succès !")
                return redirect('gerer-article')
            else:
                logger.error(f"")
                messages.error(request, "Erreur dans le formulaire de produit. Veuillez vérifier les champs.")
                
        elif type_element == 'service':
            service_form = ServiceForm(request.POST)
            if service_form.is_valid():
                service_form.save()
                messages.success(request,"Services ajoutés avec succès")
                return redirect('ajouter_element')
            else:
                messages.error(request,"Erreur dans le formulaire de service. Veuillez vérifier les champs.")
            
        elif type_element == 'category':
            category_form = CategoryForm(request.POST)
            if category_form.is_valid():
                category_form.save()
                messages.success(request,"Catégories ajoutés avec succès !")
                return redirect('ajouter_element')
            else:
                messages.error(request,"Erreur dans le formuaire de categorie. Veuillez vérifier les champs.")                   
       
    
    return render(request, 'facture/add_product_service.html', {'produit_form': produit_form,
        'service_form': service_form,
        'category_form': category_form,})



@login_required
def gerer_article(request):
    """Vue pour gérer (modifier/supprimer) les produits, services et catégories"""
    
    # Récupération de tous les articles
    produits = Produit.objects.all().order_by('-id')
    services = Service.objects.all().order_by('-id')
    categories = Category.objects.all().order_by('-id')

    if request.method == 'POST':
        type_element = request.POST.get('type_element')
        type_action = request.POST.get('type_action')
        instance_id = request.POST.get('id')

    # ========== GESTION DES PRODUITS =========================
        if type_element == 'produit' and type_action == 'delete':
                try:
                    produit = get_object_or_404(Produit, id=instance_id)
                    nom = produit.nom_produit
                    produit.delete()
                    messages.success(request, f"Produit '{nom}' supprimé avec succès !")
                    return redirect('gerer-article')
                except Exception as e:
                    messages.error(request, f"Erreur lors de la suppression : {str(e)}")
                    return redirect('gerer-article')
        
# ========== GESTION DES SERVICES ==========
        elif type_element == 'service' and type_action == 'delete':
                try:
                    service = get_object_or_404(Service, id=instance_id)
                    nom = service.nom_service
                    service.delete()
                    messages.success(request, f"Service '{nom}' supprimé avec succès !")
                    return redirect('gerer-article')
                except Exception as e:
                    messages.error(request, f"Erreur lors de la suppression : {str(e)}")
                    return redirect('gerer-article')
        
        # ========== GESTION DES CATÉGORIES ==========
        elif type_element == 'category' and type_action == 'delete':
                try:
                    category = get_object_or_404(Category, id=instance_id)
                    nom = category.nom
                    category.delete()
                    messages.success(request, f"Catégorie '{nom}' supprimée avec succès !")
                    return redirect('gerer-article')
                except Exception as e:
                    messages.error(request, f"Erreur lors de la suppression : {str(e)}")
                    return redirect('gerer-article')
            
    context = {
        'produits': produits,
        'services': services,
        'categories': categories,
    }
    return render(request, 'facture/manage_article.html', context)




@login_required
def article_update(request):
    """Vue pour modifier un produit, un service ou une catégorie"""
    
    # Récupération des paramètres
    type_element = request.GET.get('type_element', request.POST.get('type_element', 'produit'))
    instance_id = request.GET.get('id', request.POST.get('id'))
    
    # Initialisation
    produit_form = None
    service_form = None
    category_form = None
    produit = None
    service = None
    category = None
    
    # ========== TRAITEMENT GET : Charger le formulaire ==========
    if request.method == 'GET' and instance_id:
        try:
            if type_element == 'produit':
                produit = get_object_or_404(Produit, id=instance_id)
                produit_form = ProduitForm(instance=produit)
                
            elif type_element == 'service':
                service = get_object_or_404(Service, id=instance_id)
                service_form = ServiceForm(instance=service)
                
            elif type_element == 'category':
                category = get_object_or_404(Category, id=instance_id)
                category_form = CategoryForm(instance=category)
                
        except Exception as e:
            messages.error(request, f"{type_element.capitalize()} introuvable : {str(e)}")
            return redirect('gerer-article')
    
    # ========== TRAITEMENT POST : Sauvegarder les modifications ==========
    if request.method == 'POST' and instance_id:
        try:
            if type_element == 'produit':
                produit = get_object_or_404(Produit, id=instance_id)
                produit_form = ProduitForm(request.POST, instance=produit)
                
                if produit_form.is_valid():
                    produit_form.save()
                    messages.success(request, f"Produit '{produit.nom_produit}' modifié avec succès!")
                    return redirect('gerer-article')
                else:
                    messages.error(request, "Erreur dans le formulaire de produit.")
                    
            elif type_element == 'service':
                service = get_object_or_404(Service, id=instance_id)
                service_form = ServiceForm(request.POST, instance=service)
                
                if service_form.is_valid():
                    service_form.save()
                    messages.success(request, f"Service '{service.nom_service}' modifié avec succès!")
                    return redirect('gerer-article')
                else:
                    messages.error(request, "Erreur dans le formulaire de service.")
                    
            elif type_element == 'category':
                category = get_object_or_404(Category, id=instance_id)
                category_form = CategoryForm(request.POST, instance=category)
                
                if category_form.is_valid():
                    category_form.save()
                    messages.success(request, f"Catégorie '{category.nom}' modifiée avec succès!")
                    return redirect('gerer-article')
                else:
                    messages.error(request, "Erreur dans le formulaire de catégorie.")
                    
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
            return redirect('gerer-article')
    
    # ========== CONTEXTE ==========
    context = {
        'produit': produit,
        'produit_form': produit_form,
        'service': service,
        'service_form': service_form,
        'category': category,
        'category_form': category_form,
        'produit_list': Produit.objects.all(),
        'service_list': Service.objects.all(),
        'category_list': Category.objects.all(),
        'type_element': type_element,
        'instance_id': instance_id,
    }
    
    return render(request, 'facture/article_update.html', context)

# recherche dynamique de produit et service

@login_required
def search_produits(request):
    query = request.GET.get('q','')
    if len(query) < 2:
        return JsonResponse([], safe=False)
    produits = Produit.objects.filter(
        Q(nom_produit__icontains=query)
    )[:10] 

    results = [
        {
            'id':produit.id,
            'nom': produit.nom_produit,
            'description': produit.description_produit,
            'quantité': Decimal(produit.quantity),
            'prix': float(produit.prix_unitaire_produit),
            'category': produit.category.id if produit.category else ''
        }
        for produit in produits
    ]
    return JsonResponse(results, safe=False)

@login_required
def search_services(request):
    query = request.GET.get('q','')
    if len(query) < 2:
        return JsonResponse([],safe=False)
    services = Service.objects.filter(
        Q(nom_service__icontains=query)
    )[:10]
    results = [
        {
            'id': service.id,
            'nom': service.nom_service,
            'description': service.description_service,
            'montant': Decimal(service.montant_du_service),
            'date': service.date_prestation_service.strftime('%Y-%m-%d')
        }
        for service in services
    ]
    return JsonResponse(results, safe=False) 
    



#===============================================PDF Generation ==================
def generer_pdf_facture(facture):
    """Générer un PDF pour une facture"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#1f4788'),
        alignment=TA_CENTER
    )
    
    # Titre
    elements.append(Paragraph(f"FACTURE N° {facture.numero}", title_style))
    elements.append(Spacer(1, 12))
    
    # Reference devis
    if facture.devis_origine:
        elements.append(Paragraph(f"<i>Référence devis: {facture.devis_origine.numero}</i>", styles['Normal']))
        elements.append(Spacer(1, 12))
    
    # Infos client 
    client_info = f"""
    <b>Client:</b> {facture.client.nom}<br/>
    <b>Email:</b> {facture.client.email}<br/>
    <b>Téléphone:</b> {facture.client.telephone}<br/>
    <b>Adresse:</b> {facture.client.adresse}, {facture.client.ville}<br/>
    <b>Date:</b> {facture.date_creation.strftime('%d/%m/%Y')}
    """
    elements.append(Paragraph(client_info, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Tableau des produits
    if facture.produits.exists():
        data = [['Produit', 'Description', 'Prix Unit.', 'Qté', 'Total']]
        for produit in facture.produits.all():
            data.append([
                produit.nom_produit,
                (produit.description_produit[:30] + '...') if len(produit.description_produit) > 30 else produit.description_produit,
                f'{produit.prix_unitaire_produit:.2f} FCFA',
                str(produit.quantity),
                f'{produit.get_total:.2f} FCFA'
            ])
        
        table = Table(data, colWidths=[80*mm, 60*mm, 30*mm, 20*mm, 30*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))
    
    # Tableau des services
    if facture.services.exists():
        data = [['Service', 'Description', 'Montant']]
        for service in facture.services.all():
            data.append([
                service.nom_service,
                (service.description_service[:50] + '...') if len(service.description_service) > 50 else service.description_service,
                f'{service.montant_du_service:.2f} FCFA'
            ])
        
        table = Table(data, colWidths=[60*mm, 100*mm, 40*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))
    
    # Totaux
    total_style = ParagraphStyle('Total', parent=styles['Heading1'], fontSize=16, alignment=TA_RIGHT)
    elements.append(Paragraph(f"<b>Total HT: {facture.total_net_ht:.2f} FCFA</b>",total_style))
    elements.append(Paragraph(f"<b>TVA ({facture.tva_rate or 18}%): {facture.total_tva:.2f} FCFA</b>",total_style))
    elements.append(Paragraph(f"<b>TOTAL TTC: {facture.total_ttc:.2f} FCFA</b>", total_style))
    
    if facture.montant_accompte > 0:
        elements.append(Paragraph(f"<b>Accompte:{facture.montant_accompte:.2f} FCFA </b>",total_style))
        elements.append(Paragraph(f"<b> Solde dû: {facture.solde_du:.2f} FCFA </b>",total_style))

    elements.append(Spacer(1, 20))
    statut_dict = dict(Facturation.STATUT_CHOICES)
    elements.append(Paragraph(f"<b>Statut:</b> {statut_dict.get(facture.statut,'Inconnu')}", styles['Normal']))
    
    if facture.commentaire:
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("<b>Commentaires:</b>", styles['Heading2']))
        elements.append(Paragraph(facture.commentaire, styles['Normal']))
    
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("<b>Conditions de paiement:</b>", styles['Heading3']))
    elements.append(Paragraph("Paiement à 30 jours date de facture", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generer_pdf_devis(devis):
    """Générer un PDF pour un devis"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#1f4788'),
        alignment=TA_CENTER
    )
    
    elements.append(Paragraph(f"DEVIS N° {devis.numero}", title_style))
    elements.append(Spacer(1, 12))
    
    client_info = f"""
    <b>Client:</b> {devis.client.nom}<br/>
    <b>Email:</b> {devis.client.email}<br/>
    <b>Téléphone:</b> {devis.client.telephone}<br/>
    <b>Adresse:</b> {devis.client.adresse}, {devis.client.ville}<br/>
    <b>Date:</b> {devis.date_creation.strftime('%d/%m/%Y')}
    <b>Valide jusqu'au:</b> {devis.date_validite.strftime('%d/%m/%Y')}
    """
    elements.append(Paragraph(client_info, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # T produits
    if devis.produits.exists():
        data = [['Produit', 'Description', 'Prix Unit.', 'Qté', 'Total']]
        for produit in devis.produits.all():
            data.append([
                produit.nom_produit,
                (produit.description_produit[:30] + '...') if len(produit.description_produit) > 30 else produit.description_produit,
                f'{produit.prix_unitaire_produit:.2f} FCFA',
                str(produit.quantity),
                f'{produit.get_total:.2f} FCFA'
            ])
        
        table = Table(data, colWidths=[80*mm, 60*mm, 30*mm, 20*mm, 30*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))
    
    # Services
    if devis.services.exists():
        data = [['Service', 'Description', 'Montant']]
        for service in devis.services.all():
            data.append([
                service.nom_service,
                (service.description_service[:50] + '...') if len(service.description_service) > 50 else service.description_service,
                f'{service.montant_du_service:.2f} FCFA'
            ])
        
        table = Table(data, colWidths=[60*mm, 100*mm, 40*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))
    
    total_style = ParagraphStyle('Total', parent=styles['Heading1'], fontSize=16, alignment=TA_RIGHT)
    elements.append(Paragraph(f"<b> Total HT: {devis.total_net_ht:.2f} FCFA </b>",total_style))
    elements.append(Paragraph(f"<b>TVA ({devis.tva_rate or 18}%): {devis.total_tva:.2f} FCFA </b>"))
    elements.append(Paragraph(f"<b>TOTAL TTC: {devis.total_ttc:.2f} FCFA</b>", total_style))
    
    if devis.commentaire:
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("<b>Commentaires:</b>", styles['Heading2']))
        elements.append(Paragraph(devis.commentaire, styles['Normal']))
    
    elements.append(Spacer(1, 20))
    statut_dict = dict(Devis.STATUT_CHOICES)
    statut_text = statut_dict.get(devis.statut, 'Inconnu')
    elements.append(Paragraph(f"<b>Statut:</b> {statut_text}", styles['Normal']))
    
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("<b>Conditions:</b>", styles['Heading3']))
    elements.append(Paragraph(f"Valable jusqu'au {devis.date_validite.strftime('%d/%m/%Y')}", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


@login_required
def telecharger_pdf_devis(request, devis_id):
    """Télécharger le PDF d'un devis"""
    devis = get_object_or_404(Devis, id=devis_id)
    pdf_buffer = generer_pdf_devis(devis)
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Devis_{devis.numero}.pdf"'
    return response


@login_required
def telecharger_pdf_facture(request, facture_id):
    """Télécharger le PDF d'une facture"""
    facture = get_object_or_404(Facturation, id=facture_id)
    pdf_buffer = generer_pdf_facture(facture)
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Facture_{facture.numero}.pdf"'
    return response


@login_required
def envoyer_devis_email(request, devis_id):
    """Envoyer un devis par email"""
    devis = get_object_or_404(Devis, id=devis_id)
    
    if not devis.client.email:
        messages.error(request, "L'email du client est manquant.")
        return redirect('devis-detail', id=devis_id)
    
    try:
        pdf_buffer = generer_pdf_devis(devis)
        
        subject = f'Devis N°{devis.numero} - {devis.client.nom}'
        message = f"""Bonjour {devis.client.nom},

Veuillez trouver ci-joint le devis N°{devis.numero} comme convenu.

Ce devis est valable jusqu'au {devis.date_validite.strftime('%d/%m/%Y')}.

N'hésitez pas à me contacter pour toute question ou clarification.

Cordialement,
{request.user.get_full_name() or request.user.username}"""

        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL or request.user.email,
            to=[devis.client.email],
        )
        email.attach(f'Devis_{devis.numero}.pdf', pdf_buffer.getvalue(), 'application/pdf')
        email.send()
        messages.success(request, "Le devis a été envoyé avec succès.")
    except Exception as e:
        messages.error(request, f"Une erreur est survenue lors de l'envoi du devis : {e}")
    
    return redirect('devis-detail', id=devis_id)


@login_required
def envoyer_facture_email(request, facture_id):
    """Envoyer une facture par email"""
    facture = get_object_or_404(Facturation, id=facture_id)
    
    if not facture.client.email:
        messages.error(request, "L'email du client est manquant.")
        return redirect('details-facture', id=facture_id)
    
    try:
        pdf_buffer = generer_pdf_facture(facture)
        
        subject = f'Facture N°{facture.numero} - {facture.client.nom}'
        message = render_to_string('email/facture_email.html', {
            'facture': facture,
            'client': facture.client,
            'produits': facture.produits.all(),
            'services': facture.services.all(),
        })
        
        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [facture.client.email],
            reply_to=[request.user.email]
        )
        email.attach(f'Facture_{facture.numero}.pdf', pdf_buffer.getvalue(), 'application/pdf')
        email.send()
        
        messages.success(request, f"La facture a été envoyée avec succès à {facture.client.email}")
        
    except Exception as e:
        messages.error(request, f"Erreur lors de l'envoi de l'email : {str(e)}")
    
    return redirect('details-facture', id=facture_id)



# === API ENDPOINTS ===

@login_required
def api_transformer_devis(request, devis_id):
    """API pour transformer un devis en facture"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        devis = get_object_or_404(Devis, id=devis_id)
        
        if not devis.peut_etre_transforme():
            return JsonResponse({'error': 'Ce devis ne peut pas être transformé en facture'}, status=400)
        
        facture = devis.transformer_en_facture(request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Devis transformé en facture {facture.numero}',
            'facture_id': facture.id,
            'facture_numero': facture.numero,
            'redirect_url': f'/facturation/{facture.id}/'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_valider_devis(request, devis_id):
    """API pour valider un devis"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        devis = get_object_or_404(Devis, id=devis_id)
        
        devis.statut = Devis.STATUT_ACCEPTE
        devis.last_update = timezone.now()
        devis.save()
        
        response_data = {
            'success': True,
            'message': f'Devis {devis.numero} accepté',
            'peut_transformer': devis.peut_etre_transforme()
        }
        
        if request.POST.get('transformer_auto') == 'true':
            try:
                facture = devis.transformer_en_facture(request.user)
                response_data['facture_creee'] = True
                response_data['facture_id'] = facture.id
                response_data['facture_numero'] = facture.numero
            except Exception as e:
                response_data['warning'] = str(e)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# === STATISTIQUES =====================

@login_required
def statistiques_view(request):
    """Vue pour afficher la page des statistiques"""
    aujourd_hui = timezone.now().date()
    debut_mois = aujourd_hui.replace(day=1)

    # KPIs
    ca_mois_courant = Facturation.objects.filter(
        date_creation__date_gte = debut_mois,
        statut = Facturation.STATUT_PAYE
    ).aggregate(total=Sum('total_ttc'))['total'] or 0
    factures_en_attente = Facturation.objects.filter(
        statut = Facturation.STATUT_EN_ATTENTE
    ).aggregate(total=Sum('solde_du'))['total'] or 0
    nb_clients = Client.objects.count()
    nb_factures_mois = Facturation.objects.filter(
        date_creation__date__gte=debut_mois
    ).count()
    six_mois_avant = aujourd_hui - timedelta(days=180)
    evolution_ca = Facturation.objects.filter(
        statut= Facturation.STATUT_PAYE,
        date_creation__date__gte = six_mois_avant
    ).annotate(
        mois=TruncMonth('date_creation')
    ).values('mois').annotate(
        total=Sum('total_ttc')
    ).order_by('mois')
    context = {
        'ca_mois_courant':ca_mois_courant,
        'factures_en_attente':factures_en_attente,
        'nb_clients':nb_clients,
        'nb_factures_mois': nb_factures_mois,
        'evolution_ca':list(evolution_ca)
    }
    return render(request, 'facture/stat.html',context)


@login_required
def api_statistiques(request):
    """API pour récupérer les données de statistiques en JSON"""
    
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    periode = request.GET.get('periode', '365')
    
    date_fin_obj = timezone.now().date()
    if date_fin:
        date_fin_obj = datetime.strptime(date_fin, '%Y-%m-%d').date()
    
    if date_debut:
        date_debut_obj = datetime.strptime(date_debut, '%Y-%m-%d').date()
    else:
        if periode == '30':
            date_debut_obj = date_fin_obj - timedelta(days=30)
        elif periode == '90':
            date_debut_obj = date_fin_obj - timedelta(days=90)
        elif periode == '365':
            date_debut_obj = date_fin_obj - timedelta(days=365)
        else:
            date_debut_obj = None
    
    date_filter = {}
    if date_debut_obj:
        date_filter['date_creation__date__gte'] = date_debut_obj
    if date_fin_obj:
        date_filter['date_creation__date__lte'] = date_fin_obj
    
    devis_date_filter = {}
    if date_debut_obj:
        devis_date_filter['date_creation__date__gte'] = date_debut_obj
    if date_fin_obj:
        devis_date_filter['date_creation__date__lte'] = date_fin_obj
    
    try:
        # Statistiques clients
        total_clients = Client.objects.count()
        
        repartition_sexe = Client.objects.values('sexe').annotate(
            count=Count('id')
        ).order_by('sexe')
        
        sexe_data = {item['sexe'] if item['sexe'] else 'Non spécifié': item['count'] 
                     for item in repartition_sexe}
        
        nouveaux_clients_mois = Client.objects.filter(
            date_creation__gte=timezone.now() - timedelta(days=365)
        ).annotate(
            mois=TruncMonth('date_creation')
        ).values('mois').annotate(
            count=Count('id')
        ).order_by('mois')
        
        # Statistiques factures
        factures_queryset = Facturation.objects.filter(**date_filter)
        
        total_factures = factures_queryset.count()
        factures_payees = factures_queryset.filter(statut=Facturation.STATUT_PAYE).count()
        factures_en_attente = factures_queryset.filter(statut=Facturation.STATUT_EN_ATTENTE).count()
        factures_annulees = factures_queryset.filter(statut=Facturation.STATUT_ANNULE).count()
        
        chiffre_affaires = factures_queryset.filter(
            statut=Facturation.STATUT_PAYE
        ).aggregate(total=Sum('total_ttc'))['total'] or Decimal('0')
        
        evolution_ca = factures_queryset.filter(
            statut=Facturation.STATUT_PAYE,
            date_creation__gte=timezone.now() - timedelta(days=365)
        ).annotate(
            mois=TruncMonth('date_creation')
        ).values('mois').annotate(
            total=Sum('total_ttc')
        ).order_by('mois')
        
        # Statistiques devis
        devis_queryset = Devis.objects.filter(**devis_date_filter)
        
        total_devis = devis_queryset.count()
        devis_en_attente = devis_queryset.filter(statut=Devis.STATUT_ATTENTE).count()
        devis_acceptes = devis_queryset.filter(statut=Devis.STATUT_ACCEPTE).count()
        devis_refuses = devis_queryset.filter(statut=Devis.STATUT_REFUSE).count()
        devis_transformes = devis_queryset.filter(statut=Devis.STATUT_TRANSFORME_FACTURE).count()
        
        taux_acceptation = 0
        if total_devis > 0:
            taux_acceptation = round((devis_acceptes / total_devis) * 100, 1)
        
        # Top produits
        top_produits = Produit.objects.values('nom_produit').annotate(
            quantite_totale=Sum('quantity'),
            chiffre_affaires=Sum('total')
        ).order_by('-quantite_totale')[:10]
        
        # Top services
        top_services = Service.objects.values('nom_service').annotate(
            nombre_commandes=Count('id'),
            montant_total=Sum('montant_du_service')
        ).order_by('-montant_total')[:10]
        
        # Évolution mensuelle
        mois_labels = []
        ca_mensuel = []
        aujourd_hui = timezone.now()
        
        for i in range(11, -1, -1):
            date_mois = aujourd_hui - timedelta(days=30*i)
            mois_labels.append(date_mois.strftime('%b'))
            
            ca_mois = 0
            for item in evolution_ca:
                if item['mois'].month == date_mois.month and item['mois'].year == date_mois.year:
                    ca_mois = float(item['total'])
                    break
            ca_mensuel.append(ca_mois)
        
        statistiques_data = {
            'clients': {
                'total': total_clients,
                'repartitionSexe': sexe_data,
                'nouveauxParMois': [item['count'] for item in nouveaux_clients_mois]
            },
            'factures': {
                'total': total_factures,
                'payees': factures_payees,
                'enAttente': factures_en_attente,
                'annulees': factures_annulees,
                'chiffreAffaires': float(chiffre_affaires),
                'evolutionMensuelle': ca_mensuel,
                'moisLabels': mois_labels,
                'tauxPaiement': round((factures_payees / total_factures * 100) if total_factures > 0 else 0, 1)
            },
            'devis': {
                'total': total_devis,
                'enAttente': devis_en_attente,
                'acceptes': devis_acceptes,
                'refuses': devis_refuses,
                'transformes': devis_transformes,
                'tauxAcceptation': taux_acceptation
            },
            'produits': {
                'topVendus': [
                    {
                        'nom': item['nom_produit'],
                        'quantite': item['quantite_totale'] or 0,
                        'chiffreAffaires': float(item['chiffre_affaires'] or 0)
                    } for item in top_produits
                ]
            },
            'services': {
                'topDemandes': [
                    {
                        'nom': item['nom_service'],
                        'nombreCommandes': item['nombre_commandes'],
                        'montant': float(item['montant_total'] or 0)
                    } for item in top_services
                ]
            },
            'filtres': {
                'dateDebut': date_debut_obj.isoformat() if date_debut_obj else None,
                'dateFin': date_fin_obj.isoformat(),
                'periode': periode
            }
        }
        
        return JsonResponse(statistiques_data, safe=False)
    
    except Exception as e:
        return JsonResponse({
            'error': f'Erreur lors du calcul des statistiques: {str(e)}'
        }, status=500)


@login_required
def get_kpis_principales(request):
    """Récupère les KPIs principales pour le tableau de bord"""
    
    aujourd_hui = timezone.now().date()
    debut_mois = aujourd_hui.replace(day=1)
    mois_precedent = (debut_mois - timedelta(days=1)).replace(day=1)
    
    kpis = {
        'ca_mois_courant': Facturation.objects.filter(
            date_creation__date__gte=debut_mois,
            statut=Facturation.STATUT_PAYE
        ).aggregate(total=Sum('total_ttc'))['total'] or 0,
        
        'ca_mois_precedent': Facturation.objects.filter(
            date_creation__date__gte=mois_precedent,
            date_creation__date__lt=debut_mois,
            statut=Facturation.STATUT_PAYE
        ).aggregate(total=Sum('total_ttc'))['total'] or 0,
        
        'nouveaux_clients_mois': Client.objects.filter(
            date_creation__date__gte=debut_mois
        ).count(),
        
        'taux_conversion_devis': 0
    }
    
    devis_acceptes_mois = Devis.objects.filter(
        date_creation__date__gte=debut_mois,
        statut=Devis.STATUT_ACCEPTE
    ).count()
    
    factures_depuis_devis = Facturation.objects.filter(
        devis_origine__isnull=False,
        date_creation__date__gte=debut_mois
    ).count()
    
    if devis_acceptes_mois > 0:
        kpis['taux_conversion_devis'] = round(
            (factures_depuis_devis / devis_acceptes_mois) * 100, 1
        )
    
    return JsonResponse(kpis)

#============== Vues filtres========

@login_required
def facture_list_impayee(request):
    """Liste des factures impayees"""
    factures = Facturation.objects.filter(
        statut__in=[Facturation.STATUT_EN_ATTENTE,Facturation.STATUT_ANNULE]   
    ).select_related('client','save_by').order_by('date-creation')

    context = {
        'factures': factures,
        'titre':'Factures impayées',
        'statuts': Facturation.STATUT_CHOICES
    }
    return render(request,'facture/facture_impaye.html',context)

@login_required
def facture_list_payee(request):
    """Liste des factures payées"""
    factures = Facturation.objects.filter(
        statut = Facturation.STATUT_PAYE
    ).select_related('clients','save_by').order_by('-date_creation')

    context = {
        'factures': factures,
        'titre':'Factures payées',
        'statuts': Facturation.STATUT_CHOICES
    }
    return render(request, 'factures/facture_paye.html', context)


@login_required
def devis_list_attente(request):
    """Liste des devis en attente"""
    devis_list = Devis.objects.filter(
        statut = Devis.STATUT_ATTENTE
    ).select_related('client','save_by').order_by('date_creation')

    context = {
        'devis_list': devis_list,
        'titre': 'Devis En attente',
        'statuts': Devis.STATUT_CHOICES
    }
    return render(request, 'facture/devis_attente.html',context)