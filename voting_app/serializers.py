from rest_framework import serializers
from .models import Category, Nomination, Vote

class CategorySerializer(serializers.ModelSerializer):
    nominations_count = serializers.SerializerMethodField()
    total_votes = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'is_active', 'created_at', 'updated_at', 
                 'nominations_count', 'total_votes']

    def validate_name(self, value):
        if len(value) < 3:
            raise serializers.ValidationError('Название должно содержать минимум 3 символа')
        return value

    def get_nominations_count(self, obj):
        return obj.nominations.count()

    def get_total_votes(self, obj):
        return obj.get_total_votes()

class NominationSerializer(serializers.ModelSerializer):
    votes_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Nomination
        fields = ['id', 'title', 'description', 'category', 'category_name', 'is_active', 
                 'created_at', 'updated_at', 'votes_count', 'average_rating']

    def validate_title(self, value):
        if len(value) < 2:
            raise serializers.ValidationError('Название должно содержать минимум 2 символа')
        return value

    def get_votes_count(self, obj):
        return obj.votes.count()

    def get_average_rating(self, obj):
        return obj.get_average_rating()

class VoteSerializer(serializers.ModelSerializer):
    nomination_title = serializers.CharField(source='nomination.title', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Vote
        fields = ['id', 'nomination', 'nomination_title', 'user', 'user_username', 
                 'rating', 'comment', 'created_at']
        read_only_fields = ['user']

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError('Рейтинг должен быть от 1 до 5')
        return value

    def validate_comment(self, value):
        if len(value) > 1000:
            raise serializers.ValidationError('Комментарий не может быть длиннее 1000 символов')
        return value

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)