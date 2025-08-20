from django.db import models
from django.contrib.auth.models import User
#from django.db.models import JSONField
#python manage.py makemigrations chessgame
#python manage.py migrate




class ChatMessage(models.Model):
    room = models.ForeignKey('Room', on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return f"{self.user.username} @ {self.room.name}: {self.message[:30]}"

class Room(models.Model):
    ROOM_TYPES = [
        ('DUEL', 'User vs User'),
        ('TOURNAMENT', 'Tournament'),
    ]
    
    FORCE_TO_WIN = [
        ('WHITE', 'force win white'),
        ('BLACK', 'force win black'),
    ]
    
    ROUND_CHOICES = [
        (1, "1 (Single Game)"),
        (3, "Best 2 of 3"),
        (5, "Best 3 of 5"),
    ]
    
    
    name = models.CharField(max_length=100) 
    force_to_win_side = models.CharField(max_length=20, choices=FORCE_TO_WIN,null=True,blank=True)    
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES)    
    timezone = models.CharField(max_length=50, default='Asia/Colombo')  # e.g. 'America/New_York'
    round_type = models.IntegerField(choices=ROUND_CHOICES, default=1)  # Best of X  
    time_control_seconds = models.PositiveIntegerField(null=True, blank=True) # 5 min in sec
    round_number = models.IntegerField(default=1,null=True,blank=True)
    winner =  models.CharField(max_length=20,
                               choices=[('WHITE', 'White'), ('BLACK', 'Black')],
                               null=True)
    
    points = models.JSONField(null=True, blank=True)
    max_users = models.PositiveIntegerField(null=True, blank=True)
    joined_users = models.PositiveIntegerField(null=True, blank=True)
    
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms', null=True)
    start_datetime = models.DateTimeField(null=True, blank=True)  # Real start time (Agent cmd)
    starting_datetime = models.DateTimeField(null=True, blank=True)  # expected time
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_over = models.BooleanField(default=False)
    
    is_automated_room = models.BooleanField(default=False)
    is_next_auto_started =  models.BooleanField(default=False) #is next autogame created
    
    
    
    is_waiting_next_round = models.BooleanField(default=False)
    first_game_start = models.BooleanField(default=False)
    is_signal =  models.BooleanField(default=False) #for secwalletpayout
    last_move_date = models.DateTimeField(null=True,blank=True)
    is_piece_cap =  models.BooleanField(default=False)
    is_bet_shared =  models.BooleanField(default=False)
    match_pairs = models.JSONField(default=list, blank=True,null=True,)


    total_matches = models.IntegerField(default=0,null=True,blank=True)
    current_match_number = models.IntegerField(default=1)
    match_start_datetime = models.DateTimeField(null=True, blank=True)
   # played_matches = models.IntegerField(default=0,null=True,blank=True)





   # last_move_user = models.TextField(null=True,blank=True)

    

    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"
        
class Game(models.Model):
    room = models.OneToOneField(
    Room,
    on_delete=models.CASCADE,
    related_name='game',
    null=True,  # TEMPORARY
    blank=True )

    player_white = models.ForeignKey(User, on_delete=models.CASCADE, related_name='games_as_white', null=True)
    player_black = models.ForeignKey(User, on_delete=models.CASCADE, related_name='games_as_black' ,null=True)
    fen = models.TextField(default='startpos')
    fenhistory =  models.TextField(null=True,blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
      white = self.player_white.username if self.player_white else "TBD"
      black = self.player_black.username if self.player_black else "TBD"
      room_name = self.room.name if self.room else "No Room"
      return f"{white} vs {black} ({room_name})"



class PlayerRoom(models.Model):
    ROLE_CHOICES = [
        ('PLAYER', 'Player'),
        ('VIEWER', 'Viewer'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='participants')
    color_group = models.CharField(max_length=5, choices=[('white', 'White'), ('black', 'Black')],null=True)
    is_defeated =  models.BooleanField(default=False)  
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} in {self.room.name} as {self.role}"


class GameRequest(models.Model):
    requester = models.ForeignKey(User, related_name='game_requests_sent', on_delete=models.CASCADE)
    requested = models.ForeignKey(User, related_name='game_requests_received', on_delete=models.CASCADE)
    accepted = models.BooleanField(null=True)  # None = pending, True = accepted, False = declined
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Pending" if self.accepted is None else ("Accepted" if self.accepted else "Declined")
        return f"{self.requester.username} -> {self.requested.username} [{status}]"


class TournamentJoinRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='join_requests')
    approved = models.BooleanField(null=True)  # None = pending, True = approved, False = rejected
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'room')

    def __str__(self):
        return f"{self.user.username} -> {self.room.name} [{self.approved}]"



class GameBet(models.Model):
    SIDE_CHOICES = [
        ('white', 'White'),
        ('black', 'Black'),
    ]
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bets', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    is_vs_bet = models.BooleanField(default=False)
    vs_bet = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL,
        related_name='against_bet', 
        null=True,
        blank=True)

    is_bot_placed = models.BooleanField(default=False,null=True)
    side = models.CharField(max_length=15, choices=SIDE_CHOICES)
    amount = models.DecimalField(max_digits=20, decimal_places=4)
    placed_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.user.username} bets {self.amount} on {self.side}"# ({self.game})


class Notification(models.Model):
    SYSTEM_CHOICES = [
        ('BETINV', 'Betinvite'),
        ('ROOMINV', 'Roominvite'),
        ('SYSTEM', 'System'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_sent')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_received', null=True, blank=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='invroom', null=True, blank=True)
    system = models.CharField(max_length=20, choices=SYSTEM_CHOICES)
    message = models.TextField(blank=True, null=True)
    bet_amount = models.TextField(blank=True, null=True)
    bet_team = models.TextField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification to {self.to_user.username} [{self.system}]"