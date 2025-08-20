import asyncio
import chess
import chess.engine
from channels.db import database_sync_to_async
from .utils import save_fen
from .tournaments import dotournament
from .timeman import handle_time_expiry_and_round_restart,is_time_control_enabled
from .timeman import on_checkmate


import random

STOCKFISH_PATH = "/usr/games/stockfish"


@database_sync_to_async
def is_user_bot(self, user_id):
    try:
        resp = self.User.objects.select_related('profile').get(id=user_id).profile.is_bot
        return resp
    except Exception:
        return False
        
async def is_bot_turn(self):
    is_white_turn = self.board.turn == chess.WHITE
    white_id = self.game.player_white.id
    black_id = self.game.player_black.id if self.game.player_black else None
    return await is_user_bot(self,white_id if is_white_turn else black_id)



# Utility function to clean all bot tasks
async def destroy_all_tasks(self):
    global BOT_TASKS
    if not BOT_TASKS:
        print("🧹 No global bot tasks to clean.")
        return

    print(f"🧹 Cleaning up GLOBAL tasks: {len(BOT_TASKS)}")
    for room_id, task in list(BOT_TASKS.items()):  # copy to avoid mutation issues
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        BOT_TASKS.pop(room_id, None)  # remove from global dict
        
    if hasattr(self, 'tasks_list'):
        print('🧹 Cleaning up tasks:', len(self.tasks_list))
        for task in self.tasks_list:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.tasks_list = [] # Clear the list after canceling all tasks
    else:
        self.tasks_list = []
        





# Utility function to clean all bot tasks
async def destroy_all_tasks2(self):
    if hasattr(self, 'tasks_list'):
        print('🧹 Cleaning up tasks:', len(self.tasks_list))
        for task in list(self.tasks_list):  # Make a copy to avoid modification during iteration
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self.tasks_list.remove(task)
    else:
        self.tasks_list = []



async def get_stockfish_move(board_fen, time_limit=0.1,skill_level=5):
   # print('bot engine root called')
    #SKill level 0 to 20  20 is strong
    loop = asyncio.get_event_loop()
    #time_limit = random.uniform(1, 10)  
    def run_engine():
        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
            board = chess.Board(board_fen)
            engine.configure({"Skill Level": skill_level})
            result = engine.play(board, chess.engine.Limit(time=time_limit))
            return result.move.uci()

    move_uci = await loop.run_in_executor(None, run_engine)
    return move_uci















async def _bot_move_logic(self):
    """
    Actual bot move logic. Runs inside a managed task.
    """
    self.destroy_all_tasks = destroy_all_tasks

    if not self.room.start_datetime:
        return

    userlen = len(self.active_real_users)
    if userlen < 1:
        print("no active users")
        await self.destroy_all_tasks(self)
        return

    if not hasattr(self, "tasks_list"):
        self.tasks_list = []
        self.tasks_list.append(self.task_asy_ref_bot)

    if await is_time_control_enabled(self):
        lock_stat = await handle_time_expiry_and_round_restart(self)
        if lock_stat:
            await self.destroy_all_tasks(self)
            return

    if self.room.is_waiting_next_round:
        await self.destroy_all_tasks(self)
        return

   # print("-------- BOT MOVE START -------")

    # Pick bot parameters
    time_limit_zn = random.uniform(1, 5)
    skill_l = random.uniform(4, 8)
    fake_asc_time = random.uniform(3, 8)

    if self.room.time_control_seconds and self.room.time_control_seconds < 300:
        time_limit_zn = random.uniform(1, 3)
        fake_asc_time = random.uniform(1, 2)
        skill_l = random.uniform(1, 2)

    # Force win condition
    if self.room.force_to_win_side:
        force_color = self.room.force_to_win_side.upper()  # 'WHITE' or 'BLACK'
        turn_color = "WHITE" if self.board.turn == chess.WHITE else "BLACK"

        if force_color == turn_color:
            time_limit_zn = random.uniform(3, 6)
            fake_asc_time = random.uniform(3, 4)
            skill_l = random.uniform(15, 18)
            if self.room.time_control_seconds and self.room.time_control_seconds < 300:
                fake_asc_time = random.uniform(3, 5)
                skill_l = random.uniform(15, 18)

        else:
            time_limit_zn = random.uniform(0.1, 0.2)
            fake_asc_time = random.uniform(3, 6)
            skill_l = random.uniform(0.5, 1.0)

    # Simulate "thinking"
    await asyncio.sleep(fake_asc_time)

    bot_move = None
    if not self.board.is_game_over():
        bot_move = await get_stockfish_move(self.board.fen(), time_limit_zn, skill_l)

    if not bot_move:
        await self.destroy_all_tasks(self)
        print("++++++++++++++++ BOT EXITED DUE TO INTERRUPT 1 +++++++++++++++++++++++++++")
        return

    move = chess.Move.from_uci(bot_move)

    # Apply move
    self.board.push(move)
    await save_fen(self, self.board.fen())

    # Broadcast
    await self.channel_layer.group_send(
        self.room_group_name,
        {
            "type": "chess_move",
            "move": bot_move,
            "fen": self.board.fen(),
            "legal_moves": [move.uci() for move in self.board.legal_moves],
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "check": self.board.is_check(),
            "checkmate": self.board.is_checkmate(),
            "stalemate": self.board.is_stalemate(),
        },
    )

    await on_checkmate(self)

    if self.room.is_waiting_next_round:
        await self.destroy_all_tasks(self)
        print("++++++++++++++++ BOT EXITED DUE TO INTERRUPT 3 +++++++++++++++++++++++++++")
        return

    # Tournament continuation
    if not self.board.is_game_over() and await is_bot_turn(self): # and self.room.room_type == "TOURNAMENT"
        await dotournament(self)
        await asyncio.sleep(0.5)
        await handle_bot_move(self)
    else:
        await self.destroy_all_tasks(self)
        print("++++++++++++++++ BOT EXITED DUE TO INTERRUPT 4 +++++++++++++++++++++++++++")
        return




