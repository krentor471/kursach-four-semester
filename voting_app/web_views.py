from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.core.paginator import Paginator
from .models import Category, Nomination, Vote
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def category_list(request):
    categories = Category.objects.all().order_by('-created_at')
    paginator = Paginator(categories, 5)  # 5 категорий на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'category_list.html', {
        'categories': page_obj,
        'page_obj': page_obj
    })

def category_detail(request, pk):
    category = get_object_or_404(Category, pk=pk)
    nominations = category.nominations.all()
    return render(request, 'category_detail.html', {
        'category': category,
        'nominations': nominations
    })

def category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        if name:
            Category.objects.create(name=name, description=description)
            messages.success(request, 'Категория успешно создана!')
            return redirect('/api/web/')
    return render(request, 'category_form.html', {'title': 'Создать категорию'})

def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.name = request.POST.get('name', category.name)
        category.description = request.POST.get('description', category.description)
        category.save()
        messages.success(request, 'Категория успешно обновлена!')
        return redirect('/api/web/')
    return render(request, 'category_form.html', {
        'category': category,
        'title': 'Редактировать категорию'
    })

def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        if category.nominations.exists():
            messages.error(request, 'Нельзя удалить категорию с номинациями!')
        else:
            category.delete()
            messages.success(request, 'Категория удалена!')
        return redirect('/api/web/')
    return render(request, 'category_confirm_delete.html', {'category': category})

def show_categories(request):
    return redirect('/api/web/')

@login_required
def nomination_vote(request, pk):
    nomination = get_object_or_404(Nomination, pk=pk)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')
        
        if rating and 1 <= int(rating) <= 5:
            vote, created = Vote.objects.update_or_create(
                nomination=nomination,
                user=request.user,
                defaults={'rating': int(rating), 'comment': comment}
            )
            
            if created:
                messages.success(request, f'Ваш голос за "{nomination.title}" принят!')
            else:
                messages.success(request, f'Ваш голос за "{nomination.title}" обновлен!')
        else:
            messages.error(request, 'Неверный рейтинг. Выберите от 1 до 5.')
    
    return redirect('voting_app:category_detail', pk=nomination.category.pk)

def nomination_create(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        if title:
            Nomination.objects.create(
                title=title, 
                description=description, 
                category=category
            )
            messages.success(request, f'Номинация "{title}" создана!')
            return redirect('voting_app:category_detail', pk=category.pk)
    
    return render(request, 'nomination_form.html', {
        'category': category,
        'title': 'Добавить номинацию'
    })

def nomination_delete(request, pk):
    nomination = get_object_or_404(Nomination, pk=pk)
    category_pk = nomination.category.pk
    
    if request.method == 'POST':
        if nomination.votes.exists():
            messages.error(request, 'Нельзя удалить номинацию с голосами!')
        else:
            nomination.delete()
            messages.success(request, f'Номинация "{nomination.title}" удалена!')
        return redirect('voting_app:category_detail', pk=category_pk)
    
    return render(request, 'nomination_confirm_delete.html', {'nomination': nomination})