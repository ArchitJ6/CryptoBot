import discord
from discord.ext import commands, tasks
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Store user portfolios and price alerts
user_portfolios = {}
price_alerts = {}

API_BASE_URL = "https://api.coingecko.com/api/v3"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    check_price_alerts.start()

@bot.event
async def on_message(message):
    if bot.user in message.mentions:
        await message.channel.send("👋 Hello! I'm your enhanced Cryptocurrency Bot. Use `!tell` to see my features!")
    await bot.process_commands(message)

### Global Market Data ###
@bot.command(name="global")
async def global_market(ctx):
    """Fetch global cryptocurrency market stats."""
    try:
        url = f"{API_BASE_URL}/global"
        response = requests.get(url)
        data = response.json()["data"]

        embed = discord.Embed(title="🌐 Global Crypto Market Stats", color=discord.Color.purple())
        embed.add_field(name="Total Market Cap", value=f"${data['total_market_cap']['usd']:,}", inline=False)
        embed.add_field(name="Total Volume (24h)", value=f"${data['total_volume']['usd']:,}", inline=False)
        embed.add_field(name="BTC Dominance", value=f"{data['market_cap_percentage']['btc']:.2f}%", inline=False)
        await ctx.send(embed=embed)
    except Exception as e:
        print(e)
        await ctx.send("An error occurred while fetching the global market stats.")

### Portfolio Management ###
@bot.command(name="portfolio")
async def portfolio(ctx, action: str = None, coin: str = None, amount: float = None):
    """Manage your cryptocurrency portfolio."""
    user_id = ctx.author.id

    if action is None:
        await ctx.send("Usage:\n`!portfolio add <coin> <amount> \n!portfolio view`")
        return
    
    if action == "add":
        if not coin or not amount:
            await ctx.send("Usage: `!portfolio add <coin> <amount>`")
            return

        coin = coin.lower()
        if user_id not in user_portfolios:
            user_portfolios[user_id] = {}
        if coin in user_portfolios[user_id]:
            user_portfolios[user_id][coin] += amount
        else:
            user_portfolios[user_id][coin] = amount
        await ctx.send(f"✅ Added **{amount} {coin.upper()}** to your portfolio.")

    elif action == "view":
        if user_id not in user_portfolios or not user_portfolios[user_id]:
            await ctx.send("Your portfolio is empty. Use `!portfolio add <coin> <amount>` to add coins.")
            return

        portfolio = user_portfolios[user_id]
        total_value = 0
        embed = discord.Embed(title=f"📊 {ctx.author.name}'s Portfolio", color=discord.Color.gold())
        for coin, amount in portfolio.items():
            url = f"{API_BASE_URL}/simple/price"
            response = requests.get(url, params={"ids": coin, "vs_currencies": "usd"})
            data = response.json()
            if coin in data:
                price = data[coin]["usd"]
                value = price * amount
                total_value += value
                embed.add_field(name=f"{coin.upper()}", value=f"{amount} coins (${value:.2f})", inline=False)
        embed.add_field(name="Total Value", value=f"${total_value:.2f}", inline=False)
        await ctx.send(embed=embed)

    else:
        await ctx.send("Invalid action. Use `add` or `view`.")

### Historical Data ###
@bot.command(name="history")
async def history(ctx, coin: str = "bitcoin"):
    """Fetch 7-day historical price data for a cryptocurrency."""
    try:
        url = f"{API_BASE_URL}/coins/{coin}/market_chart"
        response = requests.get(url, params={"vs_currency": "usd", "days": 7, "interval": 'daily'})
        data = response.json()

        if "prices" in data:
            prices = data["prices"]
            price_list = "\n".join([f"{(datetime.utcfromtimestamp(p[0] / 1000)).strftime('%d-%m-%Y %I:%M %p')} ${p[1]:.2f}" for i, p in enumerate(prices)])
            embed = discord.Embed(title=f"📈 {coin.capitalize()} - 7 Day Price History", color=discord.Color.blue())
            embed.description = price_list
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Could not fetch historical data for **{coin}**.")
    except Exception as e:
        print(e)
        await ctx.send("An error occurred while fetching historical data.")

### Advanced Alerts ###
@bot.command(name="alert")
async def alert(ctx, coin: str, price: float, condition: str = "above"):
    """Set a price alert for a cryptocurrency."""
    user_id = ctx.author.id
    if user_id not in price_alerts:
        price_alerts[user_id] = []
    price_alerts[user_id].append({"coin": coin.lower(), "price": price, "condition": condition})
    await ctx.send(f"🔔 Alert set: **{coin.capitalize()}** {'above' if condition == 'above' else 'below'} **${price:.2f}**.")

