#---------------- Account App views ------------------

from django.shortcuts import render, redirect
from .forms import SignUpForm
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.timezone import now
from django.db.models import Count, Q
from chessgame.models import Game, PlayerRoom,Room,GameBet
from django.contrib.auth.models import User

from .models import Profile, WalletFundRequest,Referrals
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
import pytz

from django.contrib import messages
from decimal import Decimal




from collections import defaultdict


from django.http import Http404

from datetime import datetime


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login


from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.urls import reverse
from django.utils.timezone import now
import pytz

# Assuming these are your models
# from .models import Game, PlayerRoom

# Assuming get_participant_summary is a function you've defined
# from .utils import get_participant_summary

@login_required
def home_api(request):
    user = request.user
    
    # Filtering for active games
    active_games_queryset = Game.objects.filter(is_active=True).order_by('-created_at')

    # Get rooms where the user is a player
    player_room_ids = set(
        PlayerRoom.objects.filter(user=user, role='PLAYER').values_list('room_id', flat=True)
    )

    MIN_PLAYERS_PER_COLOR = 1
    games_with_display = []
    
    # Loop through the queryset to determine display properties
    for game in active_games_queryset:
        room = game.room
        room_tz = pytz.timezone(room.timezone)
        is_user_player = game.room_id in player_room_ids
        
        # Get player counts for each color
        color_counts_qs = PlayerRoom.objects.filter(
            room=room,
            role='PLAYER'
        ).values('color_group').annotate(count=Count('id'))
        
        counts = {'white': 0, 'black': 0}
        for c in color_counts_qs:
            counts[c['color_group']] = c['count']

        missing_side_players = (counts['white'] < MIN_PLAYERS_PER_COLOR or counts['black'] < MIN_PLAYERS_PER_COLOR)
        tournament_started = (
            room.starting_datetime is not None and
            room.starting_datetime.astimezone(room_tz) <= now().astimezone(room_tz)
        )
        
        # Logic to determine button properties
        button_label = 'Watch'
        button_class = 'btn btn-sm btn-outline-success'
        button_url = reverse('chessboard_watch', kwargs={'room_id': game.room.id})

        if room.is_over:
            button_label = 'Game Over'
            button_class = 'btn btn-sm btn-primary'
            button_url = reverse('chessboard', kwargs={'room_id': game.room.id})
        elif is_user_player or room.created_by == user:
            button_label = 'Play'
            button_class = 'btn btn-sm btn-primary'
            button_url = reverse('chessboard', kwargs={'room_id': game.room.id})
        elif room.room_type == 'TOURNAMENT' and (missing_side_players or not tournament_started):
            if not room.max_users == room.joined_users:
                button_label = 'Participate'
                button_class = 'btn btn-sm btn-warning'
                button_url = reverse('participate_tournament', kwargs={'room_id': room.id})
            else:
                button_label = 'Waiting'
                button_class = 'btn btn-sm btn-secondary disabled'
                button_url = '#'
        
        # Append the processed data (including the complex objects) to a list
        games_with_display.append({
            'game': game,
            'button_label': button_label,
            'button_class': button_class,
            'button_url': button_url,
            'participation_summary': get_participant_summary(room),
        })

    # PAGINATION PART
    paginator = Paginator(games_with_display, 10)
    page_number = request.GET.get('page')
    try:
        paged_games = paginator.page(page_number)
    except PageNotAnInteger:
        paged_games = paginator.page(1)
    except EmptyPage:
        paged_games = paginator.page(paginator.num_pages)

    # --- FINAL JSON SERIALIZATION ---
    serialized_games = []
    for item in paged_games:
        game_obj = item['game']
        serialized_games.append({
            'id': game_obj.id,
            'is_active': game_obj.is_active,
            'created_at': game_obj.created_at.isoformat(),
            'room': {
                'id': game_obj.room.id,
                'name': game_obj.room.name,
                'room_type': game_obj.room.room_type,
                'is_over': game_obj.room.is_over,
                'created_by': game_obj.room.created_by.username,
                'joined_users': game_obj.room.joined_users,
                'max_users': game_obj.room.max_users,
            },
            'participation_summary': item['participation_summary'],
            'button': {
                'label': item['button_label'],
                'class': item['button_class'],
                'url': item['button_url'],
            }
        })

    # Build the final response dictionary
    data = {
        'active_games': serialized_games,
        'staff': user.is_staff,
        'has_next': paged_games.has_next(),
        'has_previous': paged_games.has_previous(),
        'current_page': paged_games.number,
        'total_pages': paged_games.paginator.num_pages,
        'total_count': paged_games.paginator.count,
    }

    return JsonResponse(data)


