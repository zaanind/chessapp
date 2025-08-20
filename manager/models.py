from django.db import models
from chessgame.models import Game,Room

class CompanyCommission(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='commissions')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='commissions', null=True, blank=True)
    
    total_bets = models.DecimalField(max_digits=20, decimal_places=4)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Commission rate in % (e.g. 5.00 for 5%)")
    commission_amount = models.DecimalField(max_digits=20, decimal_places=4)
    
    calculated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Commission for Room: {self.room.name} - {self.commission_amount}"

    class Meta:
        ordering = ['-calculated_at']
