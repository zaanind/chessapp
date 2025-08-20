from .bot import handle_bot_move,is_user_bot,is_bot_turn
from .utils import set_user_online,is_user_online,get_room,get_game,get_user_role,create_viewer_playerroom,save_fen,should_lock_board,get_player_ids,get_opponent_id,get_user_by_id
import chess
import chess.engine
from .tournaments import dotournament
import asyncio
import os 
import django

import json
from .timeman import (handle_time_expiry_and_round_restart,
                     is_time_control_enabled,
                     on_no_move_activity,on_checkmate,
                     start_tournament)
import pytz

from django.utils.timezone import now

from channels.db import database_sync_to_async


@database_sync_to_async
def is_room_creator(self):
    #print('accessed')
    return self.room.created_by_id == self.user.id


async def get_joined_users(self,role="PLAYER"):
    from chessgame.models import PlayerRoom

    players = await database_sync_to_async(
        lambda: list(PlayerRoom.objects.select_related("user").filter(room=self.room, role=role))
    )()

    joined = []
    for p in players:
        is_online = await is_user_online(self, p.user.id)
        joined.append({
            "username": p.user.username,
            "is_online": is_online
        })

    return joined


async def ondisconnect_chess(self):
   # print('disconnected')
    joined_players = await get_joined_users(self) #get online players for tournament manager
    await self.channel_layer.group_send(
    self.room_group_name,
    {
        "type": "torunamentmanonline",
        "type2" : "user_joined_tman",
        "joined": joined_players,
        "max": self.room.max_users,})

                         



async def onconnect_chess_board(self):
    self.room_group_name = f'chess_{self.room_id}'
    self.room = await get_room(self, self.room_id)
    self.game = await get_game(self, self.room)
    self.active_real_users = set()

    #define_data_vars(self)


    try:
        self.role = await get_user_role(self, self.user, self.room)
    except:
        self.role = 'VIEWER'
        await create_viewer_playerroom(self, self.user, self.room)
    self.active_real_users.add(self.user.id)
    fen = self.game.fen
    self.board = chess.Board() if not fen or fen == "startpos" else chess.Board(fen)



    await self.channel_layer.group_add(self.room_group_name, self.channel_name)
    await dotournament(self) #should work for all
    if self.room.room_type == 'TOURNAMENT':
        await dotournament(self)
        joined_players = await get_joined_users(self) #get online players for tournament manager
        await self.channel_layer.group_send(self.room_group_name,
        {"type": "torunamentmanonline",
        "type2" : "user_joined_tman",
        "joined": joined_players,
        "max": self.room.max_users,})
        
        self.game = await get_game(self, self.room)
        
        
        if not self.room.start_datetime and self.room.is_automated_room:
            room_tz = pytz.timezone(self.room.timezone)
            start_datetime = now().astimezone(room_tz)  
            self.room.start_datetime = start_datetime
            
        
        if not self.room.start_datetime:
            is_cre = await is_room_creator(self)
            if not is_cre:
                await self.send(text_data=json.dumps({
                'popup': f"Game not started, Waiting For Users To Join."
                }))
            else:
                await self.send(text_data=json.dumps({
                'popup': f"Game not started, Start The game as you are owner of this tournament."
                }))
                
    if not self.room.is_over: #self.room.room_type == 'TOURNAMENT' and 
        from .bets import start_fake_betting_loop
        self.fake_bet_task = asyncio.create_task(start_fake_betting_loop(self))
        
    if not self.room.room_type == 'TOURNAMENT' and not self.room.is_over:
        from .timeman import start_single_game
        await start_single_game(self)
        
        
    if not self.room.start_datetime:
        return   
    from channels.db import database_sync_to_async
    player_white_exists = await database_sync_to_async(lambda: bool(self.game.player_white))()
    player_black_exists = await database_sync_to_async(lambda: bool(self.game.player_black))()

        

        
    if await is_time_control_enabled(self) and self.room.start_datetime:
        ret = await handle_time_expiry_and_round_restart(self)
        if ret:
            return    

    await self.send_game_state()          
    if self.role == 'PLAYER' and not await is_user_bot(self, self.user.id):
        opponent_id = await get_opponent_id(self)
        is_op_bot = await is_user_bot(self, opponent_id)
        if opponent_id and not is_op_bot:
            opponent_online = await is_user_online(self, opponent_id)
            if not opponent_online:
                await self.send(text_data=json.dumps({
                    'type': 'opponent_offline',
                    'message': 'Opponent is offline.',
                    'user_id': self.user.id,
                    'opponent_id': opponent_id,
                }))
            else:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "opponent_offline",
                        'user_id': self.user.id,
                        'opponent_id': opponent_id,
                        'message': 'Opponent is online.'
                    }
                )
    elif self.role == 'VIEWER':
        white_id = getattr(self.game.player_white, 'id', None)
        black_id = getattr(self.game.player_black, 'id', None)
        white_online = white_id and await is_user_online(self, white_id)
        black_online = black_id and await is_user_online(self, black_id)
        if not white_online and not black_online and  self.room.first_game_start: #change 8 /14
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "opponent_offline",
                    "user_id": None,
                    "opponent_id": None,
                    "message": "Both players are offline.",
                }
            )




async def on_clock_end_msg(self):
    print('clock end msg from frontend')
    lock_stat = await should_lock_board(self)
    if await is_time_control_enabled(self):
        lock_stat = await handle_time_expiry_and_round_restart(self)

on_no_move_activity = on_no_move_activity
on_checkmate = on_checkmate

start_tournament = start_tournament

async def onmove_chess_board(self, move_uci):
    if not self.room.start_datetime:
        return
    
    lock_stat = await should_lock_board(self)
    if await is_time_control_enabled(self) :
        lock_stat = await handle_time_expiry_and_round_restart(self,send_game_stat=False)
        
        
    
    if self.role != 'PLAYER':
        await self.send(text_data=json.dumps({'error': 'Viewers cannot move'}))
        await self.send_game_state()
        return

    if lock_stat:
        await self.send(text_data=json.dumps({'error': "You can't move."}))
        await self.send_game_state()
        return

    try:
        move = chess.Move.from_uci(move_uci)
    except ValueError:
        await self.send(text_data=json.dumps({'error': 'Invalid move format'}))
        await self.send_game_state()
        return

    if move in self.board.legal_moves:
        print('b m turn ','white' if self.board.turn == chess.WHITE else 'black')
        self.board.push(move)
        

        if self.room.room_type == 'TOURNAMENT':
            await dotournament(self)
            self.game = await get_game(self, self.room)

        await save_fen(self, self.board.fen())
        await on_checkmate(self)
        
        
        

        await self.send_game_state() #this works before bot turn so i can show name 
        
        if await is_bot_turn(self) and not lock_stat:
            
            await asyncio.sleep(0.5)
            #await handle_bot_move(self)
            self.task_asy_ref_bot = asyncio.create_task(handle_bot_move(self))

    else:
        await self.send(text_data=json.dumps({'error': 'Illegal move'}))
        await self.send_game_state()
