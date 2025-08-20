from django.utils.timezone import now
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
import json
import chess
from channels.layers import get_channel_layer
import pytz
from decimal import Decimal
from django.db.models import Sum

#from account.models import Profile
import logging
logger = logging.getLogger(__name__)  # or any name you want









@database_sync_to_async
def mark_defeated_user(self, defeated_user):
    player_room = self.PlayerRoom.objects.get(user=defeated_user,room=self.room)
    player_room.is_defeated = True
    player_room.save()


    

async def check_match_end_condition(self):
    """
    Checks if the current match has ended due to checkmate, stalemate, or time.
    """
    user = self.user
    room_tz = pytz.timezone(self.room.timezone)
    current_time = now().astimezone(room_tz)

    if self.room.is_over:
        return {"status": "game_over"}


 
    if not self.room.time_control_seconds :
        return {"status": "no_timer"}
        
    if not self.room.match_start_datetime: # and self.room.room_type == 'TOURNAMENT':
        return {"status": "no_timer"}
 

        
    # --- Check for game-ending conditions: Checkmate or Stalemate ---
    is_checkmate = self.board.is_checkmate()
    is_stalemate = self.board.is_stalemate()
    if is_checkmate or is_stalemate:
        winner = 'black' if self.board.turn == chess.WHITE else 'white'
        if is_checkmate:
            reason = "checkmate"
            white_point = 1 if winner == 'white' else 0
            black_point = 1 if winner == 'black' else 0
            #await update_points(self, self.room.round_number, white_point, black_point)
            await update_points(self, self.room.round_number,self.room.current_match_number, white_point, black_point)
            
            if winner == 'white':
                await mark_defeated_user(self,white_user)
            if winner == 'black':
                await mark_defeated_user(self,black_user)
        else: # Stalemate
            reason = "stalemate"
            #await update_points(self, self.room.round_number, 0.5, 0.5)
            await update_points(self, self.room.round_number,self.room.current_match_number, white_point, black_point)
        return await prepare_next_stage(self, reason=reason)
        

    # --- Check for time-based match end ---
    match_start = self.room.match_start_datetime.astimezone(room_tz)


    if getattr(self, "start_next_match_intrpt", False):
        return await prepare_next_stage(self, reason="nomove timeout")
        
        
    elapsed = (current_time - match_start).total_seconds()
    match_duration = self.room.time_control_seconds
    remaining_time = max(0, int(match_duration - elapsed))
    
    
    white_user = await database_sync_to_async(lambda: self.game.player_white)()
    black_user = await database_sync_to_async(lambda: self.game.player_black)()

    if remaining_time <= 0:
        white_material, black_material = score_board(self.board)
        white_point, black_point = determine_material_winner(white_material, black_material)
        
        
        if white_point == 1:
            await mark_defeated_user(self,black_user)
            print('marking defeated user',black_user)
        elif black_point == 1:
            await mark_defeated_user(self,white_user)
            print('marking defeated user',white_user)
            
        #await update_points(self, self.room.round_number, white_point, black_point)
        await update_points(self, self.room.round_number,self.room.current_match_number, white_point, black_point)
        return await prepare_next_stage(self, reason="time_over")


    return {
        "status": "continue",
        "round_number": self.room.round_number,
        "match_number": self.room.current_match_number,
        "remaining_time": remaining_time,
        "max_rounds": self.room.round_type,
        "max_matches_per_round": self.room.total_matches,
        "max_time_per_match": match_duration
    }


