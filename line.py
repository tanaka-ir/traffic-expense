from linebot import LineBotApi
from linebot.models import TextSendMessage
import os

bot = LineBotApi(os.getenv("LINE_TOKEN"))
bot.push_message(os.getenv("LINE_TO"), TextSendMessage(text="ID 取得テスト OK ✅"))
