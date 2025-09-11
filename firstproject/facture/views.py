from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.views import View
from django.db import transaction
from django.utils import timezone  # Ajouté : manquant pour timezone.now()
from django.forms import formset_factory
from decimal import Decimal
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from facture.forms import *  # Assumé que ClientForm est ici
from .models import *
from utils import paginate_queryset  # Assumé défini

# Classe HomeView corrigée : suppression de post redondant
class HomeView(View):
    template_name = 'facture/index.html'

    def get(self, request, *args, **kwargs):
        factures = Facturation.objects.select_related('clientFacture', 'factureSaveBy').all()
        devis = Devis.objects.select_related('clientDevis', 'devisSaveBys').all()
        context = {
            'factures': factures,
            'devis': devis
        }
        return render(request, self.template_name, context)

# addCustomerView : inchangé, mais validé
class addCustomerView(View):
    template_name = 'facture/ajouterClient.html'

    def get(self, request, *args, **kwargs):
        form = ClientForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.clientSaveBy = request.user
            client.save()
            messages.success(request, 'Client ajouté avec succès')
            return redirect('liste-clients')
        return render(request, self.template_name, {'form': form})

# addFactureView : optimisé avec Decimal pour totaux
class addFactureView(View):
    template_name = 'facture/add_facture.html'

    def get_context(self):
        clients = Client.objects.select_related('clientSaveBy').all()
        return {'clients': clients}

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context())
    
    def post(self, request, *args, **kwargs):
        try:
            client_id = request.POST.get('client')
            total_general = request.POST.get('total_general')
            commentaire_facture = request.POST.get('commentaireFacture')
            statut_facture = request.POST.get('statut_facture')
            
            if not client_id:
                messages.error(request, "Le client est obligatoire.")
                return render(request, self.template_name, self.get_context())
            
            try:
                client = Client.objects.get(id=client_id)
            except Client.DoesNotExist:
                messages.error(request, "Client introuvable.")
                return render(request, self.template_name, self.get_context())
            
            total_facture = Decimal(total_general) if total_general else Decimal('0.00')
            
            facture = Facturation.objects.create(
                clientFacture=client,
                factureSaveBy=request.user,
                totalFacture=total_facture,
                statutFacture=statut_facture,
                commentaireFacture=commentaire_facture or ''
                # Pas besoin de numeroFacture ici, géré par Facturation.save()
            )
            
            produits_items = []
            i = 0
            while f'produits[{i}][nom]' in request.POST:
                nom = request.POST.get(f'produits[{i}][nom]')
                quantity = request.POST.get(f'produits[{i}][quantity]')
                unit_price = request.POST.get(f'produits[{i}][unit_price]')
                total_price = request.POST.get(f'produits[{i}][total_price]')
                
                if nom and quantity and unit_price:
                    produit = Produit(
                        factureProduit=facture,
                        nomProduit=nom,
                        quantity=int(quantity),
                        prixUnitaireProduit=Decimal(unit_price),
                        total=Decimal(total_price) if total_price else Decimal('0.00'),
                        devisProduit=None
                    )
                    produits_items.append(produit)
                i += 1
            
            services_items = []
            i = 0
            while f'services[{i}][nom]' in request.POST:
                nom = request.POST.get(f'services[{i}][nom]')
                montant = request.POST.get(f'services[{i}][montant]')
                
                if nom and montant:
                    service = Service(
                        factureService=facture,
                        nomService=nom,
                        montantDuService=Decimal(montant),
                        devisService=None
                    )
                    services_items.append(service)
                i += 1
            
            if produits_items:
                Produit.objects.bulk_create(produits_items)
            if services_items:
                Service.objects.bulk_create(services_items)
            
            if not produits_items and not services_items:
                facture.delete()
                messages.error(request, "Une facture doit contenir au moins un produit ou un service.")
                return render(request, self.template_name, self.get_context())
            
            messages.success(request, f'Facture {facture.numeroFacture} créée avec succès !')
            return redirect('liste-facture')
            
        except ValueError as e:
            messages.error(request, f"Erreur de format dans les données numériques : {str(e)}")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement : {str(e)}")
        
        return render(request, self.template_name, self.get_context())
    