async def prepare_next_stage(self, reason=""):
    from .tournaments import mark_match_played,reset_all_matches_played
    """
    Determines if the game proceeds to the next match, next round, or is over.
    """

    total_matches = self.room.total_matches
    max_rounds = self.room.round_type
    current_round = self.room.round_number
    current_match = self.room.current_match_number
   # print(total_matches,"TM")
   # print(current_match,"CM")
    
    
    if current_match + 1 > total_matches:
        print('matchs end')
        # End of the round, check for next round or game over
        winner = await calculate_winner(self)
        if winner in ["white", "black"]:
            self.room.winner = winner.upper()
            await setwin(self)
            return {"status": "game_over", "reason": f"{winner.title()} won the required number of rounds early"}

        elif current_round + 1 > max_rounds:      
            return {"status": "game_over", "reason": reason}
        else:
            # Proceed to the next round
            
            await reset_all_matches_played(self)
            return {
                "status": "next_round",
                "reason": reason,
                "round_number": current_round + 1,
                "match_number": 1
            }
    else:
        print('next match')

        white_id = self.game.player_white.id
        black_id = self.game.player_black.id
        await mark_match_played(self, white_id, black_id)
        print('marked pair as match played')
            
        # Proceed to the next match in the same round
        return {
            "status": "next_match",
            "reason": reason,
            "round_number": current_round,
            "match_number": current_match + 1
        }

@database_sync_to_async
def reset_for_next_match(self, round_number, next_match_number):
    """Resets the board and timer for the next match within the same round."""

    print(f'DB update: Starting Round {round_number}, Match {next_match_number}')
    self.game.fen = 'startpos'
    self.room.current_match_number = next_match_number
    self.room.match_start_datetime = now()  # Reset the timer for the new match
    self.game.save()
    self.room.save()
    self.room.refresh_from_db()

@database_sync_to_async
def reset_for_next_round(self, next_round_number):
    """Resets the board, match count, and timer for a new round."""
    print(f'DB update: Starting Next Round {next_round_number}, Match 1')

    self.game.fen = 'startpos'
    self.room.round_number = next_round_number
    self.room.current_match_number = 1
    self.room.match_start_datetime = now()  # Reset the timer for the new round's first match
    self.game.save()
    self.room.save()
    self.room.refresh_from_db()

async def reset_and_notify(self,popup_message, result):
        print('reset and notify')
        from .bot import handle_bot_move, is_bot_turn
        self.game.fen = 'startpos'
        self.board = chess.Board()
        await savegm(self)
        
        
        if self.room.room_type == 'TOURNAMENT':
            print('trying to change users')
            from .tournaments import dotournament
            self.user_change_needed = True
            await dotournament(self)
        
        

        await self.send(text_data=json.dumps({
            'popup': popup_message,
            'time_clock': self.room.time_control_seconds,
            'round': result["round_number"],
            'match': result.get("match_number", 1),
          #  'state': state,
        }))
        await self.send_game_state()
        if await is_bot_turn(self):
           # print("it's bot turn")
            import asyncio
            await asyncio.sleep(0.5)
            if hasattr(self, 'task_asy_ref_bot'):
                #destroy background bot task
                await self.destroy_all_tasks(self) 
                
                
            self.task_asy_ref_bot = asyncio.create_task(handle_bot_move(self))
        return True


async def start_next_round_db(self):
    logger.warning("Start next round cmd agent")

    result = await check_match_end_condition(self) #to get result
   # print(result)
    
    if getattr(self, "start_next_match_intrpt", False):
        self.start_next_match_intrpt = False

    await set_wait_next_round(self, False)
    await reset_for_next_round(self, result["round_number"])
    popup = f'Starting Next Round ({result["round_number"]}/{self.room.round_type})'
    await reset_and_notify(self,popup,result)
   # await 
    return  






        