# Global task table for bot tasks per room
BOT_TASKS = {}






async def handle_bot_move(self):
    """
    Entry point for bot moves.
    Ensures only one bot task per room by cancelling old tasks before starting new one.
    """
    
    self.destroy_all_tasks  =  destroy_all_tasks
    if not self.room.start_datetime:
        return
    if not hasattr(self, 'tasks_list'):
        self.tasks_list = []
        self.tasks_list.append(self.task_asy_ref_bot)
    userlen = len(self.active_real_users)
    if userlen<1:
        print('no active users')
        await self.destroy_all_tasks(self) 
        
        
    global BOT_TASKS
    #print(BOT_TASKS)

    # Cancel old bot task if still alive
    if self.room.id in BOT_TASKS:
        old_task = BOT_TASKS[self.room.id]
        if not old_task.done():
            print(f"⚠️ Cancelling old bot task for room {self.room.id}")
            old_task.cancel()
            try:
                await old_task
            except asyncio.CancelledError:
                pass

    # Register new bot task
    BOT_TASKS[self.room.id] = asyncio.create_task(_bot_move_logic(self))






























    
async def handle_bot_move2(self):
    self.destroy_all_tasks  =  destroy_all_tasks
    if not self.room.start_datetime:
        return
    if not hasattr(self, 'tasks_list'):
        self.tasks_list = []
        self.tasks_list.append(self.task_asy_ref_bot)
    userlen = len(self.active_real_users)
    if userlen<1:
        print('no active users')
        await self.destroy_all_tasks(self) 
        

    
    
    
    if await is_time_control_enabled(self):
        lock_stat = await handle_time_expiry_and_round_restart(self)
        if lock_stat:
            await self.destroy_all_tasks(self) 
            return

    if self.room.is_waiting_next_round:
        await self.destroy_all_tasks(self)
    print('-------- BOT MOVE START -------')
    
    current_fen = self.board.fen()
    # Default time/skill
    time_limit_zn = random.uniform(1, 8)  # Normal speed
    skill_l = random.uniform(4, 8)        # Normal skill
    fake_asc_time = random.uniform(3, 8) 
    
    
    if self.room.time_control_seconds and self.room.time_control_seconds < 300:
        time_limit_zn = random.uniform(1, 2)
        fake_asc_time =  0.5 #random.uniform(1, 2) 
        skill_l = random.uniform(5, 8)
       
    
    # Check force win condition
    if self.room.force_to_win_side:
        force_color = self.room.force_to_win_side.upper()  # 'WHITE' or 'BLACK'
        turn_color = 'WHITE' if self.board.turn == chess.WHITE else 'BLACK'
     

        if force_color == turn_color:
            #print('✅ Forcing win for', force_color)
            time_limit_zn = random.uniform(3, 6)
            fake_asc_time = random.uniform(3, 4) 
            skill_l = random.uniform(15, 20)
            if self.room.time_control_seconds and self.room.time_control_seconds < 300:
                fake_asc_time = random.uniform(3, 10) 
                skill_l = random.uniform(15, 18)
        else:
            time_limit_zn = random.uniform(0.4, 5.4) 
            fake_asc_time = random.uniform(0, 6) 
            skill_l = random.uniform(0.5, 2.3)
            
            
            
    await asyncio.sleep(fake_asc_time)        
    bot_move = None
    if not self.board.is_game_over():
        bot_move = await get_stockfish_move(self.board.fen(),time_limit_zn,skill_l  )
    if not bot_move:
        await self.destroy_all_tasks(self) 
        return

    move = chess.Move.from_uci(bot_move)

        
        
#test lock here..   
    if await is_time_control_enabled(self):
        lock_stat = await handle_time_expiry_and_round_restart(self)
        if lock_stat:
            await self.destroy_all_tasks(self) 
            return
