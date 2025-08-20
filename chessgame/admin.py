from django.contrib import admin
from .models import (Room, Game,
 PlayerRoom, GameRequest,
 TournamentJoinRequest,ChatMessage)



@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'message_snippet', 'timestamp')
    list_filter = ('room', 'user')
    search_fields = ('user__username', 'room__name', 'message')

    def message_snippet(self, obj):
        return obj.message[:50] + ('...' if len(obj.message) > 50 else '')
    message_snippet.short_description = 'Message'
    
    
@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_type','force_to_win_side', 'created_at', 'is_active')
    list_filter = ('room_type', 'is_active')
    search_fields = ('name',)

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('room', 'player_white', 'player_black', 'created_at', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('player_white__username', 'player_black__username')

@admin.register(PlayerRoom)
class PlayerRoomAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'role', 'joined_at','color_group')
    list_filter = ('role',)
    search_fields = ('user__username', 'room__name')

@admin.register(GameRequest)
class GameRequestAdmin(admin.ModelAdmin):
    list_display = ('requester', 'requested', 'accepted', 'created_at')
    list_filter = ('accepted',)
    search_fields = ('requester__username', 'requested__username')

@admin.register(TournamentJoinRequest)
class TJRAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'approved', 'requested_at')
    