@database_sync_to_async
def create_room_auto(self,tournament=False):
    from ..vut.users import get_random_participants  
    from .dummygame import generate_fake_game_info
    from django.utils.crypto import get_random_string
    import uuid
    import names
    import random
    
    Room = self.Room
    PlayerRoom = self.PlayerRoom
    Game = self.Game
    User = self.User
    

    #user = self.user
    admin_user = User.objects.filter(is_superuser=True).first()
    name = get_random_string(random.randint(4,7)).upper()
    room_tz = pytz.timezone(self.room.timezone)
    generate_users = True

    start_datetime = now().astimezone(room_tz)       
    creator_color = random.choice(['white', 'black'])
    
    
   
    
    room_type = 'DUEL'
    if tournament:
        room_type = 'TOURNAMENT'
        #allowed_values = [16, 32, 64, 128, 256, 512, 1024]     
        max_users = self.room.max_users #random.choice(allowed_values)
        members_needed =  max_users
    else:
        room_type = 'DUEL'
        max_users = 2
        members_needed =  max_users
        
        
    room = Room.objects.create(
        name=name,
        room_type=room_type,
        created_by=admin_user,
        starting_datetime=start_datetime,
        round_type=self.room.round_type,
        is_automated_room= True,
        max_users=max_users,
        joined_users=members_needed,
        time_control_seconds=self.room.time_control_seconds #random.choice([300,600])
        
        )
    
    colors = ['white', 'black']
    if generate_users:
        for i in range(members_needed):
            print(members_needed)
            random_name = names.get_first_name()
            length = 4
            bot = User.objects.create(username=f'{random_name}.{uuid.uuid4().hex[:length]}', is_active=True)
            bot.profile.is_bot = True
            bot.profile.is_online = True
            
            
            fake_info = generate_fake_game_info()
            bot.profile.sec_wallet_balance =  Decimal(random.randint(300 - 100, 300 + 100))
            bot.profile.wallet_balance =  Decimal(random.randint(300 - 100, 300 + 100))
            bot.profile.fake_game_info = fake_info
            bot.profile.rating = random.randint(830 - 100,830 + 100)
            
            bot.profile.is_auto_sys = True
            bot.profile.save()
            color_rand = colors[i % 2]
            PlayerRoom.objects.create(user=bot, room=room, role='PLAYER', color_group=color_rand)
            colors = ['white', 'black']
            
            
        for i in range(20):
            random_name = names.get_first_name()
            length = 4
            bot = User.objects.create(username=f'{random_name}.{uuid.uuid4().hex[:length]}', is_active=True)
            bot.profile.is_online = False 
            bot.profile.is_bot = True
            bot.profile.rating = random.randint(830 - 100,830 + 100)
            
            bot.profile.is_auto_sys = True
            bot.profile.save()
            color_rand = colors[i % 2]
            PlayerRoom.objects.create(user=bot, room=room, role='VIEWER',color_group=color_rand)     
    #selected_users = get_random_participants(user=request.user, only_online=True,listneeded=True)    
    
    game = Game.objects.create(room=room,player_white=None,player_black=None,fen='startpos')
    print('game created')






