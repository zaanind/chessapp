# signals.py
#from django.db.models.signals import post_save
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile
import traceback

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile = Profile.objects.create(user=instance)
        profile.referral_code = profile.generate_referral_code()
        profile.save()

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()




#@receiver(pre_save, sender=Profile)
#def before_profile_save(sender, instance, **kwargs):
#    print(f"[DEBUG] About to save Profile id={instance.id}, balance={instance.wallet_balance}")
#   # print("[TRACEBACK] Called from:")
   # traceback.print_stack(limit=5)  # Adjust limit as needed

#@receiver(post_save, sender=Profile)
#def after_profile_save(sender, instance, created, **kwargs):
#    action = "Created" if created else "Updated"
#    print(f"[DEBUG] {action} Profile id={instance.id}, balance={instance.wallet_balance}")
#    print("[TRACEBACK] Called from:")
#    traceback.print_stack(limit=5)  # Adjust limit as needed