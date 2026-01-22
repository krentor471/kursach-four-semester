from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from simple_history.admin import SimpleHistoryAdmin
from .models import Category, Nomination, Vote

class CategoryResource(resources.ModelResource):
    nominations_count = fields.Field()
    total_votes = fields.Field()
    average_rating = fields.Field()
    status = fields.Field()
    
    class Meta:
        model = Category
        fields = ('id', 'name', 'description', 'is_active', 'is_featured', 'priority', 
                 'color', 'created_at', 'nominations_count', 'total_votes', 'average_rating', 'status')
        export_order = ('id', 'name', 'status', 'nominations_count', 'total_votes', 'average_rating')
    
    def get_export_queryset(self, request, queryset=None):
        """Экспортируем только активные категории с номинациями"""
        if queryset is None:
            queryset = self.Meta.model.objects.all()
        return queryset.filter(is_active=True, nominations__isnull=False).distinct()
    
    def dehydrate_nominations_count(self, category):
        """Количество номинаций в категории"""
        return category.nominations.count()
    
    def dehydrate_total_votes(self, category):
        """Общее количество голосов по всем номинациям категории"""
        return category.get_total_votes()
    
    def dehydrate_average_rating(self, category):
        """Средний рейтинг по всем номинациям категории"""
        from django.db.models import Avg
        avg = category.nominations.aggregate(avg_rating=Avg('votes__rating'))['avg_rating']
        return round(avg, 2) if avg else 0
    
    def dehydrate_status(self, category):
        """Статус категории с дополнительной информацией"""
        status = "Активная" if category.is_active else "Неактивная"
        if category.is_featured:
            status += " (Рекомендуемая)"
        return status
    
    def get_created_at(self, category):
        """Форматированная дата создания"""
        return category.created_at.strftime('%d.%m.%Y %H:%M')

class NominationInline(admin.TabularInline):
    model = Nomination
    extra = 0
    fields = ('title', 'is_active', 'created_at')
    readonly_fields = ('created_at',)

@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    resource_class = CategoryResource
    list_display = ['name', 'nominations_count', 'total_votes_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_featured', 'created_at']
    search_fields = ['name', 'description']
    inlines = [NominationInline]
    history_list_display = ['name', 'is_active', 'history_date', 'history_type']
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('nominations', 'nominations__votes')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'slug')
        }),
        ('Настройки', {
            'fields': ('is_active', 'is_featured', 'color', 'priority')
        }),
    )
    
    def nominations_count(self, obj):
        return obj.nominations.count()
    nominations_count.short_description = 'Количество номинаций'
    
    def total_votes_display(self, obj):
        count = obj.get_total_votes()
        return format_html('<strong>{}</strong>', count)
    total_votes_display.short_description = 'Всего голосов'

class VoteInline(admin.TabularInline):
    model = Vote
    extra = 0
    fields = ('user', 'rating', 'comment', 'created_at')
    readonly_fields = ('created_at',)

class NominationResource(resources.ModelResource):
    category_name = fields.Field()
    votes_count = fields.Field()
    average_rating = fields.Field()
    top_comment = fields.Field()
    
    class Meta:
        model = Nomination
        fields = ('id', 'title', 'subtitle', 'category_name', 'is_active', 
                 'created_at', 'votes_count', 'average_rating', 'top_comment')
    
    def get_export_queryset(self, request, queryset=None):
        if queryset is None:
            queryset = self.Meta.model.objects.all()
        return queryset.select_related('category').prefetch_related('votes')
    
    def dehydrate_category_name(self, nomination):
        return nomination.category.name
    
    def dehydrate_votes_count(self, nomination):
        return nomination.votes.count()
    
    def dehydrate_average_rating(self, nomination):
        avg = nomination.get_average_rating()
        return round(avg, 2) if avg else 0
    
    def get_top_comment(self, nomination):
        """Лучший комментарий (с максимальным рейтингом)"""
        top_vote = nomination.votes.filter(comment__isnull=False).exclude(comment='').order_by('-rating').first()
        return top_vote.comment[:100] + '...' if top_vote and len(top_vote.comment) > 100 else (top_vote.comment if top_vote else '')

@admin.register(Nomination)
class NominationAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    resource_class = NominationResource
    list_display = ['title', 'category_link', 'votes_count', 'average_rating', 'is_active', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['title', 'description']
    inlines = [VoteInline]
    history_list_display = ['title', 'category', 'is_active', 'history_date', 'history_type']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category').prefetch_related('votes', 'votes__user')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'subtitle', 'description', 'short_description')
        }),
        ('Связи и настройки', {
            'fields': ('category', 'is_active', 'voting_start', 'voting_end')
        }),
    )
    
    def category_link(self, obj):
        url = reverse('admin:voting_app_category_change', args=[obj.category.pk])
        return format_html('<a href="{}">{}</a>', url, obj.category.name)
    category_link.short_description = 'Категория'
    
    def votes_count(self, obj):
        return obj.votes.count()
    votes_count.short_description = 'Голосов'
    
    def average_rating(self, obj):
        avg = obj.get_average_rating()
        return f'{avg:.1f}' if avg else '0.0'
    average_rating.short_description = 'Средний рейтинг'

@admin.register(Vote)
class VoteAdmin(SimpleHistoryAdmin):
    list_display = ['nomination_link', 'user_link', 'rating', 'created_at']
    list_filter = ['rating', 'created_at', 'nomination__category']
    search_fields = ['nomination__title', 'user__username', 'comment']
    history_list_display = ['nomination', 'user', 'rating', 'history_date', 'history_type']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('nomination', 'nomination__category', 'user')
    
    fieldsets = (
        ('Голос', {
            'fields': ('nomination', 'user', 'rating', 'comment')
        }),
    )
    
    def nomination_link(self, obj):
        url = reverse('admin:voting_app_nomination_change', args=[obj.nomination.pk])
        return format_html('<a href="{}">{}</a>', url, obj.nomination.title)
    nomination_link.short_description = 'Номинация'
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'Пользователь'