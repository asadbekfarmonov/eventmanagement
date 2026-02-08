import csv
from io import StringIO

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from ticketbot.config import Config
from ticketbot.database import Database
from ticketbot.services import AdminService, EventService, ReservationRequest, ReservationService, UserService

(
    PROFILE_NAME,
    PROFILE_SURNAME,
    PROFILE_PHONE,
    EVENT_SELECT,
    RES_TICKET_TYPE,
    RES_QUANTITY,
    RES_ATTENDEE_NAME,
    RES_ATTENDEE_SURNAME,
    RES_BOYS,
    RES_GIRLS,
    RES_RULES,
    ADMIN_EVENT_TITLE,
    ADMIN_EVENT_DATETIME,
    ADMIN_EVENT_LOCATION,
    ADMIN_EVENT_EB_PRICE,
    ADMIN_EVENT_REG_PRICE,
    ADMIN_EVENT_EB_QTY,
    ADMIN_EVENT_CAPACITY,
) = range(18)


class TelegramBot:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.db = Database(config.database_path)
        self.users = UserService(self.db)
        self.events = EventService(self.db)
        self.reservations = ReservationService(self.db)
        self.admin = AdminService(self.db)

    def build_application(self):
        app = ApplicationBuilder().token(self.config.bot_token).build()

        profile_conv = ConversationHandler(
            entry_points=[CommandHandler("start", self.start), CommandHandler("edit_profile", self.edit_profile)],
            states={
                PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.profile_name)],
                PROFILE_SURNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.profile_surname)],
                PROFILE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.profile_phone)],
            },
            fallbacks=[],
        )

        events_conv = ConversationHandler(
            entry_points=[CommandHandler("events", self.events_list)],
            states={
                EVENT_SELECT: [CallbackQueryHandler(self.event_select, pattern=r"^event:")],
                RES_TICKET_TYPE: [
                    CallbackQueryHandler(self.reserve_start, pattern=r"^reserve$"),
                    CallbackQueryHandler(self.ticket_type, pattern=r"^ticket:")
                ],
                RES_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ticket_quantity)],
                RES_ATTENDEE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.attendee_name)],
                RES_ATTENDEE_SURNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.attendee_surname)],
                RES_BOYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.boys_count)],
                RES_GIRLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.girls_count)],
                RES_RULES: [CallbackQueryHandler(self.rules_accept, pattern=r"^rules:accept$")],
            },
            fallbacks=[],
        )

        admin_conv = ConversationHandler(
            entry_points=[CommandHandler("admin", self.admin_panel)],
            states={
                ADMIN_EVENT_TITLE: [
                    CallbackQueryHandler(self.admin_select, pattern=r"^admin:"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_title),
                ],
                ADMIN_EVENT_DATETIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_datetime)
                ],
                ADMIN_EVENT_LOCATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_location)
                ],
                ADMIN_EVENT_EB_PRICE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_early_price)
                ],
                ADMIN_EVENT_REG_PRICE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_regular_price)
                ],
                ADMIN_EVENT_EB_QTY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_early_qty)
                ],
                ADMIN_EVENT_CAPACITY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_capacity)
                ],
            },
            fallbacks=[],
        )

        app.add_handler(profile_conv)
        app.add_handler(events_conv)
        app.add_handler(admin_conv)
        app.add_handler(CommandHandler("mytickets", self.my_tickets))
        app.add_handler(CommandHandler("cancel", self.cancel_reservation))
        app.add_handler(CommandHandler("export", self.export_event))

        return app

    def is_admin(self, tg_id: int) -> bool:
        return tg_id in self.config.admin_ids

    async def start(self, update: Update, _context):
        tg_id = update.effective_user.id
        user = self.users.get(tg_id)
        if user:
            await update.message.reply_text(
                "Welcome back! Use /events to browse events or /mytickets to see reservations."
            )
            return ConversationHandler.END
        await update.message.reply_text("Welcome! Let's set up your profile. What's your name?")
        return PROFILE_NAME

    async def profile_name(self, update: Update, context):
        context.user_data["profile_name"] = update.message.text.strip()
        await update.message.reply_text("Great. What's your surname?")
        return PROFILE_SURNAME

    async def profile_surname(self, update: Update, context):
        context.user_data["profile_surname"] = update.message.text.strip()
        await update.message.reply_text("Please share your phone number.")
        return PROFILE_PHONE

    async def profile_phone(self, update: Update, context):
        phone = update.message.text.strip()
        tg_id = update.effective_user.id
        self.users.upsert(
            tg_id,
            context.user_data["profile_name"],
            context.user_data["profile_surname"],
            phone,
        )
        await update.message.reply_text("Profile saved! Use /events to browse upcoming events.")
        return ConversationHandler.END

    async def edit_profile(self, update: Update, _context):
        await update.message.reply_text("Let's update your profile. What's your name?")
        return PROFILE_NAME

    async def events_list(self, update: Update, _context):
        if self.users.is_blocked(update.effective_user.id):
            await update.message.reply_text(
                "You are blocked due to a previous no-show. Contact admin to clear fine."
            )
            return ConversationHandler.END
        event_list = self.events.list_open()
        if not event_list:
            await update.message.reply_text("No events available right now.")
            return ConversationHandler.END
        keyboard = [
            [InlineKeyboardButton(f"{event.title} ({event.event_datetime})", callback_data=f"event:{event.id}")]
            for event in event_list
        ]
        await update.message.reply_text(
            "Upcoming events:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return EVENT_SELECT

    async def event_select(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        event_id = int(query.data.split(":")[1])
        event = self.events.get(event_id)
        if not event:
            await query.edit_message_text("Event not found.")
            return ConversationHandler.END
        context.user_data["event_id"] = event_id
        detail = (
            f"*{event.title}*\n"
            f"Date: {event.event_datetime}\n"
            f"Location: {event.location}\n\n"
            f"Early bird: {event.early_bird_price} (remaining {event.early_bird_qty})\n"
            f"Regular: {event.regular_price}\n\n"
            "Rules: Pay on spot. Cancellation allowed until 72 hours before event."
        )
        keyboard = [[InlineKeyboardButton("Reserve tickets", callback_data="reserve")]]
        await query.edit_message_text(
            detail, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN
        )
        return RES_TICKET_TYPE

    async def reserve_start(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        event = self.events.get(context.user_data.get("event_id"))
        if not event:
            await query.edit_message_text("Event not found.")
            return ConversationHandler.END
        options = []
        if event.early_bird_qty > 0:
            options.append(
                InlineKeyboardButton(
                    f"Early bird ({event.early_bird_price})", callback_data="ticket:early"
                )
            )
        options.append(
            InlineKeyboardButton(
                f"Regular ({event.regular_price})", callback_data="ticket:regular"
            )
        )
        keyboard = [[option] for option in options]
        await query.edit_message_text(
            "Choose ticket type:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return RES_TICKET_TYPE

    async def ticket_type(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["ticket_type"] = query.data.split(":")[1]
        await query.edit_message_text("How many tickets do you want to reserve?")
        return RES_QUANTITY

    async def ticket_quantity(self, update: Update, context):
        quantity_text = update.message.text.strip()
        if not quantity_text.isdigit() or int(quantity_text) <= 0:
            await update.message.reply_text("Please enter a valid quantity.")
            return RES_QUANTITY
        quantity = int(quantity_text)
        context.user_data["quantity"] = quantity
        context.user_data["attendees"] = []
        context.user_data["attendee_index"] = 0
        await update.message.reply_text("Enter attendee #1 name:")
        return RES_ATTENDEE_NAME

    async def attendee_name(self, update: Update, context):
        context.user_data["current_attendee_name"] = update.message.text.strip()
        await update.message.reply_text("Enter attendee surname:")
        return RES_ATTENDEE_SURNAME

    async def attendee_surname(self, update: Update, context):
        attendees = context.user_data["attendees"]
        attendees.append(
            {
                "name": context.user_data["current_attendee_name"],
                "surname": update.message.text.strip(),
            }
        )
        context.user_data["attendee_index"] += 1
        if context.user_data["attendee_index"] >= context.user_data["quantity"]:
            await update.message.reply_text("How many boys are in the group?")
            return RES_BOYS
        next_index = context.user_data["attendee_index"] + 1
        await update.message.reply_text(f"Enter attendee #{next_index} name:")
        return RES_ATTENDEE_NAME

    async def boys_count(self, update: Update, context):
        if not update.message.text.strip().isdigit():
            await update.message.reply_text("Please enter a number for boys.")
            return RES_BOYS
        context.user_data["boys"] = int(update.message.text.strip())
        await update.message.reply_text("How many girls are in the group?")
        return RES_GIRLS

    async def girls_count(self, update: Update, context):
        if not update.message.text.strip().isdigit():
            await update.message.reply_text("Please enter a number for girls.")
            return RES_GIRLS
        girls = int(update.message.text.strip())
        boys = context.user_data["boys"]
        quantity = context.user_data["quantity"]
        if boys + girls != quantity:
            await update.message.reply_text(
                f"Boys + girls must equal {quantity}. Please enter girls again."
            )
            return RES_GIRLS
        context.user_data["girls"] = girls
        rules_text = (
            "Before confirming, please accept the rules:\n"
            "- You will pay at entrance.\n"
            "- If you won't come, inform at least 72 hours before the event.\n"
            "- No-show without notice will result in a block until fine is paid.\n"
        )
        keyboard = [[InlineKeyboardButton("I accept", callback_data="rules:accept")]]
        await update.message.reply_text(rules_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return RES_RULES

    async def rules_accept(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        tg_id = update.effective_user.id
        user = self.users.get(tg_id)
        if not user:
            await query.edit_message_text("Please set up your profile with /start.")
            return ConversationHandler.END
        event = self.events.get(context.user_data["event_id"])
        ticket_type = context.user_data["ticket_type"]
        quantity = context.user_data["quantity"]
        if ticket_type == "early" and event.early_bird_qty < quantity:
            await query.edit_message_text("Not enough early bird tickets left. Try regular.")
            return ConversationHandler.END
        price_per_ticket = (
            event.early_bird_price if ticket_type == "early" else event.regular_price
        )
        reservation = self.reservations.create(
            ReservationRequest(
                user_id=user.id,
                event_id=event.id,
                ticket_type=ticket_type,
                quantity=quantity,
                price_per_ticket=price_per_ticket,
                boys=context.user_data["boys"],
                girls=context.user_data["girls"],
                attendees=context.user_data["attendees"],
            )
        )
        attendees_list = "\n".join(
            [f"- {a['name']} {a['surname']}" for a in context.user_data["attendees"]]
        )
        confirmation = (
            f"Reservation confirmed!\n\n"
            f"Code: {reservation.code}\n"
            f"Event: {event.title}\n"
            f"Date: {event.event_datetime}\n"
            f"Location: {event.location}\n"
            f"Ticket type: {ticket_type}\n"
            f"Price per ticket: {price_per_ticket}\n"
            f"Total: {reservation.total_price}\n"
            f"Boys: {reservation.boys} | Girls: {reservation.girls}\n\n"
            f"Attendees:\n{attendees_list}\n\n"
            "Reminder: Pay on spot."
        )
        await query.edit_message_text(confirmation)
        return ConversationHandler.END

    async def my_tickets(self, update: Update, _context):
        user = self.users.get(update.effective_user.id)
        if not user:
            await update.message.reply_text("Please set up your profile with /start.")
            return ConversationHandler.END
        reservations = self.reservations.list_for_user(user.id)
        if not reservations:
            await update.message.reply_text("No reservations yet.")
            return ConversationHandler.END
        lines = []
        for reservation in reservations:
            lines.append(
                f"{reservation.code} - {reservation.status} - {reservation.quantity} tickets"
            )
        await update.message.reply_text("Your tickets:\n" + "\n".join(lines))
        return ConversationHandler.END

    async def cancel_reservation(self, update: Update, context):
        if not context.args:
            await update.message.reply_text("Usage: /cancel <reservation_id>")
            return ConversationHandler.END
        reservation_id = int(context.args[0])
        self.reservations.cancel(reservation_id)
        await update.message.reply_text("Reservation cancelled if it existed.")
        return ConversationHandler.END

    async def admin_panel(self, update: Update, _context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END
        keyboard = [
            [InlineKeyboardButton("Create event", callback_data="admin:create")],
            [InlineKeyboardButton("Events list", callback_data="admin:list")],
            [InlineKeyboardButton("Blocked users", callback_data="admin:blocked")],
        ]
        await update.message.reply_text(
            "Admin panel:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ADMIN_EVENT_TITLE

    async def admin_select(self, update: Update, _context):
        query = update.callback_query
        await query.answer()
        if query.data == "admin:create":
            await query.edit_message_text("Event title?")
            return ADMIN_EVENT_TITLE
        if query.data == "admin:list":
            events_list = self.events.list_open()
            if not events_list:
                await query.edit_message_text("No events yet.")
                return ConversationHandler.END
            message = "Events:\n" + "\n".join(
                [f"{event.id}. {event.title} ({event.event_datetime})" for event in events_list]
            )
            await query.edit_message_text(message)
            return ConversationHandler.END
        if query.data == "admin:blocked":
            blocked = self.admin.list_blocked_users()
            if not blocked:
                await query.edit_message_text("No blocked users.")
                return ConversationHandler.END
            message = "Blocked users:\n" + "\n".join(
                [f"{row['name']} {row['surname']} ({row['tg_id']})" for row in blocked]
            )
            await query.edit_message_text(message)
            return ConversationHandler.END
        await query.edit_message_text("Unknown admin action.")
        return ConversationHandler.END

    async def admin_event_title(self, update: Update, context):
        context.user_data["event_title"] = update.message.text.strip()
        await update.message.reply_text("Event date/time? (YYYY-MM-DD HH:MM)")
        return ADMIN_EVENT_DATETIME

    async def admin_event_datetime(self, update: Update, context):
        context.user_data["event_datetime"] = update.message.text.strip()
        await update.message.reply_text("Location?")
        return ADMIN_EVENT_LOCATION

    async def admin_event_location(self, update: Update, context):
        context.user_data["event_location"] = update.message.text.strip()
        await update.message.reply_text("Early bird price?")
        return ADMIN_EVENT_EB_PRICE

    async def admin_event_early_price(self, update: Update, context):
        context.user_data["event_early_price"] = float(update.message.text.strip())
        await update.message.reply_text("Regular price?")
        return ADMIN_EVENT_REG_PRICE

    async def admin_event_regular_price(self, update: Update, context):
        context.user_data["event_regular_price"] = float(update.message.text.strip())
        await update.message.reply_text("Early bird quantity?")
        return ADMIN_EVENT_EB_QTY

    async def admin_event_early_qty(self, update: Update, context):
        context.user_data["event_early_qty"] = int(update.message.text.strip())
        await update.message.reply_text("Capacity (optional, send 0 for unlimited)?")
        return ADMIN_EVENT_CAPACITY

    async def admin_event_capacity(self, update: Update, context):
        capacity = int(update.message.text.strip())
        capacity_value = capacity if capacity > 0 else None
        self.events.create(
            title=context.user_data["event_title"],
            event_datetime=context.user_data["event_datetime"],
            location=context.user_data["event_location"],
            early_bird_price=context.user_data["event_early_price"],
            regular_price=context.user_data["event_regular_price"],
            early_bird_qty=context.user_data["event_early_qty"],
            capacity=capacity_value,
        )
        await update.message.reply_text("Event created!")
        return ConversationHandler.END

    async def export_event(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END
        if not context.args:
            await update.message.reply_text("Usage: /export <event_id>")
            return ConversationHandler.END
        event_id = int(context.args[0])
        rows = self.admin.export_event_csv(event_id)
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Reservation code",
                "Ticket type",
                "Price per ticket",
                "Total price",
                "Boys",
                "Girls",
                "Status",
                "Buyer name",
                "Buyer surname",
                "Buyer phone",
            ]
        )
        writer.writerows(rows)
        output.seek(0)
        await update.message.reply_document(
            document=output.getvalue().encode("utf-8"),
            filename=f"event_{event_id}_export.csv",
        )
        return ConversationHandler.END


def main() -> None:
    config = Config.load()
    bot = TelegramBot(config)
    application = bot.build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
