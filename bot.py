import disnake
from disnake.ext import commands
import random
import asyncio, os

os.system("cls")

intents = disnake.Intents.all()
bot = commands.InteractionBot(intents=intents)

game_data = {}
game_thread = None

def generate_number(digits):
    first_digit = random.choice("123456789")
    remaining_digits = ''.join(random.sample("0123456789", digits - 1))
    return first_digit + remaining_digits

def check_guess(guess, answer):
    strikes, balls = 0, 0
    for i in range(len(answer)):
        if guess[i] == answer[i]:
            strikes += 1
        elif guess[i] in answer:
            balls += 1
    return strikes, balls

@bot.event
async def on_ready():
    print(f"로그인 완료 : {bot.user}")

@bot.slash_command(description="숫자야구 게임을 시작합니다!")
async def 숫자야구(inter: disnake.ApplicationCommandInteraction):
    global game_thread

    difficulty_select = disnake.ui.Select(
        placeholder="난이도를 선택하세요",
        options=[
            disnake.SelectOption(label="쉬움", value="easy"),
            disnake.SelectOption(label="중간", value="medium"),
            disnake.SelectOption(label="어려움", value="hard")
        ]
    )

    async def difficulty_callback(interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        difficulty = difficulty_select.values[0]
        digits_select = disnake.ui.Select(
            placeholder="숫자의 자릿수를 선택하세요",
            options=[
                disnake.SelectOption(label="3자리", value="3"),
                disnake.SelectOption(label="4자리", value="4")
            ]
        )

        async def digits_callback(digit_interaction: disnake.MessageInteraction):
            await digit_interaction.send("오류방지",ephemeral=True)
            global game_thread
            digits = int(digits_select.values[0])
            user_id = digit_interaction.author.id

            if difficulty == "easy":
                max_outs, time_limit = 6, 120
            elif difficulty == "medium":
                max_outs, time_limit = 5, 90
            else:
                max_outs, time_limit = 3, 50

            answer = generate_number(digits)
            game_data[user_id] = {
                "answer": answer,
                "attempts": 0,
                "outs": 0,
                "digits": digits,
                "max_attempts": 10,
                "max_outs": max_outs
            }
            print(f"게임 시작 - 난이도: {difficulty.capitalize()}, 정답: {answer}")

            await digit_interaction.followup.send(
                content=f"선택한 난이도: **{difficulty.capitalize()}**, 자릿수: **{digits}자리**로 게임을 시작합니다!",
                ephemeral=True
            )

            game_thread = await interaction.channel.create_thread(
                name=f"{digit_interaction.author.display_name}의 숫자야구 게임",
                type=disnake.ChannelType.public_thread,
                auto_archive_duration=60
            )

            embed = disnake.Embed(
                title="숫자야구 게임 시작!",
                description=f"{digits}자리 숫자야구 게임이 시작되었습니다. 난이도: {difficulty.capitalize()}",
                color=disnake.Color.blue()
            )
            embed.add_field(name="게임 방법", value="스레드 채널에 숫자를 입력하여 추측하세요. 정답과 위치가 일치하면 스트라이크, 숫자만 일치하면 볼입니다.")
            embed.set_footer(text=f"{time_limit}초 내에 맞추지 않으면 게임이 종료됩니다. 아웃 제한: {max_outs}회")
            await game_thread.send(content=f"{digit_interaction.author.mention}, 게임을 시작합니다!", embed=embed)

            await digit_interaction.delete_original_response()

            async def game_timeout():
                await asyncio.sleep(time_limit)
                if user_id in game_data:
                    await game_thread.send("시간 초과! 게임이 자동으로 종료됩니다.")
                    await end_game(user_id, game_thread)

            asyncio.create_task(game_timeout())

        digits_select.callback = digits_callback
        digit_view = disnake.ui.View()
        digit_view.add_item(digits_select)
        
        embed = disnake.Embed(
            title="자릿수 선택",
            description="게임에서 사용할 숫자의 자릿수를 선택하세요.",
            color=disnake.Color.purple()
        )
        await interaction.followup.send(embed=embed, view=digit_view, ephemeral=True)

    difficulty_select.callback = difficulty_callback
    difficulty_view = disnake.ui.View()
    difficulty_view.add_item(difficulty_select)
    
    embed = disnake.Embed(
        title="난이도 선택",
        description="게임의 난이도를 선택하세요.",
        color=disnake.Color.purple()
    )
    await inter.response.send_message(embed=embed, view=difficulty_view, ephemeral=True)

@bot.event
async def on_message(message: disnake.Message):
    global game_thread

    if message.author.bot or game_thread is None or message.channel.id != game_thread.id:
        return

    user_id = message.author.id
    if user_id not in game_data:
        return

    guess = message.content.strip()
    digits = game_data[user_id]["digits"]

    if len(guess) != int(digits) or not guess.isdigit() or guess.startswith("0"):
        await message.reply(embed=disnake.Embed(
            title="잘못된 입력",
            description="올바른 자리 수의 숫자를 입력해 주세요 (맨 앞에 0은 올 수 없습니다).",
            color=disnake.Color.red()
        ))
        return

    game_data[user_id]["attempts"] += 1
    answer = game_data[user_id]["answer"]
    strikes, balls = check_guess(guess, answer)

    if strikes == digits:
        await message.add_reaction("✅")
        await message.reply(embed=disnake.Embed(
            title="정답입니다! 🎉",
            description=f"{game_data[user_id]['attempts']}번 만에 정답을 맞추셨습니다!",
            color=disnake.Color.green()
        ))
        await end_game(user_id, message.channel)

    elif strikes == 0 and balls == 0:
        game_data[user_id]["outs"] += 1
        await message.reply(embed=disnake.Embed(
            title="아웃!",
            description=f"{game_data[user_id]['outs']} 아웃! 스트라이크와 볼이 모두 0입니다.",
            color=disnake.Color.red()
        ))
        if game_data[user_id]["outs"] >= game_data[user_id]["max_outs"]:
            await message.reply(embed=disnake.Embed(
                title="게임 종료",
                description="아웃 한도를 초과했습니다. 게임이 종료됩니다.",
                color=disnake.Color.red()
            ))
            await end_game(user_id, message.channel)
    else:
        await message.reply(embed=disnake.Embed(
            title="숫자야구 결과",
            description=f"{strikes} 스트라이크, {balls} 볼 입니다. 다시 시도해보세요!",
            color=disnake.Color.orange()
        ))

async def end_game(user_id, channel):
    if user_id in game_data:
        del game_data[user_id]
    await asyncio.sleep(60)
    await channel.delete()

bot.run("봇 토큰")
