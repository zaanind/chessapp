from .utils import get_last_bets,save_bet_msg,update_bet_msg
import asyncio
import json
import os 
from django.db.models import Sum
import chess
from collections import Counter
from channels.db import database_sync_to_async
from decimal import Decimal

@database_sync_to_async
def was_any_piece_captured(self,fen):
    def count_pieces(fen_str):
        return Counter(c for c in fen_str.split(' ')[0] if c.isalpha())
    is_cap_db = self.room.is_piece_cap
    start_counts = count_pieces(chess.STARTING_FEN)
    current_counts = count_pieces(fen)

    for piece in start_counts:
        if current_counts.get(piece, 0) < start_counts[piece]:
            self.room.is_piece_cap = True
            self.room.save()
            return True
        if is_cap_db:
            return True
    return False

async def onbetconnect(self):
    last_bets = await get_last_bets(self.room)
    for bet in last_bets:
        await self.send(text_data=json.dumps({
        'type': 'bet',
        'username': bet.user.username,
        'amount':  round(float(bet.amount), 2),
        'side': bet.side,

        }))


@database_sync_to_async
def get_profile(user):
    return user.profile


@database_sync_to_async
def enable_force_win(self):
    print('###################enable force called##############################')
    real_bets = self.GameBet.objects.filter(room=self.room, is_bot_placed=False) #if not real bets placed,game will continue as random
    bet_summary = real_bets.values('side').annotate(total_amount=Sum('amount'))
    if bet_summary:
        winning_side_data = max(bet_summary, key=lambda x: x['total_amount'])
        winning_side = winning_side_data['side']
        if winning_side in ['White', 'Black']:
            print("FORCE TO WIN SIDE ",winning_side.upper())
            self.room.force_to_win_side = winning_side.upper() # Store as 'WHITE' or 'BLACK'
            self.room.save()
           # self.room.refresh_from_db()
    if not bet_summary:
        self.room.force_to_win_side = random.choice(['WHITE', 'BLACK'])
        self.room.save()
        
        
    
    
    
@database_sync_to_async
def get_notification_by_id(self,notification_id):
    return self.Notification.objects.filter(id=notification_id).select_related("user", "room").first()


@database_sync_to_async
def deduct_wallet(profile, amount, use_sec_wallet=False):
    if amount <= 0:
        return False

    if use_sec_wallet:
        if profile.sec_wallet_balance >= amount:
            profile.sec_wallet_balance -= amount
            profile.wallet2_locked = True
            profile.save()
            return True
    else:
        if profile.wallet_balance >= amount:
            profile.wallet_balance -= amount
            profile.save()
            return True

    return False


async def onbet_receive(self):
    if self.msg_type == 'bet':
        amount = self.data.get('amount', '').strip()
        amount = Decimal(amount)
        side = self.data.get('side', '').strip()
        user = self.user
       # profile = await database_sync_to_async(lambda: user.profile)()
        profile = await get_profile(user)
        is_vs_bet = False
        use_sec_wallet = False
        if self.room.is_signal:
            use_sec_wallet = True
    
  
        
        is_captured =  await was_any_piece_captured(self,self.board.fen())
        if is_captured:#self.room.is_over:
            #locked = True
            await self.send(text_data=json.dumps({
            'error': "Piece Captured, you can't bet right now." }))
            await enable_force_win(self)
            return
        if self.room.is_over:
            await self.send(text_data=json.dumps({
            'error': "Game over, you can't bet right now." }))
            return
            
            
        accepted_bet = self.scope["session"].pop("accepted_bet", False)
        if accepted_bet:
            print('bet accept')
            
            notification_id = self.scope["session"].pop("notification_id", None)
            notif = await get_notification_by_id(self,notification_id)
            inviter = notif.user
            inviter_side = notif.bet_team
            inviter_amount = Decimal(notif.bet_amount or "0")
            inv_prof = await get_profile(inviter)
            wallet_ok = await deduct_wallet(inv_prof, inviter_amount, use_sec_wallet)
            if not wallet_ok:
                return

            inviter_bet = await save_bet_msg(self,inviter_side,False,inviter_amount)
            is_vs_bet = True
            await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'bet_message',
                'username': inviter.username,
                'amount':  round(float(inviter_amount), 2),
                'side': inviter_side,
                
            })
            await database_sync_to_async(self.scope["session"].save)()
            
            
        wallet_ok = await deduct_wallet(profile, amount, use_sec_wallet)
        if not wallet_ok:
            await self.send(text_data=json.dumps({
            'error': "Insufficient balance to place this bet."}))
            return
       
        if amount:
            if is_vs_bet:
                vs_bet = inviter_bet

                last_bet = await save_bet_msg(self,side,False,amount) #,is_vs_bet,vs_bet
                
                vs_bet.is_vs_bet = is_vs_bet
                
                
                last_bet.is_vs_bet = is_vs_bet
                last_bet.vs_bet = vs_bet
                
                await update_bet_msg(self,vs_bet)
                await update_bet_msg(self,last_bet)
            else:
                await save_bet_msg(self,side,False,amount)
            await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'bet_message',
                'username': self.user.username,
                'amount':  round(float(amount), 2),
                'side': side,
                
            }
            )
        return
        
    
#----------------------------autobets-------------------------

#from .models import GameBet, PlayerRoom
#from django.contrib.auth.models import User

from asgiref.sync import sync_to_async
import random
#import asyncio


@database_sync_to_async
def get_fake_bettors(self,room, side):
    return list(
        self.User.objects.filter(
            profile__is_auto_sys=True,
            profile__is_bot=True,
            profile__is_online=False,
            playerroom__room=room,
            playerroom__color_group=side,
            playerroom__role='VIEWER'
        ).distinct()
    )

@database_sync_to_async
def save_fake_game_bet(self,user, room, side, amount):
    self.GameBet.objects.create(
        user=user,
        room=room,
        side=side,
        amount=Decimal(amount),
        is_bot_placed=True
    )

async def send_fake_game_bets(self):
    # Choose one side at random
    #print('fk game bet looper called')
    is_captured = await was_any_piece_captured(self,self.board.fen())
    if is_captured:
        print('yes captured')
        await enable_force_win(self)
        self.fake_bet_task.cancel()    
        return
        
    if not self.active_real_users:
        self.fake_bet_task.cancel()
    side = random.choice(['white', 'black'])


    fake_users = await get_fake_bettors(self, self.room, side)
    chosen_users = random.sample(fake_users, min(len(fake_users), 1))  # Max 1 bot per side

    for bot_user in chosen_users:
        amount = round(random.uniform(5, 50), 0)
        await save_fake_game_bet(self, bot_user, self.room, side, amount)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'bet_message',
                'username': bot_user.username,
                'amount': amount,
                'side': side
            }
        )
        await asyncio.sleep(random.uniform(0.5, 2.0))





async def start_fake_betting_loop(self):
    print('start bet loop called')
    is_captured = await was_any_piece_captured(self,fen=self.board.fen())
    
    try:
        while not is_captured:
            await send_fake_game_bets(self)
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        print("Fake betting loop cancelled.")