async def handle_time_expiry_and_round_restart(self,send_game_stat=False):
    if not self.room.start_datetime:
        return


    
    result = await check_match_end_condition(self)
   # print(result)


    if result["status"] == "next_match":
        #await self.destroy_all_tasks(self) 
        #import asyncio
        #self.task_asy_ref_bot =   asyncio.create_task(handle_bot_move(self))
        await reset_for_next_match(self, result["round_number"], result["match_number"])
        popup = f'Starting Next Match ({result["match_number"]}/{self.room.total_matches})'
        
        return await reset_and_notify(self,popup,result)

    elif result["status"] == "next_round":
        logger.warning("Next Round interrupt ")
        await set_wait_next_round(self, True)
        if hasattr(self, "destroy_all_tasks"):
            await self.destroy_all_tasks(self) 
            
        if getattr(self.room, "is_waiting_next_round", False) and self.room.room_type == 'TOURNAMENT' and not self.room.is_automated_room:
            await self.send(text_data=json.dumps({
                'popup': "Next round not started. Waiting for start.",
                'time_clock': '0',
                'enable_start_btn' : 'true',
            }))        
            return True
            
        if getattr(self.room, "is_waiting_next_round", False) and self.room.is_automated_room:  #Change 1
            await start_tournament(self)
            await set_wait_next_round(self, False)
            return True            
            
        if getattr(self.room, "is_waiting_next_round", False) and not self.room.room_type == 'TOURNAMENT': #if it's single type
            await start_tournament(self) #WRONG
            #print('rgfdsbszbbbbbbbbhtduuuuunnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn')
            #await self.send_game_state()
            await set_wait_next_round(self, False)
            return True
        return True
        
        
    elif result["status"] == "no_timer" and self.room.is_automated_room and not self.room.first_game_start:
        logger.warning("Next Round interrupt ")
        await set_wait_next_round(self, True)

      
        if getattr(self.room, "is_waiting_next_round", False) and self.room.is_automated_room:  #Change 1
            await start_tournament(self)
            await set_wait_next_round(self, False)
            return True            
            
        return True    
        
        
    elif result["status"] == "game_over":
        if hasattr(self, "fake_bet_task") and self.fake_bet_task:
            self.fake_bet_task.cancel()

        winside = await calculate_winner(self)
       # self.room.winner = winside.upper() if winside != "bothloss" else None
        self.room.winner = winside.upper() if winside and winside != "bothloss" else None
        await setwin(self)

        user_won_price = await calculate_and_save_bet_share(self)
        won_amount = user_won_price.get(self.user.id, Decimal('0.00'))
        from decimal import ROUND_DOWN
        formatted_amount = won_amount.quantize(Decimal('0.01'), rounding=ROUND_DOWN)

        user_has_bet = await database_sync_to_async(self.GameBet.objects.filter)(
            room=self.room,
            user=self.user,
            is_bot_placed=False)

        has_bet = await database_sync_to_async(user_has_bet.exists)()
        formatted_text = f"<br> You Won : {formatted_amount}" if has_bet else ""

        await self.send(text_data=json.dumps({
            'popup': f"Game Finished. {formatted_text}",
            'state': 'over',
            'winner': self.room.winner or "No Winner",
        }))
        if send_game_stat:
            await self.send_game_state()
            
            
        if self.room.is_automated_room and not self.room.is_next_auto_started: #Change 2
            if self.room.room_type == 'TOURNAMENT':
                await create_room_auto(self, tournament= True)
            else:
                await create_room_auto(self, tournament= False)
            self.room.is_next_auto_started = True

        return True

    elif result["status"] == "continue":
        userlen = len(self.active_real_users)
        from .bot import handle_bot_move, is_bot_turn
        if await is_bot_turn(self): # and self.room.is_automated_room
            
            import asyncio
            await asyncio.sleep(0.5)
            if not hasattr(self, 'task_asy_ref_bot'):     
                print("create bt task")
                self.task_asy_ref_bot = asyncio.create_task(handle_bot_move(self))    #create background bot task
        
        await self.send(text_data=json.dumps({
            'time_clock': result["remaining_time"],
            'round': result["round_number"],
            'match': result["match_number"],
            'max_rounds': result["max_rounds"],
            'max_time_per_round' : result["max_time_per_match"],
            'max_time_per_match': result["max_time_per_match"],
        }))
        return False
        
        

async def start_single_game(self,round_change=False):
    from .bot import handle_bot_move,is_user_bot,is_bot_turn
    if self.room.is_over:
        await self.send(text_data=json.dumps({'error': f"Game over."}))
        return

    room_tz = pytz.timezone(self.room.timezone)
    now_time = now().astimezone(room_tz)
    
    
    if not self.room.first_game_start and not round_change:
       # print('gfmsdohnxdjkfgnodxg=================')
        
        self.room.is_waiting_next_round = False 
        self.room.start_datetime = now_time
        self.room.match_start_datetime = now_time
       # from .tournaments import dotournament
        #self.user_change_needed = True
        #await dotournament(self)
        self.room.first_game_start = True
        await saverm(self)
        await savegm(self)
        await start_next_round_db(self)

    #await self.send_game_state()        
    if round_change:
        print('round change requested')
        
      
    
    

    
    