class addDevisView(View):
    template_name = 'facture/add_devis.html'
 
    def get_context(self):
        clients = Client.objects.all()
        return {'clients': clients}

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context())

    def post(self, request, *args, **kwargs):
        try:
            client_id = request.POST.get('client')
            total_general = request.POST.get('total_general')
            commentaire_devis = request.POST.get('commentaireDevis')
            statut_devis = request.POST.get('statut_devis')
            
            if not client_id:
                messages.error(request, "Le client est obligatoire.")
                return render(request, self.template_name, self.get_context())
            
            client = get_object_or_404(Client, id=client_id)
            
            devis = Devis.objects.create(
                clientDevis=client,
                devisSaveBy=request.user,
                totalDevis=Decimal(total_general) if total_general else Decimal('0.00'),
                statutDevis=statut_devis,
                commentaireDevis=commentaire_devis or ''
                # numeroDevis géré par Devis.save()
            )
            
            produits_items = []
            i = 0
            while f'produits[{i}][nom]' in request.POST:
                nom = request.POST.get(f'produits[{i}][nom]')
                quantity = request.POST.get(f'produits[{i}][quantity]')
                unit_price = request.POST.get(f'produits[{i}][unit_price]')
                total_price = request.POST.get(f'produits[{i}][total_price]')
                
                if nom and quantity and unit_price:
                    produit = Produit(
                        devisProduit=devis,
                        nomProduit=nom,
                        quantity=int(quantity),
                        prixUnitaireProduit=Decimal(unit_price),
                        total=Decimal(total_price) if total_price else Decimal('0.00'),
                        factureProduit=None
                    )
                    produits_items.append(produit)
                i += 1
            
            services_items = []
            i = 0
            while f'services[{i}][nom]' in request.POST:
                nom = request.POST.get(f'services[{i}][nom]')
                montant = request.POST.get(f'services[{i}][montant]')
                
                if nom and montant:
                    service = Service(
                        devisService=devis,
                        nomService=nom,
                        montantDuService=Decimal(montant),
                        factureService=None
                    )
                    services_items.append(service)
                i += 1
            
            if produits_items:
                Produit.objects.bulk_create(produits_items)
            if services_items:
                Service.objects.bulk_create(services_items)
            
            if not produits_items and not services_items:
                devis.delete()
                messages.error(request, "Un devis doit contenir au moins un produit ou un service.")
                return render(request, self.template_name, self.get_context())
            
            messages.success(request, f"Devis {devis.numeroDevis} créé avec succès !")
            return redirect('liste-devis')
            
        except ValueError as e:
            messages.error(request, f"Erreur de format dans les données numériques : {str(e)}")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement : {str(e)}")
        
        return render(request, self.template_name, self.get_context()) 

# listClient : inchangé
def listClient(request):
    clients = Client.objects.all()
    return render(request, 'facture/listClient.html', {"clients": clients})

# detailsClient : utilisation de get_object_or_404 pour sécurité
def detailsClient(request, id):
    client = get_object_or_404(Client, id=id)
    return render(request, 'facture/detailsClient.html', {'client': client})

# listfacture : ajout de timezone import (déjà fait)
def listfacture(request):
    #modification de facture
    if request.method == 'POST' and request.POST.get('id_modified'):
        try:
            facture = get_object_or_404(Facturation, id=request.POST.get('id_modified'))
            statut = int(request.POST.get('modified'))
            if statut in [Facturation.STATUT_PAYE, Facturation.STATUT_EN_ATTENTE, Facturation.STATUT_ANNULE]:
                facture.statutFacture = statut
                facture.paid = (statut == Facturation.STATUT_PAYE)
                facture.lastUpdateFacture = timezone.now()
                facture.save()
                messages.success(request, "Facture modifiée avec succès.")
            else:
                messages.error(request, "Statut invalide.")
        except (Facturation.DoesNotExist, ValueError):
            messages.error(request, "Erreur lors de la modification.")
        return redirect('liste-facture')
    #suppression de facture
    if request.method == 'POST' and request.POST.get('id_supprimer'):
        try:
            facture = get_object_or_404(Facturation,id=request.POST.get('id_supprimer'))
            facture.delete()
            messages.success(request,"Supprimée avec succès.")
        except Exception as e:
            messages.error(request, f"Erreur suivante {e} ")
    factures = Facturation.objects.all().order_by('-dateCreationFacturation')
    paginated_factures = paginate_queryset(request, factures, per_page=10)
    context = {'factures': paginated_factures}
    return render(request, 'facture/listeFacture.html', context)

