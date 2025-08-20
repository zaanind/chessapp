from .consumersmod.bot import handle_bot_move,is_user_bot,is_bot_turn
from .consumersmod.utils import set_user_online,is_user_online,get_room,get_game,get_user_role,create_viewer_playerroom,save_fen,should_lock_board,get_player_ids,get_opponent_id,get_user_by_id
from .consumersmod.utils import get_user_color_in_room
from .consumersmod.tournaments import dotournament

from .consumersmod.chesscon import (onconnect_chess_board,on_clock_end_msg,
                                     on_no_move_activity,
                                     on_checkmate,
                                     start_tournament,ondisconnect_chess)

from .consumersmod.chatcon import onchatconnect,onchat_receive
from .consumersmod.bets import onbetconnect,onbet_receive
from .consumersmod.notifications import on_bet_inv,onconnect_send_notifications

#from .consumersmod.user_offline_timeouts import check_opponent_timeout

import os 
import django
import asyncio
import json
import chess
import chess.engine
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chessapp.settings')
django.setup()

from chessgame.models import Game, Room, PlayerRoom,GameBet
from chessgame.models import ChatMessage,Notification

User = get_user_model()


class Online_check_landing_Consumer(AsyncWebsocketConsumer):
    User = User
    Notification=Notification
    Room = Room
    Game = Game
    PlayerRoom = PlayerRoom
    GameBet= GameBet

    async def connect(self):
        self.user = self.scope["user"]
        self.user_group_name = f"user_{self.user.id}"
       
        await self.accept()
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        
        await set_user_online(self,True)
        await onconnect_send_notifications(self)
        
    @staticmethod
    @database_sync_to_async
    def refresh_user_profile(user):
        return User.objects.select_related("profile").get(id=user.id) 
        
    async def disconnect(self, close_code):
        self.user = await self.refresh_user_profile(self.user)
        await set_user_online(self,False)
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

        
        
        
    async def global_notif(self, event):
        data_to_send = {k: v for k, v in event.items() if k != "type"}
        await self.send(text_data=json.dumps({
        "type": "global_notif",
        **data_to_send
        }))


