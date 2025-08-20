from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone



class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_bot = models.BooleanField(default=False)
    fake_game_info = models.JSONField(default=dict, blank=True)
    is_auto_sys = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)
    timezone = models.CharField(max_length=50, default='Asia/Colombo')  # e.g. 'America/New_York'
    wallet2_locked = models.BooleanField(default=False)
    sec_wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rating = models.IntegerField(default=450)  # optional example field
    is_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=20,null=True,blank=True)
    
    
    
    
    referrer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    refz_referrer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='refzref')
    refz_referrerz_ref = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='refzrefzref')
    referral_reward_given = models.BooleanField(default=False)
    
    referral_code = models.CharField(max_length=20,null=True,blank=True)

    def __str__(self):
        return f"{self.user.username} Profile"
        
    def generate_referral_code(self):
        # You can also use hash of ID or username, here we use UUID short
        return str(uuid.uuid4()).split('-')[0] + str(self.user.id)

class Referrals(models.Model):
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referral_events')
    referred = models.ForeignKey(User, on_delete=models.CASCADE, related_name='was_referred_by')
    referral_reward_amount = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    reward_given = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.referrer.username} referred {self.referred.username}"
        
        

class WalletFundRequest(models.Model):
    REQUEST_TYPE_CHOICES = (
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAW', 'Withdraw'),
        ('TRANSFER', 'Transfer'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    WALLET_TYPES = (
        ('MAIN', 'Main'),
        ('SECWAL', 'Secwal'),
    )
    
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    request_type = models.CharField(max_length=10, choices=REQUEST_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    wallet_type = models.CharField(max_length=10, choices=WALLET_TYPES, default='MAIN')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    reference_number = models.TextField(
        blank=True,
        null=True,
        help_text="Enter full bank or online receipt text or reference number"
    )
    note = models.TextField(blank=True, help_text="Optional admin note or user message")

    def __str__(self):
        return f"{self.user.username} - {self.request_type} - {self.amount} ({self.status})"