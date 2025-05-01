import discord
from discord.ext import commands
import os
import asyncio
from data.config import CONFIG
from system.classes.db import Database
from discord import app_commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    async def cog_load(self):
        """Initialize database connection when cog loads"""
        await self.db.initialize()
    
    async def cog_unload(self):
        """Clean up database connection when cog unloads"""
        if self.db.pool:
            self.db.pool.close()
            await self.db.pool.wait_closed()
    
    async def cog_check(self, ctx):
        return ctx.author.id in CONFIG['owners']

    @commands.command(name='aemojis')
    async def update_emojis(self, ctx, action: str = 'update'):
        """Emoji manager for the bot. (admin)"""
        if action.lower() != 'update':
            return await ctx.send('Invalid action. Use: ,aemojis update')
        
        emoji_path = './emojis'
        if not os.path.exists(emoji_path):
            return await ctx.send('❌ Emojis directory not found!')
        
        dev_server = self.bot.get_guild(CONFIG['dev_server_id'])
        if not dev_server:
            return await ctx.send('❌ Development server not found!')
        
        status_msg = await ctx.send('🔄 Processing emojis...')
        
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT name FROM emojis")
                existing_emojis = [row[0] for row in await cur.fetchall()]
                
                added = 0
                skipped = 0
                failed = 0
                
                for filename in os.listdir(emoji_path):
                    if filename.endswith(('.png', '.gif', '.jpg', '.jpeg', '.webp')):
                        name = os.path.splitext(filename)[0].lower()
                        
                        if name in existing_emojis:
                            skipped += 1
                            continue
                        
                        try:
                            with open(os.path.join(emoji_path, filename), 'rb') as f:
                                emoji_data = f.read()
                                
                            uploaded_emoji = await dev_server.create_custom_emoji(
                                name=name,
                                image=emoji_data,
                                reason=f"Uploaded by {ctx.author}"
                            )
                            await cur.execute(
                                "INSERT INTO emojis (name, dname) VALUES (%s, %s)",
                                (name, f"<:{uploaded_emoji.name}:{uploaded_emoji.id}>")
                            )
                            added += 1
                            await asyncio.sleep(1.5)
                            
                        except discord.HTTPException as e:
                            failed += 1
                            self.bot.logger.error(f"Failed to upload emoji {name}: {e}")
                            continue
                        
                await conn.commit()
        
        result = f"✅ Process complete!\nAdded: {added}\nSkipped: {skipped}"
        if failed > 0:
            result += f"\nFailed: {failed}"
            
        await status_msg.edit(content=result)

async def setup(bot):
    await bot.add_cog(Admin(bot))