@csrf_exempt
def login_api(request):
    print('api called')
    if request.method != 'POST':        
        return JsonResponse({'error': 'Only POST requests are allowed.'}, status=405)

    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format.'}, status=400)

    user = authenticate(request, username=username, password=password)

    if user is not None:
        login(request, user)
        return JsonResponse({'success': True, 'message': 'Logged in successfully.'})
    else:
        return JsonResponse({'error': 'Invalid username or password.'}, status=400)





@csrf_exempt
def signup_api(request):
    if request.method != 'POST':
        # Return a 405 Method Not Allowed error
        return JsonResponse({'error': 'Only POST requests are allowed.'}, status=405)

    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        referral_code = data.get('referral_code', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format.'}, status=400)

    # Manual Validation
    if not username or not password or not email:
        return JsonResponse({'error': 'Username, password, and email are required.'}, status=400)
    
    if User.objects.filter(username=username).exists():
        return JsonResponse({'error': 'A user with that username already exists.'}, status=409) # 409 Conflict
        
    if User.objects.filter(email=email).exists():
        return JsonResponse({'error': 'A user with that email already exists.'}, status=409)

    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        

        profile = user.profile

        if referral_code:
            try:
                referrer_profile = Profile.objects.get(referral_code=referral_code)
                profile.referrer = referrer_profile.user


                if referrer_profile.referrer:
                    profile.refz_referrer = referrer_profile.referrer


                    refz_ref_profile = Profile.objects.filter(user=referrer_profile.referrer).first()
                    if refz_ref_profile and refz_ref_profile.referrer:
                        profile.refz_referrerz_ref = refz_ref_profile.referrer

                profile.save()


                Referrals.objects.create(
                    referrer=referrer_profile.user,
                    referred=user,
                    referral_reward_amount=Decimal('0.00')
                )

            except Profile.DoesNotExist:
                pass


        return JsonResponse({
            'success': True,
            'message': 'User created successfully.',
            'username': user.username
        }, status=201) # 201 Created

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_participant_summary(room):
    participants = PlayerRoom.objects.filter(
        room=room, role='PLAYER'
    ).select_related('user')

    names = [p.user.username for p in participants]
    count = len(names)

    if count == 0:
        return "No players"
    elif count == 1:
        return names[0]
    elif count == 2:
        return f"{names[0]} and {names[1]}"
    elif count == 3:
        return f"{names[0]}, {names[1]} and {names[2]}"
    else:
        return f"{names[0]}, {names[1]}, {names[2]} and {count - 3} more people"

# Normal web login page view
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')  # change 'home' to your landing page
        else:
            context = {'error': 'Invalid username or password.'}
            return render(request, 'login.html', context)

    return render(request, 'login.html')





def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('referral_code', '').strip()
            user = form.save()  # Save user first
            profile = user.profile  # Get the profile via post_save signal

            if ref_code:
                try:
                    # Main referrer (Level 1)
                    referrer_profile = Profile.objects.get(referral_code=ref_code)
                    profile.referrer = referrer_profile.user

                    # Level 2 (referrer of the referrer)
                    if referrer_profile.referrer:
                        profile.refz_referrer = referrer_profile.referrer

                        # Level 3 (referrer of level 2)
                        refz_ref_profile = Profile.objects.filter(user=referrer_profile.referrer).first()
                        if refz_ref_profile and refz_ref_profile.referrer:
                            profile.refz_referrerz_ref = refz_ref_profile.referrer

                    profile.save()

                    # Create referral record (you can later update reward amount)
                    Referrals.objects.create(
                        referrer=referrer_profile.user,
                        referred=user,
                        referral_reward_amount=Decimal('0.00')  # or set initial reward
                    )

                except Profile.DoesNotExist:
                    pass  # invalid referral code, just ignore it

            return redirect('login')

    else:
        form = SignUpForm()
    
    return render(request, 'signup.html', {'form': form})



    


@login_required
def home(request):  
    user = request.user
    
    active_games = Game.objects.filter(is_active=True).order_by('-created_at')

    player_room_ids = set(
        PlayerRoom.objects.filter(user=user, role='PLAYER').values_list('room_id', flat=True)
    )

    MIN_PLAYERS_PER_COLOR = 1
    games_with_display = []
    
    for game in active_games:
        room = game.room
        room_tz = pytz.timezone(room.timezone)
        is_user_player = game.room_id in player_room_ids
        color_counts_qs = PlayerRoom.objects.filter(
            room=room,
            role='PLAYER').values('color_group').annotate(count=Count('id'))
        
        counts = {'white': 0, 'black': 0}
        for c in color_counts_qs:
            counts[c['color_group']] = c['count']

        missing_side_players = (counts['white'] < MIN_PLAYERS_PER_COLOR or counts['black'] < MIN_PLAYERS_PER_COLOR)
        tournament_started = (
        room.starting_datetime is not None and
        room.starting_datetime.astimezone(room_tz) <= now().astimezone(room_tz)
        )

        #print(room.created_by == user)
        if room.room_type == 'TOURNAMENT' and (missing_side_players or not tournament_started):
           if not room.max_users == room.joined_users and not is_user_player:
                button_label = 'Participate'
                button_class = 'btn btn-sm btn-warning'
                button_url = reverse('participate_tournament', kwargs={'room_id': room.id})
           else:
                button_label = 'Waiting'
                button_class = 'btn btn-sm btn-secondary disabled'
                button_url = '#'
           if is_user_player:
                button_label = 'Play'
                button_class = 'btn btn-sm btn-primary'
                button_url = reverse('chessboard', kwargs={'room_id': game.room.id})
           if room.created_by == user:
                button_label = 'Play'
                button_class = 'btn btn-sm btn-primary'
                button_url = reverse('chessboard', kwargs={'room_id': game.room.id})

           if room.is_over:
                button_label = 'Game Over'
                button_class = 'btn btn-sm btn-primary'
                button_url = reverse('chessboard', kwargs={'room_id': game.room.id})
  

        elif room.is_over:
            button_label = 'Game Over'
            button_class = 'btn btn-sm btn-primary'
            button_url = reverse('chessboard', kwargs={'room_id': game.room.id})
     
        elif is_user_player:
            button_label = 'Play'
            button_class = 'btn btn-sm btn-primary'
            button_url = reverse('chessboard', kwargs={'room_id': game.room.id})
        
        elif room.created_by == user:
            button_label = 'Play'
            button_class = 'btn btn-sm btn-primary'
            button_url = reverse('chessboard', kwargs={'room_id': game.room.id})
        else:
            button_label = 'Watch'
            button_class = 'btn btn-sm btn-outline-success'
            button_url = reverse('chessboard_watch', kwargs={'room_id': game.room.id})
        
        game.participation_summary = get_participant_summary(room)
        games_with_display.append({
            'game': game,
            'button_label': button_label,
            'button_class': button_class,
            'button_url': button_url,
        })

    # PAGINATION PART
    paginator = Paginator(games_with_display, 10)  # Show 10 games per page
    page = request.GET.get('page')
    try:
        paged_games = paginator.page(page)
    except PageNotAnInteger:
        paged_games = paginator.page(1)
    except EmptyPage:
        paged_games = paginator.page(paginator.num_pages)

    return render(request, 'home.html', {
        'active_games': paged_games,
        'staff': user.is_staff,
        'page_obj': paged_games,
    })






@login_required
def wallet_dashboard(request):
    profile = request.user.profile
    transactions = WalletFundRequest.objects.filter(user=request.user,wallet_type='MAIN').order_by('-created_at')
    return render(request, 'wallet/dashboard.html', {
        'balance': profile.wallet_balance,
        'transactions': transactions
    })



@login_required
def wallet_request(request, req_type):
    if req_type not in ['DEPOSIT', 'WITHDRAW']:
        return redirect('wallet_dashboard')

    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', '0'))
        except ValueError:
            amount = 0

        if amount <= 0:
            return render(request, 'wallet/request.html', {
                'error': 'Amount must be greater than 0',
                'req_type': req_type
            })

        reference = request.POST.get('reference_number', '').strip()
        
        if req_type == 'WITHDRAW':
            current_balance = getattr(request.user.profile, 'wallet_balance', 0)
            print("cbal",current_balance)
            print("ral",amount)
            if amount > current_balance:
                
                return render(request, 'wallet/request.html', {
                'error': 'Insufficient balance for withdrawal.',
                'req_type': req_type
                })

        WalletFundRequest.objects.create(
            user=request.user,
            request_type=req_type,
            amount=amount,
            reference_number=reference  # Always store in this field
        )
        return redirect('wallet_dashboard')

    return render(request, 'wallet/request.html', {'req_type': req_type})

    



#----------------------------- Refls -------------------------------------------#



@login_required
def referral_dashboard(request):
    user = request.user

    # Get or create profile
    profile, created = Profile.objects.get_or_create(user=user)

    # Generate referral code if not present
    if not profile.referral_code:
        profile.referral_code = profile.generate_referral_code()
        profile.save()

    # Get all referred users
    referrals = Referrals.objects.filter(referrer=user)

    context = {
        'referral_code': profile.referral_code,
        'referrals': referrals,
    }
    return render(request, 'refs.html', context)


#------------------------------------------------------------------------------#
#------------------------------------------------------------------------------#
#---------------------------    Wallet 2   ------------------------------------#
#------------------------------------------------------------------------------#
#------------------------------------------------------------------------------#
#------------------------------------------------------------------------------#



@login_required
def secwallet_dashboard(request):
    profile = request.user.profile
    transactions = WalletFundRequest.objects.filter(
        user=request.user,
        wallet_type='SECWAL'
    ).order_by('-created_at')

    # You may need to add a separate balance field for secwallet (e.g., profile.sec_wallet_balance)
    secwal_balance = getattr(profile, 'sec_wallet_balance', 0)

    return render(request, 'secwallet/dashboard.html', {
        'balance': secwal_balance,
        'transactions': transactions
    })




@login_required
def secwallet_request(request, req_type):
    profile = request.user.profile

    if profile.wallet2_locked:
        return redirect('secwallet_dashboard') #render(request, 'secwallet/locked.html')  # show locked warning

    if req_type not in ['DEPOSIT', 'WITHDRAW']:
        return redirect('secwallet_dashboard')

    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', '0'))
        except ValueError:
            amount = 0

        if amount <= 0:
            return render(request, 'secwallet/request.html', {
                'error': 'Amount must be greater than 0',
                'req_type': req_type
            })

        reference = request.POST.get('reference_number', '').strip()
        if req_type == 'WITHDRAW':
            current_balance = getattr(profile, 'sec_wallet_balance', 0)
            if amount > current_balance:
                return render(request, 'secwallet/request.html', {
                    'error': 'Insufficient balance for withdrawal.',
                    'req_type': req_type
                })

        WalletFundRequest.objects.create(
            user=request.user,
            request_type=req_type,
            amount=amount,
            reference_number=reference,
            wallet_type='SECWAL'  # important
        )

        return redirect('secwallet_dashboard')

    return render(request, 'secwallet/request.html', {'req_type': req_type})
    
    



@login_required
def profile_view(request):
    user_id = request.GET.get('user_id')
    username = request.GET.get('username')

    # Get target user
    try:
        if user_id:
            target_user = User.objects.get(id=user_id)
        elif username:
            target_user = User.objects.get(username=username)
        else:
            raise Http404("User ID or Username not specified")
    except User.DoesNotExist:
        raise Http404("User not found")

    # Profile & wallets
    profile = getattr(target_user, 'profile', None)
    if not profile:
        raise Http404("Profile not found")

    main_balance = profile.wallet_balance
    sec_balance = getattr(profile, 'sec_wallet_balance', 0)
    rating = getattr(profile, 'rating', 0)
    rating_percent = int((rating / 1500) * 100)

    # Real played games converted to dict
    played_games_qs = Game.objects.filter(
        Q(player_white=target_user) | Q(player_black=target_user)
    ).order_by('-created_at')

    real_games_list = []
    for game in played_games_qs:
        winner = getattr(game, 'winner', None)
        real_games_list.append({
            "game_name": getattr(game, "name", f"Game {game.id}"),
            "bet_amount": getattr(game, "bet_amount", 0),
            "result": "won" if winner == target_user else "lost",
            "date": game.created_at.isoformat()
        })

    # Fake games (if bot)
    if getattr(profile, 'is_bot', False):
        fake_info = getattr(profile, 'fake_game_info', {}) or {}
        fake_games = fake_info.get("games", [])
        combined_games = real_games_list + fake_games
    else:
        combined_games = real_games_list

    # Sort combined games by date descending
    def parse_date2(game):    
        try:
            return datetime.fromisoformat(game.get("date", "1970-01-01T00:00:00"))
        except Exception:
            return datetime.min

    def parse_date(g):
        from django.utils import timezone
        dt = g['date']
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)  # or use strptime depending on format
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt



    combined_games.sort(key=parse_date, reverse=True)
    for g in combined_games:
        dt = datetime.fromisoformat(g['date'])
        g['date_str'] = dt.strftime("%b %d, %Y ")


    # Paginate combined games
    paginator = Paginator(combined_games, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Bets counts
    if getattr(profile, 'is_bot', False):
        fake_bets = fake_info.get("bets", {})
        total_bets = fake_bets.get("total_placed", 0)
        won_bets = fake_bets.get("won", 0)
    else:
        bets_qs = GameBet.objects.filter(user=target_user)
        total_bets = bets_qs.count()
        won_bets = bets_qs.filter(
            Q(side='white', room__winner='WHITE') |
            Q(side='black', room__winner='BLACK')
        ).count()

    # Count of played games and won games
    played_count = len(combined_games)
    won_games = sum(1 for g in combined_games if g.get("result") == "won")

    context = {
        'profile_user': target_user,
        'main_balance': main_balance,
        'sec_balance': sec_balance,
        'played_count': played_count,
        'won_count': won_games,
        'won_bets_count': won_bets,
        'total_bets_count': total_bets,
        'games_page': page_obj,
        'rating_percent': rating_percent,
    }

    return render(request, 'account/profile.html', context)




@login_required
def profile_viewold(request):
    user_id = request.GET.get('user_id')
    username = request.GET.get('username')

    # Try to get user either by ID or username
    try:
        if user_id:
            target_user = User.objects.get(id=user_id)
        elif username:
            target_user = User.objects.get(username=username)
        else:
            raise Http404("User ID or Username not specified")
    except User.DoesNotExist:
        raise Http404("User not found")

    # Profile & Wallets
    profile = getattr(target_user, 'profile', None)
    if not profile:
        raise Http404("Profile not found")

    main_balance = profile.wallet_balance
    sec_balance = getattr(profile, 'sec_wallet_balance', 0)

    # Played games (either white or black)
    played_games = Game.objects.filter(
        Q(player_white=target_user) | Q(player_black=target_user)
    ).order_by('-created_at')

    # Win count (if Game has winner info)
    won_games = 0  # adjust if you track winners in Game

    # Bets (won bets calculation based on GameBet)
    bets = GameBet.objects.filter(user=target_user)
    total_bets = bets.count()
    won_bets = bets.filter(
        Q(side='white', room__winner='WHITE') |
        Q(side='black', room__winner='BLACK')
    ).count()

    # Rating percent (0–1500 scale)
    rating = profile.rating
    rating_percent = int((rating / 1500) * 100)

    # Pagination
    paginator = Paginator(played_games, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'profile_user': target_user,
        'main_balance': main_balance,
        'sec_balance': sec_balance,
        'played_count': played_games.count(),
        'won_count': won_games,
        'won_bets_count': won_bets,
        'total_bets_count': total_bets,
        'games_page': page_obj,
        'rating_percent': rating_percent,
    }
    return render(request, 'account/profile.html', context)




@login_required
def transfer_to_secwallet(request):
    profile = request.user.profile

    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', '0'))
        except:
            amount = Decimal('0.00')

        if amount <= 0:
            messages.warning(request, " Amount must be greater than 0.")
            return redirect('transfer_to_secwallet')

        if profile.wallet_balance < amount:
            messages.warning(request, "Insufficient balance in main wallet.")
            return redirect('transfer_to_secwallet')

        # Perform the transfer
        profile.wallet_balance -= amount
        profile.sec_wallet_balance += amount
        profile.save()

        # Log the transaction in WalletFundRequest
        WalletFundRequest.objects.create(
            user=request.user,
            request_type='TRANSFER',
            amount=amount,
            status='APPROVED',
            wallet_type='SECWAL',
            note='Transfer from Main to Secwal'
        )

        messages.success(request, f"Successfully transferred  ${amount} to secondary wallet.")
        return redirect('secwallet_dashboard')

    return render(request, 'secwallet/transfer.html')