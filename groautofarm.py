import asyncio
import logging
from datetime import datetime
from telethon import events

from hikkatl.types import Message
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class GROFarmerMod(loader.Module):
    """Модуль для автоматической отправки /farm в @OfficialGRO_bot каждые 3 часа"""
    
    strings = {
        "name": "GROFarmer",
        "active": "✅ Авто-фарминг активирован. Команда /farm будет отправлена СРАЗУ и затем каждые {} часов",
        "already_active": "⚠️ Авто-фарминг уже активен",
        "stopped": "❌ Авто-фарминг остановлен",
        "not_active": "⚠️ Авто-фарминг не был активен",
        "status": "📊 Статус авто-фарминга: {}",
        "last_sent": "🕒 Последняя отправка: {}",
        "next_send": "⏳ Следующая отправка: {}",
        "sending": "📤 Отправляю /farm в @OfficialGRO_bot",
        "sent": "✅ Команда /farm отправлена",
        "error": "❌ Ошибка при отправке: {}"
    }

    strings_ru = {
        "active": "✅ Авто-фарминг активирован. Команда /farm будет отправлена СРАЗУ и затем каждые {} часов",
        "already_active": "⚠️ Авто-фарминг уже активен",
        "stopped": "❌ Авто-фарминг остановлен",
        "not_active": "⚠️ Авто-фарминг не был активен",
        "status": "📊 Статус авто-фарминга: {}",
        "last_sent": "🕒 Последняя отправка: {}",
        "next_send": "⏳ Следующая отправка: {}",
        "sending": "📤 Отправляю /farm в @OfficialGRO_bot",
        "sent": "✅ Команда /farm отправлена",
        "error": "❌ Ошибка при отправке: {}"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "interval",
                10800,  # 3 часа в секундах
                lambda: "Интервал между отправками (в секундах)",
                validator=loader.validators.Integer(minimum=1800)  # минимум 30 минут
            )
        )
        self.task = None
        self.is_active = False
        self.last_sent = None
        self.next_send = None

    async def client_ready(self, client, db):
        self._client = client
        self._db = db
        self._me = await client.get_me()

    async def on_unload(self):
        if self.task:
            self.task.cancel()
            await asyncio.sleep(0.1)

    @loader.command(
        ru_doc="Включить авто-фарминг (отправка /farm СРАЗУ и каждые N часов)"
    )
    async def grofarmon(self, message: Message):
        """Включить авто-фарминг"""
        if self.is_active:
            await utils.answer(message, self.strings("already_active"))
            return

        self.is_active = True
        
        # Сразу отправляем команду
        await utils.answer(message, self.strings("sending"))
        await self._send_farm_command()
        
        # Показываем активное сообщение с точным интервалом
        interval_hours = self.config["interval"] / 3600
        await utils.answer(message, self.strings("active").format(f"{interval_hours:.2f}"))
        
        if self.task:
            self.task.cancel()
        
        self.task = asyncio.create_task(self._farm_task(message))
        logger.info(f"Авто-фарминг активирован с интервалом {interval_hours:.2f} часов")

    @loader.command(
        ru_doc="Выключить авто-фарминг"
    )
    async def grofarmoff(self, message: Message):
        """Выключить авто-фарминг"""
        if not self.is_active:
            await utils.answer(message, self.strings("not_active"))
            return

        self.is_active = False
        if self.task:
            self.task.cancel()
            self.task = None
        
        await utils.answer(message, self.strings("stopped"))
        logger.info("Авто-фарминг остановлен")

    @loader.command(
        ru_doc="Отправить команду /farm сейчас"
    )
    async def grofarmnow(self, message: Message):
        """Отправить /farm сейчас"""
        await utils.answer(message, self.strings("sending"))
        await self._send_farm_command()
        await utils.answer(message, self.strings("sent"))

    @loader.command(
        ru_doc="Показать статус авто-фарминга"
    )
    async def grofarmstatus(self, message: Message):
        """Показать статус авто-фарминга"""
        status = "🟢 Активен" if self.is_active else "🔴 Не активен"
        
        last_sent_str = self.strings("last_sent").format(
            self.last_sent.strftime("%H:%M:%S %d.%m.%Y") if self.last_sent else "Никогда"
        )
        
        next_send_str = self.strings("next_send").format(
            self.next_send.strftime("%H:%M:%S %d.%m.%Y") if self.next_send else "Не запланировано"
        )
        
        # Показываем точный интервал с двумя знаками после запятой
        interval_hours = self.config["interval"] / 3600
        
        response = (
            f"{self.strings('status').format(status)}\n"
            f"{last_sent_str}\n"
            f"{next_send_str}\n"
            f"📅 Интервал: {interval_hours:.2f} часа"
        )
        
        await utils.answer(message, response)

    async def _send_farm_command(self):
        """Отправляет команду /farm в бота"""
        try:
            # Ищем бота
            bot_entity = await self._client.get_entity("@OfficialGRO_bot")
            
            # Отправляем команду
            await self._client.send_message(bot_entity, "/farm")
            
            # Обновляем время последней отправки
            self.last_sent = datetime.now()
            
            # Рассчитываем следующую отправку
            self.next_send = datetime.fromtimestamp(
                datetime.now().timestamp() + self.config["interval"]
            )
            
            logger.info(f"Команда /farm отправлена в @OfficialGRO_bot")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке команды /farm: {e}")
            return False

    async def _farm_task(self, message: Message = None):
        """Фоновая задача для регулярной отправки команды"""
        logger.info("Запущена фоновая задача авто-фарминга")
        
        while self.is_active:
            try:
                # Проверяем, прошло ли достаточно времени с последней отправки
                if self.last_sent:
                    time_since_last = (datetime.now() - self.last_sent).total_seconds()
                    
                    if time_since_last >= self.config["interval"]:
                        logger.info("Плановое время отправки /farm")
                        await self._send_farm_command()
                
                # Ждем до следующей проверки (каждую минуту)
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info("Задача авто-фарминга отменена")
                break
            except Exception as e:
                logger.error(f"Ошибка в задаче авто-фарминга: {e}")
                await asyncio.sleep(300)  # Ждем 5 минут при ошибке

    @loader.command(
        ru_doc="Настроить интервал отправки (в часах, можно дробное: 2.75)"
    )
    async def grofarminterval(self, message: Message):
        """Настроить интервал отправки"""
        args = utils.get_args_raw(message)
        
        if not args:
            # Показываем точный текущий интервал
            current_hours = self.config["interval"] / 3600
            await utils.answer(message, 
                f"📅 Текущий интервал: {current_hours:.2f} часа\n"
                f"Используйте: .grofarminterval <часы>\n"
                f"Пример: .grofarminterval 2.75\n"
                f"Минимум: 0.5 часа (30 минут)"
            )
            return
        
        try:
            hours = float(args)
            if hours < 0.5:
                await utils.answer(message, "⚠️ Интервал должен быть не менее 0.5 часа (30 минут)")
                return
            
            seconds = int(hours * 3600)
            self.config["interval"] = seconds
            
            # Пересчитываем следующую отправку
            if self.last_sent:
                self.next_send = datetime.fromtimestamp(
                    self.last_sent.timestamp() + seconds
                )
            
            await utils.answer(message, 
                f"✅ Интервал обновлен:\n"
                f"📊 {hours:.2f} часа\n"
                f"⏱️ {seconds} секунд\n"
                f"⏳ {int(seconds/60)} минут"
            )
            
            # Перезапускаем задачу, если она активна
            if self.is_active and self.task:
                self.task.cancel()
                await asyncio.sleep(0.1)
                self.task = asyncio.create_task(self._farm_task(message))
                
        except ValueError:
            await utils.answer(message, 
                "⚠️ Пожалуйста, укажите число\n"
                "Примеры:\n"
                "• .grofarminterval 3\n"
                "• .grofarminterval 2.5\n"
                "• .grofarminterval 2.75"
            )

    @loader.command(
        ru_doc="Показать точный текущий интервал"
    )
    async def grofarmcurrent(self, message: Message):
        """Показать точный текущий интервал"""
        interval_hours = self.config["interval"] / 3600
        interval_minutes = self.config["interval"] / 60
        
        await utils.answer(message,
            f"📊 Текущий интервал:\n"
            f"⏰ {interval_hours:.2f} часа\n"
            f"⏱️ {self.config['interval']} секунд\n"
            f"⏳ {interval_minutes:.0f} минут\n"
            f"📅 {interval_hours*60:.0f} минут"
        )
