
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from sales.models import UserProfile


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a UserProfile row when a new auth_user is created.
    On subsequent saves it just calls save() to update auto fields (updated_at).
    """
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # Guard: profile may not exist yet for users created before this
        # migration was applied. get_or_create handles that gracefully.
        profile, _ = UserProfile.objects.get_or_create(user=instance)
        profile.save()
