from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from voting_app.models import Category, Nomination, Vote
from django.utils import timezone
import random

class Command(BaseCommand):
    help = 'Создает тестовые данные для системы голосования'

    def add_arguments(self, parser):
        parser.add_argument(
            '--categories',
            type=int,
            default=5,
            help='Количество категорий для создания'
        )
        parser.add_argument(
            '--nominations',
            type=int,
            default=3,
            help='Количество номинаций на категорию'
        )

    def handle(self, *args, **options):
        categories_count = options['categories']
        nominations_per_category = options['nominations']
        
        self.stdout.write('Создание тестовых данных...')
        
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(f'Создан пользователь: {user.username}')
        
        category_names = [
            'Лучший фильм', 'Лучший актер', 'Лучшая актриса',
            'Лучшая музыка', 'Лучшие спецэффекты', 'Лучший режиссер',
            'Лучший сценарий', 'Лучшая операторская работа'
        ]
        
        for i in range(categories_count):
            name = category_names[i % len(category_names)]
            category, created = Category.objects.get_or_create(
                name=f'{name} {i+1}',
                defaults={
                    'description': f'Номинации на {name.lower()}',
                    'is_featured': random.choice([True, False]),
                    'color': random.choice(['#0078d4', '#107c10', '#d13438', '#ff8c00'])
                }
            )
            
            if created:
                self.stdout.write(f'Создана категория: {category.name}')
                
                nomination_titles = [
                    'Титаник', 'Аватар', 'Мстители', 'Звездные войны',
                    'Властелин колец', 'Гарри Поттер', 'Матрица', 'Терминатор'
                ]
                
                for j in range(nominations_per_category):
                    title = f'{nomination_titles[j % len(nomination_titles)]} - {j+1}'
                    nomination = Nomination.objects.create(
                        title=title,
                        subtitle=f'Подзаголовок для {title}',
                        description=f'Описание номинации {title}',
                        short_description=f'Краткое описание {title}',
                        category=category,
                        voting_start=timezone.now(),
                        voting_end=timezone.now() + timezone.timedelta(days=30)
                    )
                    
                    self.stdout.write(f'  Создана номинация: {nomination.title}')
                    
                    if random.choice([True, False]):
                        Vote.objects.create(
                            nomination=nomination,
                            user=user,
                            rating=random.randint(1, 5),
                            comment=f'Тестовый комментарий для {nomination.title}'
                        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно создано {categories_count} категорий с номинациями!'
            )
        )