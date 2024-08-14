from django.conf import settings
from base.models import Item


def base(request):
    items = Item.object.filter(is_published=True)
    return {
        'TITLE': settings.TITLE,
        'ADDITIONAL': items,
        'POPULAR_ITEMS': items.order_by('-sold_count')
    }
