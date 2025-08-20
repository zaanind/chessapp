from django.shortcuts import render, redirect, get_object_or_404
import uuid

from itertools import combinations
from datetime import datetime, timedelta
from django.utils.timezone import now
from itertools import combinations
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Game, Room, PlayerRoom,TournamentJoinRequest,Notification  
import random
from django.utils.timezone import now, localtime

import pytz

from django.http import JsonResponse
from django.db.models import Count, Q
from django.urls import reverse
from .vut.users import get_random_participants
from .consumersmod.dummygame import generate_fake_game_info

@login_required
def api_search_users(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    users = User.objects.filter(
        Q(username__icontains=query)
    ).exclude(id=request.user.id).order_by('username')[:10]

    results = [{'id': user.id, 'username': user.username} for user in users]
    return JsonResponse({'results': results})


@login_required
def notification_redirect_view(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id)

    if notif.to_user != request.user:
        return HttpResponseForbidden("You don't own this notification.")

    # Mark as read
    if not notif.is_read:
        notif.is_read = True
        notif.save()

    # Handle specific system types
    if notif.system == 'BETINV':
        request.session['accepted_bet'] = True
        opposite_team = 'Black' if notif.bet_team == 'White' else 'White'
        request.session['team'] = opposite_team
        request.session['notification_id'] = notif_id

    # Redirect to room if present, else home
    if notif.room:     
        return redirect(reverse('chessboard_watch', args=[notif.room.id]))  # customize 'room_view'
    else:
        return redirect(reverse('home'))  # fallback



def is_game_ready(game,user):
    room = game.room
    room_tz = pytz.timezone(room.timezone)

    
    if room.starting_datetime is not None:
        room_start = room.starting_datetime.astimezone(room_tz)
        current_time = now().astimezone(room_tz)
        print(room_start)
        print(current_time)
        print(current_time - room_start)
        if room_start < current_time:
            print('looooo')
            return True
    else:
        print('room.start_datetime is None')
        return False  # or False depending on your logic

    MIN_PLAYERS_PER_COLOR = 1
    room = game.room

    color_counts_qs = PlayerRoom.objects.filter(
        room=room,
        role='PLAYER'
    ).values('color_group').annotate(count=Count('id'))

    counts = {'white': 0, 'black': 0}
    for c in color_counts_qs:
        counts[c['color_group']] = c['count']

    return counts['white'] >= MIN_PLAYERS_PER_COLOR and counts['black'] >= MIN_PLAYERS_PER_COLOR


@login_required
def chessboard_view(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    game = get_object_or_404(Game, room=room)
    if not is_game_ready(game, request.user):
        print('yanna denne n pko true')
        return redirect('home')
    is_agent = False
    if room.room_type == 'TOURNAMENT':
        is_agent = (room.created_by_id == request.user.id)
    return render(request, 'chessgame/board.html', {'game_id': room.id,
    'is_view_only': False,
    'is_agent': is_agent,
    'is_tournament': room.room_type == 'TOURNAMENT',
    'room_id' : room.id, 
    })

@login_required
def watch_game_view(request, room_id):
    room = get_object_or_404(Room,  id=room_id)
    game = room.game
    
    bet_challenge = request.session.get('accepted_bet', False) #request.session.pop('accepted_bet', False)
    preselected_team = request.session.get('team', None)
   # inviter_team = request.session.pop('inviterteam', None)
  #  inviter_bet = request.session.pop('inviter_bet', None)
    
    if not is_game_ready(game, request.user):
        return redirect('home')    
    return render(request, 'chessgame/board.html', {
        'game_id': room.id,  # used in WebSocket path
        'is_view_only': True,
        'preselected_team': preselected_team,
        'bet_locked': bet_challenge,
        'is_tournament': room.room_type == 'TOURNAMENT',
        'room_id' : room.id, 

    })


@login_required
def create_game_view(request):
    if request.method == 'POST':
        #opponent_id = request.POST['opponent']
        room_name = request.POST['room_name']
        #chosen_color = request.POST.get('color')  # 'white' or 'black'
        chosen_color = random.choice(['white', 'black'])
        #opponent = get_object_or_404(User, id=opponent_id)
        
        selected_users = get_random_participants(user=request.user, only_online=True)
        if not selected_users:
            selected_users = get_random_participants(user=request.user, only_online=False)
        opponent = selected_users[0]
        
        round_raw = request.POST['rounds']
        #print(round_raw)
        gtime = request.POST['gtime']
        round_map = {'1': 1, '2by3': 3, '3by5': 5}
        rounds = round_map.get(round_raw, 1)
        
        room = Room.objects.create(
                             name=room_name,
                             room_type='DUEL',
                             created_by=request.user,
                      #       start_datetime=now(),
                             starting_datetime=now(),
                             round_type=rounds,
                             time_control_seconds=int(gtime) if gtime else None
                             )

        if chosen_color == 'white':
            PlayerRoom.objects.create(user=request.user, room=room, role='PLAYER', color_group='white')
            PlayerRoom.objects.create(user=opponent, room=room, role='PLAYER', color_group='black')           
            player_white = request.user
            player_black = opponent
        else:
            PlayerRoom.objects.create(user=request.user, room=room, role='PLAYER', color_group='black')
            PlayerRoom.objects.create(user=opponent, room=room, role='PLAYER', color_group='white')    
            player_white = opponent
            player_black = request.user
      
     
        game = Game.objects.create(
            room=room,
            player_white=player_white,
            player_black=player_black,
            fen='startpos'
        )


        

        return redirect('chessboard', room_id=room.id)

    users = User.objects.exclude(id=request.user.id)
    return render(request, 'chessgame/create_game.html', {'users': users})



def nearest_bigger_allowed(max_users):
    allowed_values = [16, 32, 64, 128, 256, 512, 1024]
    for val in allowed_values:
        if max_users <= val:
            return val
    return allowed_values[-1]  # max fallback if bigger than all



@login_required
def create_tournament_view(request):
    if request.method == 'POST':
        room_name = request.POST['room_name']
        start_datetime_str = request.POST['start_datetime']
        
        round_raw = request.POST['rounds']
        gtime = request.POST['gtime']
        
        max_users =  int(request.POST['max_users'])
        max_users_input = max_users
        nearest_max = nearest_bigger_allowed(max_users_input)
        members_needed = nearest_max - max_users_input if nearest_max > max_users_input else 0
        if nearest_max != max_users:
            # redirect to suggestion page with form data preserved
            request.session['tournament_data'] = request.POST.dict()
            return redirect('suggest_tournament_fill')  # name of new view

        
        round_map = {'1': 1, '2by3': 3, '3by5': 5}
        rounds = round_map.get(round_raw, 1)
        
        invited_user_ids = request.POST.getlist('invited_users')
        #creator_color = request.POST.get('creator_color', 'white')  # default white
        creator_color = random.choice(['white', 'black'])
        start_datetime = datetime.fromisoformat(start_datetime_str)

        # Create one tournament room
        room = Room.objects.create(
            name=room_name,
            room_type='TOURNAMENT',
            created_by=request.user,
            max_users=nearest_max,
           # start_datetime=start_datetime,
            starting_datetime=start_datetime,
            round_type=rounds,
            time_control_seconds=int(gtime) if gtime else None
        )

        # Add all players to the room
        #[request.user] + 
        #all_users = [get_object_or_404(User, id=uid) for uid in invited_user_ids]
        #for user in all_users:
        #    PlayerRoom.objects.create(user=user, room=room, role='PLAYER', color_group=creator_color)
        #    if user != request.user:
        #        TournamentJoinRequest.objects.create(user=user, room=room, approved=True)

        # Create a single Game board for the tournament room
        Game.objects.create(
            room=room,
            player_white=None, #request.user # or leave this flexible
            player_black=None,          # to be assigned later
            fen='startpos'
        )

        return redirect('chessboard', room_id=room.id)

    users = User.objects.exclude(id=request.user.id)
    return render(request, 'chessgame/create_tournament.html', {'users': users})
    
    
@login_required
def participate_tournament_view(request, room_id):
    from decimal import Decimal
    from django.contrib import messages
    from django.shortcuts import redirect, render, get_object_or_404
    from django.utils.timezone import now
    import pytz

    user = request.user
    profile = user.profile
    room = get_object_or_404(Room, id=room_id, room_type='TOURNAMENT')

    # Check if room is already over or full
    if room.is_over:
        messages.error(request, "Game over.")
        #return redirect('home')

    if room.max_users == room.joined_users:
        messages.error(request, "Room is already full.")
        #return redirect('home')

    game = room.game
    if not is_game_ready(game, user):
        messages.warning(request, "Game has already started.")
       # return redirect('home')

    already_joined = PlayerRoom.objects.filter(user=user, room=room).exists()

    white_count = PlayerRoom.objects.filter(room=room, color_group='white').count()
    black_count = PlayerRoom.objects.filter(room=room, color_group='black').count()
    max_per_color = (room.max_users + 1) // 2

    # Amount user needs to pay to join
    total_amount = Decimal('11')

    if request.method == 'POST' and not already_joined:
        color = request.POST.get('color_group')

        if color not in ['white', 'black']:
            messages.error(request, "Invalid color selected.")
        else:
            # Enforce color balancing
            if color == 'white' and white_count > black_count:
                messages.error(request, "Too many players on white side. Please join as black.")
            elif color == 'black' and black_count > white_count:
                messages.error(request, "Too many players on black side. Please join as white.")
            else:
                # ✅ Deduct wallet only when joining
                if profile.wallet_balance < total_amount:
                    messages.error(request, "Not enough balance to join the tournament.")
                   # return redirect('home')

                #profile.wallet_balance -= total_amount
                profile.save()

                # Referral bonuses
                ref = profile.referrer
                refz_ref = ref.profile.referrer if ref else None
                refz_refz_ref = refz_ref.profile.referrer if refz_ref else None

                if ref:
                    #ref.profile.wallet_balance += Decimal('8')
                    ref.profile.save()

                if refz_ref:
                    #refz_ref.profile.wallet_balance += Decimal('2')
                    refz_ref.profile.save()

                if refz_refz_ref:
                    #refz_refz_ref.profile.wallet_balance += Decimal('1')
                    refz_refz_ref.profile.save()

                PlayerRoom.objects.create(user=user, room=room, role='PLAYER', color_group=color)
                room.joined_users += 1
                room.save()
                return redirect('chessboard', room_id=room.id)
                #return redirect('home')

    # Time display logic
    room_tz = pytz.timezone(room.timezone)
    room_start = room.starting_datetime.astimezone(room_tz)
    current_time = now().astimezone(room_tz)

    time_remaining = room_start - current_time if room_start else None
    if room_start < current_time:
        time_remaining = "Scheduled time is over, waiting for participants to join."

    return render(request, 'chessgame/join_tournament.html', {
        'room': room,
        'already_joined': already_joined,
        'time_remaining': time_remaining,
    })

    





@login_required
def suggest_tournament_fill(request):
    from django.utils.crypto import get_random_string
    import names
    from decimal import Decimal
    import random

    data = request.session.get('tournament_data')
    if not data:
        return redirect('create_tournament')

    max_users = int(data.get('max_users', 0))
    nearest_max = nearest_bigger_allowed(max_users)
    members_needed = nearest_max - max_users
    round_map = {'1': 1, '2by3': 3, '3by5': 5}
    rounds = round_map.get(data.get('rounds'), 1)

    # Create fake room suggestions
    suggestions = []
    for i in range(3):
        name = f"Tournament {get_random_string(4).upper()}"
        suggestion = {
            'name': name,
            'total_needed': nearest_max,
            'current_users': members_needed,
            'remaining': max_users, 
            'room_id': i  # fake ID for frontend
        }
        suggestions.append(suggestion)

    if request.method == 'POST':
        # Same as create_tournament_with_bots, just hidden from user
        start_datetime = datetime.fromisoformat(data['start_datetime'])
        creator_color = random.choice(['white', 'black'])



        room = Room.objects.create(
            name=data['room_name'],
            room_type='TOURNAMENT',
            created_by=request.user,
            starting_datetime=start_datetime,
            round_type=rounds,
            max_users = nearest_max,
            joined_users = members_needed,
            time_control_seconds=int(data.get('gtime', 0))
        )

        colors = ['white', 'black']
        for i in range(members_needed):
            random_name = names.get_first_name()
            length = 4
            bot = User.objects.create(username=f'{random_name}.{uuid.uuid4().hex[:length]}', is_active=True)
            bot.profile.is_online = True
            bot.profile.is_bot = True
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



        Game.objects.create(
            room=room,
            player_white=None,
            player_black=None,
            fen='startpos'
        )

        return redirect('chessboard', room_id=room.id)

    return render(request, 'chessgame/suggest_fill.html', {
        'data': data,
        'nearest_max': nearest_max,
        'members_needed': members_needed,
        'suggestions': suggestions
    })


@login_required
def room_pairings_view(request):
    room_id = request.GET.get('id')
    room = get_object_or_404(Room, id=room_id)
    match_pairs = room.match_pairs or []

    # Attach user objects to display names
    for pair in match_pairs:
        pair['white_user'] = User.objects.filter(id=pair['white']).first()
        pair['black_user'] = User.objects.filter(id=pair['black']).first()

    return render(request, 'chessgame/room_pairings.html', {
        'room': room,
        'match_pairs': match_pairs
    })
    
    

