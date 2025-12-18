from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse,HttpResponseForbidden, Http404,HttpResponseRedirect
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
from django.db.models import Sum, Count, Q, Avg, F, OuterRef, Subquery, Value,DecimalField
from django.db.models.functions import TruncMonth, TruncYear,Coalesce
import json
from django.views.decorators.http import require_POST
from functools import wraps
import logging
# Packages pour la vue pdf
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import logging
from django.core.exceptions import ValidationError 
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.safestring import mark_safe
from django.views.generic import UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from dateutil.relativedelta import relativedelta


logger = logging.getLogger(__name__)


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
            messages.success(
                request, 
                f'Client {client.nom} ajouté avec succès !'
            )
            return redirect('liste-clients')
        
        # ✅ CORRIGÉ : Retour simple (pas de tuple)
        return render(request, self.template_name, {'form': form})

@login_required
def client_list(request):
    """Liste des clients"""
    clients = Client.objects.all().select_related('save_by').order_by('-date_creation')

    # Pagination avec le package Paginator
    paginator = Paginator(clients,10) #10 clients par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stat rapides
    total_clients = clients.count()
    clients_actifs = clients.filter(client_type__isnull=False).count()
    context = {
        'clients': page_obj,
        'total_clients': total_clients,
        'clients_actifs': clients_actifs,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages
    }
    return render(request, 'facture/listClient.html', context)


