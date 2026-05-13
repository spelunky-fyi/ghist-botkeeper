import colorsys
import io
from math import ceil
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from ttf_opensans import opensans
from PIL import Image, ImageDraw


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

            left, top, right, bottom = IMG_FONT.getbbox(role_name)
            width = right - left
            height = bottom - top
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

    @app_commands.command(
        name="color",
        description="Set the color of your name. Omit to see available colors. Use `none` to clear.",
    )
    @app_commands.describe(
        name="A color name from the available list, or `none` to clear."
    )
    async def color(
        self, interaction: discord.Interaction, name: Optional[str] = None
    ):
        guild_color_roles = self.get_colors_roles(interaction.guild.roles)
        member = interaction.user

        if name is None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            img_file = make_available_colors_image(guild_color_roles)
            await interaction.followup.send(
                "Available colors:",
                file=discord.File(img_file, "colors.png"),
                ephemeral=True,
            )
            return

        requested_color = name.strip().lower()
        author_color_roles = self.get_colors_roles(member.roles)

        if requested_color == "none":
            if author_color_roles:
                await member.remove_roles(*author_color_roles.values())
            await interaction.response.send_message(
                "Cleared your color. 👍", ephemeral=True
            )
            return

        target_role = guild_color_roles.get(requested_color)
        if target_role is None:
            await interaction.response.send_message(
                f"The color `{requested_color}` isn't available. "
                "Use `/color` with no argument to see available colors.",
                ephemeral=True,
            )
            return

        # Add the target color first so the user's color doesn't flash back to
        # default during the swap.
        await member.add_roles(target_role)

        roles_to_remove = set(author_color_roles.values())
        roles_to_remove.discard(target_role)
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        await interaction.response.send_message(
            f"Set your color to `{requested_color}`. 👍", ephemeral=True
        )

    @color.autocomplete("name")
    async def color_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        current_lower = current.lower()
        names = ["none"] + sorted(
            self.get_colors_roles(interaction.guild.roles).keys()
        )
        matches = [n for n in names if current_lower in n]
        return [app_commands.Choice(name=n, value=n) for n in matches[:25]]
