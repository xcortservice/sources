import aiomysql
from typing import Optional, Dict, Any
from data.config import CONFIG
from .logger import Logger

class Database:
    def __init__(self):
        self.logger = Logger()
        self.pool: Optional[aiomysql.Pool] = None
        
    async def initialize(self) -> None:
        try:
            self.pool = await aiomysql.create_pool(
                host="localhost",
                port=3306,
                user=CONFIG['database']['user'],
                password=CONFIG['database']['password'],
                db=CONFIG['database']['name'],
                autocommit=True
            )
            self.logger.info("[DB] Database connection established")
            #await self._setup_tables()
        except Exception as e:
            self.logger.error(f"[DB] Database connection failed: {e}")
            raise
    
    async def _setup_tables(self) -> None:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        uid VARCHAR(10) PRIMARY KEY,
                        discord_username VARCHAR(255),
                        discord_displayname VARCHAR(255),
                        discord_id BIGINT UNIQUE,
                        cash BIGINT DEFAULT 5000,
                        bank BIGINT DEFAULT 0,
                        banklimit BIGINT DEFAULT 50000,
                        premium BOOLEAN DEFAULT FALSE,
                        admin BOOLEAN DEFAULT FALSE,
                        blacklisted BOOLEAN DEFAULT FALSE,
                        lastfm VARCHAR(255) DEFAULT NULL,
                        statsfm VARCHAR(255) DEFAULT NULL,
                        items TEXT DEFAULT NULL,
                        cases TEXT DEFAULT NULL
                    )
                """)
                
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS items (
                        id INT AUTO_INCREMENT PRIMARY KEY
                    )
                """)
                
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS cases (
                        id INT AUTO_INCREMENT PRIMARY KEY
                    )
                """)
                
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS emojis (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        dname TEXT NOT NULL
                    )
                """)
                await conn.commit()
    
    async def get_next_uid(self) -> str:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM users")
                count = await cur.fetchone()
                return str(count[0] + 1)
    
    async def register_user(self, discord_id: int, username: str, displayname: str) -> None:
        uid = await self.get_next_uid()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO users (uid, discord_username, discord_displayname, discord_id) "
                    "VALUES (%s, %s, %s, %s)",
                    (uid, username, displayname, discord_id)
                )
                await conn.commit()

    async def get_emoji(self, name: str) -> Optional[str]:
        """Get emoji display name by emoji name
        
        Args:
            name (str): The emoji name to look up
            
        Returns:
            Optional[str]: The emoji display name (<:name:id>) or None if not found
        :nerd:
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT dname FROM emojis WHERE name = %s",
                    (name,)
                )
                result = await cur.fetchone()
                return result[0] if result else None