from django.core.management.base import BaseCommand
from django.db.models import Count, Avg, Q
from voting_app.models import Category, Nomination, Vote
import json
import os

class Command(BaseCommand):
    help = 'Экспортирует статистику голосования в JSON файл'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='voting_statistics.json',
            help='Имя выходного файла'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Включить детальную статистику по каждой номинации'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        detailed = options['detailed']
        
        self.stdout.write('Сбор статистики голосования...')
        
        # Общая статистика
        stats = {
            'general': {
                'total_categories': Category.objects.count(),
                'active_categories': Category.objects.filter(is_active=True).count(),
                'featured_categories': Category.objects.filter(is_featured=True).count(),
                'total_nominations': Nomination.objects.count(),
                'active_nominations': Nomination.objects.filter(is_active=True).count(),
                'total_votes': Vote.objects.count(),
                'average_rating': Vote.objects.aggregate(avg=Avg('rating'))['avg'] or 0,
            }
        }
        
        # Статистика по категориям
        categories_stats = []
        for category in Category.objects.annotate(
            nominations_count=Count('nominations'),
            total_votes=Count('nominations__votes'),
            avg_rating=Avg('nominations__votes__rating')
        ):
            cat_stat = {
                'name': category.name,
                'is_active': category.is_active,
                'is_featured': category.is_featured,
                'nominations_count': category.nominations_count,
                'total_votes': category.total_votes,
                'average_rating': round(category.avg_rating, 2) if category.avg_rating else 0,
            }
            
            if detailed:
                # Детальная статистика по номинациям
                nominations = []
                for nomination in category.nominations.annotate(
                    votes_count=Count('votes'),
                    avg_rating=Avg('votes__rating')
                ):
                    nominations.append({
                        'title': nomination.title,
                        'votes_count': nomination.votes_count,
                        'average_rating': round(nomination.avg_rating, 2) if nomination.avg_rating else 0,
                        'is_active': nomination.is_active,
                    })
                cat_stat['nominations'] = nominations
            
            categories_stats.append(cat_stat)
        
        stats['categories'] = categories_stats
        
        # Топ номинаций по рейтингу
        top_nominations = Nomination.objects.annotate(
            votes_count=Count('votes'),
            avg_rating=Avg('votes__rating')
        ).filter(
            votes_count__gt=0
        ).order_by('-avg_rating')[:10]
        
        stats['top_nominations'] = [
            {
                'title': nom.title,
                'category': nom.category.name,
                'votes_count': nom.votes_count,
                'average_rating': round(nom.avg_rating, 2)
            }
            for nom in top_nominations
        ]
        
        # Сохранение в файл
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Статистика успешно экспортирована в файл: {output_file}'
                )
            )
            
            # Вывод краткой статистики в консоль
            self.stdout.write('\n=== КРАТКАЯ СТАТИСТИКА ===')
            self.stdout.write(f'Всего категорий: {stats["general"]["total_categories"]}')
            self.stdout.write(f'Активных категорий: {stats["general"]["active_categories"]}')
            self.stdout.write(f'Всего номинаций: {stats["general"]["total_nominations"]}')
            self.stdout.write(f'Всего голосов: {stats["general"]["total_votes"]}')
            self.stdout.write(f'Средний рейтинг: {stats["general"]["average_rating"]:.2f}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при сохранении файла: {e}')
            )