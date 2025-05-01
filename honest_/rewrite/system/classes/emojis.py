from typing import Optional, Dict
import asyncio
from functools import wraps

class EmojiManager:
    def __init__(self, bot):
        self.bot = bot
        self._cache: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Load all emojis into cache on startup"""
        async with self._lock:
            async with self.bot.db.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT name, dname FROM emojis")
                    results = await cur.fetchall()
                    self._cache = {row[0]: row[1] for row in results}
    
    async def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Get emoji by name from cache asynchronously
        
        Args:
            name (str): Name of the emoji to retrieve
            default (Optional[str]): Default value if emoji not found
            
        Returns:
            Optional[str]: The emoji display name or default value
        """
        async with self._lock:
            return self._cache.get(name, default)
            
    async def refresh(self):
        """Refresh the emoji cache from database"""
        await self.initialize()
        
    async def add(self, name: str, dname: str):
        """Add a new emoji to cache"""
        async with self._lock:
            self._cache[name] = dname
            
    async def remove(self, name: str):
        """Remove an emoji from cache"""
        async with self._lock:
            self._cache.pop(name, None)