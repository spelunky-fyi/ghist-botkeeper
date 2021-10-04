import colorsys
import io
from math import ceil

import discord
from discord.ext import commands
from ttf_opensans import opensans
from PIL import Image, ImageDraw


from ghist.checks import SUPPORT_CHANNELS, is_support_channel

COLOR_PREFIX = "Color: "

IMG_FONT = opensans(font_weight=600).imagefont(size=16)
FONT_X_PADDING = 5
FONT_Y_PADDING = 5


def chunk(items, num_chunks=3):
    chunks = []

    if not items:
        return chunks

    chunk_size = ceil(len(items) / num_chunks)
    for idx in range(0, len(items), chunk_size):
        chunks.append(items[idx : idx + chunk_size])

    return chunks


def get_text_color(rgb):
    if (rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114) > 160:
        return (0, 0, 0, 255)
    return (255, 255, 255, 255)


def make_available_colors_image(roles):

    max_column_widths = []
    max_text_height = 0

    roles = [
        (k, v)
        for k, v in sorted(
            roles.items(), key=lambda role: colorsys.rgb_to_hsv(*role[1].color.to_rgb())
        )
    ]
    roles = chunk(roles, 3)

    for column_idx, column in enumerate(roles):
        for role_name, _ in column:
            if len(max_column_widths) == column_idx:
                max_column_widths.append(0)

            width, height = IMG_FONT.getsize(role_name, None, None, None, 0)
            max_text_height = max(max_text_height, height)
            max_column_widths[column_idx] = max(max_column_widths[column_idx], width)

    img_width = sum(max_column_widths) + ((len(roles) * 2) * FONT_X_PADDING)
    max_len_column = max(map(len, roles))
    img_height = (max_len_column * max_text_height) + (
        (max_len_column * 2) * FONT_Y_PADDING
    )

    out_img = Image.new("RGBA", (img_width, img_height))
    img_draw = ImageDraw.Draw(out_img)

    x0 = 0
    for column_idx, column in enumerate(roles):
        column_width = max_column_widths[column_idx] + FONT_X_PADDING * 2
        for row_idx, (role_name, role) in enumerate(column):
            row_height = max_text_height + FONT_Y_PADDING * 2
            x1 = x0 + column_width - 1
            y0 = row_idx * row_height
            y1 = y0 + row_height - 1
            img_draw.rectangle([x0, y0, x1, y1], fill=role.color.to_rgb())
            img_draw.text(
                (x0 + FONT_X_PADDING, y0 + FONT_Y_PADDING),
                role_name,
                font=IMG_FONT,
                fill=get_text_color(role.color.to_rgb()),
            )

        x0 += column_width

    buf = io.BytesIO()
    out_img.save(buf, format="PNG")
    buf.seek(0)

    return buf


class Color(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def get_colors_roles(roles):
        colors = {}
        for role in roles:
            if role.name.startswith(COLOR_PREFIX):
                colors[role.name[len(COLOR_PREFIX) :].lower()] = role
        return colors

    def get_guild_colors(self, ctx):
        return self.get_colors_roles(ctx.guild.roles)

    def get_author_colors(self, ctx):
        return self.get_colors_roles(ctx.author.roles)

    @commands.command(
        aliases=["colour"],
        help=(
            "Set the color of your name.\n"
            "`none` can be passed to clear your color.\n"
            "Calling the command with no arguments will show available colors."
        ),
        brief="Set the color of your name.",
        usage="color_name",
    )
    @commands.check(is_support_channel)
    async def color(self, ctx, *args):
        guild_color_roles = self.get_guild_colors(ctx)

        # Check that the user passed a color at all
        if not args:
            img_file = make_available_colors_image(guild_color_roles)
            await ctx.send(
                "Available colors:", file=discord.File(img_file, "colors.png")
            )
            return

        requested_color = " ".join(args).strip().lower()
        if requested_color.lower() == "none":
            await ctx.author.remove_roles(*self.get_author_colors(ctx).values())
            await ctx.message.add_reaction("👍")
            return

        # Check that the requested color is available.
        target_role = guild_color_roles.get(requested_color)
        if target_role is None:
            await ctx.send(
                f"The color `{requested_color}` isn't available. Type `!color` to see available colors."
            )
            return

        # Give requested color role. We add the color first as small
        # UI benefit so we don't see the color flash back to default color
        # when changing colors.
        await ctx.author.add_roles(target_role)

        # Remove other color roles
        roles_to_remove = set(self.get_author_colors(ctx).values())
        roles_to_remove.discard(target_role)
        if roles_to_remove:
            await ctx.author.remove_roles(*roles_to_remove)

        await ctx.message.add_reaction("👍")
