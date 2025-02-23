import xml.etree.ElementTree as ET

import aiohttp

from bot import LOGGER
from bot.core.config_manager import Config
from bot.helper.ext_utils.bot_utils import new_task
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import edit_message, send_message


@new_task
async def hydra_search(client, message):
    """
    Handler for the search command that initiates an NZB search
    """
    key = message.text.split()

    if len(key) == 1:
        await send_message(
            message,
            "Please provide a search query. Example: `/nzbsearch movie title`.",
        )
        return

    query = " ".join(key[1:]).strip()
    message = await send_message(message, f"🔍 Searching for '{query}'...")

    try:
        items = await search_nzbhydra(query)
        if not items:
            await edit_message(message, "No results found.")
            LOGGER.info(f"No results found for search query: {query}")
            return

        page_url = await create_telegraph_page(query, items)
        buttons = ButtonMaker()
        buttons.url_button("Results", page_url)
        button = buttons.build_menu()
        await edit_message(
            message, f"Search results for '{query}' are available here", button
        )
    except Exception as e:
        LOGGER.error(f"Error in hydra_search: {e!s}")
        await edit_message(message, "Something went wrong\nUse /shell cat rlog.txt")


async def search_nzbhydra(query, limit=100):
    """
    Performs the actual search query to NZBHydra
    """
    search_url = f"{Config.HYDRA_IP}/api"
    params = {
        "apikey": Config.HYDRA_API_KEY,
        "t": "search",
        "q": query,
        "limit": limit,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, params=params) as response:
            if response.status == 200:
                try:
                    content = await response.text()
                    root = ET.fromstring(content)
                    return root.findall('.//item')
                except ET.ParseError:
                    LOGGER.info("Failed to parse the XML response.")
                    return None
            
            LOGGER.info(f"Failed to search NZBHydra. Status Code: {response.status}")
            return None


async def create_telegraph_page(query, items):
    """
    Creates a Telegraph page with the search results
    """
    content = "<b>🔍 Search Results:</b><br><br>"
    sorted_items = sorted(
        [
            (
                int(item.find("size").text) if item.find("size") is not None else 0,
                item,
            )
            for item in items[:100]
        ],
        reverse=True,
        key=lambda x: x[0],
    )

    for idx, (size_bytes, item) in enumerate(sorted_items, 1):
        title = (
            item.find("title").text
            if item.find("title") is not None
            else "No Title Available"
        )
        download_url = (
            item.find("link").text
            if item.find("link") is not None
            else "No Link Available"
        )
        size = format_size(size_bytes)

        # Add category-based icons
        title_lower = title.lower()
        if any(
            word in title_lower
            for word in ["movie", "movies", "1080p", "720p", "2160p", "uhd"]
        ):
            icon = "🎬"
        elif any(
            word in title_lower for word in ["episode", "season", "tv", "show"]
        ):
            icon = "📺"
        elif any(word in title_lower for word in ["mp3", "flac", "music", "album"]):
            icon = "🎵"
        elif any(word in title_lower for word in ["ebook", "book", "pdf", "epub"]):
            icon = "📚"
        elif any(word in title_lower for word in ["game", "ps4", "xbox"]):
            icon = "🎮"
        else:
            icon = "📁"

        content += (
            f"{idx}. {icon} <b>Title:</b> {title}<br>"
            f"🔗 <b>Download URL:</b> <code>{download_url}</code><br>"
            f"💾 <b>Size:</b> {size}<br>"
            f"━━━━━━━━━━━━━━━━━━━━━━<br><br>"
        )

    response = await telegraph.create_page(
        title=f"🔍 Search Results for '{query}'",
        content=content,
    )
    LOGGER.info(f"Telegraph page created for search: {query}")
    return f"https://telegra.ph/{response['path']}"


def format_size(size_bytes):
    """
    Formats byte size to human readable format
    """
    size_bytes = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"