#    if self.board.fen() != current_fen:
#        await handle_bot_move(self)
#        print('⚠️ Board FEN changed during bot thinking — skipping move to avoid desync')
#        return
#    else:
#        self.board.push(move)
    self.board.push(move)    
    await save_fen(self,self.board.fen())


    await self.channel_layer.group_send(
        self.room_group_name,
        {
            'type': 'chess_move',
            'move': bot_move,
            'fen': self.board.fen(),
            'legal_moves': [move.uci() for move in self.board.legal_moves],
            'turn': 'white' if self.board.turn == chess.WHITE else 'black',
            'check': self.board.is_check(),
            'checkmate': self.board.is_checkmate(),
            'stalemate': self.board.is_stalemate(),
        }
    )
    await on_checkmate(self)

    

    
    if self.room.is_waiting_next_round:
        await self.destroy_all_tasks(self)
        
    if not self.board.is_game_over() and self.room.room_type == 'TOURNAMENT' and await is_bot_turn(self):
        await dotournament(self)
        await asyncio.sleep(0.5) 
        await handle_bot_move(self)
    else:
        await self.destroy_all_tasks(self) 
              












    
    
    
    
async def handle_bot_move4(self):
    self.destroy_all_tasks  =  destroy_all_tasks
    if not self.room.start_datetime:
        return

    userlen = len(self.active_real_users)
    if userlen<1:
        print('no active users')
        await self.destroy_all_tasks(self) 
        return


    if not hasattr(self, 'tasks_list'):
        self.tasks_list = []
        self.tasks_list.append(self.task_asy_ref_bot)        

    
    
    
    if await is_time_control_enabled(self):
        lock_stat = await handle_time_expiry_and_round_restart(self)
        if lock_stat:
            await self.destroy_all_tasks(self) 
            return

    if self.room.is_waiting_next_round:
        await self.destroy_all_tasks(self)
        return
    print('-------- BOT MOVE START -------')
    
    current_fen = self.board.fen()
    # Default time/skill
    time_limit_zn = random.uniform(1, 8)  # Normal speed
    skill_l = random.uniform(4, 8)        # Normal skill
    fake_asc_time = random.uniform(3, 8) 
    
    
    if self.room.time_control_seconds and self.room.time_control_seconds < 300:
        time_limit_zn = random.uniform(1, 2)
        fake_asc_time = random.uniform(1, 3) 
        skill_l = random.uniform(5, 8)
       
    
    # Check force win condition
    if self.room.force_to_win_side:
        force_color = self.room.force_to_win_side.upper()  # 'WHITE' or 'BLACK'
        turn_color = 'WHITE' if self.board.turn == chess.WHITE else 'BLACK'
     

        if force_color == turn_color:
            #print('✅ Forcing win for', force_color)
            time_limit_zn = random.uniform(3, 6)
            fake_asc_time = random.uniform(3, 4) 
            skill_l = random.uniform(15, 20)
            if self.room.time_control_seconds and self.room.time_control_seconds < 300:
                fake_asc_time = random.uniform(3, 10) 
                skill_l = random.uniform(15, 18)
        else:
            time_limit_zn = random.uniform(0.4, 5.4) 
            fake_asc_time = random.uniform(2, 6) 
            skill_l = random.uniform(0.5, 2.3)
            
            
            
    await asyncio.sleep(fake_asc_time)        
    bot_move = None
    if not self.board.is_game_over():
        bot_move = await get_stockfish_move(self.board.fen(),time_limit_zn,skill_l  )
    if not bot_move:
        await self.destroy_all_tasks(self) 
        print('++++++++++++++++  BOT EXITED DUE TO INTERRUPT  1 +++++++++++++++++++++++++++')
        return

    move = chess.Move.from_uci(bot_move)

        
 #   if await is_time_control_enabled(self):
 #       lock_stat = await handle_time_expiry_and_round_restart(self)
 #       if lock_stat:
 #           await self.destroy_all_tasks(self) 
 #           print('++++++++++++++++  BOT EXITED DUE TO INTERRUPT 2  +++++++++++++++++++++++++++')
 #           return

    self.board.push(move)    
    await save_fen(self,self.board.fen())


    await self.channel_layer.group_send(
        self.room_group_name,
        {
            'type': 'chess_move',
            'move': bot_move,
            'fen': self.board.fen(),
            'legal_moves': [move.uci() for move in self.board.legal_moves],
            'turn': 'white' if self.board.turn == chess.WHITE else 'black',
            'check': self.board.is_check(),
            'checkmate': self.board.is_checkmate(),
            'stalemate': self.board.is_stalemate(),
        }
    )
    await on_checkmate(self)
    
    if self.room.is_waiting_next_round:
        await self.destroy_all_tasks(self)
        print('++++++++++++++++  BOT EXITED DUE TO INTERRUPT 3 +++++++++++++++++++++++++++')
        return
        
    if not self.board.is_game_over() and self.room.room_type == 'TOURNAMENT' and await is_bot_turn(self):
        await dotournament(self)
        await asyncio.sleep(0.5) 
        await handle_bot_move(self)
    else:
        await self.destroy_all_tasks(self)  
        print('++++++++++++++++  BOT EXITED DUE TO INTERRUPT 4  +++++++++++++++++++++++++++')        
        return
              