@database_sync_to_async
def deduct_ref_share(self):
    print('Deduction called')
    player_rooms = self.room.participants.filter(role='PLAYER')  # only players participants is related name of db see models py
    
    
    for pr in player_rooms:
        profile = pr.user.profile
        total_amount = Decimal('0')
        ref = profile.referrer
        refz_ref = ref.profile.referrer if ref else None
        refz_refz_ref = refz_ref.profile.referrer if refz_ref else None
        
        if ref:
            total_amount += Decimal('8')
        if refz_ref:
            total_amount += Decimal('2')
        if refz_refz_ref:
            total_amount += Decimal('1')
            
            
        if profile.wallet_balance > total_amount and not profile.is_bot:     
            profile.wallet_balance -= total_amount
            profile.save()
            
            if ref:
                 ref.profile.wallet_balance += Decimal('8')
                 ref.profile.save()
                 
            if refz_ref:
                 refz_ref.profile.wallet_balance += Decimal('2')
                 refz_ref.profile.save()
                 
            if refz_refz_ref:
                 refz_refz_ref.profile.wallet_balance += Decimal('1')
                 refz_refz_ref.profile.save()
        

        

async def start_tournament(self):
    from .tournaments import reset_all_matches_played
    
    from .bot import handle_bot_move,is_user_bot,is_bot_turn

        
    if self.room.is_over:
        await self.send(text_data=json.dumps({'error': f"Game over."}))
        return
        
    room_tz = pytz.timezone(self.room.timezone)
    now_time = now().astimezone(room_tz)
    next_round_set = False
    waiting_agent_btn = getattr(self, "set_wait_next_round", False) 
    
    
    if not waiting_agent_btn and self.room.first_game_start:
        await start_next_round_db(self)
        next_round_set = True
        
    if not self.room.first_game_start:
        await deduct_ref_share(self)
        
    self.room.is_waiting_next_round = False   
    self.room.start_datetime = now_time
    self.room.match_start_datetime = now_time
    from .tournaments import dotournament
    self.user_change_needed = True
    await dotournament(self)
    
    self.room.first_game_start = True
    
    await saverm(self)
    await savegm(self)
    await reset_all_matches_played(self)
    if not next_round_set:
        await self.send(text_data=json.dumps({'popup': f"Game Started."}))
        #await self.send_game_state()
        await start_next_round_db(self)

        
        
#    if await is_bot_turn(self):
#        print('botz started from start tournament agent func')
#        import asyncio
#        self.task_asy_ref_bot =   asyncio.create_task(handle_bot_move(self))
        
    
        
    
    



@database_sync_to_async
def is_time_control_enabled(self):
    """Check if time control is enabled for the room."""
    return self.Room.objects.filter(id=self.room_id, time_control_seconds__isnull=False).exists()



    

