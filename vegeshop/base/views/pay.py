from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import serializers
from django.shortcuts import redirect
from django.views.generic import View, TemplateView
from django.conf import settings
from django.contrib import messages
from base.models import Item, Order

import json
import stripe


stripe.api_key = settings.STRIPE_API_SECRET_KEY
tax_rate = stripe.TaxRate.create(
    display_name='消費税',
    description='消費税',
    country='JP',
    jurisdiction='JP',
    percentage=settings.TAX_RATE * 100,
    inclusive=False,
)


class PaySuccessView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/success.html'

    def get(self, request, *args, **kwargs):
        order_id = request.GET.get('order_id')
        orders = Order.objects.filter(user=request.user, id=order_id)

        if len(orders) != 1:
            return super().get(request, *args, **kwargs)

        order = orders[0]

        if order.is_confirmed:
            return super().get(request, *args, **kwargs)

        order.is_confirmed = True
        order.save()

        if 'cart' in request.session:
            del request.session['cart']

        return super().get(request, *args, **kwargs)


class PayCancelView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/cancel.html'

    def get(self, request, *args, **kwargs):
        order_id = request.GET.get('order_id')
        orders = Order.objects.filter(user=request.user, id=order_id)

        if len(orders) != 1:
            return super().get(request, *args, **kwargs)

        order = orders[0]

        for elem in json.loads(order.items):
            item = Item.objects.get(pk=elem['pk'])
            item.sold_count -= elem['quantity']
            item.stock += elem['quantity']
            item.save()

        if not order.is_confirmed:
            order.delete()

        return super().get(request, *args, **kwargs)


def create_line_item(unit_amount, name, quantity):
    return {
        'price_data': {
            'currency': 'JPY',
            'unit_amount': unit_amount,
            'product_data': {'name': name, }
        },
        'quantity': quantity,
        'tax_rates': [tax_rate.id]
    }


def check_profile_filled(profile):
    if profile.name is None or profile.name == '':
        return False
    elif profile.zipcode is None or profile.zipcode == '':
        return False
    elif profile.prefecture is None or profile.prefecture == '':
        return False
    elif profile.city is None or profile.city == '':
        return False
    elif profile.address1 is None or profile.address1 == '':
        return False
    return True


class PayWithStripe(LoginRequiredMixin, View):

    def post(self, request, *args, **kwargs):
        if not check_profile_filled(request.user.profile):
            messages.error(request, '配送のためプロフィールを埋めてください。')
            return redirect('/profile/')

        cart = request.session.get('cart', None)
        if cart is None or len(cart) == 0:
            messages.error(request, 'カートが空です。')
            return redirect('/')

        items = []
        line_items = []
        for item_pk, quantity in cart['items'].items():
            item = Item.objects.get(pk=item_pk)
            line_item = create_line_item(
                item.price, item.name, quantity)
            line_items.append(line_item)

            items.append({
                'pk': item.pk,
                'name': item.name,
                'image': str(item.image),
                'price': item.price,
                'quantity': quantity,
            })

            item.stock -= quantity
            item.sold_count += quantity
            item.save()

        order = Order.objects.create(
            user=request.user,
            uid=request.user.pk,
            items=json.dumps(items),
            shipping=serializers.serialize("json", [request.user.profile]),
            amount=cart["total"],
            tax_included=cart["tax_included_total"]
        )

        checkout_session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=f'{settings.MY_URL}/pay/success/?order_id={order.pk}',
            cancel_url=f'{settings.MY_URL}/pay/cancel/?order_id={order.pk}',

        )
        return redirect(checkout_session.url)
