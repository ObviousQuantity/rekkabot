import discord
import asyncio
from discord import DMChannel
from discord.ext import commands, tasks
from typing import Optional
from datetime import datetime
from discord.ext.commands import CheckFailure
from discord.ext.commands import command, has_permissions, bot_has_permissions
from discord.ext.commands import Cog, Greedy
from datetime import datetime,timedelta
from discord import Embed, Member
import json

class Moderation(commands.Cog):

    def __init__(self,client):
        self.client = client

    #Add words to the filter
    @commands.guild_only()
    @commands.command(name = "addword",
                      brief = "add a word from the filter",
                      aliases = ["aw"])
    @commands.has_permissions(manage_messages=True)
    async def addword(self,ctx,*,word):
        data = await self.client.config.find(ctx.guild.id)
        if not data or "filter" not in data:
            await self.client.config.upsert({"_id": ctx.guild.id, "filter": []})
            data = await self.client.config.find(ctx.guild.id)

        filteredwords = data["filter"]
        if word in filteredwords:
            await ctx.send(f"**{word}** is already in the filter")
        else:
            filteredwords.append(word)
            await self.client.config.upsert({"_id": ctx.guild.id, "filter": filteredwords})

    #Remove words from the filter
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.command(name = "removeword",
                      brief = "remove a word from the filter",
                      aliases = ["rw"])
    async def removeword(self,ctx,*,word):
        data = await self.client.config.find(ctx.guild.id)
        if not data or "filter" not in data:
            await self.client.config.upsert({"_id": ctx.guild.id, "filter": []})
            data = await self.client.config.find(ctx.guild.id)

        filteredwords = data["filter"]
        if word not in filteredwords:
            await ctx.send(f"**{word}** is not in the filter")
        else:
            filteredwords.remove(word)
            await self.client.config.upsert({"_id": ctx.guild.id, "filter": filteredwords})        

    #View Filter
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.command(name = "viewfilter",
                      brief = "view the words being filtered",
                      aliases = ["filter","f","vf"])
    async def viewfilter(self,ctx):
        data = await self.client.config.find(ctx.guild.id)
        filteredwords = data["filter"]

        try:
            embed = Embed(title = "Filter",
                            colour = 0x3498DB)

            fields  = [("Current Words Being Filtered",'\n'.join(filteredwords),False)]

            for name,value,inline in fields:
                embed.add_field(name = name, value = value, inline = inline)

            await ctx.send(embed=embed)
        except:
                embed=discord.Embed()
                embed.add_field(name="❌ Couldn't Get Filter", value=f"something went wrong or the list is empty. Use the **addword** command to filter a word", inline=False)
                await ctx.send(embed=embed)

    #Clear/Purge
    @commands.guild_only()
    @commands.command(name = "clear", aliases = ["purge"], help = "deletes messages")
    @commands.bot_has_permissions(manage_messages = True)
    @commands.has_permissions(manage_messages = True)
    async def clear_messages(self,ctx,targets: Greedy[Member],limit: int = 1):

        def _check(message):
            return not len(targets) or message.author in targets

        if 0 < limit <= 100:
            with ctx.channel.typing():
                await ctx.message.delete()
                deleted = await ctx.channel.purge(limit=limit,check=_check)

                await ctx.send(f"Deleted {len(deleted):,} messages",delete_after = 5)
        else:
            await ctx.send("The limit provided is not within acceptable bounds")

    #Nuke
    @commands.guild_only()
    @commands.command(name = "nuke",help = "deletes the chanel and readds it")
    @commands.has_permissions(manage_messages=True)
    async def nuke(self, ctx, channel: discord.TextChannel = None):
        if channel == None: 
            await ctx.send("You did not mention a channel!")
            return

        nuke_channel = discord.utils.get(ctx.guild.channels, name=channel.name)

        if nuke_channel is not None:
            new_channel = await nuke_channel.clone(reason="Has been Nuked!")
            await nuke_channel.delete()
            await new_channel.send("THIS CHANNEL HAS BEEN NUKED!")
            await ctx.send("Nuked the Channel sucessfully!")

        else:
            await ctx.send(f"No channel named {channel.name} was found!")

    #Kick
    @commands.guild_only()
    @command(name = "kick")
    @bot_has_permissions(kick_members = True)
    @has_permissions(kick_members = True)
    async def kick(self,ctx,targets: Greedy[Member],*,reason: Optional[str] = "No reason provided"):

        if not len(targets):
            embed=discord.Embed()
            embed.add_field(name="❌ Missing Targets", value=f"please mention the people you wanna kick", inline=False)
            await ctx.send(embed=embed,delete_after=5)
            return

        else:
            for target in targets:
                #Checks if the role of the bot is higher and make sure the target is not an admin
                if (ctx.guild.me.top_role.position > target.top_role.position and not target.guild_permissions.administrator):
                    await target.kick(reason = reason)

                    embed = Embed(title = "Member Kicked",
                                  colour = 0xDD2222,
                                  timestamp = datetime.utcnow())

                    embed.set_thumbnail(url = target.avatar_url)

                    fields = [("Member",f"{target.name} a.k.a {target.display_name}",False),
                              ("Kicked By", ctx.author.display_name,False),
                              ("Reason",reason,False)]

                    for name,value,inline in fields:
                        embed.add_field(name = name, value = value, inline = inline)
                    
                    with open("./data/server_settings.json","r") as f:
                        settings = json.load(f)
                    
                    if "logs_channel" in settings[str(ctx.guild.id)]:
                        if settings[str(ctx.guild.id)]["logs_channel"] != "":
                            log_channel_id = settings[str(ctx.guild.id)]["logs_channel"]
                            try:
                                channel = await self.client.fetch_channel(log_channel_id)
                                await channel.send(embed=embed)
                            except:
                                pass
                        else:
                            await ctx.send(embed=embed)

                else:
                    await ctx.send(f"{target.display_name} could not be kicked")

    #Mute Functions
    async def mute_members(self,message,targets,hours,reason):

        mute_role = discord.utils.get(message.guild.roles,name="mute")
        #Check if the mute role exisits
        if not mute_role:
            try:
                mute_role = await message.guild.create_role(name="mute")

                for channel in message.guild.channels:
                    await channel.set_permissions(mute_role,speak=False,send_messages=False,
                                                   read_message_history=True,read_messages=False)

            except discord.Forbidden:
                return

        unmutes = []

        for target in targets:
            if not mute_role in target.roles:
                if message.guild.me.top_role.position > target.top_role.position:
                    role_ids = ",".join([str(r.id) for r in target.roles])
                    end_time = datetime.utcnow() + timedelta(seconds=hours) if hours else None

                    await target.edit(roles=[mute_role])
                    #await ctx.target.add_roles(role)

                    embed = Embed(title = "Member Muted",
                                    colour = message.guild.owner.colour,
                                    timestamp = datetime.utcnow())

                    embed.set_thumbnail(url = target.avatar_url)

                    fields = [("Member",target.display_name,False),
                                ("Muted By",message.author.display_name,False),
                                ("Duration",f"{hours:,}hour(s)" if hours else "Indefinite",False),
                                ("Reason",reason,False)]

                    for name,value,inline in fields:
                        embed.add_field(name=name,value=value,inline=inline)

                    with open("./data/server_settings.json","r") as f:
                        settings = json.load(f)

                    if "logs_channel" in settings[str(message.guild.id)]:
                        if settings[str(message.guild.id)]["logs_channel"] != "":
                            log_channel_id = settings[str(message.guild.id)]["logs_channel"]
                            try:
                                channel = await self.client.fetch_channel(log_channel_id)
                                await channel.send(embed=embed)
                            except:
                                pass

                    if hours:
                        unmutes.append(target)

        return unmutes

    #Mute
    @commands.guild_only()
    @command(name = "mute")
    @bot_has_permissions(manage_roles = True)
    @has_permissions(manage_roles = True,manage_guild = True)
    async def mute_command(self,ctx,targets:Greedy[Member],hours:Optional[int],*,reason:Optional[str]):
        
        mute_role = discord.utils.get(ctx.guild.roles,name="mute")

        if not len(targets):
            embed=discord.Embed()
            embed.add_field(name="❌ Missing Targets", value=f"please mention the people you wanna mute", inline=False)
            await ctx.send(embed=embed,delete_after=5)
            return
        else:
            unmutes = await self.mute_members(ctx.message,targets,hours,reason)

            if len(unmutes):
                await asyncio.sleep(hours)
                await self.unmute_members(ctx.guild,targets)

    #Unmute Function
    async def unmute_members(self,guild,targets,*,reason="Mute time expired."):
        mute_role = discord.utils.get(guild.roles,name="mute")
        for target in targets:
            if mute_role in target.roles:
                await target.remove_roles(mute_role)

    #Unmute
    @commands.guild_only()
    @command(name = "unmute")
    @bot_has_permissions(manage_roles = True)
    @has_permissions(manage_roles = True,manage_guild = True)
    async def unmute_command(self,ctx,targets:Greedy[Member],*,reason: Optional[str] = "No reason provided"):
        if not len(targets):
            embed=discord.Embed()
            embed.add_field(name="❌ Missing Targets", value=f"please mention the people you wanna mute", inline=False)
            await ctx.send(embed=embed,delete_after=5)
        else:
            await self.unmute_members(ctx.guild,targets,reason=reason)

    #Ban
    @commands.guild_only()
    @command(name = "ban")
    @bot_has_permissions(ban_members = True)
    @has_permissions(ban_members = True)
    async def ban(self,ctx,targets: Greedy[Member],*,reason: Optional[str] = "No reason provided"):

        if not len(targets):
            embed=discord.Embed()
            embed.add_field(name="❌ Missing Targets", value=f"please mention the people you wanna ban", inline=False)
            await ctx.send(embed=embed,delete_after=5)
            return

        else:
            for target in targets:
                #Checks if the role of the bot is higher and make sure the target is not an admin
                if (ctx.guild.me.top_role.position > target.top_role.position and not target.guild_permissions.administrator):
                    await target.ban(reason = reason)

                    embed = Embed(title = "Member Banned",
                                  colour = 0xDD2222,
                                  timestamp = datetime.utcnow())

                    embed.set_thumbnail(url = target.avatar_url)

                    fields = [("Member",f"{target.name} a.k.a {target.display_name}",False),
                              ("Banned By", ctx.author.display_name,False),
                              ("Reason",reason,False)]

                    for name,value,inline in fields:
                        embed.add_field(name = name, value = value, inline = inline)

                    with open("./data/server_settings.json","r") as f:
                        settings = json.load(f)
                    
                    if "logs_channel" in settings[str(ctx.guild.id)]:
                        if settings[str(ctx.guild.id)]["logs_channel"] != "":
                            log_channel_id = settings[str(ctx.guild.id)]["logs_channel"]
                            try:
                                channel = await self.client.fetch_channel(log_channel_id)
                                await channel.send(embed=embed)
                            except:
                                pass
                        else:
                            await ctx.send(embed=embed)

                else:
                    await ctx.send(f"{target.display_name} could not be banned")

    #Unban
    @commands.guild_only()
    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self,ctx,*,member:discord.Member):
           banned_users = await ctx.guild.bans()
           member_name, member_discriminator = member.split("#")

           for ban_entry in banned_users:
               user = ban_entry.user

               if (user.name,user.discriminator) == (member_name,member_discriminator):
                   await ctx.guild.unban(user)
                   await ctx.send(f"Unbanned {user.mention}")
                   return

def setup(client):
   client.add_cog(Moderation(client))
