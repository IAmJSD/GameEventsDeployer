from dopy.manager import DoManager
import yaml
import discord
import asyncio
import logging
import time
import os
# Imports go here.

loop = asyncio.get_event_loop()
# Gets the event loop.

logger = logging.getLogger("game_events")
logging.basicConfig(level=logging.INFO)
# Configures logging.

client = discord.Client(loop=loop)
# Defines the Discord client.

config = yaml.load(
    open("config.yaml", "r")
)
# Loads the config.

do_client = DoManager(
    None,
    config["DIGITALOCEAN_API_KEY"],
    api_version=2
)
# Defines the DigitalOcean client.


class BrandedEmbed(discord.Embed):
    def __init__(self, user, **kwargs):
        super().__init__(**kwargs)
        self.set_author(
            name=user.name,
            icon_url=user.avatar_url
        )
        self.set_footer(
            text=f"{client.user.name} - Created by JakeMakesStuff#0001"
        )
# The branded embed.


class VPSNuker:
    def __init__(self, loop, user_id, droplet_id, secs_until_kill):
        self.loop = loop
        loop.create_task(
            self.timed_nuke_vps(user_id, secs_until_kill, droplet_id)
        )

    @staticmethod
    def nuke_vps(droplet_id):
        try:
            do_client.destroy_droplet(droplet_id)
        except BaseException:
            pass

    async def timed_nuke_vps(self, user_id, secs_until_kill, droplet_id):
        await asyncio.sleep(secs_until_kill)
        await self.loop.run_in_executor(
            None,
            self.nuke_vps,
            droplet_id
        )

        try:
            user = client.get_user(user_id)
        except discord.NotFound:
            return

        try:
            await user.send(
                embed=BrandedEmbed(
                    client.user,
                    title="⏲ VPS killed.",
                    description="A VPS you generated has been "
                    "killed.",
                    colour=discord.Colour.red()
                )
            )
        except discord.Forbidden:
            return
# Nukes VPS's when their time is up.


def timed_deletion_recover():
    for droplet in do_client.all_active_droplets():
        droplet_name_split = droplet["name"].split("-")
        if len(droplet_name_split) == 3:
            droplet_destruction_time = int(droplet_name_split[2].split(".")[0])
            secs_until_destruction = droplet_destruction_time - time.time()
            if 0 > secs_until_destruction:
                do_client.destroy_droplet(droplet['id'])
            else:
                user_id = int(droplet_name_split[1])
                VPSNuker(
                    loop, user_id, droplet['id'], secs_until_destruction
                )
# Recovers the timed nukers.


async def dm_maintainers(embed):
    for maintainer in config["BOT_MAINTAINERS"]:
        while True:

            try:
                maintainer_duser = client.get_user(
                    maintainer
                )
            except BaseException:
                logger.warning(
                    "Could not find the maintainer"
                    f" {maintainer} on Discord."
                )
                break

            try:
                await maintainer_duser.send(
                    embed=embed
                )
                logger.info(
                    f"DM'd {maintainer_duser} a maintainer DM."
                )
            except discord.HTTPException:
                logger.warning(
                    f"Could not DM {maintainer_duser}."
                )

            break
# A function made to DM maintainers.


async def show_help(msg):
    help_em = BrandedEmbed(
        msg.author,
        title="👋 Hello!",
        description="I can do the following things:",
        colour=discord.Colour.blurple()
    )
    help_em.add_field(
        name=f"@{client.user} ping",
        value="Pings the bot.",
        inline=False
    )
    help_em.add_field(
        name=f"@{client.user} deploy [game type] [hours active]",
        value="Deploys a game server. **Please set the hours active"
        " to something reasonable.**",
        inline=False
    )
    try:
        await msg.channel.send(
            embed=help_em,
            delete_after=60
        )
    except discord.Forbidden:
        pass
# Shows the help screen.


async def run_ping(message):
    t_1 = time.perf_counter()
    async with message.channel.typing():
        t_2 = time.perf_counter()
    time_delta = round((t_2 - t_1) * 1000)
    try:
        await message.channel.send(
            embed=BrandedEmbed(
                message.author,
                title="🏓 Pong!",
                description=f"This took {time_delta} ms.",
                colour=discord.Colour.blurple()
            ),
            delete_after=15
        )
    except discord.Forbidden:
        pass
# Runs the ping command.