# liste des devis 
def liste_devis(request):
    if request.method == 'POST' and request.POST.get('id_modified'):
        try:
            devis_to_update = get_object_or_404(Devis, id=request.POST.get('id_modified'))
            statut = int(request.POST.get('modified'))
            if statut in [Devis.STATUT_ACCEPTE_DEVIS, Devis.STATUT_ATTENTE_DEVIS, Devis.STATUT_REFUSE_DEVIS]:
                devis_to_update.statutDevis = statut
                devis_to_update.lastUpdateDevis = timezone.now()
                devis_to_update.save()
                
                messages.success(request, "Devis modifié avec succès.")
            else:
                messages.error(request, "Statut invalide.")
                
        except (Devis.DoesNotExist, ValueError):
            messages.error(request, "Erreur lors de la modification")
            
        return redirect('liste-devis')
    
    # Récupération de tous les devis
    devis_lists = Devis.objects.all().order_by('-dateCreationDevis')
    
    # Pagination
    paginated_devis = paginate_queryset(request, devis_lists, per_page=10)
    context = {'devis_lists': paginated_devis}
    return render(request, 'facture/liste_devis.html', context)

# detailsFacture : utilisation de get_object_or_404
def detailsFacture(request, facture_id):
    facture = get_object_or_404(Facturation, id=facture_id)
   
    return render(request, 'facture/details_devis_facture.html', {'facture': facture})


# detailsdevis
def details_devis(request,devis_id):
    devis = get_object_or_404(Devis, id=devis_id)
    return render (request, 'facture/details_devis_facture.html' , {'devis':devis})

# Suppression de addClient (redondant avec addCustomerView)

# changeClient : correction de is_valid()
def changeClient(request, id):
    client = get_object_or_404(Client, id=id)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():  # Correction : ajout des parenthèses
            form.save()
            return redirect('details-clients', client.id)
    else:
        form = ClientForm(instance=client)
    return render(request, 'facture/client_update.html', {'form': form})


# modification facture 
def modifier_facture(request, facture_id):
    facture = get_object_or_404(Facturation, id=facture_id)
    clients = Client.objects.all()

    if request.method == 'POST':
        client_id = request.POST.get('client')
        statut_facture = request.POST.get('statut_facture')
        commentaire_facture = request.POST.get('commentaireFacture', '')
        total_general = request.POST.get('total_general', 0)

        # --- Mise à jour du client et du statut ---
        if client_id:
            facture.clientFacture_id = client_id
        if statut_facture:
            facture.statutFacture = int(statut_facture)
        facture.commentaireFacture = commentaire_facture
        facture.totalFacture = Decimal(total_general) if total_general else Decimal('O.00')
        facture.save()

        # --- Mise à jour des produits ---
        facture.produit_set.all().delete()
        produits = request.POST.getlist('produits')
        # Mais pour la structure "produits[0][nom]" etc, on parcourt par index:
        i = 0
        while f'produits[{i}][nom]' in request.POST:
            nom = request.POST.get(f'produits[{i}][nom]')
            quantity = request.POST.get(f'produits[{i}][quantity]', 1)
            unit_price = request.POST.get(f'produits[{i}][unit_price]', 0)
            total_price = request.POST.get(f'produits[{i}][total_price]', 0)
            if nom and quantity and unit_price:
                produit= Produit(
                    factureProduit=facture,
                    nomProduit=nom,
                    quantity=int(quantity),
                    prixUnitaireProduit=Decimal(unit_price),
                    total = Decimal(total_price) if total_price else Decimal('0.00'),
                    devisProduit=None
                )
                produit.save()
            i += 1

        # --- Mise à jour des services ---
        facture.service_set.all().delete()
        j = 0
        while f'services[{j}][nom]' in request.POST:
            nom = request.POST.get(f'services[{j}][nom]')
            montant = request.POST.get(f'services[{j}][montant]', 0)
            if nom:
                service=Service(
                    factureService=facture,
                    nomService=nom,
                    montantDuService=montant
                )
                service.save()
            j += 1

        messages.success(request, "Facture modifiée avec succès.")
        return redirect('details-facture', facture_id)

    return render(request, 'facture/update_facture.html', {
        'facture': facture,
        'clients': clients,
    })

