from typing import Optional
from sqlalchemy.future import select
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.sql_models import Chat


class ChatRepository:

    async def create(self,chat_data: dict) -> Chat:

        async with AsyncSessionLocal() as session:
            db_chat = Chat(**chat_data)
            session.add(db_chat)
            await session.commit()
            await session.refresh(db_chat)
            return db_chat
        

    async def get_by_id(self, chat_id:str ) -> Optional[Chat]:

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Chat).filter(Chat.chat_id == chat_id))

            return result.scalars().first()


    async def update(self,chat_id:str,updates:dict) -> Optional[Chat]:
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Chat).filter(Chat.chat_id == chat_id)
            )
            chat = result.scalars().first()

            if chat:

                for key,value in updates.items():
                    setattr(chat,key,value)
                await session.commit()
                await session.refresh(chat)

            return chat

    async def exists(self,chat_id:str) -> bool:

        chat = await self.get_by_id(chat_id)
        return chat is not None