### Price Alerts ###
@tasks.loop(minutes=1)
async def check_price_alerts():
    """Check for triggered price alerts."""
    for user_id, alerts in list(price_alerts.items()):
        for alert in alerts:
            try:
                coin = alert["coin"]
                target_price = alert["price"]
                condition = alert["condition"]

                url = f"{API_BASE_URL}/simple/price"
                response = requests.get(url, params={"ids": coin, "vs_currencies": "usd"})
                data = response.json()

                if coin in data:
                    current_price = data[coin]["usd"]
                    if (condition == "above" and current_price >= target_price) or (condition == "below" and current_price <= target_price):
                        user = await bot.fetch_user(user_id)
                        await user.send(f"🔔 Price Alert! **{coin.capitalize()}** has hit **${current_price:.2f}** ({condition} **${target_price:.2f}**).")
                        alerts.remove(alert)
            except Exception as e:
                print(e)

### Price Command ###
@bot.command(name="price")
async def price(ctx, coin: str = "bitcoin"):
    """Get the current price of a cryptocurrency."""
    response = requests.get(f"{API_BASE_URL}/simple/price?ids={coin}&vs_currencies=usd")
    if response.status_code == 200:
        data = response.json()
        if coin in data:
            price = data[coin]["usd"]
            await ctx.send(f"The current price of {coin.capitalize()} is ${price:.2f}.")
        else:
            await ctx.send(f"Could not find data for the cryptocurrency: {coin}")
    else:
        await ctx.send("Failed to fetch data. Please try again later.")

### Top 10 Command ###
@bot.command(name="top10")
async def top10(ctx):
    """Get the top 10 cryptocurrencies by market cap."""
    response = requests.get(f"{API_BASE_URL}/coins/markets", params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": 10, "page": 1, "sparkline": False})
    if response.status_code == 200:
        data = response.json()
        embed = discord.Embed(title="🏆 Top 10 Cryptocurrencies by Market Cap", color=discord.Color.gold())
        for coin in data:
            embed.add_field(name=f"{coin['market_cap_rank']}. {coin['name']}", value=f"Price: ${coin['current_price']:.2f}\nMarket Cap: ${coin['market_cap']:,}", inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Failed to fetch data. Please try again later.")

### Stats Command ###
@bot.command(name="stats")
async def stats(ctx, coin: str = "bitcoin"):
    """Get 24-hour stats for a cryptocurrency."""
    response = requests.get(f"{API_BASE_URL}/coins/{coin}")
    if response.status_code == 200:
        data = response.json()
        market_data = data.get("market_data", {})
        high = market_data.get("high_24h", {}).get("usd", "N/A")
        low = market_data.get("low_24h", {}).get("usd", "N/A")
        change = market_data.get("price_change_percentage_24h", "N/A")
        await ctx.send(
            f"24-hour stats for {coin.capitalize()}:\n"
            f"High: ${high}\n"
            f"Low: ${low}\n"
            f"Change: {change:.2f}%"
        )
    else:
        await ctx.send(f"Could not fetch stats for {coin}. Please try again later.")

### Tell Command ###
@bot.command(name="tell")
async def help_command(ctx):
    """Show the list of available commands."""
    embed = discord.Embed(title="🤖 Cryptocurrency Bot Commands", color=discord.Color.green())
    embed.add_field(name="!price [coin]", value="Get the current price of a cryptocurrency. (Default: Bitcoin)", inline=False)
    embed.add_field(name="!top10", value="Get the top 10 cryptocurrencies by market cap.", inline=False)
    embed.add_field(name="!stats [coin]", value="Get 24-hour stats for a cryptocurrency. (Default: Bitcoin)", inline=False)
    embed.add_field(name="!global", value="Get global cryptocurrency market stats.", inline=False)
    embed.add_field(name="!portfolio <action> [coin] [amount]", value="Manage your cryptocurrency portfolio.", inline=False)
    embed.add_field(name="!alert <coin> <price> [condition]", value="Set a price alert (default: 'above').", inline=False)
    embed.add_field(name="!history [coin]", value="Fetch 7-day historical price data for a cryptocurrency.", inline=False)
    await ctx.send(embed=embed)

token = os.getenv("BOT_TOKEN")
bot.run(token)
