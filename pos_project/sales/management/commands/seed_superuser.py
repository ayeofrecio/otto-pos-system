from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds a default administrator/superuser account if it does not exist"

    def handle(self, *args, **kwargs):
        self.stdout.write("Checking for default admin account...")
        
        username = "admin"
        email = "admin@ottopos.local"
        password = "otto1234"  # Change this to your preferred default local password
        role = "manager"

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                role=role
            )
            self.stdout.write(self.style.SUCCESS(f"🎉 Superuser '{username}' created successfully!"))
        else:
            self.stdout.write(f"Superuser '{username}' already exists. Skipping...")