async def on_no_move_activity(self):
    if not self.room.start_datetime:
        return
    if self.room.is_waiting_next_round:
        print('start time',self.room.start_datetime)
        return
    user = self.user
    room_tz = pytz.timezone(self.room.timezone)

    # Safety checks
    if not self.room or self.room.is_over: # or not self.room.last_move_date
        return
    if not self.room.last_move_date:
        self.room.last_move_date = self.room.start_datetime.astimezone(room_tz)
        
    last_move_time = self.room.last_move_date.astimezone(room_tz)
    now_time = now().astimezone(room_tz)
    inactivity_duration = (now_time - last_move_time).total_seconds()

    # Notify but take no action yet
    if 15 < inactivity_duration < 30:
        print('Still early, notify only')

        import chess
        board = chess.Board(self.game.fen) if self.game.fen and self.game.fen != "startpos" else chess.Board()
        turn_color = board.turn  # True=White to move, False=Black to move

        # Identify who is inactive (the player to move)
        inactive_user_id = None
        if turn_color:
            inactive_user_id = self.game.player_white.id if self.game.player_white else None
        else:
            inactive_user_id = self.game.player_black.id if self.game.player_black else None

        if inactive_user_id:
            await send_to_one_user(inactive_user_id, f"Warning! You have been inactive for 15 seconds in room {self.room.name}  (#ID {self.room.id}). Please make your move.")
        return

    print('Stepping to inactivity handling logic')

    player_white_id = self.game.player_white.id if self.game.player_white else None
    player_black_id = self.game.player_black.id if self.game.player_black else None

    from .utils import is_user_online
    white_online = await is_user_online(self, player_white_id)
    black_online = await is_user_online(self, player_black_id)
    timeout_game_over = False
    if inactivity_duration >= 30:
        print('Handling full 30-second inactivity case')

        self.start_next_match_intrpt = False
        if white_online and black_online:
            import chess
            board = chess.Board(self.game.fen) if self.game.fen and self.game.fen != "startpos" else chess.Board()
            turn_color = board.turn  # True = white, False = black

            if turn_color:  # White to move  
                if timeout_game_over:
                    self.room.round_number = self.room.round_type
                    self.room.winner = "BLACK"
                    await setwin(self)
                    
                else:
                    await update_points(self, self.room.round_number,self.room.current_match_number, 0, 1)
                    self.start_next_match_intrpt = True
                    
                                       
            elif not turn_color:  # Black to move
                if timeout_game_over:
                    self.room.round_number = self.room.round_type
                    self.room.winner = "WHITE"
                    
                    
                    await setwin(self)
                else:
                    await update_points(self, self.room.round_number,self.room.current_match_number, 1, 0)
                    self.start_next_match_intrpt = True
                    #Next Match or round

        elif not white_online and black_online:
            self.room.round_number = self.room.round_type
            self.room.winner = "BLACK"
            
            await setwin(self)
     

        elif not black_online and white_online:
            self.room.round_number = self.room.round_type
            self.room.winner = "WHITE"
            await setwin(self)
           
            
       # self.start_next_match_intrpt = True    
        print('winner tc:',self.room.winner) #ok, working

        if await is_time_control_enabled(self):
            lock_stat = await handle_time_expiry_and_round_restart(self)
        




@database_sync_to_async
def set_wait_next_round(self,arg):
    if not self.room.is_waiting_next_round:
        self.room.is_waiting_next_round = arg
        
        self.room.save()
        if arg:
            self.room.start_datetime = None







async def send_to_one_user(user_id, message):
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f"user_{user_id}",
        {
            "type": "global_notif",  # Triggers your Consumer's send_global method
            "popup": message
        }
    ) 

























# Piece values (material scoring)
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0  # King not counted in material
}

def score_board(board):
    white_score = 0
    black_score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            value = PIECE_VALUES[piece.piece_type]
            if piece.color == chess.WHITE:
                white_score += value
            else:
                black_score += value
    return white_score, black_score

def determine_material_winner(white_material, black_material):
    if white_material > black_material:
        return 1, 0
    elif black_material > white_material:
        return 0, 1
    else:
        return 0.5, 0.5  # or return 0, 0 if you prefer
        
@database_sync_to_async
def delete_sys_bots_in_room(self):
    # Get all PlayerRoom entries in this room where the user is a system bot
    sys_bot_users = self.User.objects.filter(
        profile__is_auto_sys=True,
        playerroom__room=self.room
    ).distinct()

    sys_bot_users.delete()
    