class ChessConsumer(AsyncWebsocketConsumer):
    Room = Room
    PlayerRoom = PlayerRoom
    User = User
    GameBet= GameBet
    Game = Game
    
    Notification=Notification
    ChatMessage = ChatMessage
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.user = self.scope["user"]
        self.room_group_name = f'chess_{self.room_id}'
        self.user_group_name = f"user_{self.user.id}"
        await self.accept()
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        
        
        await set_user_online(self,True)
        if self.room_id:
            await onconnect_chess_board(self)
        await onchatconnect(self)
        await onbetconnect(self)
        await onconnect_send_notifications(self)


    async def disconnect(self, close_code):
        self.active_real_users.discard(self.user.id)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)
        await set_user_online(self,False)
        await ondisconnect_chess(self)
        if self.role == 'PLAYER' and not await is_user_bot(self,self.user.id):
            opponent_id = await get_opponent_id(self)
            if opponent_id and not await is_user_bot(self,opponent_id):
              #  asyncio.create_task(check_opponent_timeout(self,opponent_id, self.user.id))
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'opponent_offline',
                        'user_id': self.user.id,
                        'opponent_id': opponent_id,
                        'message': 'Opponent has gone offline.'
                    }
                )

    async def receive(self, text_data):
        lock_stat = await should_lock_board(self)
        data = json.loads(text_data)
        move_uci = data.get('move')
        if move_uci and '-' in move_uci:
            move_uci = move_uci.replace('-', '')
        if move_uci:
            from .consumersmod.chesscon import onmove_chess_board
            await onmove_chess_board(self, move_uci)
            return
            
        # You can continue handling other message types here, e.g.:
        msg_type = data.get('type')
        self.msg_type = msg_type
        self.data = data
        if msg_type == 'chat':
            print(msg_type)
            await onchat_receive(self)
            pass
        if msg_type == 'bet':
            await onbet_receive(self)
            pass
        if msg_type == 'clock_end':
            await on_clock_end_msg(self)
            pass
        if msg_type == 'no_activity':
            await on_no_move_activity(self)
            pass      
        if msg_type == 'checkmate_respond':
            await on_checkmate(self)
            pass         
        if msg_type == 'tournament_start':
            await start_tournament(self)
            pass                     
        if msg_type == 'bet_invite_notification':
            await on_bet_inv(self,data)
            pass               
      
    async def global_notif(self, event):
        data_to_send = {k: v for k, v in event.items() if k != "type"}

        await self.send(text_data=json.dumps({
        "type": "global_notif",
        **data_to_send
        }))

    async def torunamentmanonline(self, event):
        data_to_send = {k: v for k, v in event.items() if k != "type"}

        await self.send(text_data=json.dumps({
        "type": "torunamentmanonline",
        **data_to_send
        }))
      
    async def chess_move(self, event):
        #print('🔁 chess_move received:', event)
        
        try:
            self.board = chess.Board(event['fen'])
        except ValueError:
            self.board = chess.Board()
            
        locked = await should_lock_board(self)
        
        is_white_turn = self.board.turn == chess.WHITE
        user_id = self.user.id
        white_id, black_id = await get_player_ids(self)
        if self.room.is_over:
            locked = True
            
        
        
        user_color = await get_user_color_in_room(self, self.user)
        if not user_color:user_color = "viewer"
        current_player_id = white_id if is_white_turn else black_id
        current_user = await get_user_by_id(self,current_player_id) if current_player_id else None
        current_player_name = current_user.username if current_user else 'Unknown Player'
        current_player_name = current_player_name+"'s"
        if user_id==current_player_id:
            current_player_name = 'Your'
        #await self.send_game_state()
        
        
        white_player_obj = await get_user_by_id(self, white_id) if white_id else None
        black_player_obj = await get_user_by_id(self, black_id) if black_id else None

        await self.send(text_data=json.dumps({
            'type': 'move',
            'move': event['move'],
            'user_color': user_color,
           # 'cplayer' : current_player_name,
            'locked': locked,
            'fen': event['fen'],
            'white_player_username': white_player_obj.username if white_player_obj else 'White Player',
            'black_player_username': black_player_obj.username if black_player_obj else 'Black Player',
            'turn': event['turn'],
            'legal_moves': [move.uci() for move in self.board.legal_moves],
            'check': event['check'],
            'checkmate': event['checkmate'],
            'stalemate': event['stalemate'],
        }))
        print('move sent')

    async def opponent_offline(self, event):
        if self.role == 'PLAYER':
            if self.user.id == event.get('opponent_id'):
                await self.send(text_data=json.dumps({
                    'type': 'opponent_offline',
                    'message': event['message'],
                    'user_id': event.get('user_id')
                }))
        elif self.role == 'VIEWER':
            await self.send(text_data=json.dumps({
                'type': 'opponent_offline',
                'message': event['message'],
                'user_id': event.get('user_id')
            }))

    async def opponent_online(self, event):
        if self.user.id == event['opponent_id']:
            await self.send(text_data=json.dumps({
                'type': 'opponent_offline', 
                'message': event['message'],
                'user_id': event['user_id']
            }))
    async def bet_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'bet',
            'username': event['username'],
            'amount': float(event['amount']),
            'side': event['side'],
            }))

    # ✅ 🔊 Broadcast handler for chat
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'sender': event['sender'],
            'message': event['message']
        }))
        
    async def send_game_state(self):
        legal_moves = [move.uci() for move in self.board.legal_moves]
        locked = await should_lock_board(self)
        is_white_turn = self.board.turn == chess.WHITE
        user_id = self.user.id
        white_id, black_id = await get_player_ids(self)
        if self.room.is_over:
            locked = True
        
        user_color = await get_user_color_in_room(self, self.user)
        if not user_color:user_color = "viewer"

        current_player_id = white_id if is_white_turn else black_id
        current_user = await get_user_by_id(self,current_player_id) if current_player_id else None
        current_player_name = current_user.username if current_user else 'Unknown Player'

        current_player_name = current_player_name+"'s"
        if user_id==current_player_id:
            current_player_name = 'Your'
        

        white_player_obj = await get_user_by_id(self, white_id) if white_id else None
        black_player_obj = await get_user_by_id(self, black_id) if black_id else None
        
        print('update sent')
        await self.send(text_data=json.dumps({
            'user_id': user_id,
            'user_color': user_color,
            'type': 'game_state',
            'fen': self.board.fen(),
            'legal_moves': legal_moves,
            'locked': locked,
            'turn': 'white' if is_white_turn else 'black',
            'cplayer' : current_player_name,
            'check': self.board.is_check(),
            'checkmate': self.board.is_checkmate(),
            'stalemate': self.board.is_stalemate(),
            'is_white_turn': is_white_turn,
            'white_player_username': white_player_obj.username if white_player_obj else 'White Player',
            'black_player_username': black_player_obj.username if black_player_obj else 'Black Player',
            'current_round': self.room.round_number, 
            'total_rounds': self.room.round_type, 
            
        }))


  



