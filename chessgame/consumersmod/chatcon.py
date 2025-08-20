from .utils import get_last_messages,save_chat_message
import asyncio
import json
import os 

async def onchatconnect(self):
    last_messages = await get_last_messages(self.room)
    for msg in last_messages:
        await self.send(text_data=json.dumps({
        'type': 'chat',
        'sender': msg.user.username,
        'message': msg.message,
        'timestamp': msg.timestamp.isoformat()
        }))



async def onchat_receive(self):
    if self.msg_type == 'chat':
        message = self.data.get('message', '').strip()
        print(message)
        if message:
            await save_chat_message(self,message)
            await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'sender': self.user.username,
                'message': message,
            }
            )
        return