@login_required
def client_detail(request, client_id):
    """Détails d'un client"""
    client = get_object_or_404(Client, id=client_id)
    factures = Facturation.objects.filter(client=client).select_related('save_by').order_by('-date_creation')
    devis_lists = Devis.objects.filter(client=client).select_related('save_by').order_by('-date_creation')

    # statistiques
    total_factures = factures.count()
    total_devis = devis_lists.count()
    total_documents = total_factures + total_devis 

    

    context = {
        'client': client,
        'factures': factures,
        'devis_lists': devis_lists,
        'total_factures': total_factures,
        'total_devis': total_devis,
        'total_documents' : total_documents,

        # statut Facture 
        'STATUT_PAYE': Facturation.STATUT_PAYE,
        'STATUT_EN_ATTENTE': Facturation.STATUT_EN_ATTENTE,
        'STATUT_ANNULE': Facturation.STATUT_ANNULE,

        # statut Devis
        'STATUT_ATTENTE': Devis.STATUT_ATTENTE,
        'STATUT_ACCEPTE': Devis.STATUT_ACCEPTE,
        'STATUT_REFUSE': Devis.STATUT_REFUSE,
        'STATUT_TRANSFORME_FACTURE': Devis.STATUT_TRANSFORME_FACTURE,
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
            messages.success(request, f'Client {client.nom} modifié avec succès!')
            return redirect('details-clients',client_id= client.id)
    else:
        form = ClientForm(instance=client)
    return render(request, 'facture/client_update.html', {'form': form, 'client': client})



@login_required
def client_delete(request, client_id):
    """Suppression d'un client"""
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        factures_count = Facturation.objects.filter(client=client).count()
        Devis.objects.filter(client=client).delete()
        Facturation.objects.filter(client=client).delete()
        client.delete()
        messages.success(request,f'{client.nom} supprimé ! (facture_count) facture(s))' )
        return redirect('liste-clients')
    
    raise Http404("Le client demandé n'existe pas ou ne peut être supprimé")
    

#============================VUES FACTURES=============================
@method_decorator(login_required, name='dispatch')
class FactureCreateView(View):
    template_name = 'facture/add_facture.html'

    def get(self, request, *args, **kwargs):
        """
        Affiche le formulaire de création de facture.
        Si devis_id est fourni, pré-remplit les données depuis le devis.
        """
        devis_id = request.GET.get('devis_id')
        devis = None
        
        # Récupérer les devis acceptés et non transformés de l'utilisateur
        devis_disponibles = Devis.objects.filter(
            save_by=request.user,
            statut=Devis.STATUT_ACCEPTE,
            est_transforme_en_facture=False
        ).select_related('client','save_by').order_by('-date_creation')
        
        form = FacturationForm(user=request.user)
        produit_formset = ProduitFacturationFormset(prefix='produits')
        service_formset = ServiceFacturationFormset(prefix='services')

        # Si un devis_id est fourni, charger ses données
        if devis_id:
            try:
                devis = Devis.objects.get(
                    id=devis_id,
                    save_by=request.user,
                    statut=Devis.STATUT_ACCEPTE,
                    est_transforme_en_facture=False
                )
                
                # Pré-remplir le formulaire avec les données du devis
                form = FacturationForm(
                    user=request.user,
                    initial={
                        'client': devis.client,
                        'taux_tva': devis.taux_tva,
                        'commentaire': f"Facture générée depuis le devis {devis.numero}\n{devis.commentaire or ''}"
                    }
                )
                
                # Préparer les données des produits
                produit_initial = []
                for pd in devis.produitdevis_set.all():
                    produit_initial.append({
                        'produit': pd.produit.id,
                        'nom_produit': pd.produit.nom_produit,
                        'description_produit': pd.produit.description_produit,
                        'prix_unitaire_produit': pd.produit.prix_unitaire_produit,
                        'quantite': pd.quantite,
                        'remise': pd.remise,
                    })
                
                # Préparer les données des services
                service_initial = []
                for sd in devis.servicedevis_set.all():
                    service_initial.append({
                        'service': sd.service.id,
                        'nom_service': sd.service.nom_service,
                        'description_service': sd.service.description_service,
                        'montant_du_service': sd.service.montant_du_service,
                        'date_prestation_service': sd.date_prestation_service,
                    })
                
                # Créer les formsets avec les données initiales
                produit_formset = ProduitFacturationFormset(
                    initial=produit_initial, 
                    prefix='produits'
                )
                service_formset = ServiceFacturationFormset(
                    initial=service_initial, 
                    prefix='services'
                )
                
                messages.info(request, f'Données chargées depuis le devis {devis.numero}')
                
            except Devis.DoesNotExist:
                messages.error(request, 'Devis non trouvé ou non valide pour transformation.')

        context = {
            'form': form,
            'produit_formset': produit_formset,
            'service_formset': service_formset,
            'devis_id': devis_id,
            'devis': devis,
            'devis_disponibles': devis_disponibles,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        Traite la soumission du formulaire de création de facture.
        """
        devis_id = request.POST.get('devis_origine')
        devis = None
        
        # Si un devis est sélectionné, le récupérer
        if devis_id:
            try:
                devis = Devis.objects.get(
                    id=devis_id,
                    save_by=request.user,
                    statut=Devis.STATUT_ACCEPTE,
                    est_transforme_en_facture=False
                )
            except Devis.DoesNotExist:
                messages.error(request, 'Devis non trouvé ou non valide pour transformation.')
                return redirect('create-facture')

        # Créer les formsets
        produit_formset = ProduitFacturationFormset(
            request.POST, 
            prefix='produits'
        )
        service_formset = ServiceFacturationFormset(
            request.POST, 
            prefix='services'
        )
        
        # Créer le formulaire principal
        form = FacturationForm(
            request.POST, 
            user=request.user,
            produit_formset=produit_formset,
            service_formset=service_formset
        )

        # Validation
        if form.is_valid() and produit_formset.is_valid() and service_formset.is_valid():
            try:
                with transaction.atomic():
                    # 1. Créer la facture
                    facture = form.save(commit=False)
                    facture.save_by = request.user
                    
                    # Associer le devis si fourni
                    if devis:
                        facture.devis_origine = devis
                    
                    # Sauvegarder la facture pour obtenir un pk
                    facture.save()
                    
                    # 2. Sauvegarder les produits
                    produits_instances = produit_formset.save(commit=False)
                    for produit_instance in produits_instances:
                        produit_instance.facture = facture
                        produit_instance.save()
                        print(f"Produit sauvegardé: {produit_instance.produit} - Qté: {produit_instance.quantite}")
                    
                    # Gérer les suppressions de produits
                    for obj in produit_formset.deleted_objects:
                        obj.delete()
                    
                    # 3. Sauvegarder les services
                    services_instances = service_formset.save(commit=False)
                    for service_instance in services_instances:
                        service_instance.facture = facture
                        service_instance.save()
                        print(f"Service sauvegardé: {service_instance.service}")
                    
                    # Gérer les suppressions de services
                    for obj in service_formset.deleted_objects:
                        obj.delete()
                    
                    # 4. Recalculer les totaux
                    facture.recalculer_totaux()
                    
                    # 5. Mettre à jour le devis si applicable
                    if devis:
                        devis.est_transforme_en_facture = True
                        devis.statut = Devis.STATUT_TRANSFORME_FACTURE
                        devis.date_transformation = timezone.now()
                        devis.last_update = timezone.now()
                        devis.save()
                        
                        messages.success(
                            request, 
                            f'Facture {facture.numero} créée avec succès depuis le devis {devis.numero}!'
                        )
                    else:
                        messages.success(request, f'Facture {facture.numero} créée avec succès !')
                    
                    return redirect('document-detail', document_id=facture.id, document_type='facture')
                    
            except IntegrityError as e:
                messages.error(request, f'Erreur d\'intégrité : {str(e)}')
                print(f"IntegrityError: {e}")
            except ValidationError as e:
                messages.error(request, f'Erreur de validation : {str(e)}')
                print(f"ValidationError: {e}")
            except Exception as e:
                messages.error(request, f'Erreur lors de la création : {str(e)}')
                print(f"Exception: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Afficher les erreurs
            print("=== ERREURS DE VALIDATION ===")
            if not form.is_valid():
                print("Erreurs formulaire:", form.errors)
                for field, errors in form.errors.items():
                    messages.error(request, f"{field}: {errors}")
            if not produit_formset.is_valid():
                print("Erreurs produits:", produit_formset.errors)
            if not service_formset.is_valid():
                print("Erreurs services:", service_formset.errors)
            
            messages.error(request, 'Veuillez corriger les erreurs dans le formulaire.')

        # En cas d'erreur, recharger les devis disponibles
        devis_disponibles = Devis.objects.filter(
            save_by=request.user,
            statut=Devis.STATUT_ACCEPTE,
            est_transforme_en_facture=False
        ).select_related('client','save_by').order_by('-date_creation')

        context = {
            'form': form,
            'produit_formset': produit_formset,
            'service_formset': service_formset,
            'devis_id': devis_id,
            'devis': devis,
            'devis_disponibles': devis_disponibles,
        }
        return render(request, self.template_name, context)


# Vue AJAX pour charger les données d'un devis
@login_required
def get_devis_data(request, devis_id):
    """
    Retourne les données d'un devis en JSON pour pré-remplir le formulaire via AJAX.
    """
    try:
        devis = Devis.objects.get(
            id=devis_id,
            save_by=request.user,
            statut=Devis.STATUT_ACCEPTE,
            est_transforme_en_facture=False
        )
        
        data = {
            'success': True,
            'devis_numero': devis.numero,
            'client_id': devis.client.id,
            'client_nom': devis.client.nom,
            'taux_tva': str(devis.taux_tva),
            'commentaire': f"Facture générée depuis le devis {devis.numero}\n{devis.commentaire or ''}",
            'total_ttc': str(devis.total_ttc),
            'produits': [
                {
                    'produit': pd.produit.id,
                    'nom': pd.produit.nom_produit,
                    'description': pd.produit.description_produit or '',
                    'prix_unitaire': str(pd.produit.prix_unitaire_produit),
                    'quantite': pd.quantite,
                    'remise': str(pd.remise),
                    'category': pd.produit.category.id if hasattr(pd.produit, 'category') and pd.produit.category else None
                }
                for pd in devis.produitdevis_set.select_related('produit').all()
            ],
            'services': [
                {
                    'service': sd.service.id,
                    'nom': sd.service.nom_service,
                    'description': sd.service.description_service or '',
                    'montant': str(sd.service.montant_du_service),
                    'date_prestation_service': sd.date_prestation_service.isoformat() if sd.date_prestation_service else ''
                }
                for sd in devis.servicedevis_set.select_related('service').all()
            ]
        }
        
        return JsonResponse(data)
        
    except Devis.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Devis non trouvé ou non valide'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def get_devis_data(request, devis_id):
    try:
        devis = Devis.objects.get(id=devis_id, save_by=request.user)
        data = {
            'client_id': devis.client.id,
            'taux_tva': str(devis.taux_tva),
            'commentaire': f"Facture générée depuis le devis {devis.numero}\n{devis.commentaire or ''}",
            'produits': [
                {'produit': pd.produit.id, 'quantite': pd.quantite, 'remise': str(pd.remise)}
                for pd in devis.produitdevis_set.all()
            ],
            'services': [
                {'service': sd.service.id, 'date_prestation_service': sd.date_prestation_service}
                for sd in devis.servicedevis_set.all()
            ]
        }
        return JsonResponse(data)
    except Devis.DoesNotExist:
        return JsonResponse({'error': 'Devis non trouvé'}, status=404)


def handle_modify_status_facture(request,facture_id,new_status):
    """ Gérer la modification du statut d'une facture"""
    try:
        facture = get_object_or_404(Facturation, id=facture_id)
        if new_status not in ['1','2','3']:
            messages.error(request, "Statut invalide.")
            return False
        facture.statut = int(new_status)
        facture.last_update = timezone.now()
        facture.save()
        messages.success(request, f"Le statut de la facture {facture.numero} a été mis à jour avec succès.")
        return True
    except Facturation.DoesNotExist:
        messages.error(request, "Facture non trouvée.")
        return False


def handle_delete_facture(request,facture_id):
    """ Gérer la suppression d'une facture"""
    try:
        facture = get_object_or_404(Facturation, id=facture_id)
        if facture.save_by != request.user:
            messages.error(request, "Vous n'êtes pas autorisé à supprimer cette facture.")
            return False
        facture.delete()
        messages.success(request, f"La facture {facture.numero} a été supprimée avec succès.")
        return True
    except Facturation.DoesNotExist:
        messages.error(request, "La facture demandée n'existe pas.")
        return False



@login_required
def facture_list(request):
    """Liste des factures avec recherche et pagination et gestion des actions."""
    if request.method == 'POST':
        if 'id_modified' in request.POST:
            facture_id = request.POST.get('id_modified')
            new_status = request.POST.get('modified')
            handle_modify_status_facture(request, facture_id, new_status)
        elif 'id_supprimer' in request.POST:
            facture_id = request.POST.get('id_supprimer')
            handle_delete_facture(request, facture_id)
        return redirect('liste-facture')
    # Gerer la recherche et l'affichage (request GET)
    query = request.GET.get('q', '').strip()
    factures = Facturation.objects.select_related('client', 'save_by').order_by('-date_creation')

    if query:
        factures = factures.filter(
            Q(numero__icontains=query) |
            Q(client__nom__icontains=query) |
            Q(save_by__username__icontains=query) |
            Q(commentaire__icontains=query)
        )
    
    paginator = Paginator(factures, 5)
    page = request.GET.get('page')
    try:
        factures = paginator.page(page)
    except PageNotAnInteger:
        factures = paginator.page(1)
    except EmptyPage:
        factures = paginator.page(paginator.num_pages)
    
    context = {
        'factures': factures,
        'query': query,
    }
    return render(request, 'facture/listeFacture.html',context)


@method_decorator(login_required, name='dispatch')
class FacturationEditView(View):
    template_name = 'facture/update_facture.html'

    def get(self, request, *args, **kwargs):
        facture_id = kwargs.get('facture_id')
        facture = get_object_or_404(
            Facturation, 
            id=facture_id, 
            save_by=request.user
        )
        
        form = FacturationForm(user=request.user, instance=facture)
        produit_formset = ProduitFacturationFormset(instance=facture, prefix='produits')
        service_formset = ServiceFacturationFormset(instance=facture, prefix='services')
        
        context = {
            'form': form,
            'produit_formset': produit_formset,
            'service_formset': service_formset,
            'facture': facture,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        facture_id = kwargs.get('facture_id')
        facture = get_object_or_404(
            Facturation, 
            id=facture_id, 
            save_by=request.user
        )
        
        produit_formset = ProduitFacturationFormset(
            request.POST, 
            instance=facture, 
            prefix='produits'
        )
        service_formset = ServiceFacturationFormset(
            request.POST, 
            instance=facture, 
            prefix='services'
        )
        
        form = FacturationForm(
            request.POST,
            user=request.user,
            instance=facture,
            produit_formset=produit_formset,
            service_formset=service_formset
        )

        if form.is_valid() and produit_formset.is_valid() and service_formset.is_valid():
            try:
                print(f"Modification demandée pour facture: {facture.id}")
                
                with transaction.atomic():
                    # 1. Sauvegarder le formulaire principal
                    facture = form.save(commit=False)
                    facture.save_by = request.user
                    facture.last_update = timezone.now()
                    facture.save()
                    print(f"Facture sauvegardée - Taux TVA: {facture.taux_tva}")
                    
                    # 2. Sauvegarder les produits
                    produits_instances = produit_formset.save(commit=False)
                    for produit_instance in produits_instances:
                        produit_instance.facture = facture
                        produit_instance.save()
                        print(f"Produit sauvegardé: {produit_instance.produit} - Qté: {produit_instance.quantite}")
                    
                    # Gérer les suppressions de produits
                    for obj in produit_formset.deleted_objects:
                        print(f"Suppression produit: {obj}")
                        obj.delete()

                    # 3. Sauvegarder les services
                    services_instances = service_formset.save(commit=False)
                    for service_instance in services_instances:
                        service_instance.facture = facture
                        service_instance.save()
                        print(f"Service sauvegardé: {service_instance.service}")
                    
                    # Gérer les suppressions de services
                    for obj in service_formset.deleted_objects:
                        print(f"Suppression service: {obj}")
                        obj.delete()
                    
                    # 4. IMPORTANT : Recalculer les totaux APRÈS avoir sauvegardé tous les produits/services
                    print(f"Avant recalcul - Total HT: {facture.total_net_ht}, TVA: {facture.total_tva}, TTC: {facture.total_ttc}")
                    facture.recalculer_totaux()
                    print(f"Après recalcul - Total HT: {facture.total_net_ht}, TVA: {facture.total_tva}, TTC: {facture.total_ttc}")
                    
                messages.success(request, f'Facture {facture.numero} modifiée avec succès !')
                return redirect('document-detail', document_id=facture.id, document_type='facture')
                
            except IntegrityError as e:
                print(f"IntegrityError: {str(e)}")
                messages.error(request, f'Erreur d\'intégrité : {str(e)}')
            except ValidationError as e:
                print(f"ValidationError: {str(e)}")
                messages.error(request, f'Erreur de validation : {str(e)}')
            except Exception as e:
                print(f"Exception inattendue: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Erreur lors de la modification : {str(e)}')
        else:
            # Afficher les erreurs en détail
            print("=== ERREURS DE VALIDATION ===")
            
            if not form.is_valid():
                print("Erreurs du formulaire principal:")
                for field, errors in form.errors.items():
                    print(f"  - {field}: {errors}")
            
            if not produit_formset.is_valid():
                print("Erreurs produit formset:")
                for idx, form_errors in enumerate(produit_formset.errors):
                    if form_errors:
                        print(f"  - Produit {idx}: {form_errors}")
                if produit_formset.non_form_errors():
                    print(f"  - Erreurs non-form: {produit_formset.non_form_errors()}")
            
            if not service_formset.is_valid():
                print("Erreurs service formset:")
                for idx, form_errors in enumerate(service_formset.errors):
                    if form_errors:
                        print(f"  - Service {idx}: {form_errors}")
                if service_formset.non_form_errors():
                    print(f"  - Erreurs non-form: {service_formset.non_form_errors()}")
            
            messages.error(request, 'Veuillez corriger les erreurs dans le formulaire.')

        context = {
            'form': form,
            'produit_formset': produit_formset,
            'service_formset': service_formset,
            'facture': facture,
        }
        return render(request, self.template_name, context)


@login_required
def facture_change_statut(request, facture_id):
    """ Changer le statut de la facture (AJAX)"""
    if request.method == 'POST':
        facture = get_object_or_404(Facturation, id=facture_id)
        nouveau_statut = int(request.POST.get('statut', 0))

        statuts_valides = [
            Facturation.STATUT_PAYE,
            Facturation.STATUT_EN_ATTENTE,
            Facturation.STATUT_ANNULE
        ]

        if nouveau_statut in  statuts_valides:
            facture.statut = nouveau_statut
            facture.last_update = timezone.now()
            facture.save

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' :
                return JsonResponse({
                    'success': True,
                    'message': 'Statut modifié avec succès',
                    'statut': nouveau_statut,
                    'badge_class': get_badge_class(nouveau_statut)
                })
            else:
                messages.success(request, 'Statut modifié avec succès')

        else:
            if request.headers.get('X-Reqested-With') == 'XMLHttpReqest':
                return JsonResponse({
                    'success': False,

                    'message': 'Statut invalide'
                })
            else:
                messages.success(request, 'Statut invalide')
    
    return redirect('details-facture', facture_id = facture_id)

def get_badge_class(statut):
    """ retourne la classe CSS du badge selon le statut"""
    classes= {
        Facturation.STATUT_PAYE: 'bg-success',
        Facturation.STATUT_EN_ATTENTE : 'bg-warning',
        Facturation.STATUT_ANNULE : 'bg-danger'
    }

    return classes.get(statut, 'bg-secondary')

 
#============================Vues pour details devis et facture =======================
@login_required
def detail_document(request, document_id, document_type):
    """
    Vue unifiée pour afficher les détails d'un devis OU facture
    document_type: 'devis' ou 'facture'
    """

    # Initialisation à None
    produit_devis = None
    service_devis = None
    produit_facture = None
    service_facture = None
    reglements = None

    if document_type == 'devis':
        document = get_object_or_404(
            Devis.objects.select_related('client', 'save_by'),
            id=document_id
        )
        produits = document.produits.all()
        services = document.services.all()
        produit_devis = document.produitdevis_set.all()
        service_devis = document.servicedevis_set.all()
        reglements = None  # Pas de règlements pour les devis
        
    elif document_type == 'facture':
        document = get_object_or_404(
            Facturation.objects.select_related('client', 'save_by', 'devis_origine'),
            id=document_id
        )
        produits = document.produits.all()
        services = document.services.all()
        produit_facture = document.produitfacturation_set.all()
        service_facture = document.servicefacturation_set.all()
        reglements = document.reglement_set.all().order_by('-date_reglement')
        
    else:
        raise ValueError("document_type doit être 'devis' ou 'facture'")

    # Récupérer TOUS les modes de règlement actifs pour la section paiement
    modes_reglement = ModeReglement.objects.filter(est_actif=True).order_by('nom')

    context = {
        'document': document,
        'produits': produits,
        'services': services,
        'produit_devis': produit_devis,
        'service_devis': service_devis,
        'produit_facture': produit_facture,
        'service_facture': service_facture,
        'reglements': reglements,
        'document_type': document_type,
        'modes_reglement': modes_reglement,
        'peut_transformer': document.peut_etre_transforme() if document_type == 'devis' else False,
    }
    
    return render(request, 'facture/details_devis_facture.html', context)


#===========================================VUES DEVIS =============================================
@method_decorator(login_required, name='dispatch')
class DevisCreateView(View):
    template_name = 'facture/add_devis.html'

    def get(self, request, *args, **kwargs):
        form_data = request.session.pop('devis_form_data', None)
        if form_data:
            form = DevisForm(data=form_data, user=request.user)
            produit_formset = ProduitDevisFormset(data=form_data, prefix='produits')
            service_formset = ServiceDevisFormset(data=form_data, prefix='services')
        else:
            form = DevisForm(user=request.user)
            produit_formset = ProduitDevisFormset(prefix='produits')
            service_formset = ServiceDevisFormset(prefix='services')
        
        context = {
            'form': form,
            'produit_formset': produit_formset,
            'service_formset': service_formset,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        produit_formset = ProduitDevisFormset(request.POST, prefix='produits')
        service_formset = ServiceDevisFormset(request.POST, prefix='services')
        form = DevisForm(request.POST, user=request.user, produit_formset=produit_formset, service_formset=service_formset)

        if form.is_valid() and produit_formset.is_valid() and service_formset.is_valid():
            # Vérifier qu'il y a au moins un produit ou service valide
            has_valid_produit = any(
                pf.is_valid() and not pf.cleaned_data.get('DELETE', False) 
                for pf in produit_formset
            )
            has_valid_service = any(
                sf.is_valid() and not sf.cleaned_data.get('DELETE', False) 
                for sf in service_formset
            )
            
            if not (has_valid_produit or has_valid_service):
                messages.error(request, "Veuillez ajouter au moins un produit ou service valide.")
                context = {
                    'form': form,
                    'produit_formset': produit_formset,
                    'service_formset': service_formset,
                }
                return render(request, self.template_name, context)
            
            try:
                with transaction.atomic():
                    devis = form.save(commit=False)
                    devis.save_by = request.user
                    devis.save()
                    
                    # Sauvegarder les produits
                    produit_formset.instance = devis
                    produit_formset.save()
                    
                    # Sauvegarder les services
                    service_formset.instance = devis
                    service_formset.save()
                    
                    # Recalculer les totaux
                    devis.recalculer_totaux()
                    devis.save()
                    
                    messages.success(request, f'Devis {devis.numero} créé avec succès !')
                    return redirect('document-detail', document_id=devis.id, document_type='devis')
                    
            except IntegrityError as e:
                messages.error(request, f"Erreur : impossible de créer le devis (numéro déjà utilisé ou autre problème de base de données).")
                print(f"IntegrityError: {e}")
            except ValidationError as e:
                messages.error(request, f"Erreur de validation : {str(e)}")
                print(f"ValidationError: {e}")
            except Exception as e:
                messages.error(request, f"Erreur inattendue : {str(e)}")
                print(f"Exception: {e}")
        else:
            # Gestion des erreurs de validation
            errors = []
            
            if not form.is_valid():
                for field, error_list in form.errors.items():
                    if field == '__all__':
                        errors.append(f"Erreur : {error_list.as_text()}")
                    else:
                        field_label = form.fields[field].label if field in form.fields else field
                        errors.append(f"Erreur dans {field_label} : {error_list.as_text()}")
            
            # Erreurs des produits
            for idx, produit_form in enumerate(produit_formset):
                if not produit_form.is_valid() and not produit_form.cleaned_data.get('DELETE', False):
                    if produit_form.errors.get('nom_produit'):
                        nom_produit = produit_form.cleaned_data.get('nom_produit', 'inconnu')
                        errors.append(
                            f"Produit {idx + 1} : {produit_form.errors['nom_produit'].as_text()}. "
                            f"<a href='{reverse('ajouter_element')}?type=produit&nom={nom_produit}&return_to_devis=true' target='_blank'>Créer le produit</a>"
                        )
                    else:
                        for field, error_list in produit_form.errors.items():
                            if field != 'DELETE':
                                errors.append(f"Produit {idx + 1} - {field}: {error_list.as_text()}")
            
            # Erreurs des services
            for idx, service_form in enumerate(service_formset):
                if not service_form.is_valid() and not service_form.cleaned_data.get('DELETE', False):
                    if service_form.errors.get('nom_service'):
                        nom_service = service_form.cleaned_data.get('nom_service', 'inconnu')
                        errors.append(
                            f"Service {idx + 1} : {service_form.errors['nom_service'].as_text()}. "
                            f"<a href='{reverse('ajouter_element')}?type=service&nom={nom_service}&return_to_devis=true' target='_blank'>Créer le service</a>"
                        )
                    else:
                        for field, error_list in service_form.errors.items():
                            if field != 'DELETE':
                                errors.append(f"Service {idx + 1} - {field}: {error_list.as_text()}")
            
            if errors:
                messages.error(request, mark_safe("<br>".join(errors)))
                # Stocker les données du formulaire dans la session pour les préserver
                request.session['devis_form_data'] = request.POST.dict()

        context = {
            'form': form,
            'produit_formset': produit_formset,
            'service_formset': service_formset,
        }
        return render(request, self.template_name, context)

def handle_modify_status(request, devis_id, new_status):
    """Gérer la modification du statut d'un devis."""
    try:
        devis = get_object_or_404(Devis, id=devis_id)
        if devis.statut == Devis.STATUT_TRANSFORME_FACTURE:
            messages.error(request, "Impossible de modifier un devis transformé en facture.")
            return False
        if new_status not in ['1', '2', '3']:
            messages.error(request, "Statut invalide.")
            return False
        devis.statut = int(new_status)
        devis.last_update = timezone.now()
        devis.save()
        messages.success(request, f"Le statut du devis {devis.numero} a été mis à jour.")
        return True
    except Devis.DoesNotExist:
        messages.error(request, "Devis non trouvé.")
        return False

def handle_delete_devis(request, devis_id):
    """Gérer la suppression d'un devis."""
    try:
        devis = get_object_or_404(Devis, id=devis_id)
        if devis.save_by != request.user:
            messages.error(request, "Vous n'êtes pas autorisé à supprimer ce devis.")
            return False
        devis.delete()
        messages.success(request, f"Le devis {devis.numero} a été supprimé.")
        return True
    except Devis.DoesNotExist:
        messages.error(request, "Devis non trouvé.")
        return False

@login_required
def devis_list(request):
    """Liste des devis avec recherche, pagination et gestion des actions."""
    if request.method == 'POST':
        if 'id_modified' in request.POST:
            devis_id = request.POST.get('id_modified')
            new_status = request.POST.get('modified')
            handle_modify_status(request, devis_id, new_status)
        elif 'id_supprimer' in request.POST:
            devis_id = request.POST.get('id_supprimer')
            handle_delete_devis(request, devis_id)
        return redirect('liste-devis')

    # Gérer la recherche et l'affichage (requête GET)
    query = request.GET.get('q', '').strip()
    devis_list = Devis.objects.select_related('client', 'save_by').order_by('-date_creation')
    
    if query:
        devis_list = devis_list.filter(
            Q(numero__icontains=query) |
            Q(client__nom__icontains=query) |
            Q(save_by__username__icontains=query) |
            Q(commentaire__icontains=query)
        )
    
    paginator = Paginator(devis_list, 5)
    page = request.GET.get('page')
    try:
        devis_lists = paginator.page(page)
    except PageNotAnInteger:
        devis_lists = paginator.page(1)
    except EmptyPage:
        devis_lists = paginator.page(paginator.num_pages)
    
    context = {
        'devis_lists': devis_lists,
        'query': query
    }
    return render(request, 'facture/liste_devis.html', context)

@login_required
def devis_list_attente(request):
    """Liste des devis en attente d'acceptation."""
    
    if request.method == 'POST':
        # Modifier le statut
        if 'id_modified' in request.POST:
            devis_id = request.POST.get('id_modified', '').strip()
            new_status = request.POST.get('modified', '').strip()
            
            print(f"DEBUG - Modification demandée: devis_id={devis_id}, new_status={new_status}")
            
            if not devis_id:
                messages.error(request, 'Erreur : ID du devis manquant.')
            elif not new_status:
                messages.error(request, 'Erreur : Nouveau statut manquant.')
            else:
                try:
                    devis = get_object_or_404(Devis, id=int(devis_id), save_by=request.user)
                    old_status = devis.get_statut_display()
                    
                    devis.statut = int(new_status)
                    devis.save()
                    
                    new_status_display = devis.get_statut_display()
                    messages.success(
                        request, 
                        f'Statut du devis {devis.numero} changé de "{old_status}" à "{new_status_display}".'
                    )
                    print(f"DEBUG - Statut modifié avec succès: {devis.numero}")
                    
                except ValueError as e:
                    messages.error(request, f'Erreur : ID ou statut invalide. {str(e)}')
                    print(f"DEBUG - ValueError: {e}")
                except Exception as e:
                    messages.error(request, f'Erreur lors de la modification : {str(e)}')
                    print(f"DEBUG - Exception: {e}")
        
        # Supprimer le devis
        elif 'id_supprimer' in request.POST:
            devis_id = request.POST.get('id_supprimer', '').strip()
            
            print(f"DEBUG - Suppression demandée: devis_id={devis_id}")
            
            if not devis_id:
                messages.error(request, 'Erreur : ID du devis manquant.')
            else:
                try:
                    devis = get_object_or_404(Devis, id=int(devis_id), save_by=request.user)
                    numero = devis.numero
                    devis.delete()
                    messages.success(request, f'Devis {numero} supprimé avec succès.')
                    print(f"DEBUG - Devis supprimé: {numero}")
                    
                except ValueError as e:
                    messages.error(request, f'Erreur : ID invalide. {str(e)}')
                    print(f"DEBUG - ValueError: {e}")
                except Exception as e:
                    messages.error(request, f'Erreur lors de la suppression : {str(e)}')
                    print(f"DEBUG - Exception: {e}")
        
        return redirect('liste-attente')
    
    # GET : Affichage et recherche
    query = request.GET.get('q', '').strip()

    devis_en_attente = Devis.objects.filter(
        save_by=request.user,  # Important : filtrer par utilisateur
        statut=Devis.STATUT_ATTENTE
    ).select_related('client', 'save_by').order_by('-date_creation')

    if query:
        devis_en_attente = devis_en_attente.filter(
            Q(numero__icontains=query) |
            Q(client__nom__icontains=query) |
            Q(save_by__username__icontains=query) |
            Q(commentaire__icontains=query)
        )
    
    # Pagination
    paginator = Paginator(devis_en_attente, 10)  # 10 devis par page
    page = request.GET.get('page')
    
    try:
        devis_en_attente = paginator.page(page)
    except PageNotAnInteger:
        devis_en_attente = paginator.page(1)
    except EmptyPage:
        devis_en_attente = paginator.page(paginator.num_pages)
    
    context = {
        'devis_en_attente': devis_en_attente,
        'query': query,
    }
   
    return render(request, 'facture/devis_attente.html', context)
@method_decorator(login_required, name='dispatch')
class DevisEditView(View):
    template_name = 'facture/update_devis.html'

    def get(self, request, *args, **kwargs):
            
        devis_id = kwargs.get('devis_id')
        devis = get_object_or_404(
            Devis,
            id=devis_id,
            save_by=request.user,
            #est_transforme_en_facture=False
        ) 
        if devis.est_transforme_en_facture:
            messages.error(request, "Impossible de modifier un devis qui a été transformé en facture.")
            return redirect('document-detail', document_id=devis.id, document_type='devis')
        
        form = DevisForm(user=request.user, instance=devis)
        # Utiliser 'form' comme prefix pour les produits (convention Django)
        produit_formset = ProduitDevisFormset(instance=devis, prefix='produits')
        # Utiliser 'service_form' comme prefix pour les services
        service_formset = ServiceDevisFormset(instance=devis, prefix='services')
        
        context = {
            'form': form,
            'produit_formset': produit_formset,
            'service_formset': service_formset,
            'devis': devis,
            'clients': Client.objects.filter(save_by=request.user),
            'produits': Produit.objects.all(),        
            'services': Service.objects.all(), 
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        devis_id = kwargs.get('devis_id')
        devis = get_object_or_404(
            Devis,
            id=devis_id,
            save_by=request.user,
            #est_transforme_en_facture=False
        )
        if devis.est_transforme_en_facture:
            messages.error(request, "Impossible de modifier un devis qui a été transformé en facture.")
            return redirect('document-detail', document_id=devis.id, document_type='devis')
        # Utiliser les mêmes prefixes que dans GET
        produit_formset = ProduitDevisFormset(request.POST, instance=devis, prefix='produits')
        service_formset = ServiceDevisFormset(request.POST, instance=devis, prefix='services')
        
        form = DevisForm(
            request.POST,
            user=request.user,
            instance=devis,
            produit_formset=produit_formset,
            service_formset=service_formset
        )

        if form.is_valid() and produit_formset.is_valid() and service_formset.is_valid():
            try:
                print("Modification demandée pour devis:", devis.id)
                with transaction.atomic():
                    devis = form.save(commit=False)
                    devis.save_by = request.user
                    devis.save()
                    
                    # Sauvegarder les produits
                produits_instances = produit_formset.save(commit=False)
                for produit_instance in produits_instances:
                    #print(f"Sauvegarde produit: {produit_instance.produit} - Qté: {produit_instance.quantite}")
                    produit_instance.save()
                
                # Gérer les suppressions
                for obj in produit_formset.deleted_objects:
                    #print(f"Suppression produit: {obj}")
                    obj.delete()


                # Sauvegarder les services
                services_instances = service_formset.save(commit=False)
                for service_instance in services_instances:
                    #print(f"Sauvegarde service: {service_instance.service}")
                    service_instance.save()
                
                # Gérer les suppressions
                for obj in service_formset.deleted_objects:
                    #print(f"Suppression service: {obj}")
                    obj.delete()
                    
                    # Recalculer les totaux
                devis.recalculer_totaux()
                devis.last_update = timezone.now()
                devis.save()
                    
                messages.success(request, f'Devis {devis.numero} modifié avec succès !')
                return redirect('document-detail', document_id=devis.id, document_type='devis')
            except Exception as e:
                #print(f"Erreur détaillée: {str(e)}")
                messages.error(request, f'Erreur lors de la modification : {str(e)}')
        else:
            # Afficher les erreurs en détail
            #print("=== ERREURS DE VALIDATION ===")
            #print("Erreurs du formulaire:", form.errors)
            #print("Erreurs produit formset:", produit_formset.errors)
            #print("Erreurs service formset:", service_formset.errors)
            
            # Afficher aussi les erreurs non-field
        
            
            messages.error(request, 'Veuillez corriger les erreurs dans le formulaire.')
        
        context = {
            'form': form,
            'produit_formset': produit_formset,
            'service_formset': service_formset,
            'devis': devis,
            'clients': Client.objects.filter(save_by=request.user),
            'produits': Produit.objects.all(),        
            'services': Service.objects.all(),
        }
        return render(request, self.template_name, context)


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

@method_decorator(login_required, name='dispatch')
class DevisTransformView(View):
    template_name = 'facture/transformer_devis_to_facture.html'  # Ton template simple

    def get(self, request, *args, **kwargs):
        devis_id = kwargs.get('devis_id')
        devis = get_object_or_404(
            Devis,
            id=devis_id,
            save_by=request.user,
            est_transforme_en_facture=False
        )
        
        # Vérifier si le devis peut être transformé
        if not devis.peut_etre_transforme():
            messages.warning(request, "Ce devis ne peut pas être transformé en facture.")
            return redirect('document-detail', document_id=devis.id, document_type='devis')
        
        context = {
            'devis': devis,
            'document': devis,
            'document_type': 'devis',
            'docuement_id': devis.id,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        devis_id = kwargs.get('devis_id')
        devis = get_object_or_404(
            Devis,
            id=devis_id,
            save_by=request.user,
            est_transforme_en_facture=False
        )
        
        if not devis.peut_etre_transforme():
            messages.error(request, "Ce devis ne peut pas être transformé en facture.")
            return redirect('devis-detail', devis.id)
        
        envoyer_email = request.POST.get('envoyer_email') == 'on'
        
        try:
            with transaction.atomic():
                # Utiliser la méthode existante du modèle ✅
                facture = devis.transformer_en_facture(request.user)
                
                # Optionnel : envoyer email
                if envoyer_email:
                    envoyer_document_email(request, document_type='facture', document_id=facture.id) 
                    pass
                
                messages.success(
                    request, 
                    f'Facture {facture.numero} créée avec succès à partir du devis {devis.numero}!'
                )
                return redirect('document-detail', document_id=facture.id, document_type='facture')
                
        except (DevisAlreadyTransformedError, DevisNotAcceptedError) as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Erreur lors de la transformation : {str(e)}')
            import traceback
            traceback.print_exc() # pour deboggage
        
        return redirect('document-detail', document_id=devis.id,document_type='devis')  


# ======================================Vues REGLEMENTS =========================

@login_required
def reglement_create(request, facture_id):
    facture = get_object_or_404(Facturation, id=facture_id)
    facture.recalculer_totaux()  # ← important maintenant

    if request.method == 'POST':
        form = ReglementForm(request.POST, facture=facture)
        if form.is_valid():
            reglement = form.save(commit=False)
            reglement.client = facture.client
            reglement.facture = facture
            reglement.save()  # déclenche recalculer_totaux() via le save() du modèle
            messages.success(request, f"Règlement de {reglement.montant_reglement} FCFA enregistré.")
            return redirect('document-detail', document_id=facture.id, document_type='facture')
    else:
        form = ReglementForm(facture=facture, initial={'montant_reglement': facture.solde_du})

    context = {
        'form': form,
        'facture': facture,
        'max_possible': facture.solde_du,
        'max_possible_raw': float(facture.solde_du or 0),
    }
    return render(request, 'facture/add_reglement.html', context)


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


class ReglementUpdateView(SuccessMessageMixin, UpdateView):
    model = Reglement
    form_class = ReglementForm
    template_name = 'facture/update_reglement.html'
    success_message = "Règlement modifié avec succès !"

    def get_success_url(self):
        return reverse_lazy('liste-reglements')

    def form_valid(self, form):
        # Débogage
        # Sauvegarder sans appeler model.clean()
        self.object = form.save(commit=False)
        self.object.save()  # ← Sauvegarde sans validation du modèle
        self.object.facture.recalculer_totaux()
        response = super(UpdateView, self).form_valid(form)
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())
    
    def form_invalid(self, form):
        # Débogage des erreurs
        print("❌ Formulaire invalide")
        print(f"Erreurs: {form.errors}")
        print(f"Erreurs non-field: {form.non_field_errors()}")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        facture = self.object.facture
        ancien_montant = self.object.montant_reglement
        solde_actuel = facture.solde_du
        
        max_possible = solde_actuel + ancien_montant

        context.update({
            'nouveau_solde': max_possible,
            'max_possible': max_possible,
        })
        return context
    
    # def get_form_kwargs(self):
    #     kwargs = super().get_form_kwargs()
    #     kwargs['facture'] = self.object.facture  # si tu veux garder cette logique
    #     return kwargs

class ReglementDeleteView(SuccessMessageMixin, DeleteView):
    model = Reglement
    #template_name = 'facture/reglement_confirm_delete.html'
    success_url = reverse_lazy('liste-reglements')
    success_message = "Règlement supprimé avec succès."

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)

@login_required
def mode_reglement_list(request):
    modes = ModeReglement.objects.all().order_by('-est_actif', 'nom')
    return render(request, 'facture/mode_reglement_list.html', {'modes': modes})

@login_required
def mode_reglement_create(request):
    if request.method == 'POST':
        form = ModeReglementForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Mode '{form.cleaned_data['nom']}' ajouté avec succès.")
            return redirect('mode-reglement-list')
    else:
        form = ModeReglementForm()
    
    return render(request, 'facture/mode_reglement_form.html', {'form': form})

@login_required
def mode_reglement_update(request, mode_id):
    mode = get_object_or_404(ModeReglement, id=mode_id)
    
    if request.method == 'POST':
        form = ModeReglementForm(request.POST, instance=mode)
        if form.is_valid():
            form.save()
            messages.success(request, f"Mode '{form.cleaned_data['nom']}' mis à jour avec succès.")
            return redirect('mode-reglement-list')
    else:
        form = ModeReglementForm(instance=mode)
    
    return render(request, 'facture/mode_reglement_update.html', {'form': form, 'mode': mode})

@login_required
def mode_reglement_delete(request, mode_id):
    mode = get_object_or_404(ModeReglement, id=mode_id)
    
    if request.method == 'POST':
        nom_mode = mode.nom
        mode.delete()
        messages.success(request, f"Mode '{nom_mode}' supprimé avec succès.")
        return redirect('mode-reglement-list')
    
    raise Http404("Le client demandé n'existe pas ou ne peut être supprimé")
    

@login_required
def toggle_mode_reglement(request, mode_id):
    # 1. Récupérer le mode
    mode = get_object_or_404(ModeReglement, id=mode_id)
    
    if request.method == 'POST':
        # 2. Inverser l'état
        mode.est_actif = not mode.est_actif
        # 3. Sauvegarder
        mode.save()
        # 4. Message + redirection
        etat = "activé" if mode.est_actif else "désactivé"
        messages.success(request, f"Mode '{mode.nom}' {etat}.")
        return redirect('mode-reglement-list')
    
    # Si GET → on ne fait rien, ou on redirige
    return redirect('mode-reglement-list')

#=========================VUES PRODUITS ET SERVICES =========================== 
@login_required
def ajouter_article(request):
    """Vue pour ajouter un produit, un service ou une catégorie"""
    initial_produit = {}
    initial_service = {}
    type_element = request.GET.get('type')
    nom = request.GET.get('nom')
    return_to_devis = request.GET.get('return_to_devis', 'false') == 'true'

    if type_element == 'produit' and nom:
        initial_produit = {'nom_produit': nom}
    elif type_element == 'service' and nom:
        initial_service = {'nom_service': nom}

    produit_form = ProduitForm(initial=initial_produit)
    service_form = ServiceForm(initial=initial_service)
    category_form = CategoryForm()

    if request.method == 'POST':
        type_element = request.POST.get('type_element')
        logger.debug(f"Type element: {type_element}")
        logger.debug(f"POST data: {request.POST}")

        if type_element == 'produit':
            produit_form = ProduitForm(request.POST)
            if produit_form.is_valid():
                produit_form.save()
                messages.success(request, "Produit ajouté avec succès !")
                if request.POST.get('return_to_devis') == 'true':
                    request.session['devis_form_data'] = request.session.get('devis_form_data', {})
                    return redirect('add-devis')
                return redirect('gerer-article')
            else:
                logger.error(f"Erreurs produit_form: {produit_form.errors}")
                messages.error(request, "Erreur dans le formulaire de produit. Veuillez vérifier les champs.")

        elif type_element == 'service':
            service_form = ServiceForm(request.POST)
            if service_form.is_valid():
                service_form.save()
                messages.success(request, "Service ajouté avec succès !")
                if request.POST.get('return_to_devis') == 'true':
                    request.session['devis_form_data'] = request.session.get('devis_form_data', {})
                    return redirect('add-devis')
                return redirect('ajouter_element')
        elif type_element == 'category':
            category_form = CategoryForm(request.POST)
            if category_form.is_valid():
                category_form.save()
                messages.success(request, "Catégorie ajoutée avec succès !")
                return redirect('ajouter_element')
            else:
                logger.error(f"Erreurs category_form: {category_form.errors}")
                messages.error(request, "Erreur dans le formulaire de catégorie. Veuillez vérifier les champs.")

    return render(request, 'facture/add_product_service.html', {
        'produit_form': produit_form,
        'service_form': service_form,
        'category_form': category_form,
        'type_element': type_element,
        'return_to_devis': return_to_devis,
    })

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
    """Recherche dynamique de produits"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    try:
        produits = Produit.objects.filter(
            Q(nom_produit__icontains=query)
        ).select_related('category')[:10]  # Optimisation avec select_related

        results = []
        for produit in produits:
            results.append({
                'id': produit.id,
                'nom': produit.nom_produit,
                'description': produit.description_produit or '',
                'prix': float(produit.prix_unitaire_produit),
                'category': produit.category.id if produit.category else None
            })
        
        return JsonResponse(results, safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def search_services(request):
    """Recherche dynamique de services"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    try:
        services = Service.objects.filter(
            Q(nom_service__icontains=query)
        )[:10]

        results = []
        for service in services:
            results.append({
                'id': service.id,
                'nom': service.nom_service,
                'description': service.description_service or '',
                'montant': float(service.montant_du_service),
            })
        
        return JsonResponse(results, safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_prices(request):
    """Récupère tous les prix des produits et services"""
    try:
        produits = {
            str(p.id): float(p.prix_unitaire_produit) 
            for p in Produit.objects.all()
        }
        
        services = {
            str(s.id): float(s.montant_du_service) 
            for s in Service.objects.all()
        }
        
        return JsonResponse({
            'produits': produits, 
            'services': services
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 



#===============================================PDF Generation ==================
def generer_pdf_document(document, document_type):
    """
    Générer un PDF unifié pour un DEVIS ou une FACTURE
    document_type: 'devis' ou 'facture'
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        topMargin=20*mm, 
        bottomMargin=20*mm,
        leftMargin=20*mm,
        rightMargin=20*mm
    )
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#1f4788'),
        alignment=TA_CENTER
    )
    total_style = ParagraphStyle(
        'Total', 
        parent=styles['Heading1'], 
        fontSize=15, 
        alignment=TA_RIGHT
    )
    
    # Style pour les sections alignées à gauche
    left_aligned_style = ParagraphStyle(
        'LeftAligned',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        leftIndent=0    )
    
    # =====================================
    # 1. TITRE
    # =====================================
    titre = f"{'DEVIS' if document_type == 'devis' else 'FACTURE'} N° {document.numero}"
    elements.append(Paragraph(titre, title_style))
    elements.append(Spacer(1, 12))
    
    # Référence devis (SEULEMENT pour factures)
    if document_type == 'facture' and document.devis_origine:
        elements.append(Paragraph(
            f"<i>Référence devis: {document.devis_origine.numero}</i>", 
            styles['Normal']
        ))
        elements.append(Spacer(1, 12))
    
    # =====================================
    # 2. INFORMATIONS CLIENT (aligné à gauche)
    # =====================================
    client_lines = []
    if document.client.nom:
        client_lines.append(f"<b>Client:</b> {document.client.nom}")
    if document.client.email:
        client_lines.append(f"<b>Email:</b> {document.client.email}")
    if document.client.telephone:
        client_lines.append(f"<b>Téléphone:</b> {document.client.telephone}")

    adresse = document.client.adresse or ""
    ville = document.client.ville or ""
    if adresse or ville:
        client_lines.append(f"<b>Adresse:</b> {adresse}, {ville}".strip(" ,"))

    client_lines.append(f"<b>Date:</b> {document.date_creation.strftime('%d/%m/%Y')}")

    client_info = "<br/>".join(client_lines)
    client_paragraph = Paragraph(client_info, left_aligned_style)
    
    elements.append(client_paragraph)
    elements.append(Spacer(1, 20))
    
    # =====================================
    # 3. TABLEAU PRODUITS
    # =====================================
    if hasattr(document, 'produits') and document.produits.exists():
        data = [['Produit', 'Description', 'Prix Unit.', 'Qté', 'Total']]
        
        # Récupérer les produits avec leurs quantités/remises
        if document_type == 'devis':
            produits_rel = document.produitdevis_set.all()
        else:
            produits_rel = document.produitfacturation_set.all()
            
        for prod_rel in produits_rel:
            total = prod_rel.get_total()
            data.append([
                prod_rel.produit.nom_produit,
                (prod_rel.produit.description_produit[:30] + '...') 
                if len(prod_rel.produit.description_produit) > 30 
                else prod_rel.produit.description_produit,
                f'{prod_rel.produit.prix_unitaire_produit:.2f} FCFA',
                str(prod_rel.quantite),
                f'{total:.2f} FCFA'
            ])
        
        table = Table(data, colWidths=[60*mm, 60*mm, 30*mm, 20*mm, 30*mm])
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
    
    # =====================================
    # 4. TABLEAU SERVICES
    # =====================================
    if hasattr(document, 'services') and document.services.exists():
        data = [['Service', 'Description', 'Montant']]
        
        # Récupérer les services
        if document_type == 'devis':
            services_rel = document.servicedevis_set.all()
        else:
            services_rel = document.servicefacturation_set.all()
            
        for serv_rel in services_rel:
            data.append([
                serv_rel.service.nom_service,
                (serv_rel.service.description_service[:50] + '...') 
                if len(serv_rel.service.description_service) > 50 
                else serv_rel.service.description_service,
                f'{serv_rel.service.montant_du_service:.2f} FCFA'
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
    
    # =====================================
    # 5. TOTAUX
    # =====================================
    taux_tva = document.taux_tva or 18
    elements.append(Paragraph(
        f"<b>Total HT: {document.total_net_ht:.2f} FCFA</b>", 
        total_style
    ))
    elements.append(Paragraph(
        f"<b>TVA ({taux_tva}%): {document.total_tva:.2f} FCFA</b>", 
        total_style
    ))
    elements.append(Paragraph(
        f"<b>TOTAL TTC: {document.total_ttc:.2f} FCFA</b>", 
        total_style
    ))
    
    # Accompte et solde (SEULEMENT pour factures)
    if document_type == 'facture':
        if document.montant_accompte > 0:
            elements.append(Paragraph(
                f"<b>Accompte: {document.montant_accompte:.2f} FCFA</b>", 
                total_style
            ))
        elements.append(Paragraph(
            f"<b>Solde dû: {document.solde_du:.2f} FCFA</b>", 
            total_style
        ))
    
    elements.append(Spacer(1, 20))
    
    # =====================================
    # 6. STATUT (aligné à gauche)
    # =====================================
    if document_type == 'devis':
        statut_dict = dict(Devis.STATUT_CHOICES)
    else:
        statut_dict = dict(Facturation.STATUT_CHOICES)
    
    statut_paragraph = Paragraph(
        f"<b>Statut:</b> {statut_dict.get(document.statut, 'Inconnu')}", 
        left_aligned_style
    )
    elements.append(statut_paragraph)
    
    # =====================================
    # 7. COMMENTAIRES (aligné à gauche)
    # =====================================
    if document.commentaire:
        elements.append(Spacer(1, 20))
        commentaire_title = ParagraphStyle(
            'CommentaireTitle',
            parent=styles['Heading2'],
            alignment=TA_LEFT,
            leftIndent=0
        )
        elements.append(Paragraph("<b>Commentaires:</b>", commentaire_title))
        elements.append(Paragraph(document.commentaire, left_aligned_style))
    
    # =====================================
    # 8. MODALITÉS DE PAIEMENT (aligné à gauche)
    # =====================================
    elements.append(Spacer(1, 30))
    modalite_title = ParagraphStyle(
        'ModaliteTitle',
        parent=styles['Heading3'],
        alignment=TA_LEFT,
        leftIndent=0
    )
    elements.append(Paragraph("<b>Modalités de paiement:</b>", modalite_title))
    
    # Récupérer les modes de règlement actifs
    modes_reglement = ModeReglement.objects.filter(est_actif=True)
    if modes_reglement.exists():
        for mode in modes_reglement:
            mode_paragraph = Paragraph(
                f"• {mode.nom}" + (f" - {mode.description}" if mode.description else ""), 
                left_aligned_style
            )
            elements.append(mode_paragraph)
    else:
        elements.append(Paragraph(
            "Paiement à 30 jours date de facture", 
            left_aligned_style
        ))
    
    # =====================================
    # 9. CONSTRUCTION PDF
    # =====================================
    doc.build(elements)
    buffer.seek(0)
    return buffer


@login_required
def telecharger_pdf_document(request, document_type, document_id):
    """Télécharger le PDF d'un document (devis/facture)"""
    if document_type == 'devis':
        document = get_object_or_404(Devis, id=document_id)
    else:
        document = get_object_or_404(Facturation, id=document_id)
    
    # Générer le PDF
    pdf_buffer = generer_pdf_document(document, document_type)
    
    # Préparer la réponse HTTP
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    filename = f"{document_type}_{document.numero}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
def envoyer_document_email(request, document_type, document_id):
    """
    Envoyer un DEVIS ou FACTURE par email
    document_type: 'devis' ou 'facture'
    """
    # Récupérer le document
    if document_type == 'devis':
        document = get_object_or_404(Devis, id=document_id)
    else:
        document = get_object_or_404(Facturation, id=document_id)
    
    # Vérifier l'email du client
    if not document.client.email:
        messages.error(request, "L'email du client est manquant.")
        return redirect('document-detail', document_type=document_type, document_id=document.id)
    
    try:
        # Générer le PDF avec la fonction unifiée
        pdf_buffer = generer_pdf_document(document, document_type)
        
        # =====================================
        # SUJET ADAPTATIF
        # =====================================
        subject = f"{'Devis' if document_type == 'devis' else 'Facture'} N°{document.numero} - {document.client.nom}"
        
        # =====================================
        # MESSAGE ADAPTATIF
        # =====================================
        user_name = request.user.get_full_name() or request.user.username
        
        if document_type == 'devis':
            message = f"""Bonjour {document.client.nom},

Veuillez trouver ci-joint le **DEVIS N°{document.numero}** comme convenu.

✦ **Validité** : jusqu'au {document.date_validite.strftime('%d/%m/%Y')}
✦ **Montant total** : {document.total_ttc:,.2f} FCFA
✦ **TVA** : {document.taux_tva or 18:.1f}%

Pour accepter ce devis, merci de me le retourner signé ou de me confirmer par email.

N'hésitez pas à me contacter pour toute question.

Cordialement,  
{user_name}
---
*Ce message a été envoyé automatiquement"""
            
        else:  # Facture
            solde = document.solde_du
            statut = dict(Facturation.STATUT_CHOICES).get(document.statut, 'En attente')
            
            message = f"""Bonjour {document.client.nom},

Veuillez trouver ci-joint la **FACTURE N°{document.numero}**.

📋 **Détails importants** :
✦ **Montant total TTC** : {document.total_ttc:,.2f} FCFA
✦ **Accompte versé** : {document.montant_accompte:,.2f} FCFA
✦ **Solde à payer** : {solde:,.2f} FCFA
✦ **Statut** : {statut}
✦ **Date d'émission** : {document.date_creation.strftime('%d/%m/%Y')}

💳 **Modalités de paiement** :
• À réception de la facture
• IBAN : {request.user.profile.company_iban if hasattr(request.user, 'profile') and request.user.profile.company_iban else 'Non spécifié'}

Merci de procéder au règlement dans les plus brefs délais.

Cordialement,  
{user_name}
---
*Ce message a été envoyé automatiquement"""
        
        # =====================================
        # ENVOI EMAIL
        # =====================================
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL or request.user.email,
            to=[document.client.email],
        )
        
        # Joindre le PDF
        filename = f"{document_type}_{document.numero}.pdf"
        email.attach(filename, pdf_buffer.getvalue(), 'application/pdf')
        
        # Envoyer
        email.send()
        
        # Message de succès ADAPTATIF
        success_msg = f"Le {'devis' if document_type == 'devis' else 'facture'} a été envoyé avec succès à {document.client.email}"
        messages.success(request, success_msg)
        
    except Exception as e:
        error_msg = f"Une erreur est survenue lors de l'envoi : {str(e)}"
        messages.error(request, error_msg)
    
    # Redirection vers la vue unifiée
    return redirect('document-detail', document_type=document_type, document_id=document.id)



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
    aujourd_hui = timezone.now().date()
    debut_mois = aujourd_hui.replace(day=1)

    # CA du mois courant
    ca_mois_courant = Facturation.objects.filter(
        date_creation__date__gte=debut_mois,
        statut=Facturation.STATUT_PAYE
    ).aggregate(total=Sum('total_ttc'))['total'] or Decimal('0.00')

    # ENCAISSEMENTS EN ATTENTE (solde réel recalculé)
    factures_en_attente = Facturation.objects.filter(
        statut=Facturation.STATUT_EN_ATTENTE
    ).annotate(
        total_reglements=Coalesce(
            Subquery(
                Reglement.objects.filter(facture_id=OuterRef('pk'))
                .values('facture_id')
                .annotate(total=Sum('montant_reglement'))
                .values('total')[:1]
            ),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        ),
        solde_calcule=F('net_a_payer') - F('montant_accompte') - F('total_reglements'),
        solde_final=Coalesce(F('solde_calcule'), Value(Decimal('0.00')), output_field=DecimalField(max_digits=14, decimal_places=2))
    ).aggregate(total=Sum('solde_final'))['total'] or Decimal('0.00')

    nb_clients = Client.objects.count()
    nb_factures_mois = Facturation.objects.filter(date_creation__date__gte=debut_mois).count()

    six_mois_avant = aujourd_hui - timedelta(days=180)
    evolution_ca = Facturation.objects.filter(
        statut=Facturation.STATUT_PAYE,
        date_creation__date__gte=six_mois_avant
    ).annotate(mois=TruncMonth('date_creation')
    ).values('mois').annotate(total=Sum('total_ttc')).order_by('mois')

    context = {
        'ca_mois_courant': ca_mois_courant,
        'factures_en_attente': factures_en_attente,
        'nb_clients': nb_clients,
        'nb_factures_mois': nb_factures_mois,
        'evolution_ca': list(evolution_ca)
    }
    return render(request, 'facture/stat.html', context)


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
        
        # CORRECTION ICI : Gérer correctement les valeurs nulles
        repartition_type_client = Client.objects.values('client_type').annotate(
            count=Count('id')
        ).order_by('client_type')
        
        # Créer un dictionnaire avec des clés propres
        type_client_data = {}
        for item in repartition_type_client:
            client_type = item['client_type']
            if client_type:
                type_client_data[client_type] = item['count']
            else:
                # Regrouper les valeurs nulles/vides sous "Non spécifié"
                type_client_data['Non spécifié'] = type_client_data.get('Non spécifié', 0) + item['count']
        
        # S'assurer qu'il y a toujours au moins des données par défaut
        if not type_client_data:
            type_client_data = {'Individu': 0, 'Entreprise': 0}
        
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
        
        # Statistiques devis
        devis_queryset = Devis.objects.filter(**devis_date_filter)

        total_devis = devis_queryset.count()
        devis_en_attente = devis_queryset.filter(statut=Devis.STATUT_ATTENTE).count()
        devis_acceptes = devis_queryset.filter(statut=Devis.STATUT_ACCEPTE).count()
        devis_refuses = devis_queryset.filter(statut=Devis.STATUT_REFUSE).count()
        devis_transformes = devis_queryset.filter(statut=Devis.STATUT_TRANSFORME_FACTURE).count()

        # CORRECTION : Le taux d'acceptation inclut les devis acceptés ET transformés
        taux_acceptation = 0
        if total_devis > 0:
            devis_acceptes_total = devis_acceptes + devis_transformes
            taux_acceptation = round((devis_acceptes_total / total_devis) * 100, 1)
        
        # === TOP 10 PRODUITS LES PLUS VENDUS (en quantité) ===
        top_produits = ProduitFacturation.objects.filter(
            facture__statut=Facturation.STATUT_PAYE
        ).values(
            'produit__nom_produit'
        ).annotate(
            quantite_totale=Sum('quantite'),
            chiffre_affaires=Sum('total')
        ).order_by('-quantite_totale')[:10]

        top_produits_list = [
            {
                'nom': item['produit__nom_produit'] or 'Produit inconnu',
                'quantite': item['quantite_totale'] or 0,
                'chiffreAffaires': float(item['chiffre_affaires'] or 0)
            }
            for item in top_produits
        ]

        # === TOP 10 SERVICES LES PLUS DEMANDÉS (en montant) ===
        top_services = ServiceFacturation.objects.filter(
            facture__statut=Facturation.STATUT_PAYE
        ).values(
            'service__nom_service'
        ).annotate(
            nombre_commandes=Count('id'),
            montant_total=Sum('service__montant_du_service')
        ).order_by('-montant_total')[:10]

        top_services_list = [
            {
                'nom': item['service__nom_service'] or 'Service inconnu',
                'nombreCommandes': item['nombre_commandes'],
                'montant': float(item['montant_total'] or 0)
            }
            for item in top_services
        ]
        
        # Évolution CA sur les 12 derniers mois
        end_date = timezone.now().date()
        start_date = end_date - relativedelta(months=12)

        evolution_ca = Facturation.objects.filter(
            statut=Facturation.STATUT_PAYE,
            date_creation__date__gte=start_date,
            date_creation__date__lte=end_date
        ).annotate(
            mois=TruncMonth('date_creation')
        ).values('mois').annotate(
            total=Sum('total_ttc')
        ).order_by('mois')

        ca_dict = {item['mois'].strftime('%Y-%m'): float(item['total'] or 0) for item in evolution_ca}

        mois_labels = []
        ca_mensuel = []
        current = end_date.replace(day=1)
        for _ in range(12):
            key = current.strftime('%Y-%m')
            mois_labels.append(current.strftime('%b %Y'))
            ca_mensuel.append(ca_dict.get(key, 0))
            current -= relativedelta(months=1)

        mois_labels.reverse()
        ca_mensuel.reverse()
        
        statistiques_data = {
            'clients': {
                'total': total_clients,
                'repartitionTypeClient': type_client_data,  # CORRECTION : camelCase
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
                'topVendus': top_produits_list
            },
            'services': {
                'topDemandes': top_services_list
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
    ).select_related('client','save_by').order_by('-date_creation')

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
    ).select_related('client','save_by').order_by('-date_creation')

    context = {
        'factures': factures,
        'titre':'Factures payées',
        'statuts': Facturation.STATUT_CHOICES
    }
    return render(request, 'facture/facture_paye.html', context)


