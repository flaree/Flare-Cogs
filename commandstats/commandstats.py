import asyncio
import datetime
import logging
from collections import OrderedDict
from copy import deepcopy
from typing import Counter, Optional

import discord
import tabulate
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i : i + n]


log = logging.getLogger("red.flare.commandstats")


class CommandStats(commands.Cog):
    """Command Statistics."""

    __version__ = "0.0.5"

    def format_help_for_context(self, ctx):
        """Thanks Sinbad."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\nCog Version: {self.__version__}"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1398467138476, force_registration=True)
        default_global = {"globaldata": Counter({}), "guilddata": {}}
        self.config.register_global(**default_global)
        self.cache = {"guild": {}, "session": Counter({})}
        self.session = Counter()
        self.session_time = datetime.datetime.utcnow()
        self.bg_loop_task = self.bot.loop.create_task(self.bg_loop())

    async def red_get_data_for_user(self, *, user_id: int):
        # this cog does not story any data
        return {}

    async def red_delete_data_for_user(self, *, requester, user_id: int) -> None:
        # this cog does not story any data
        pass

    async def bg_loop(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                await self.update_global()
                await self.update_data()
                await asyncio.sleep(300)
            except Exception as exc:
                log.error("Exception in bg_loop: ", exc_info=exc)
                self.bg_loop_task.cancel()

    def cog_unload(self):
        if self.bg_loop_task:
            self.bg_loop_task.cancel()
        asyncio.create_task(self.update_data())
        asyncio.create_task(self.update_global())

    def record(self, ctx, name):
        guild = ctx.message.guild
        if not ctx.message.author.bot:
            if guild is not None:
                if str(guild.id) not in self.cache["guild"]:
                    self.cache["guild"][str(guild.id)] = Counter({})
                if name not in self.cache["guild"][str(guild.id)]:
                    self.cache["guild"][str(guild.id)][name] = 1
                else:
                    self.cache["guild"][str(guild.id)][name] += 1
            if name not in self.cache["session"]:
                self.cache["session"][name] = 1
            else:
                self.cache["session"][name] += 1
            if name not in self.session:
                self.session[name] = 1
            else:
                self.session[name] += 1

    @commands.Cog.listener()
    async def on_command(self, ctx):
        """Record standard command events."""
        name = str(ctx.command)
        self.record(ctx, name)

    @commands.Cog.listener()
    async def on_commandstats_action(self, ctx):
        """Record action events (i.e. other cog emits 'commandstats_action')."""
        name = str(ctx.command)
        self.record(ctx, name)

    @commands.is_owner()
    @commands.group(invoke_without_command=True)
    async def cmd(self, ctx, *, command: str = None):
        """Group command for command stats.

        This command does not log the issuing command.
        """
        await self.update_global()
        data = await self.config.globaldata()
        if not data:
            return await ctx.send("No commands have been used yet.")
        if command is None:
            data = OrderedDict(sorted(data.items(), key=lambda t: t[1], reverse=True))
            stats = []
            for cmd, amount in data.items():
                stats.append([f"{cmd}", f"{amount} time{'s' if amount > 1 else ''}!"])
            a = chunks(stats, 15)
            embeds = []
            for items in a:
                stats = []
                for item in items:
                    stats.append(item)
                embed = discord.Embed(
                    title="Commands used",
                    colour=await self.bot.get_embed_color(ctx.channel),
                    description=box(
                        tabulate.tabulate(stats, headers=["Command", "Times Used"]), lang="prolog"
                    ),
                )
                embeds.append(embed)
            if len(embeds) == 1:
                await ctx.send(embed=embeds[0])
            else:
                await menu(ctx, embeds, DEFAULT_CONTROLS)

        else:
            if command in data:
                await ctx.send(f"`{command}` has been used {data[command]} times!")
            else:
                await ctx.send(f"`{command}` hasn't been used yet!")

    @cmd.command(aliases=["server"])
    async def guild(
        self,
        ctx,
        server: Optional[commands.converter.GuildConverter] = None,
        *,
        command: str = None,
    ):
        """Guild Command Stats."""
        if not server:
            server = ctx.guild
        await self.update_data()
        data = await self.config.guilddata()
        data = data[str(server.id)]
        if not data:
            return await ctx.send(f"No commands have been used in {server.name} yet.")
        if command is None:
            data = OrderedDict(sorted(data.items(), key=lambda t: t[1], reverse=True))
            stats = []
            for cmd, amount in data.items():
                stats.append([f"{cmd}", f"{amount} time{'s' if amount > 1 else ''}!"])
            a = chunks(stats, 15)
            embeds = []
            for items in a:
                stats = []
                for item in items:
                    stats.append(item)
                embed = discord.Embed(
                    title=f"Commands used in {server.name}",
                    colour=await self.bot.get_embed_color(ctx.channel),
                    description=box(
                        tabulate.tabulate(stats, headers=["Command", "Times Used"]), lang="prolog"
                    ),
                )
                embeds.append(embed)
            if len(embeds) == 1:
                await ctx.send(embed=embeds[0])
            else:
                await menu(ctx, embeds, DEFAULT_CONTROLS)

        else:
            if command in data:
                await ctx.send(
                    f"`{command}` has been used {data[command]} time{'s' if data[command] > 1 else ''} in {ctx.guild}!"
                )
            else:
                await ctx.send(f"`{command}` hasn't been used in {server.name}!")

    @cmd.command()
    async def session(self, ctx, *, command: str = None):
        """Session command stats."""
        data = deepcopy(self.session)
        if str(ctx.command) in data:
            data[str(ctx.command)] += 1
        else:
            data[str(ctx.command)] = 1
        if not data:
            return await ctx.send("No commands have been used in this session")
        if command is None:
            data = OrderedDict(sorted(data.items(), key=lambda t: t[1], reverse=True))
            stats = []
            for cmd, amount in data.items():
                stats.append([f"{cmd}", f"{amount} time{'s' if amount > 1 else ''}!"])
            a = chunks(stats, 15)
            embeds = []
            for items in a:
                stats = []
                for item in items:
                    stats.append(item)
                embed = discord.Embed(
                    title="Commands used in this session",
                    colour=await self.bot.get_embed_color(ctx.channel),
                    description=box(
                        tabulate.tabulate(stats, headers=["Command", "Times Used"]), lang="prolog"
                    ),
                    timestamp=self.session_time,
                )
                embed.set_footer(text="Recording sessions commands since")
                embeds.append(embed)
            if len(embeds) == 1:
                await ctx.send(embed=embeds[0])
            else:
                await menu(ctx, embeds, DEFAULT_CONTROLS)

        else:
            if command in data:
                await ctx.send(
                    f"`{command}` has been used {data[command]} time{'s' if data[command] > 1 else ''} in this session!"
                )
            else:
                await ctx.send(f"`{command}` hasn't been used in this session!")

    async def update_data(self):
        async with self.config.guilddata() as guilddata:
            for guild in self.cache["guild"]:
                if guild in guilddata:
                    olddata = Counter(guilddata[guild])
                else:
                    olddata = Counter({})
                data = Counter(olddata + self.cache["guild"][guild])
                self.cache["guild"][guild] = Counter()
                guilddata[guild] = data

    async def update_global(self):
        globaldata = await self.config.globaldata()
        data = globaldata + self.cache["session"]
        await self.config.globaldata.set(data)
        self.cache["session"] = Counter({})
