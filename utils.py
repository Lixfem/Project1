from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

def paginate_queryset(request, queryset, per_page=10):
    paginator = Paginator(queryset, per_page)
    page = request.GET.get('page')
    try:
        paginated_queryset = paginator.page(page)
    except PageNotAnInteger:
        paginated_queryset = paginator.page(1)
    except EmptyPage:
        paginated_queryset = paginator.page(paginator.num_pages)
    return paginated_queryset
    