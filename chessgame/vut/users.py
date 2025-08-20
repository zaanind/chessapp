import random
from django.contrib.auth.models import User
from account.models import Profile
from django.db.models import Q
from chessgame.models import PlayerRoom




def get_random_participants(user, only_online=True,listneeded=False):
    
    is_bot = True
    
    # Step 1: get candidate users (online or all except request.user)
    if only_online:
        if is_bot:
            online_profiles = Profile.objects.filter(is_online=True,is_bot=is_bot).exclude(user=user)
        else:
            online_profiles = Profile.objects.filter(is_online=True).exclude(user=user)
            
        candidate_users = User.objects.filter(id__in=online_profiles.values_list('user_id', flat=True))
    else:
        candidate_users = User.objects.exclude(id=user.id)

    # Step 2: get user IDs of participants in ongoing rooms (room.is_over=False) with role 'PLAYER'
    busy_user_ids = PlayerRoom.objects.filter(
        room__is_over=False,
        role='PLAYER'
    ).values_list('user_id', flat=True).distinct()

    # Step 3: exclude busy users from candidates
    free_users = candidate_users.exclude(id__in=busy_user_ids)

    free_users_list = list(free_users)

    if free_users_list:
        if listneeded:
            free_users_list
        else:
            return random.sample(free_users_list, 1)
    else:
        return []