# deleteClient : inchangé, mais get_object_or_404
def deleteClient(request, id):
    client = get_object_or_404(Client, id=id)
    if request.method == 'POST':
        client.delete()
        return redirect('liste-clients')
    return render(request, 'facture/client_delete.html', {'client': client})

# transformer_devis_en_facture : inchangé
@login_required
def transformer_devis_en_facture(request, devis_id):
    devis = get_object_or_404(Devis, id=devis_id)
    
    if request.method == 'POST':
        try:
            if not devis.peut_etre_transforme():
                messages.error(request, "Ce devis ne peut pas être transformé en facture.")
                return redirect('devis_detail', devis_id=devis_id)
            
            facture = devis.transformer_en_facture(request.user)
            messages.success(request, f"Le devis {devis.numeroDevis} a été transformé en facture {facture.numeroFacture} avec succès.")
            
            if request.POST.get('envoyer_email'):
                envoyer_facture_email(request, facture.id)
            
            return redirect('facture_detail', facture_id=facture.id)
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la transformation : {str(e)}")
            return redirect('devis_detail', devis_id=devis_id)
    
    context = {
        'devis': devis,
        'peut_transformer': devis.peut_etre_transforme()
    }
    return render(request, 'transformer_devis.html', context)

# valider_devis : inchangé
@login_required
def valider_devis(request, devis_id):
    devis = get_object_or_404(Devis, id=devis_id)
    
    if request.method == 'POST':
        devis.statutDevis = Devis.STATUT_ACCEPTE_DEVIS
        devis.lastUpdateDevis = timezone.now()
        devis.save()
        
        messages.success(request, f"Le devis {devis.numeroDevis} a été accepté.")
        
        if request.POST.get('transformer_auto'):
            try:
                facture = devis.transformer_en_facture(request.user)
                messages.success(request, f"Une facture {facture.numeroFacture} a été créée automatiquement.")
                return redirect('facture_detail', facture_id=facture.id)
            except Exception as e:
                messages.warning(request, f"Le devis a été accepté mais n'a pas pu être transformé en facture : {str(e)}")
        
        return redirect('devis_detail', devis_id=devis_id)
    
    return render(request, 'valider_devis.html', {'devis': devis})


# envoyer_devis_email : ajout vérif email
@login_required
def envoyer_devis_email(request, devis_id):
    devis = get_object_or_404(Devis, id=devis_id)
    
    # Vérification de l'email du client
    if not devis.clientDevis.emailClient:
        messages.error(request, "L'email du client est manquant.")
        return redirect('devis-detail', id=devis_id)
    
    try:
        # Génération du PDF
        pdf_buffer = generer_pdf_devis(devis)
        
        # Préparation du contenu de l'email
        subject = f'Devis N°{devis.numeroDevis} - {devis.clientDevis.nomClient}'
        message = f"""Bonjour {devis.clientDevis.nomClient},

Veuillez trouver ci-joint le devis N°{devis.numeroDevis} comme convenu.

Ce devis est valable 30 jours à compter de sa date d'émission.

N'hésitez pas à me contacter pour toute question ou clarification.

Cordialement,
{request.user.get_full_name() or request.user.username}"""

        # Envoi de l'email
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=request.user.email,
            to=[devis.clientDevis.emailClient],
        )
        email.attach(f'Devis_{devis.numeroDevis}.pdf', pdf_buffer.getvalue(), 'application/pdf')
        email.send()
        messages.success(request, "Le devis a été envoyé avec succès.")
    except Exception as e:
        messages.error(request, f"Une erreur est survenue lors de l'envoi du devis : {e}")
    
    return redirect('devis-detail', id=devis_id)