# === BET REWARDS CALCULATION ONLY (no DB changes) ===
@database_sync_to_async
def calculate_bet_rewards(self):
    

    commission_rate = Decimal('15')
    commission_global = True  # can be dynamic from room/game settings
    commission_bet_wise = False

    real_bets = self.GameBet.objects.filter(room=self.room, is_bot_placed=False)
    bet_summary = real_bets.values('side').annotate(total_amount=Sum('amount'))

    bets_white = next((b['total_amount'] for b in bet_summary if b['side'] == 'White'), Decimal('0.00'))
    bets_black = next((b['total_amount'] for b in bet_summary if b['side'] == 'Black'), Decimal('0.00'))
    total_real_bets = bets_white + bets_black
    if not self.room.winner or self.room.winner not in ['WHITE', 'BLACK']:
        return {}
    winner_bets = real_bets.filter(side=self.room.winner)
    user_rewards = {}

    if commission_global:
        commission_amount = (total_real_bets * commission_rate) / Decimal('100.00')
        distributable_amount = total_real_bets - commission_amount

        total_winning_bets = winner_bets.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        for bet in winner_bets:
            user_id = bet.user.id
            user_bet = bet.amount
            if total_winning_bets > 0:
                share_percentage = user_bet / total_winning_bets
                reward = share_percentage * distributable_amount
                user_rewards[user_id] = user_rewards.get(user_id, Decimal('0.00')) + reward

    elif commission_bet_wise:
        for bet in winner_bets:
            user_id = bet.user.id
            bet_commission = (bet.amount * commission_rate) / Decimal('100.00')
            net_bet_amount = bet.amount - bet_commission
            user_rewards[user_id] = user_rewards.get(user_id, Decimal('0.00')) + net_bet_amount

    else:
        total_winning_bets = winner_bets.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        for bet in winner_bets:
            user_id = bet.user.id
            user_bet = bet.amount
            if total_winning_bets > 0:
                share_percentage = user_bet / total_winning_bets
                reward = share_percentage * total_real_bets
                user_rewards[user_id] = user_rewards.get(user_id, Decimal('0.00')) + reward

    return user_rewards






# === SAVE COMMISSION & UPDATE WALLETS (takes rewards dict) ===
@database_sync_to_async
def save_bet_rewards_and_commission(self, user_rewards):
    from manager.models import CompanyCommission
    from account.models import Profile
    commission_rate = Decimal('15')
    commission_global = True  # should be consistent with calculation
    commission_bet_wise = False

    real_bets = self.GameBet.objects.filter(room=self.room, is_bot_placed=False)
    bet_summary = real_bets.values('side').annotate(total_amount=Sum('amount'))

    bets_white = next((b['total_amount'] for b in bet_summary if b['side'] == 'White'), Decimal('0.00'))
    bets_black = next((b['total_amount'] for b in bet_summary if b['side'] == 'Black'), Decimal('0.00'))
    total_real_bets = bets_white + bets_black
    
    
    # No winner: company takes all bets as commission
    if not self.room.winner or self.room.winner not in ['WHITE', 'BLACK']:
        CompanyCommission.objects.create(
            room=self.room,
            game=self.game,
            total_bets=total_real_bets,
            commission_rate=Decimal('100.00'),
            commission_amount=total_real_bets
        )
        return
        
        
    if commission_global:
        commission_amount = (total_real_bets * commission_rate) / Decimal('100.00')
    elif commission_bet_wise:
        commission_amount = sum(
            (bet.amount * commission_rate) / Decimal('100.00') for bet in real_bets.filter(side=self.room.winner)
        )
    else:
        commission_amount = Decimal('0.00')

    CompanyCommission.objects.create(
        room=self.room,
        game=self.game,
        total_bets=total_real_bets,
        commission_rate=commission_rate,
        commission_amount=commission_amount
    )

    for user_id, reward_amount in user_rewards.items():
        user_profile = Profile.objects.select_related('user').get(user__id=user_id)
        if self.sec_wal_payout:
            user_profile.sec_wallet_balance += reward_amount
        else:
            user_profile.wallet_balance += reward_amount
        self.room.is_bet_shared = True
        self.room.save()
        user_profile.save()





@database_sync_to_async
def markrating_loser(self):
    if self.room.winner == "WHITE":
        loser_side = "black"
    elif self.room.winner == "BLACK":
        loser_side = "white"
    else:
        return  # no valid loser

    player_room = self.PlayerRoom.objects.filter(
        room=self.room,
        color_group=loser_side,
        role="PLAYER"
    ).first()

    if not player_room:
        return

    profile = player_room.user.profile
    profile.rating = max(profile.rating - 5, 0)  # prevent negative rating
    profile.save()



