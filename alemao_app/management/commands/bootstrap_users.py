from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from alemao_app.models import CEFRLevel, UserProfile


DEFAULT_USERS = [
    {"username": "marcos", "email": "marcos@local.dev", "password": "Marcos@123", "level": CEFRLevel.C1},
    {"username": "caio", "email": "caio@local.dev", "password": "Caio@12345", "level": CEFRLevel.B1},
    {"username": "thais", "email": "thais@local.dev", "password": "Thais@12345", "level": CEFRLevel.A1},
]


class Command(BaseCommand):
    help = "Cria/atualiza usuários padrão e seus níveis CEFR"

    def handle(self, *args, **options):
        User = get_user_model()
        for item in DEFAULT_USERS:
            user, created = User.objects.get_or_create(
                username=item["username"],
                defaults={
                    "email": item["email"],
                    "is_staff": False,
                    "is_superuser": False,
                },
            )

            if not created:
                user.email = item["email"]

            user.set_password(item["password"])
            user.save(update_fields=["email", "password"])

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.proficiency_level = item["level"]
            profile.save(update_fields=["proficiency_level", "updated_at"])

            self.stdout.write(
                self.style.SUCCESS(
                    f"Usuário '{user.username}' pronto com nível {profile.proficiency_level}."
                )
            )