# envoyer_facture_email : ajout vérif email
@login_required
def envoyer_facture_email(request, facture_id):
    facture = get_object_or_404(Facturation, id=facture_id)
    
    if not facture.clientFacture.emailClient:
        messages.error(request, "L'email du client est manquant.")
        return redirect('details-facture', id=facture_id)
    
    try:
        pdf_buffer = generer_pdf_facture(facture)
        
        subject = f'Facture N°{facture.numeroFacture} - {facture.clientFacture.nomClient}'
        message = render_to_string('email/facture_email.html', {
            'facture': facture,
            'client': facture.clientFacture,
            'produits': facture.produit_set.all(),
            'services': facture.service_set.all(),
        })
        
        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [facture.clientFacture.emailClient],
            reply_to=[request.user.email]
        )
        email.attach(f'Facture_{facture.numeroFacture}.pdf', pdf_buffer.getvalue(), 'application/pdf')
        email.send()
        
        messages.success(request, f"La facture a été envoyée avec succès à {facture.clientFacture.emailClient}")
        
    except Exception as e:
        messages.error(request, f"Erreur lors de l'envoi de l'email : {str(e)}")
    
    return redirect('details-facture', id=facture_id)

# generer_pdf_devis : corrigé entièrement
def generer_pdf_devis(devis):
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
    
    # En-tête
    elements.append(Paragraph(f"DEVIS N° {devis.numeroDevis}", title_style))
    elements.append(Spacer(1, 12))
    
    # Informations client
    client_info = f"""
    <b>Client:</b> {devis.clientDevis.nomClient}<br/>
    <b>Email:</b> {devis.clientDevis.emailClient}<br/>
    <b>Téléphone:</b> {devis.clientDevis.telephoneClient}<br/>
    <b>Adresse:</b> {devis.clientDevis.adresseClient}, {devis.clientDevis.villeClient}<br/>
    <b>Date:</b> {devis.dateCreationDevis.strftime('%d/%m/%Y')}
    """
    elements.append(Paragraph(client_info, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Tableau des produits
    if devis.produit_set.exists():
        data = [['Produit', 'Description', 'Prix Unit.', 'Quantité', 'Total']]
        for produit in devis.produit_set.all():
            data.append([
                produit.nomProduit,
                (produit.descriptionProduit[:30] + '...') if len(produit.descriptionProduit) > 30 else produit.descriptionProduit,
                f'{produit.prixUnitaireProduit:.2f} CFA',
                str(produit.quantity),
                f'{produit.get_total:.2f} CFA'
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
    
    # Tableau des services (corrigé : devis au lieu de facture)
    if devis.service_set.exists():
        data = [['Service', 'Description', 'Montant']]
        for service in devis.service_set.all():
            data.append([
                service.nomService,
                (service.descriptionService[:50] + '...') if len(service.descriptionService) > 50 else service.descriptionService,
                f'{service.montantDuService:.2f} CFA'
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
    
    # Total (corrigé : devis.totalDevis)
    total_style = ParagraphStyle(
        'Total',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_RIGHT
    )
    elements.append(Paragraph(f"<b>TOTAL TTC: {devis.totalDevis:.2f} CFA</b>", total_style))
    
    # Commentaires
    if hasattr(devis, 'commentaireDevis') and devis.commentaireDevis:
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("<b>Commentaires:</b>", styles['Heading2']))
        elements.append(Paragraph(devis.commentaireDevis, styles['Normal']))
    
    # Statut (adapté pour devis)
    elements.append(Spacer(1, 20))
    statut_text = dict(getattr(Devis, 'STATUT_CHOICE_DEVIS', {})).get(devis.statutDevis, 'Inconnu')
    elements.append(Paragraph(f"<b>Statut:</b> {statut_text}", styles['Normal']))
    
    # Conditions (adaptées pour devis)
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("<b>Conditions:</b>", styles['Heading3']))
    elements.append(Paragraph("Valable 30 jours", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# generer_pdf_facture : complété et corrigé
def generer_pdf_facture(facture):
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
    
    # En-tête
    elements.append(Paragraph(f"FACTURE N° {facture.numeroFacture}", title_style))
    elements.append(Spacer(1, 12))
    
    # Référence au devis
    if hasattr(facture, 'devis_origine') and facture.devis_origine:
        elements.append(Paragraph(f"<i>Référence devis: {facture.devis_origine.numeroDevis}</i>", styles['Normal']))
        elements.append(Spacer(1, 12))
    
    # Informations client
    client_info = f"""
    <b>Client:</b> {facture.clientFacture.nomClient}<br/>
    <b>Email:</b> {facture.clientFacture.emailClient}<br/>
    <b>Téléphone:</b> {facture.clientFacture.telephoneClient}<br/>
    <b>Adresse:</b> {facture.clientFacture.adresseClient}, {facture.clientFacture.villeClient}<br/>
    <b>Date:</b> {facture.dateCreationFacturation.strftime('%d/%m/%Y')}
    """
    elements.append(Paragraph(client_info, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Tableau des produits
    if facture.produit_set.exists():
        data = [['Produit', 'Description', 'Prix Unit.', 'Quantité', 'Total']]
        for produit in facture.produit_set.all():
            data.append([
                produit.nomProduit,
                (produit.descriptionProduit[:30] + '...') if len(produit.descriptionProduit) > 30 else produit.descriptionProduit,
                f'{produit.prixUnitaireProduit:.2f} CFA',
                str(produit.quantity),
                f'{produit.get_total:.2f} CFA'
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
    if facture.service_set.exists():
        data = [['Service', 'Description', 'Montant']]
        for service in facture.service_set.all():
            data.append([
                service.nomService,
                (service.descriptionService[:50] + '...') if len(service.descriptionService) > 50 else service.descriptionService,
                f'{service.montantDuService:.2f} CFA'
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
    
    # Total
    total_style = ParagraphStyle(
        'Total',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_RIGHT
    )
    elements.append(Paragraph(f"<b>TOTAL TTC: {facture.totalFacture:.2f} CFA</b>", total_style))
    
    # Statut de paiement
    elements.append(Spacer(1, 20))
    statut_text = dict(getattr(Facturation, 'STATUT_CHOICES_FACTURATION', {})).get(facture.statutFacture, 'Inconnu')
    statut_color = colors.green if facture.paid else colors.red
    statut_style = ParagraphStyle(
        'Statut',
        parent=styles['Normal'],
        fontSize=14,
        textColor=statut_color
    )
    elements.append(Paragraph(f"<b>Statut:</b> {statut_text}", statut_style))
    
    # Commentaires
    if facture.commentaireFacture:
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("<b>Commentaires:</b>", styles['Heading2']))
        elements.append(Paragraph(facture.commentaireFacture, styles['Normal']))
    
    # Conditions de paiement
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("<b>Conditions de paiement:</b>", styles['Heading3']))
    elements.append(Paragraph("Paiement à 30 jours date de facture", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# telecharger_pdf_devis : inchangé
@login_required
def telecharger_pdf_devis(request, devis_id):
    devis = get_object_or_404(Devis, id=devis_id)
    pdf_buffer = generer_pdf_devis(devis)
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Devis_{devis.numeroDevis}.pdf"'
    return response

# telecharger_pdf_facture : inchangé
@login_required
def telecharger_pdf_facture(request, facture_id):
    facture = get_object_or_404(Facturation, id=facture_id)
    pdf_buffer = generer_pdf_facture(facture)
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Facture_{facture.numeroFacture}.pdf"'
    return response




# api_transformer_devis : inchangé
@login_required
def api_transformer_devis(request, devis_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        devis = get_object_or_404(Devis, id=devis_id)
        
        if not devis.peut_etre_transforme():
            return JsonResponse({'error': 'Ce devis ne peut pas être transformé en facture'}, status=400)
        
        facture = devis.transformer_en_facture(request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Devis transformé en facture {facture.numeroFacture}',
            'facture_id': facture.id,
            'facture_numero': facture.numeroFacture,
            'redirect_url': f'/factures/{facture.id}/'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# api_valider_devis : suppression du code mal placé
@login_required
def api_valider_devis(request, devis_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        devis = get_object_or_404(Devis, id=devis_id)
        
        devis.statutDevis = Devis.STATUT_ACCEPTE_DEVIS
        devis.lastUpdateDevis = timezone.now()
        devis.save()
        
        response_data = {
            'success': True,
            'message': f'Devis {devis.numeroDevis} accepté',
            'peut_transformer': devis.peut_etre_transforme()
        }
        
        if request.POST.get('transformer_auto') == 'true':
            try:
                facture = devis.transformer_en_facture(request.user)
                response_data['facture_creee'] = True
                response_data['facture_id'] = facture.id
                response_data['facture_numero'] = facture.numeroFacture
            except Exception as e:
                response_data['warning'] = str(e)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)