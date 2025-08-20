import asyncio
from channels.db import database_sync_to_async
import json
from decimal import Decimal

from datetime import timedelta
from django.utils.timezone import now


@database_sync_to_async
def deduct_wallet(profile, amount, use_sec_wallet=False):
    amount = Decimal(amount)
    if amount <= 0:
        return False

    if use_sec_wallet:
        if profile.sec_wallet_balance >= amount:
            return True
    else:
        if profile.wallet_balance >= amount:
            return True

    return False




async def onconnect_send_notifications(self):
    print('onconnect notification called')

    def get_unread_notifications():
        time_threshold = now() - timedelta(minutes=5)
        return list(
            self.Notification.objects
                .filter(to_user=self.user, is_read=False)
                .exclude(system='BETINV', created_at__lt=time_threshold)
                .select_related('user')
                .order_by('-created_at')
        )

    unread_notifications = await database_sync_to_async(get_unread_notifications)()

    for notif in unread_notifications:
        await self.send(text_data=json.dumps({
            "type": "global_notif",
            "from_user": notif.user.username,
            "message": notif.message,
            "ui_ref": 'ui_notification',
            "notif_link": f"/board/notifications/{notif.id}/redirect/",
            "system": notif.system,
            "created_at": notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }))


async def onconnect_send_notifications2(self):
    print('onconnect notification called')
    """
    Send all unread notifications to the connected user when they join.
    """
    # Use select_related to fetch related user in the same query synchronously
    def get_unread_notifications():
        return list(
            self.Notification.objects
                .filter(to_user=self.user, is_read=False)
                .select_related('user')  # eager load user FK
                .order_by('-created_at')
        )

    unread_notifications = await database_sync_to_async(get_unread_notifications)()

    for notif in unread_notifications:
        await self.send(text_data=json.dumps({
            "type": "global_notif",
            "from_user": notif.user.username,  # no lazy DB call here now
            "message": notif.message,
            "ui_ref": 'ui_notification',
            "notif_link": f"/board/notifications/{notif.id}/redirect/",  
           # "notif_link" : "#",
            "system": notif.system,
            "created_at": notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }))


async def on_bet_inv(self, data):
    to_user_id = data.get('to_user_id')
    bet_team = data.get('bet_team')
    bet_amount = data.get('bet_amount')

    if not (to_user_id and bet_team and bet_amount):
        return

    to_user = await database_sync_to_async(self.User.objects.get)(id=to_user_id)
    
    use_sec_wallet = False
    if self.room.is_signal:
        use_sec_wallet = True    
    
    wallet_ok = await deduct_wallet(self.user.profile, bet_amount, use_sec_wallet)
    if not wallet_ok:
        await self.send(text_data=json.dumps({
        'error': "Insufficient balance to place this bet."}))
        return

    opposite_team = 'Black' if bet_team == 'White' else 'White'

    # Message now shows it as a challenge
    full_message = f"{self.user.username} challenged you to bet against their bet, Rs. {bet_amount}! They chose Team {bet_team}. You will be Team {opposite_team}. "


    #full_message = f"{self.user.username} invited you to bet on team {bet_team} for Rs. {bet_amount}"

    # Save notification to DB
    notification = await database_sync_to_async(self.Notification.objects.create)(
        user=self.user,
        to_user=to_user,
        room=self.room,
        system='BETINV',
        message=full_message,
        bet_team=bet_team,
        bet_amount=bet_amount
    )

    # Send over WebSocket via 'global_notif'
    await self.channel_layer.group_send(
        f"user_{to_user_id}",
        {
            'type': 'global_notif',
            'from_user': self.user.username,
            'message': full_message,
            'ui_ref' : 'ui_notification',
            'system': 'BETINV',
            "notif_link": f"/board/notifications/{notification.id}/redirect/",  # auto redirect URL
            #"notif_link" : "#",
        }
    )
