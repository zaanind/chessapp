
#---------------- Manager App views ------------------
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from account.models import Profile, WalletFundRequest
from django.utils.timezone import now
from django.db.models import Count, Q

from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from django.db.models import Count, Q
from chessgame.models import Game, PlayerRoom

from django.db.models import Sum
from chessgame.models import GameBet
from .models import CompanyCommission  # adjust import if needed

@staff_member_required
def company_commission_list(request):
    commissions = CompanyCommission.objects.select_related('room', 'game').order_by('-calculated_at')
    paginator = Paginator(commissions, 10)  # 10 per page

    page = request.GET.get('page')
    try:
        paged_commissions = paginator.page(page)
    except PageNotAnInteger:
        paged_commissions = paginator.page(1)
    except EmptyPage:
        paged_commissions = paginator.page(paginator.num_pages)

    return render(request, 'manager/commission_list.html', {
        'commissions': paged_commissions,
        'page_obj': paged_commissions,
        'staff': request.user.is_staff,
    })


# Create your views here.
@staff_member_required
def manager(request):
    user = request.user
    active_games = Game.objects.all().order_by('-created_at')
    player_room_ids = set(
        PlayerRoom.objects.filter(user=user, role='PLAYER').values_list('room_id', flat=True)
    )
    
    games_with_display = []
    
    for game in active_games:
        games_with_display.append({'game': game})

    # PAGINATION PART
    paginator = Paginator(games_with_display, 10)  # Show 10 games per page
    page = request.GET.get('page')
    try:
        paged_games = paginator.page(page)
    except PageNotAnInteger:
        paged_games = paginator.page(1)
    except EmptyPage:
        paged_games = paginator.page(paginator.num_pages)


    x ='p'
    return render(request, 'managerhome.html', {
        'active_games': paged_games,
        'staff': user.is_staff,
        'page_obj': paged_games,
    })
    


    
#----------------------ADMIN Approvals -----------------------
from decimal import Decimal
@staff_member_required
def manage_wallet_request22s(request):
    user = request.user
    requests = WalletFundRequest.objects.all().order_by('-created_at')

    if request.method == 'POST':
        req_id = request.POST.get('req_id')
        action = request.POST.get('action')  # 'approve' or 'reject'
        note = request.POST.get('note', '')

        try:
            req = WalletFundRequest.objects.get(id=req_id)
        except WalletFundRequest.DoesNotExist:
            return redirect('manage_wallet_requests')

        if req.status != 'PENDING':
            return redirect('manage_wallet_requests')

        profile = req.user.profile
        wallet_type = req.wallet_type or 'MAIN'

        wallet_field = 'wallet_balance' if wallet_type == 'MAIN' else 'sec_wallet_balance'

        if action == 'approve':
            # Ensure req.amount is Decimal, not string
            amount = req.amount if isinstance(req.amount, Decimal) else Decimal(req.amount)

            if req.request_type == 'DEPOSIT':
                # Add money to wallet
                current_balance = getattr(profile, wallet_field, Decimal('0'))
                setattr(profile, wallet_field, current_balance + amount)
                profile.save()

                req.status = 'APPROVED'

            elif req.request_type == 'WITHDRAW':
                current_balance = getattr(profile, wallet_field, Decimal('0'))
                if current_balance >= amount:
                    setattr(profile, wallet_field, current_balance - amount)
                    profile.save()

                    req.status = 'APPROVED'
                else:
                    req.status = 'REJECTED'
                    req.note = 'Insufficient balance'
                    req.processed_at = now()
                    req.save()
                    return redirect('manage_wallet_requests')

        elif action == 'reject':
            req.status = 'REJECTED'

        req.note = note
        req.processed_at = now()
        req.save()

    # Pagination
    paginator = Paginator(requests, 10)
    page = request.GET.get('page')
    try:
        paged_requests = paginator.page(page)
    except PageNotAnInteger:
        paged_requests = paginator.page(1)
    except EmptyPage:
        paged_requests = paginator.page(paginator.num_pages)

    return render(request, 'wallet/manage.html', {
        'requests': paged_requests,
        'staff': user.is_staff,
        'page_obj': paged_requests,
    })
    
    
@staff_member_required
def manage_wallet_requests(request):
    user = request.user
    requests = WalletFundRequest.objects.all().order_by('-created_at')

    if request.method == 'POST':
        req_id = request.POST.get('req_id')
        action = request.POST.get('action')  # 'approve' or 'reject'
        note = request.POST.get('note', '')

        try:
            req = WalletFundRequest.objects.get(id=req_id)
        except WalletFundRequest.DoesNotExist:
            return redirect('manage_wallet_requests')

        if req.status != 'PENDING':
            return redirect('manage_wallet_requests')

        profile = req.user.profile
        wallet_type = req.wallet_type or 'MAIN'

        if wallet_type == 'MAIN':
            wallet_field = 'wallet_balance'
        else:
            wallet_field = 'sec_wallet_balance'

        if action == 'approve':
            if req.request_type == 'DEPOSIT':
                setattr(profile, wallet_field, getattr(profile, wallet_field) + req.amount)
                profile.save()

            elif req.request_type == 'WITHDRAW':
                current_balance = getattr(profile, wallet_field)
                if current_balance >= req.amount:
                    setattr(profile, wallet_field, current_balance - req.amount)
                else:
                    req.status = 'REJECTED'
                    req.note = 'Insufficient balance'
                    req.processed_at = now()
                    req.save()
                    return redirect('manage_wallet_requests')

            profile.save()
            req.status = 'APPROVED'

        elif action == 'reject':
            req.status = 'REJECTED'

        req.note = note
        req.processed_at = now()
        req.save()

    # Pagination
    paginator = Paginator(requests, 10)
    page = request.GET.get('page')
    try:
        paged_requests = paginator.page(page)
    except PageNotAnInteger:
        paged_requests = paginator.page(1)
    except EmptyPage:
        paged_requests = paginator.page(paginator.num_pages)

    return render(request, 'wallet/manage.html', {
        'requests': paged_requests,
        'staff': user.is_staff,
        'page_obj': paged_requests,
    })