@database_sync_to_async
def markrating_winner(self):
    if self.room.winner == "WHITE":
        winner_side = "white"
    elif self.room.winner == "BLACK":
        winner_side = "black"
    else:
        return  # no valid winner

    player_room = self.PlayerRoom.objects.filter(
        room=self.room,
        color_group=winner_side,
        role="PLAYER"
    ).first()

    if not player_room:
        return

    profile = player_room.user.profile
    profile.rating += 5
    profile.save()



# === WRAPPER: calculate + save + return current user reward ===
async def calculate_and_save_bet_share(self):
    saving = False
    self.sec_wal_payout = False
    if self.room.is_signal:
        self.sec_wal_payout = True
    if not self.room.is_bet_shared:
        await markrating_winner(self)
        saving = True
        
    user_rewards = await calculate_bet_rewards(self)
    if saving:
        await save_bet_rewards_and_commission(self,user_rewards)
    current_user_reward = user_rewards.get(self.user.id, Decimal('0.00'))
    return {self.user.id: current_user_reward}










@database_sync_to_async
def savegm(self):
    """Save the current game object."""
    self.game.save()
    

@database_sync_to_async
def update_points(self, round_number, match_number, white_point, black_point):
    """
    Updates points per round and per match to prevent overwriting previous matches.
    """
    points = self.room.points or {}
    round_key = str(round_number)
    
    if round_key not in points:
        points[round_key] = {}
    
    # Save each match separately
    points[round_key][str(match_number)] = {"white": white_point, "black": black_point}
    
    self.room.points = points
    self.room.save()

    
@database_sync_to_async
def update_points2(self, round_number, white_point, black_point):
    points = self.room.points or {}
    points[str(round_number)] = {"white": white_point, "black": black_point}
    self.room.points = points
    self.room.save()

@database_sync_to_async
def calculate_winner(self):
    points = self.room.points or {}
    round_type = self.room.round_type

    win_white = 0
    win_black = 0
    total_white_points = 0
    total_black_points = 0

    for round_num, matches in points.items():
        round_white = 0
        round_black = 0

        # Sum all matches in this round
        for match_num, score in matches.items():
            white = score.get("white", 0)
            black = score.get("black", 0)
            round_white += white
            round_black += black

        total_white_points += round_white
        total_black_points += round_black

        if round_white > round_black:
            win_white += 1
        elif round_black > round_white:
            win_black += 1

    needed_wins = (round_type // 2) + 1

    if win_white >= needed_wins:
        return "white"
    elif win_black >= needed_wins:
        return "black"
    elif len(points) >= round_type:
        # No one got required wins, fallback to total points
        if total_white_points > total_black_points:
            return "white"
        elif total_black_points > total_white_points:
            return "black"
        else:
            return "bothloss"
    else:
        return None


@database_sync_to_async
def calculate_winnerold_2(self):
    points = self.room.points or {}
    round_type = self.room.round_type

    win_white = 0
    win_black = 0
    total_white_points = 0
    total_black_points = 0

    for round_num, score in points.items():
        white = score.get("white", 0)
        black = score.get("black", 0)

        total_white_points += white
        total_black_points += black

        if white > black:
            win_white += 1
        elif black > white:
            win_black += 1

    needed_wins = (round_type // 2) + 1

    if win_white >= needed_wins:
        return "white"
    elif win_black >= needed_wins:
        return "black"
    elif len(points) >= round_type:
        # No one got required wins, fallback to total points
        if total_white_points > total_black_points:
            return "white"
        elif total_black_points > total_white_points:
            return "black"
        else:
            return "bothloss"
    else:
        return None




@database_sync_to_async
def saverm(self):
    """Save the current game object."""
    self.room.save()


@database_sync_to_async
def setwin(self):
   # print('setwin called')
    if not self.room.is_over:
        self.room.is_over = True
        self.room.save()






async def on_checkmate(self):
    if await is_time_control_enabled(self):
        lock_stat = await handle_time_expiry_and_round_restart(self)   
    pass