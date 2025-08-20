from .utils import get_players_for_color,set_game_current_turn_player,set_game_player,get_user_by_id
import random
from channels.db import database_sync_to_async


               
    
async def round_robbin_tournament(self):

   #print('accessed tmt with ',self.room.is_waiting_next_round)
   if not getattr(self, "user_change_needed", False):
       return
   #print('accessed tmt ',self.user_change_needed)
   if self.room.is_waiting_next_round:
       return
        
        
   print('-----------------------RR Requested---------------------')
   for match in self.room.match_pairs:
        if not match.get('played', False):
            print("-----------------RR Done-------------------------")
            white_user = await get_user_by_id(self,match['white'])
            black_user = await get_user_by_id(self,match['black'])

            await set_game_player(self, color='white', user=white_user)
            await set_game_player(self, color='black', user=black_user)
            
            self.user_change_needed = False

            print(f"Match started: White={white_user}, Black={black_user}")
            return  # Stop after setting one match



    #print('Round is over')


@database_sync_to_async
def is_user_in_match_pairs(self, user_id):
    if not self.room.match_pairs:
        return False
    for pair in self.room.match_pairs:
        if pair.get('white') == user_id or pair.get('black') == user_id:
            return True
    return False


               


 
async def dotournament(self):
    if not self.room.match_pairs or self.room.total_matches == 0:
        await create_pairings(self)
    is_user_in_pairs = await is_user_in_match_pairs(self, self.user.id)
    #if not is_user_in_pairs:
    #    await create_pairings(self)
        
        
    await round_robbin_tournament(self) #round robbin method






@database_sync_to_async
def mark_match_played(self, white_id, black_id):
    print('called mark users as played')
    match_pairs = self.room.match_pairs or []
    updated = False

    for match in match_pairs:
        if match.get('white') == white_id and match.get('black') == black_id:
            match['played'] = True
            updated = True
            break

    if updated:
        #round_robbin_tournament(self)
       # print(match_pairs)
        self.room.match_pairs = match_pairs  # Reassign to trigger change tracking
        self.room.current_match_number = (self.room.current_match_number or 0) + 1
        self.room.save()
        self.user_change_needed = True





@database_sync_to_async
def create_pairings(self):
  #  print('#####################pairing function reached###########################')
    # Get white players in the room      where is_defeated= False
    white_players = list(
        self.PlayerRoom.objects.filter(
            room=self.room,
            role="PLAYER",
            color_group="white",
            is_defeated=False 
        ).order_by('id').values_list('user_id', flat=True)
    )

    # Get black players in the room
    black_players = list(
        self.PlayerRoom.objects.filter(
            room=self.room,
            role="PLAYER",
            color_group="black",
            is_defeated=False 
        ).order_by('id').values_list('user_id', flat=True)
    )

    pairs = []

    min_len = min(len(white_players), len(black_players))
    for i in range(min_len):
        pairs.append({
            'white': white_players[i],
            'black': black_players[i],
            'played': False
        })
   # print('pairs : ',pairs)

    self.room.match_pairs = pairs
    self.room.total_matches = len(pairs)
    self.room.played_matches = 0
    self.room.save()





async def reset_all_matches_played(self): 
    #print("♻️ Resetting all matches...")
    await create_pairings(self) #this not working