async def run_deploy(message, args):
    if len(args) < 2:
        try:
            await message.channel.send(
                embed=BrandedEmbed(
                    message.author,
                    title="💬 Not enough arguments.",
                    description="You need the game type and "
                    "the length you want the VPS to be active"
                    " for.",
                    colour=discord.Colour.red()
                ),
                delete_after=15
            )
        except discord.Forbidden:
            pass

        return

    try:
        hours = int(args[1]) * 3600
    except ValueError:
        try:
            await message.channel.send(
                embed=BrandedEmbed(
                    message.author,
                    title="💬 Invalid amount of hours.",
                    description="Your second argument needs to"
                    " be a integer.",
                    colour=discord.Colour.red()
                ),
                delete_after=15
            )
        except discord.Forbidden:
            pass

        return

    if hours == 0:
        try:
            await message.channel.send(
                embed=BrandedEmbed(
                    message.author,
                    title="⏲ Time is up!",
                    description="You specified 0 hours.",
                    colour=discord.Colour.red()
                ),
                delete_after=15
            )
        except discord.Forbidden:
            pass

        return

    gamemode = args[0]

    if not os.path.isfile(f"./build_scripts/{gamemode}.sh"):
        try:
            await message.channel.send(
                embed=BrandedEmbed(
                    message.author,
                    title="🎲 Invalid game mode.",
                    description="I do not have a build script "
                    "for that.",
                    colour=discord.Colour.red()
                ),
                delete_after=15
            )
        except discord.Forbidden:
            pass

        return

    build_script = open(f"./build_scripts/{gamemode}.sh", "r").read()

    build_embed = BrandedEmbed(
        message.author,
        title="⚒ Building...",
        description="Building VPS...\n",
        colour=discord.Colour.blurple()
    )

    try:
        build_msg = await message.channel.send(
            embed=build_embed
        )
    except discord.Forbidden:
        return

    try:
        def non_async_wrap():
            return do_client.new_droplet(
                f"{gamemode}-{message.author.id}-{time.time()+hours}",
                "s-2vcpu-4gb",
                "ubuntu-16-04-x64",
                "lon1",
                user_data=build_script
            )

        droplet = await loop.run_in_executor(
            None,
            non_async_wrap
        )
    except BaseException as e:
        try:
            await build_msg.edit(
                embed=BrandedEmbed(
                    message.author,
                    title="⚒ Build error.",
                    description=f"There was a build error: ```{e}```",
                    colour=discord.Colour.red()
                )
            )
        except discord.Forbidden:
            pass

        await dm_maintainers(
            BrandedEmbed(
                client.user,
                title="⚒ Build error.",
                description=f"{message.author} tried to run `{message.content}`"
                f" but I could not build because of this error: ```{e}```",
                colour=discord.Colour.red()
            )
        )

        return

    build_embed.description += "Waiting for VPS to come online...\n"

    try:
        await build_msg.edit(
            embed=build_embed
        )
    except discord.Forbidden:
        pass

    def get_droplet_status(droplet_id):
        d = do_client.show_droplet(droplet_id)
        return d["status"] == "active", d

    while True:
        await asyncio.sleep(1)
        try:
            status, new_droplet = await loop.run_in_executor(
                None,
                get_droplet_status,
                droplet["id"]
            )
        except BaseException:
            status = False
        if status:
            break

    ip = new_droplet['networks']['v4'][0]['ip_address']
    try:
        await build_msg.edit(
            embed=BrandedEmbed(
                message.author,
                title="⚒ Build done.",
                description=f"The VPS is live over at `{ip}`."
                f" It will be destroyed in {args[1]} hour(s)."
                " If you need this changed, DM JakeMakesStuff#0001.",
                colour=discord.Colour.green()
            )
        )
    except discord.Forbidden:
        pass

    await dm_maintainers(
        BrandedEmbed(
            client.user,
            title="⚒ VPS built.",
            description=f"{message.author} created the VPS "
            f"`{droplet['name']}` with the IP `{ip}`. They made it last "
            f"{args[1]} hour(s).",
            colour=discord.Colour.green()
        )
    )

    VPSNuker(loop, message.author.id, droplet['id'], hours)
# Allows you to deploy a DigitalOcean droplet.


async def unknown_cmd(message):
    try:
        await message.channel.send(
            embed=BrandedEmbed(
                message.author,
                title="❔ Unknown command.",
                description="I do not know that command. "
                "Please just tag me for help.",
                colour=discord.Colour.red()
            ),
            delete_after=15
        )
    except discord.Forbidden:
        pass
# The message for unknown commands.


@client.event
async def on_ready():
    await client.change_presence(
        activity=discord.Game(
            f"@{client.user} help"
        )
    )
    await dm_maintainers(
        BrandedEmbed(
            client.user,
            title="👋 I'm alive.",
            description="I am alive! You are "
            "marked as a maintainer.",
            colour=discord.Colour.blurple()
        )
    )
# Defines on_ready.


@client.event
async def on_message(message):
    if len(message.mentions) == 0 or message.author.bot:
        return

    if client.user.id not in [m.id for m in message.mentions]:
        return

    # Alright! We were mentioned.

    if message.channel.id not in config["ALLOWED_CHANNELS"]:
        try:
            await message.channel.send(
                embed=BrandedEmbed(
                    message.author,
                    title="💬 Invalid channel.",
                    description="This channel has not been set "
                    "to be allowed in the config.",
                    colour=discord.Colour.red()
                ),
                delete_after=15
            )
        except discord.Forbidden:
            pass

        return

    allowed = False
    for role in message.author.roles:
        if role.id in config["ALLOWED_ROLES"]:
            allowed = True
            break

    if not allowed:
        try:
            await message.channel.send(
                embed=BrandedEmbed(
                    message.author,
                    title="👥 Required role not found.",
                    description="You do not have a role "
                    "which is set as a allowed role in the "
                    "config.",
                    colour=discord.Colour.red()
                ),
                delete_after=15
            )
        except discord.Forbidden:
            pass

        return

    # We can treat this as something we handle now.

    msg_split = [
        m for m in message.content.lower().split(" ") if str(client.user.id) not in m and m != ""
    ]

    if len(msg_split) == 0 or msg_split[0] == "help":
        await show_help(message)
    elif msg_split[0] == "ping":
        await run_ping(message)
    elif msg_split[0] == "deploy":
        await run_deploy(message, msg_split[1:])
    else:
        await unknown_cmd(message)
# Defines on_message.

timed_deletion_recover()
client.run(config["DISCORD_TOKEN"])
# Starts the bot.