@staff_member_required
def manage_game_room(request, game_id):
    try:
        game = Game.objects.get(id=game_id)
        room = game.room
    except Game.DoesNotExist:
        return redirect('manager')

    players = PlayerRoom.objects.filter(room=room).select_related('user')
    all_profiles = Profile.objects.exclude(user__playerroom__room=room)
    #bet_summary = GameBet.objects.filter(room=room).values('side').annotate(total_amount=Sum('amount'))
    bet_summary = GameBet.objects.filter(room=room, is_bot_placed=False).values('side').annotate(total_amount=Sum('amount'))

    #print(bet_summary)
    bets_white = next((b['total_amount'] for b in bet_summary if b['side'] == 'White'), 0)
    bets_black = next((b['total_amount'] for b in bet_summary if b['side'] == 'Black'), 0)
    #print(bets_white)
    
    from django.utils.dateparse import parse_datetime
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    # Fallback: show all non-bot bets if no range provided
    bet_filter = Q(room=room, is_bot_placed=False)
    if start_date_str and end_date_str:
        try:
            start_dt = parse_datetime(start_date_str)
            end_dt = parse_datetime(end_date_str)
            if start_dt and end_dt:
                bet_filter &= Q(placed_at__range=(start_dt, end_dt))
        except:
            pass
    bets = GameBet.objects.filter(bet_filter).select_related('user').order_by('-placed_at')
            

    if request.method == 'POST':
        print("POST DATA:", request.POST.dict())

        action = request.POST.get('action')



        
        if action == 'force_win':        
            selected_side = request.POST.get('force_to_win_side')
            if selected_side in ['WHITE', 'BLACK']:
                room.force_to_win_side = selected_side   
                room.save()
                
                #room.refresh_from_db()
                #print(f"Force win side after save: {room.force_to_win_side}")
            



        if action == 'assign':
            user_id = request.POST.get('user_id')
            try:
                profile = Profile.objects.get(user__id=user_id)
            except Profile.DoesNotExist:
                return redirect('manage_game_room', game_id=game.id)
            selected_color = request.POST.get('color_group')  # read from form
            if room.room_type == 'DUEL' and PlayerRoom.objects.filter(room=room, color_group=selected_color).exists():
                return redirect('manage_game_room', game_id=game.id)
                #Do this if room type dual, not in tournament
            
            PlayerRoom.objects.create(
                user=profile.user,
                room=room,
                role='PLAYER',
                color_group=selected_color
            )
            
            if selected_color == 'white':
                game.player_white = profile.user
            elif selected_color == 'black':
                game.player_black = profile.user
            
            game.save()
            #print("Game updated successfully.")
        if action == 'remove':
            user_id = request.POST.get('user_id')
            try:
                profile = Profile.objects.get(user__id=user_id)
            except Profile.DoesNotExist:
                return redirect('manage_game_room', game_id=game.id)
            print('ru')
            
            PlayerRoom.objects.filter(user=profile.user, room=room).delete()
            if game.player_white == profile.user:
                game.player_white = None
            if game.player_black == profile.user:
                game.player_black = None
            game.save()
            
        if action == 'toggle_signal': #Is-singnal
            is_signal_val = request.POST.get('is_signal')
            room.is_signal = True if is_signal_val == 'true' else False
            room.save()
        if action == 'enable24hours': #Is-24auto
            print('about to set 24')
            is_24auto_val = request.POST.get('is_auto_24') 
            room.is_automated_room = True if is_24auto_val == 'true' else False
            print('enabled',room.is_automated_room)
            room.save()  
      
        return redirect('manage_game_room', game_id=game.id)
    import pytz
    room_tz = pytz.timezone(room.timezone)
    context = {
    'game': game,
    'room': room,
    'players': players,
    'available_profiles': all_profiles,
    'staff': request.user.is_staff,
    'room_type': room.room_type,
    'bets_white': bets_white,
    'bets_black': bets_black,
    'room_tz': now().astimezone(room_tz),
    }
    
    if start_date_str and end_date_str:
        context.update({
        'bets': bets,
        'start_date': start_date_str,
        'end_date': end_date_str,
        })
    return render(request, 'game/manage_room.html', context)

  

#-------------------------Add users------------------
from django.contrib.auth.models import User
from .forms import AdminUserCreationForm  # adjust import path accordingly

@staff_member_required
def add_user_view(request):
    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST)
        
        if form.is_valid():
            print( form.cleaned_data['is_bot'])
            user = form.save(commit=False)      
            user.save()
            

            user.profile.is_online = form.cleaned_data['is_active']
            user.profile.is_bot = form.cleaned_data['is_bot']
            if user.profile.is_bot:
                user.profile.is_online = True
                
            user.profile.save()
            


            return redirect('manager')  # or anywhere relevant
    else:
        form = AdminUserCreationForm()

    return render(request, 'manager/add_user.html', {'form': form})


#---------------user's list----


@staff_member_required
def user_list_view(request):
    #users = User.objects.select_related('profile').all().order_by('username')  # Optional ordering
    users = User.objects.select_related('profile').filter(profile__is_auto_sys=False).order_by('-date_joined')  # Newest first
    paginator = Paginator(users, 10)  # Show 10 users per page

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'manager/user_list.html', {'page_obj': page_obj})