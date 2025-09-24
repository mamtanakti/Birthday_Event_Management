from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from io import BytesIO
import tempfile
from .models import *
from .forms import *
from decimal import Decimal

def home(request):
    categories = Category.objects.all()[:6]
    services = Service.objects.filter(status='active')[:8]
    return render(request, 'home.html', {
        'categories': categories,
        'services': services
    })

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('home')
    else:
        form = UserRegistrationForm()
    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('home')
            else:
                messages.error(request, 'Invalid credentials')
    else:
        form = UserLoginForm()
    return render(request, 'login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

def category_list(request):
    categories = Category.objects.all()
    return render(request, 'categories.html', {'categories': categories})

def service_list(request, category_slug=None):
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        services = Service.objects.filter(category=category, status='active')
    else:
        category = None
        services = Service.objects.filter(status='active')
    
    categories = Category.objects.all()  # For sidebar/filter
    
    return render(request, 'services.html', {
        'services': services,
        'category': category,
        'categories': categories
    })

@login_required
def service_detail(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    return render(request, 'service_detail.html', {'service': service})

@login_required
def add_to_cart(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        service=service,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, f'{service.title} added to cart!')
    return redirect('cart')

@login_required
def cart_view(request):
    cart_items = Cart.objects.filter(user=request.user)
    total = sum(item.service.price * item.quantity for item in cart_items)
    tax_rate = Decimal('0.10')
    tax = (Decimal(total) * tax_rate).quantize(Decimal('0.01')) if total else Decimal('0.00')
    grand_total = (Decimal(total) + tax).quantize(Decimal('0.01')) if total else Decimal('0.00')
    
    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total': total,
        'tax': tax,
        'grand_total': grand_total,
    })

@login_required
def update_cart(request, cart_item_id):
    cart_item = get_object_or_404(Cart, id=cart_item_id, user=request.user)
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
    return redirect('cart')

@login_required
def remove_from_cart(request, cart_item_id):
    cart_item = get_object_or_404(Cart, id=cart_item_id, user=request.user)
    cart_item.delete()
    messages.success(request, 'Item removed from cart!')
    return redirect('cart')

@login_required
def checkout(request):
    cart_items = Cart.objects.filter(user=request.user)
    if not cart_items:
        messages.warning(request, 'Your cart is empty!')
        return redirect('service_list')
    
    total = sum(item.service.price * item.quantity for item in cart_items)
    tax_rate = Decimal('0.10')
    tax = (Decimal(total) * tax_rate).quantize(Decimal('0.01')) if total else Decimal('0.00')
    grand_total = (Decimal(total) + tax).quantize(Decimal('0.01')) if total else Decimal('0.00')
    
    if request.method == 'POST':
        # Create order
        import random
        import string
        order_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        
        order = Order.objects.create(
            user=request.user,
            order_number=order_number,
            total_amount=grand_total,
            status='completed'
        )
        
        # Create order items
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                service=item.service,
                quantity=item.quantity,
                price=item.service.price
            )
        
        # Clear cart
        cart_items.delete()
        
        messages.success(request, f'Order #{order.order_number} placed successfully!')
        return redirect('order_detail', order_id=order.id)
    
    return render(request, 'checkout.html', {
        'cart_items': cart_items,
        'total': total,
        'tax': tax,
        'grand_total': grand_total,
    })

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_detail.html', {'order': order})

@login_required
def generate_invoice_pdf(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    html_string = render_to_string('invoice_pdf.html', {'order': order})
    
    # For PDF generation, you'll need to install weasyprint
    # pip install weasyprint
    try:
        from weasyprint import HTML
        html = HTML(string=html_string)
        pdf_bytes = html.write_pdf()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename=invoice_{order.order_number}.pdf'
        response['Content-Transfer-Encoding'] = 'binary'
        return response
    except ImportError:
        messages.error(request, 'PDF generation is not available. Please install weasyprint.')
        return redirect('order_detail', order_id=order_id)