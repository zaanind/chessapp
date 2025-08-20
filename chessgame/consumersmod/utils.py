from channels.db import database_sync_to_async
import chess



@database_sync_to_async
def get_last_bets(room):
    return list(
        room.bets.select_related('user').order_by('-placed_at')[:20][::-1]
        
    )

@database_sync_to_async
def save_bet_msg(self, side,is_bot_placed,amount):
    new_bet = self.GameBet.objects.create(user=self.user, room=self.room,
                                 side=side,is_bot_placed=is_bot_placed,
                                 amount=amount
                                 )
    return new_bet



@database_sync_to_async
def update_bet_msg(self, bet_to_update):
    bet_to_update.save()
    return bet_to_update


@database_sync_to_async
def get_last_messages(room):
    return list(
        room.messages.select_related('user').order_by('-timestamp')[:20][::-1]
    )


@database_sync_to_async
def save_chat_message(self, message):
    self.ChatMessage.objects.create(user=self.user, room=self.room, message=message)


@database_sync_to_async
def set_user_online(self, online: bool):
    try:
        profile = self.user.profile
        profile.is_online = online
        profile.save()
    except Exception as e:
        print(f"Error setting online status: {e}")

@database_sync_to_async
def is_user_online(self, user_id):
    try:
        user = self.User.objects.select_related('profile').get(id=user_id)
        return user.profile.is_online
    except Exception:
        return False

@database_sync_to_async
def get_room(self, room_id):
    return self.Room.objects.get(id=room_id)

@database_sync_to_async
def get_game(self, room):
    return room.game

@database_sync_to_async
def get_user_role(self, user, room):
    try:
        return self.PlayerRoom.objects.get(user=user, room=room).role
    except self.PlayerRoom.DoesNotExist:
        return 'VIEWER'

@database_sync_to_async
def create_viewer_playerroom(self, user, room):
    return self.PlayerRoom.objects.create(user=user, room=room, role='VIEWER')

@database_sync_to_async
def save_fen(self, fen):
    import pytz
    from django.utils.timezone import now
    user= self.user
    user_tz = pytz.timezone(user.profile.timezone)
    self.game.fen = fen
    self.room.last_move_date = now().astimezone(user_tz)
    self.room.save()
    self.game.save()


@database_sync_to_async
def should_lock_board(self):
    if self.role != 'PLAYER':
        return True
    if not self.room.start_datetime:
        return True
  #  print('role not player')
    is_white_turn = self.board.turn == chess.WHITE
    
    user_id = self.user.id
   # print('---------------b lock start---------')
    white_id = self.game.player_white.id
    black_id = self.game.player_black.id if self.game.player_black else None
   # print('Data in :  user',user_id,' | Wid - ',white_id,' | Bid -',black_id, 'is Wt',is_white_turn)
    
    
    resp = not ((is_white_turn and user_id == white_id) or
                    (not is_white_turn and user_id == black_id))
                    
    #print(resp)
    #print('----------------b lock end------------')                
    return resp

@database_sync_to_async
def get_player_ids(self):
    white_id = getattr(self.game.player_white, 'id', None)
    black_id = getattr(self.game.player_black, 'id', None)
    return white_id, black_id

@database_sync_to_async
def get_opponent_id(self):
    if self.role != 'PLAYER':
        return None
        
    user_id = self.user.id
    white_id = getattr(self.game.player_white, 'id', None)
    black_id = getattr(self.game.player_black, 'id', None)
    if user_id == white_id:
        return black_id
    elif user_id == black_id:
        return white_id
    return None


@database_sync_to_async
def get_players_for_color(self, color: str, online_only: bool = True) -> list:
    """
    Retrieves a list of User objects who are players of a specific color
    in the current room, optionally filtering for online users only.
    """
    qs = self.User.objects.filter(
    playerroom__room=self.room,
    playerroom__role='PLAYER',
    playerroom__color_group=color,
    ).distinct()
    if online_only:
        qs = qs.filter(profile__is_online=True)
    return list(qs)
    
    
@database_sync_to_async
def set_game_player(self, color: str, user):
    """
    Assigns a User object to either player_white or player_black in the Game model.
    """
    if color == 'white':
        self.game.player_white = user
        self.game.save(update_fields=['player_white'])
        #print('Sw',user.id)
    else:
        self.game.player_black = user
        self.game.save(update_fields=['player_black'])
        #print('Bw',user.id)
        
        
@database_sync_to_async
def set_game_current_turn_player(self, player_id: int | None):
    """
    Updates the `current_turn_player` field in the Game model.
    """
    self.game.current_turn_player_id = player_id
    self.game.save(update_fields=['current_turn_player'])
    
    
@database_sync_to_async
def get_user_by_id(self, user_id):
    if user_id:
        try:
            return self.User.objects.get(id=user_id)
        except self.User.DoesNotExist:
            return None
    return None

@database_sync_to_async
def get_user_color_in_room(self,user):
    return self.PlayerRoom.objects.filter(user=user, room=self.room).values_list('color_group', flat=True).first()
