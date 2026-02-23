import csv
import json
from io import StringIO
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from ticketbot.config import Config
from ticketbot.database import (
    STATUS_APPROVED,
    STATUS_PENDING,
    Database,
)
from ticketbot.services import AdminService, EventService, ReservationService, UserService

(
    PROFILE_NAME,
    PROFILE_SURNAME,
    PROFILE_PHONE,
    EVENT_SELECT,
    RES_ENTRY,
    RES_BOYS,
    RES_GIRLS,
    RES_ATTENDEE_NAME,
    RES_PAYMENT,
    RES_RULES,
    ADMIN_EVENT_TITLE,
    ADMIN_EVENT_DATETIME,
    ADMIN_EVENT_LOCATION,
    ADMIN_EVENT_CAPTION,
    ADMIN_EVENT_PHOTO,
    ADMIN_EB_BOY,
    ADMIN_EB_GIRL,
    ADMIN_EB_QTY,
    ADMIN_T1_BOY,
    ADMIN_T1_GIRL,
    ADMIN_T1_QTY,
    ADMIN_T2_BOY,
    ADMIN_T2_GIRL,
    ADMIN_T2_QTY,
    ADMIN_REJECT_NOTE,
    ADMIN_PRICE_EDIT_CHOOSE,
    ADMIN_PRICE_EDIT_VALUE,
    ADMIN_GUEST_PANEL,
    ADMIN_GUEST_SEARCH_TEXT,
    ADMIN_GUEST_RENAME_TEXT,
    ADMIN_GUEST_ADD_NAME_TEXT,
    ADMIN_EVENT_EDIT_PANEL,
    ADMIN_EVENT_EDIT_VALUE,
) = range(33)


class TelegramBot:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.application = None
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

        booking_conv = ConversationHandler(
            entry_points=[
                CommandHandler("events", self.events_list),
                CommandHandler("book", self.open_mini_app),
                MessageHandler(filters.Regex(r"^Browse Events$"), self.events_list),
                MessageHandler(filters.Regex(r"^(Open Booking App|Menu)$"), self.open_mini_app),
                MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.webapp_booking_data),
            ],
            states={
                EVENT_SELECT: [CallbackQueryHandler(self.event_select, pattern=r"^event:")],
                RES_ENTRY: [CallbackQueryHandler(self.reserve_start, pattern=r"^reserve$")],
                RES_BOYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.boys_count)],
                RES_GIRLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.girls_count)],
                RES_ATTENDEE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.attendee_full_name)],
                RES_PAYMENT: [
                    MessageHandler(filters.PHOTO | filters.Document.ALL, self.payment_proof),
                    MessageHandler(filters.ALL, self.payment_proof_required),
                ],
                RES_RULES: [CallbackQueryHandler(self.rules_accept, pattern=r"^rules:accept$")],
            },
            fallbacks=[],
        )

        admin_create_conv = ConversationHandler(
            entry_points=[CommandHandler("admin", self.admin_panel)],
            states={
                ADMIN_EVENT_TITLE: [
                    CallbackQueryHandler(self.admin_select, pattern=r"^admin:"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_title),
                ],
                ADMIN_EVENT_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_datetime)],
                ADMIN_EVENT_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_location)],
                ADMIN_EVENT_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_event_caption)],
                ADMIN_EVENT_PHOTO: [
                    MessageHandler(filters.PHOTO, self.admin_event_photo),
                    MessageHandler(filters.ALL, self.admin_event_photo_required),
                ],
                ADMIN_EB_BOY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_eb_boy_price)],
                ADMIN_EB_GIRL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_eb_girl_price)],
                ADMIN_EB_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_eb_qty)],
                ADMIN_T1_BOY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_t1_boy_price)],
                ADMIN_T1_GIRL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_t1_girl_price)],
                ADMIN_T1_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_t1_qty)],
                ADMIN_T2_BOY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_t2_boy_price)],
                ADMIN_T2_GIRL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_t2_girl_price)],
                ADMIN_T2_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_t2_qty)],
            },
            fallbacks=[],
        )

        admin_reject_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    self.admin_reject_custom_start,
                    pattern=r"^review:reject:custom:",
                )
            ],
            states={
                ADMIN_REJECT_NOTE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_reject_custom_submit)
                ]
            },
            fallbacks=[],
        )

        admin_price_edit_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.price_edit_start, pattern=r"^priceedit:start:")],
            states={
                ADMIN_PRICE_EDIT_CHOOSE: [
                    CallbackQueryHandler(self.price_edit_choose, pattern=r"^priceedit:field:"),
                    CallbackQueryHandler(self.price_edit_cancel, pattern=r"^priceedit:cancel$"),
                ],
                ADMIN_PRICE_EDIT_VALUE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.price_edit_value)
                ],
            },
            fallbacks=[],
        )

        admin_guest_conv = ConversationHandler(
            entry_points=[
                CommandHandler("admin_guests", self.admin_guests_command),
                CallbackQueryHandler(self.admin_guests_open_from_panel, pattern=r"^admin:guests$"),
                CallbackQueryHandler(self.admin_guests_callback, pattern=r"^adminguests:"),
            ],
            states={
                ADMIN_GUEST_PANEL: [CallbackQueryHandler(self.admin_guests_callback, pattern=r"^adminguests:")],
                ADMIN_GUEST_SEARCH_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_guests_search_text)],
                ADMIN_GUEST_RENAME_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_guest_rename_text)],
                ADMIN_GUEST_ADD_NAME_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_guest_add_name_text)],
            },
            fallbacks=[],
        )

        admin_event_edit_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.event_edit_pick, pattern=r"^eventedit:pick:"),
                CallbackQueryHandler(self.event_edit_action, pattern=r"^eventedit:"),
            ],
            states={
                ADMIN_EVENT_EDIT_PANEL: [CallbackQueryHandler(self.event_edit_action, pattern=r"^eventedit:")],
                ADMIN_EVENT_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.event_edit_value)],
            },
            fallbacks=[],
        )

        app.add_handler(profile_conv)
        app.add_handler(booking_conv)
        app.add_handler(admin_create_conv)
        app.add_handler(admin_reject_conv)
        app.add_handler(admin_price_edit_conv)
        app.add_handler(admin_guest_conv)
        app.add_handler(admin_event_edit_conv)

        app.add_handler(CommandHandler("mytickets", self.my_tickets))
        app.add_handler(MessageHandler(filters.Regex(r"^My Tickets$"), self.my_tickets))
        app.add_handler(CommandHandler("cancel", self.cancel_reservation))
        app.add_handler(CommandHandler("adminapp", self.open_admin_mini_app))
        app.add_handler(CommandHandler("admin_stats", self.admin_stats_command))
        app.add_handler(CommandHandler("admin_find", self.admin_find_command))
        app.add_handler(CommandHandler("admin_guest_add", self.admin_guest_add_command))
        app.add_handler(CommandHandler("admin_guest_remove", self.admin_guest_remove_command))
        app.add_handler(CommandHandler("admin_guest_rename", self.admin_guest_rename_command))
        app.add_handler(CommandHandler("admin_event_set", self.admin_event_set_command))
        app.add_handler(CommandHandler("admin_event_show", self.admin_event_show_command))
        app.add_handler(CommandHandler("export", self.export_event))

        app.add_handler(CallbackQueryHandler(self.inline_cancel, pattern=r"^cancel:"))
        app.add_handler(CallbackQueryHandler(self.admin_approve, pattern=r"^review:approve:"))
        app.add_handler(CallbackQueryHandler(self.admin_reject_template, pattern=r"^review:reject:tpl:"))
        app.add_handler(CallbackQueryHandler(self.admin_stats_sort, pattern=r"^adminstats:sort:"))

        return app

    def is_admin(self, tg_id: int) -> bool:
        return tg_id in self.config.admin_ids

    def _tier_label(self, tier_key: str) -> str:
        labels = {
            "early": "Early Bird",
            "tier1": "Regular Tier-1",
            "tier2": "Regular Tier-2",
        }
        return labels.get(tier_key, tier_key)

    def _event_caption(self, event, active_tier: Optional[dict]) -> str:
        base_caption = event.caption.strip() if event.caption.strip() else event.title
        body = (
            f"{base_caption}\n\n"
            f"Title: {event.title}\n"
            f"Date: {event.event_datetime}\n"
            f"Location: {event.location}\n"
        )
        if not active_tier:
            return body + "\nStatus: SOLD OUT"

        return (
            body
            + "\n"
            + f"Available ticket: {active_tier['name']}\n"
            + f"Boys: {active_tier['boy_price']:.2f}\n"
            + f"Girls: {active_tier['girl_price']:.2f}"
        )

    def _price_edit_keyboard(self, event_id: int) -> InlineKeyboardMarkup:
        buttons = []
        for field_key, label in self.admin.price_field_labels():
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"Edit {label}",
                        callback_data=f"priceedit:field:{event_id}:{field_key}",
                    )
                ]
            )
        buttons.append([InlineKeyboardButton("Done", callback_data="priceedit:cancel")])
        return InlineKeyboardMarkup(buttons)

    def _stats_sort_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Sort Date", callback_data="adminstats:sort:date"),
                    InlineKeyboardButton("Sort Sold", callback_data="adminstats:sort:sold"),
                ],
                [
                    InlineKeyboardButton("Sort Approved", callback_data="adminstats:sort:approved"),
                    InlineKeyboardButton("Sort Pending", callback_data="adminstats:sort:pending"),
                ],
                [
                    InlineKeyboardButton("Sort Revenue", callback_data="adminstats:sort:revenue"),
                    InlineKeyboardButton("Sort Title", callback_data="adminstats:sort:title"),
                ],
            ]
        )

    def _guest_sort_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Sort Newest", callback_data="adminguests:sort:newest"),
                    InlineKeyboardButton("Sort Name", callback_data="adminguests:sort:name"),
                ],
                [
                    InlineKeyboardButton("Sort Event", callback_data="adminguests:sort:event"),
                    InlineKeyboardButton("Sort Status", callback_data="adminguests:sort:status"),
                ],
                [
                    InlineKeyboardButton("Sort Reservation", callback_data="adminguests:sort:reservation"),
                ],
            ]
        )

    def _mini_app_markup(self) -> Optional[InlineKeyboardMarkup]:
        if not self.config.web_app_url:
            return None
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Menu",
                        web_app=WebAppInfo(url=self.config.web_app_url),
                    )
                ]
            ]
        )

    def _admin_mini_app_markup(self) -> Optional[InlineKeyboardMarkup]:
        if not self.config.web_app_url:
            return None
        admin_url = self.config.web_app_url.rstrip("/") + "/?open_admin=1"
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Open Admin App",
                        web_app=WebAppInfo(url=admin_url),
                    )
                ]
            ]
        )

    def _render_event_stats(self, sort_by: str = "date", search: Optional[str] = None) -> str:
        rows = self.admin.list_event_stats(sort_by=sort_by, search=search, limit=15)
        if not rows:
            if search:
                return f'No events found for search "{search}".'
            return "No events found."

        lines = ["Event analytics:"]
        if search:
            lines.append(f'Search: "{search}"')
        lines.append(f"Sort: {sort_by}")
        for row in rows:
            lines.append(
                f"{row['id']}. {row['title']} ({row['event_datetime']})"
            )
            lines.append(
                "Approved: "
                f"{row['approved_tickets']} | Pending: {row['pending_tickets']} | "
                f"Rejected: {row['rejected_tickets']} | Cancelled: {row['cancelled_tickets']}"
            )
            lines.append(
                "Sold/Held: "
                f"{row['held_tickets']} | Revenue approved: {float(row['approved_revenue']):.2f} | "
                f"Pending value: {float(row['pending_revenue']):.2f}"
            )
        return "\n".join(lines)

    def _render_guest_list(self, sort_by: str = "newest", search: Optional[str] = None) -> str:
        rows = self.admin.list_guests(sort_by=sort_by, search=search, limit=20)
        if not rows:
            if search:
                return f'No guests found for "{search}".'
            return "No guests found."

        lines = [f"Guests list (sort: {sort_by})"]
        if search:
            lines.append(f'Search: "{search}"')
        for row in rows:
            lines.append(
                f"#{row['attendee_id']} {row['full_name']} [{row['gender']}] | "
                f"{row['event_title']} ({row['event_datetime']})"
            )
            lines.append(
                f"Res: {row['reservation_code']} ({row['reservation_status']}) | "
                f"Buyer: {row['buyer_name']} {row['buyer_surname']} | tg:{row['buyer_tg_id']}"
            )

        lines.append("")
        lines.append("Actions:")
        lines.append("/admin_guest_add <reservation_code> <boy|girl> <Name Surname>")
        lines.append("/admin_guest_remove <attendee_id>")
        lines.append("/admin_guest_rename <attendee_id> <Name Surname>")
        return "\n".join(lines)

    def _render_guest_panel(self, sort_by: str = "newest", search: Optional[str] = None):
        rows = self.admin.list_guests(sort_by=sort_by, search=search, limit=8)
        if not rows:
            text = f"Guests manager (sort: {sort_by})"
            if search:
                text += f'\nSearch: "{search}"'
            text += "\nNo guests found."
        else:
            lines = [f"Guests manager (sort: {sort_by})"]
            if search:
                lines.append(f'Search: "{search}"')
            for row in rows:
                lines.append(
                    f"#{row['attendee_id']} {row['full_name']} [{row['gender']}] | "
                    f"{row['reservation_code']} | {row['reservation_status']}"
                )
                lines.append(f"{row['event_title']} ({row['event_datetime']})")
            text = "\n".join(lines)
        return text, rows

    def _guest_panel_keyboard(self, rows, sort_by: str = "newest", search: Optional[str] = None) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("Newest", callback_data="adminguests:sort:newest"),
                InlineKeyboardButton("Name", callback_data="adminguests:sort:name"),
                InlineKeyboardButton("Event", callback_data="adminguests:sort:event"),
            ],
            [
                InlineKeyboardButton("Reservation", callback_data="adminguests:sort:reservation"),
                InlineKeyboardButton("Status", callback_data="adminguests:sort:status"),
            ],
            [
                InlineKeyboardButton("Search", callback_data="adminguests:search:start"),
                InlineKeyboardButton("Clear Search", callback_data="adminguests:search:clear"),
            ],
            [InlineKeyboardButton("Add Guest", callback_data="adminguests:add:start")],
        ]
        for row in rows:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"Open #{row['attendee_id']} {row['full_name'][:24]}",
                        callback_data=f"adminguests:open:{row['attendee_id']}",
                    )
                ]
            )
        keyboard.append([InlineKeyboardButton("Refresh", callback_data=f"adminguests:sort:{sort_by}")])
        return InlineKeyboardMarkup(keyboard)

    def _render_guest_detail(self, row) -> str:
        return (
            f"Guest #{row['attendee_id']}\n"
            f"Name: {row['full_name']}\n"
            f"Gender: {row['gender']}\n"
            f"Reservation: {row['reservation_code']} ({row['reservation_status']})\n"
            f"Event: {row['event_title']} ({row['event_datetime']})\n"
            f"Buyer: {row['buyer_name']} {row['buyer_surname']} | tg:{row['buyer_tg_id']}"
        )

    def _guest_detail_keyboard(self, attendee_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Rename", callback_data=f"adminguests:rename:{attendee_id}"),
                    InlineKeyboardButton("Remove", callback_data=f"adminguests:remove:{attendee_id}"),
                ],
                [InlineKeyboardButton("Back", callback_data="adminguests:back")],
            ]
        )

    def _reservation_picker_text(self, rows) -> str:
        if not rows:
            return "No active reservations found (pending/approved)."
        lines = ["Select reservation for adding guest:"]
        for row in rows:
            lines.append(
                f"{row['reservation_code']} | {row['reservation_status']} | "
                f"{row['event_title']} ({row['event_datetime']})"
            )
            lines.append(
                f"Buyer: {row['buyer_name']} {row['buyer_surname']} | "
                f"Qty {row['quantity']} (boys {row['boys']}, girls {row['girls']})"
            )
        return "\n".join(lines)

    def _reservation_picker_keyboard(self, rows) -> InlineKeyboardMarkup:
        keyboard = []
        for row in rows:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{row['reservation_code']} | {row['event_title'][:20]}",
                        callback_data=f"adminguests:add:res:{row['reservation_id']}",
                    )
                ]
            )
        keyboard.append([InlineKeyboardButton("Back", callback_data="adminguests:back")])
        return InlineKeyboardMarkup(keyboard)

    def _event_edit_text(self, event) -> str:
        return (
            f"Edit Event #{event.id}\n"
            f"Title: {event.title}\n"
            f"Date: {event.event_datetime}\n"
            f"Location: {event.location}\n"
            f"Caption: {event.caption}\n\n"
            f"Early: b {event.early_bird_price:.2f} | g {event.early_bird_price_girl:.2f} | qty {event.early_bird_qty}\n"
            f"Tier-1: b {event.regular_tier1_price:.2f} | g {event.regular_tier1_price_girl:.2f} | qty {event.regular_tier1_qty}\n"
            f"Tier-2: b {event.regular_tier2_price:.2f} | g {event.regular_tier2_price_girl:.2f} | qty {event.regular_tier2_qty}"
        )

    def _event_edit_keyboard(self, event_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Title", callback_data=f"eventedit:set:{event_id}:title"),
                    InlineKeyboardButton("Date/Time", callback_data=f"eventedit:set:{event_id}:datetime"),
                ],
                [
                    InlineKeyboardButton("Location", callback_data=f"eventedit:set:{event_id}:location"),
                    InlineKeyboardButton("Caption", callback_data=f"eventedit:set:{event_id}:caption"),
                ],
                [
                    InlineKeyboardButton("EB Boy", callback_data=f"eventedit:set:{event_id}:early_boy"),
                    InlineKeyboardButton("EB Girl", callback_data=f"eventedit:set:{event_id}:early_girl"),
                    InlineKeyboardButton("EB Qty", callback_data=f"eventedit:set:{event_id}:early_qty"),
                ],
                [
                    InlineKeyboardButton("T1 Boy", callback_data=f"eventedit:set:{event_id}:tier1_boy"),
                    InlineKeyboardButton("T1 Girl", callback_data=f"eventedit:set:{event_id}:tier1_girl"),
                    InlineKeyboardButton("T1 Qty", callback_data=f"eventedit:set:{event_id}:tier1_qty"),
                ],
                [
                    InlineKeyboardButton("T2 Boy", callback_data=f"eventedit:set:{event_id}:tier2_boy"),
                    InlineKeyboardButton("T2 Girl", callback_data=f"eventedit:set:{event_id}:tier2_girl"),
                    InlineKeyboardButton("T2 Qty", callback_data=f"eventedit:set:{event_id}:tier2_qty"),
                ],
                [InlineKeyboardButton("Refresh", callback_data=f"eventedit:pick:{event_id}")],
            ]
        )

    async def _notify_user_after_review(self, reservation, approved: bool, note: str) -> None:
        user = self.users.get_by_id(reservation.user_id)
        if not user:
            return
        event = self.events.get(reservation.event_id)
        event_title = event.title if event else f"Event #{reservation.event_id}"
        if approved:
            text = (
                f"Payment approved.\nReservation: {reservation.code}\n"
                f"Event: {event_title}\n"
                f"Status: approved"
            )
        else:
            text = (
                f"Payment rejected.\nReservation: {reservation.code}\n"
                f"Event: {event_title}\n"
                f"Reason: {note}"
            )
        await self.application.bot.send_message(chat_id=user.tg_id, text=text)

    async def _notify_admins_pending(self, reservation) -> None:
        event = self.events.get(reservation.event_id)
        user = self.users.get_by_id(reservation.user_id)
        attendees = self.reservations.list_attendees(reservation.id)
        attendee_lines = "\n".join([f"- {name}" for name in attendees])

        event_title = event.title if event else f"Event #{reservation.event_id}"
        tier_label = self._tier_label(reservation.ticket_type)
        buyer = "Unknown"
        if user:
            buyer = f"{user.name} {user.surname} (tg:{user.tg_id})"

        caption = (
            f"New payment proof pending review\n\n"
            f"Code: {reservation.code}\n"
            f"Event: {event_title}\n"
            f"Tier: {tier_label}\n"
            f"Boys: {reservation.boys} | Girls: {reservation.girls}\n"
            f"Total: {reservation.total_price:.2f}\n"
            f"Buyer: {buyer}\n\n"
            f"Attendees:\n{attendee_lines}"
        )

        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Approve",
                        callback_data=f"review:approve:{reservation.id}",
                    ),
                    InlineKeyboardButton(
                        "Reject unreadable",
                        callback_data=f"review:reject:tpl:unreadable:{reservation.id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Reject wrong amount",
                        callback_data=f"review:reject:tpl:amount:{reservation.id}",
                    ),
                    InlineKeyboardButton(
                        "Reject custom",
                        callback_data=f"review:reject:custom:{reservation.id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Edit event prices",
                        callback_data=f"priceedit:start:{reservation.event_id}",
                    )
                ],
            ]
        )

        for admin_id in self.config.admin_ids:
            try:
                if reservation.payment_file_type == "photo":
                    await self.application.bot.send_photo(
                        chat_id=admin_id,
                        photo=reservation.payment_file_id,
                        caption=caption,
                        reply_markup=buttons,
                    )
                else:
                    await self.application.bot.send_document(
                        chat_id=admin_id,
                        document=reservation.payment_file_id,
                        caption=caption,
                        reply_markup=buttons,
                    )
            except Exception:
                await self.application.bot.send_message(
                    chat_id=admin_id,
                    text=caption,
                    reply_markup=buttons,
                )

    async def start(self, update: Update, _context):
        intro = (
            "🎉 Welcome to the official Budapest Tunderi bot.\n\n"
            "Here you can:\n"
            "🎟 Buy tickets for our events\n"
            "📋 Join the guest list\n"
            "🍾 Request table reservations\n"
            "📩 Get the latest event updates\n\n"
            "Choose a section below and follow the instructions.\n"
            "If you have any questions, you can message us directly."
        )
        tg_id = update.effective_user.id
        user = self.users.get(tg_id)
        if user:
            await update.message.reply_text(
                f"{intro}\n\nUse the Menu button to start booking.",
            )
            return ConversationHandler.END

        profile_name = (update.effective_user.first_name or "Guest").strip() or "Guest"
        profile_surname = (update.effective_user.last_name or "-").strip() or "-"
        self.users.upsert(
            tg_id=tg_id,
            name=profile_name,
            surname=profile_surname,
            phone="-",
        )
        await update.message.reply_text(
            f"{intro}\n\nUse the Menu button to start booking.",
        )
        return ConversationHandler.END

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
        await update.message.reply_text(
            "Profile saved. Use the Menu button to continue.",
        )
        return ConversationHandler.END

    async def edit_profile(self, update: Update, _context):
        await update.message.reply_text("Let's update your profile. What's your name?")
        return PROFILE_NAME

    async def open_mini_app(self, update: Update, _context):
        tg_id = update.effective_user.id
        if self.users.is_blocked(tg_id):
            await update.message.reply_text("You are blocked. Contact admin.")
            return ConversationHandler.END

        user = self.users.get(tg_id)
        if not user:
            await update.message.reply_text("Please set up your profile first with /start.")
            return ConversationHandler.END

        markup = self._mini_app_markup()
        if not markup:
            await update.message.reply_text(
                "Mini App URL is not configured yet. Ask admin to set WEB_APP_URL."
            )
            return ConversationHandler.END

        await update.message.reply_text(
            "Open modern booking app:",
            reply_markup=markup,
        )
        return ConversationHandler.END

    async def open_admin_mini_app(self, update: Update, _context):
        tg_id = update.effective_user.id
        if not self.is_admin(tg_id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END

        markup = self._admin_mini_app_markup()
        if not markup:
            await update.message.reply_text("Admin Mini App URL is not configured. Set WEB_APP_URL.")
            return ConversationHandler.END

        await update.message.reply_text("Open Admin Mini App:", reply_markup=markup)
        return ConversationHandler.END

    async def webapp_booking_data(self, update: Update, context):
        tg_id = update.effective_user.id
        if self.users.is_blocked(tg_id):
            await update.message.reply_text("You are blocked. Contact admin.")
            return ConversationHandler.END

        user = self.users.get(tg_id)
        if not user:
            await update.message.reply_text("Please set up your profile first with /start.")
            return ConversationHandler.END

        raw_data = update.message.web_app_data.data if update.message.web_app_data else ""
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            await update.message.reply_text("Invalid Mini App payload.")
            return ConversationHandler.END

        if payload.get("type") != "booking_draft_v1":
            await update.message.reply_text("Unsupported Mini App payload.")
            return ConversationHandler.END

        event_id = payload.get("event_id")
        boys = payload.get("boys")
        girls = payload.get("girls")
        attendees = payload.get("attendees")

        if not isinstance(event_id, int):
            await update.message.reply_text("Mini App payload is missing event id.")
            return ConversationHandler.END
        if not isinstance(boys, int) or boys < 0 or not isinstance(girls, int) or girls < 0:
            await update.message.reply_text("Mini App payload has invalid boys/girls values.")
            return ConversationHandler.END
        if not isinstance(attendees, list) or not all(isinstance(x, str) for x in attendees):
            await update.message.reply_text("Mini App payload has invalid attendees.")
            return ConversationHandler.END

        event = self.events.get(event_id)
        if not event:
            await update.message.reply_text("Selected event was not found.")
            return ConversationHandler.END

        active_tier = self.events.active_tier(event)
        if not active_tier:
            await update.message.reply_text("This event is sold out.")
            return ConversationHandler.END

        quantity = boys + girls
        if quantity <= 0:
            await update.message.reply_text("Total attendees must be at least 1.")
            return ConversationHandler.END
        if quantity > active_tier["remaining"]:
            await update.message.reply_text(
                "Current tier does not have enough tickets now. Please reopen booking app."
            )
            return ConversationHandler.END
        if len(attendees) != quantity:
            await update.message.reply_text("Attendee count must match boys + girls.")
            return ConversationHandler.END

        cleaned_attendees = [name.strip() for name in attendees]
        if any(len(name.split()) < 2 for name in cleaned_attendees):
            await update.message.reply_text('Each attendee must be in format "Name Surname".')
            return ConversationHandler.END

        context.user_data["event_id"] = event.id
        context.user_data["ticket_type"] = active_tier["key"]
        context.user_data["boy_price"] = active_tier["boy_price"]
        context.user_data["girl_price"] = active_tier["girl_price"]
        context.user_data["boys"] = boys
        context.user_data["girls"] = girls
        context.user_data["quantity"] = quantity
        context.user_data["attendees"] = cleaned_attendees
        context.user_data["attendee_index"] = quantity

        total = boys * active_tier["boy_price"] + girls * active_tier["girl_price"]
        context.user_data["total_price"] = total

        await update.message.reply_text(
            "Mini App draft received.\n"
            "Booking summary:\n"
            f"Event: {event.title}\n"
            f"Tier: {active_tier['name']}\n"
            f"Boys: {boys} x {active_tier['boy_price']:.2f}\n"
            f"Girls: {girls} x {active_tier['girl_price']:.2f}\n"
            f"Total paid by transfer: {total:.2f}\n\n"
            "Send payment proof as image or PDF (one file)."
        )
        return RES_PAYMENT

    async def events_list(self, update: Update, _context):
        tg_id = update.effective_user.id
        if self.users.is_blocked(tg_id):
            await update.message.reply_text("You are blocked. Contact admin.")
            return ConversationHandler.END

        user = self.users.get(tg_id)
        if not user:
            await update.message.reply_text("Please set up your profile first with /start.")
            return ConversationHandler.END

        event_list = self.events.list_open()
        if not event_list:
            await update.message.reply_text("No events available right now.")
            return ConversationHandler.END

        mini_markup = self._mini_app_markup()
        if mini_markup:
            await update.message.reply_text(
                "Modern booking UI is available:",
                reply_markup=mini_markup,
            )

        keyboard = []
        for event in event_list:
            status = "SOLD OUT" if self.events.total_remaining(event) == 0 else "OPEN"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{event.title} | {event.event_datetime} | {status}",
                        callback_data=f"event:{event.id}",
                    )
                ]
            )

        await update.message.reply_text("Upcoming events:", reply_markup=InlineKeyboardMarkup(keyboard))
        return EVENT_SELECT

    async def event_select(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        event_id = int(query.data.split(":")[1])
        event = self.events.get(event_id)
        if not event:
            await query.edit_message_text("Event not found.")
            return ConversationHandler.END

        context.user_data["event_id"] = event.id
        active_tier = self.events.active_tier(event)
        caption = self._event_caption(event, active_tier)

        keyboard = None
        if active_tier:
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Reserve", callback_data="reserve")]]
            )

        if event.photo_file_id:
            await query.message.reply_photo(photo=event.photo_file_id, caption=caption, reply_markup=keyboard)
        else:
            await query.message.reply_text(caption, reply_markup=keyboard)

        return RES_ENTRY if active_tier else ConversationHandler.END

    async def reserve_start(self, update: Update, context):
        query = update.callback_query
        await query.answer()

        event = self.events.get(context.user_data.get("event_id"))
        if not event:
            await query.edit_message_text("Event not found.")
            return ConversationHandler.END

        active_tier = self.events.active_tier(event)
        if not active_tier:
            await query.edit_message_text("This event is sold out.")
            return ConversationHandler.END

        context.user_data["ticket_type"] = active_tier["key"]
        context.user_data["boy_price"] = active_tier["boy_price"]
        context.user_data["girl_price"] = active_tier["girl_price"]

        await query.edit_message_text(
            f"Current tier: {active_tier['name']}\n"
            f"Boys: {active_tier['boy_price']:.2f}\n"
            f"Girls: {active_tier['girl_price']:.2f}\n\n"
            "How many boys?"
        )
        return RES_BOYS

    async def boys_count(self, update: Update, context):
        text = update.message.text.strip()
        if not text.isdigit():
            await update.message.reply_text("Please enter a non-negative integer for boys.")
            return RES_BOYS
        context.user_data["boys"] = int(text)
        await update.message.reply_text("How many girls?")
        return RES_GIRLS

    async def girls_count(self, update: Update, context):
        text = update.message.text.strip()
        if not text.isdigit():
            await update.message.reply_text("Please enter a non-negative integer for girls.")
            return RES_GIRLS

        boys = context.user_data.get("boys", 0)
        girls = int(text)
        quantity = boys + girls
        if quantity <= 0:
            await update.message.reply_text("Total attendees must be at least 1. Enter boys again.")
            return RES_BOYS

        context.user_data["girls"] = girls
        context.user_data["quantity"] = quantity
        context.user_data["attendees"] = []
        context.user_data["attendee_index"] = 0

        await update.message.reply_text(
            'Enter attendee #1 full name (name + surname), example: "Olzhas Olzhasov"'
        )
        return RES_ATTENDEE_NAME

    async def attendee_full_name(self, update: Update, context):
        full_name = update.message.text.strip()
        if len(full_name.split()) < 2:
            await update.message.reply_text(
                'Please enter full name in format "Name Surname", example: "Olzhas Olzhasov".'
            )
            return RES_ATTENDEE_NAME

        attendees = context.user_data["attendees"]
        attendees.append(full_name)
        context.user_data["attendee_index"] += 1
        if context.user_data["attendee_index"] >= context.user_data["quantity"]:
            boys = context.user_data["boys"]
            girls = context.user_data["girls"]
            boy_price = context.user_data["boy_price"]
            girl_price = context.user_data["girl_price"]
            total = boys * boy_price + girls * girl_price
            context.user_data["total_price"] = total

            await update.message.reply_text(
                "Booking summary:\n"
                f"Boys: {boys} x {boy_price:.2f}\n"
                f"Girls: {girls} x {girl_price:.2f}\n"
                f"Total paid by transfer: {total:.2f}\n\n"
                "Send payment proof as image or PDF (one file)."
            )
            return RES_PAYMENT

        next_idx = context.user_data["attendee_index"] + 1
        await update.message.reply_text(
            f'Enter attendee #{next_idx} full name (name + surname), example: "Olzhas Olzhasov"'
        )
        return RES_ATTENDEE_NAME

    async def payment_proof(self, update: Update, context):
        file_id = ""
        file_type = ""

        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            file_type = "photo"
        elif update.message.document:
            mime = (update.message.document.mime_type or "").lower()
            if mime.startswith("image/") or mime == "application/pdf":
                file_id = update.message.document.file_id
                file_type = "document"

        if not file_id:
            await update.message.reply_text("Only image or PDF is accepted. Send one file.")
            return RES_PAYMENT

        context.user_data["payment_file_id"] = file_id
        context.user_data["payment_file_type"] = file_type

        rules_text = (
            "Rules:\n"
            "- Reservation is pending until admin approves payment proof.\n"
            "- If cancelled, contact admin for resolution.\n"
            "- Fake or invalid proof will be rejected."
        )
        keyboard = [[InlineKeyboardButton("I accept rules", callback_data="rules:accept")]]
        await update.message.reply_text(rules_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return RES_RULES

    async def payment_proof_required(self, update: Update, _context):
        await update.message.reply_text("Send one payment proof file (image or PDF).")
        return RES_PAYMENT

    async def rules_accept(self, update: Update, context):
        query = update.callback_query
        await query.answer()

        tg_id = update.effective_user.id
        user = self.users.get(tg_id)
        if not user:
            await query.edit_message_text("Please set up your profile with /start.")
            return ConversationHandler.END

        try:
            reservation = self.reservations.create_pending(
                user_id=user.id,
                event_id=context.user_data["event_id"],
                boys=context.user_data["boys"],
                girls=context.user_data["girls"],
                attendees=context.user_data["attendees"],
                payment_file_id=context.user_data["payment_file_id"],
                payment_file_type=context.user_data["payment_file_type"],
            )
        except ValueError as exc:
            await query.edit_message_text(f"Could not create reservation: {exc}")
            return ConversationHandler.END

        await query.edit_message_text(
            f"Reservation submitted.\nCode: {reservation.code}\nStatus: pending admin approval."
        )
        await self._notify_admins_pending(reservation)
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

        for reservation in reservations:
            event = self.events.get(reservation.event_id)
            event_title = event.title if event else f"Event #{reservation.event_id}"
            text = (
                f"{reservation.code}\n"
                f"Event: {event_title}\n"
                f"Status: {reservation.status}\n"
                f"Tier: {self._tier_label(reservation.ticket_type)}\n"
                f"Boys: {reservation.boys} | Girls: {reservation.girls}\n"
                f"Total: {reservation.total_price:.2f}"
            )
            if reservation.admin_note:
                text += f"\nAdmin note: {reservation.admin_note}"

            keyboard = None
            if reservation.status in {STATUS_PENDING, STATUS_APPROVED}:
                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Cancel", callback_data=f"cancel:{reservation.code}")]]
                )
            await update.message.reply_text(text, reply_markup=keyboard)

        return ConversationHandler.END

    async def cancel_reservation(self, update: Update, context):
        if not context.args:
            await update.message.reply_text("Usage: /cancel <reservation_code>")
            return ConversationHandler.END

        user = self.users.get(update.effective_user.id)
        if not user:
            await update.message.reply_text("Please set up your profile with /start.")
            return ConversationHandler.END

        result = self.reservations.cancel_by_code(user.id, context.args[0].strip())
        await update.message.reply_text(result.message)
        return ConversationHandler.END

    async def inline_cancel(self, update: Update, _context):
        query = update.callback_query
        await query.answer()

        user = self.users.get(update.effective_user.id)
        if not user:
            await query.message.reply_text("Please set up your profile with /start.")
            return

        reservation_code = query.data.split(":", 1)[1]
        result = self.reservations.cancel_by_code(user.id, reservation_code)
        await query.message.reply_text(result.message)
        if result.success:
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass

    async def admin_panel(self, update: Update, _context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton("Create event", callback_data="admin:create")],
            [InlineKeyboardButton("Events list", callback_data="admin:list")],
            [InlineKeyboardButton("Edit events", callback_data="admin:eventsedit")],
            [InlineKeyboardButton("Analytics", callback_data="admin:analytics")],
            [InlineKeyboardButton("Guests", callback_data="admin:guests")],
            [InlineKeyboardButton("Blocked users", callback_data="admin:blocked")],
        ]
        admin_app_url = (
            self.config.web_app_url.rstrip("/") + "/?open_admin=1"
            if self.config.web_app_url
            else None
        )
        if admin_app_url:
            keyboard.insert(
                0,
                [InlineKeyboardButton("Open Admin App", web_app=WebAppInfo(url=admin_app_url))],
            )
        await update.message.reply_text(
            "Admin panel: use buttons below. Open Admin App for full dashboard UI.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return ADMIN_EVENT_TITLE

    async def admin_select(self, update: Update, context):
        query = update.callback_query
        await query.answer()

        if query.data == "admin:create":
            context.user_data.clear()
            await query.edit_message_text("Event title?")
            return ADMIN_EVENT_TITLE

        if query.data == "admin:list":
            events_list = self.events.list_open()
            if not events_list:
                await query.edit_message_text("No events yet.")
                return ConversationHandler.END
            lines = ["Events:"]
            for event in events_list:
                status = "SOLD OUT" if self.events.total_remaining(event) == 0 else "OPEN"
                lines.append(f"{event.id}. {event.title} ({event.event_datetime}) - {status}")
            await query.edit_message_text("\n".join(lines))
            return ConversationHandler.END

        if query.data == "admin:analytics":
            await query.edit_message_text(
                self._render_event_stats(sort_by="date"),
                reply_markup=self._stats_sort_keyboard(),
            )
            return ConversationHandler.END

        if query.data == "admin:eventsedit":
            events_list = self.events.list_open()
            if not events_list:
                await query.edit_message_text("No events to edit.")
                return ConversationHandler.END
            keyboard = []
            for event in events_list[:15]:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"Edit #{event.id} {event.title[:28]}",
                            callback_data=f"eventedit:pick:{event.id}",
                        )
                    ]
                )
            await query.edit_message_text("Select event to edit:", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END

        if query.data == "admin:guests":
            context.user_data["guest_sort"] = "newest"
            context.user_data["guest_search"] = None
            text, rows = self._render_guest_panel(sort_by="newest")
            await query.edit_message_text(text, reply_markup=self._guest_panel_keyboard(rows, sort_by="newest"))
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

    async def admin_stats_sort(self, update: Update, _context):
        query = update.callback_query
        await query.answer()
        if not self.is_admin(update.effective_user.id):
            await query.message.reply_text("Access denied.")
            return

        sort_key = query.data.split(":")[-1]
        await query.edit_message_text(
            self._render_event_stats(sort_by=sort_key),
            reply_markup=self._stats_sort_keyboard(),
        )

    async def admin_stats_command(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END

        allowed_sorts = {"date", "title", "approved", "pending", "sold", "revenue"}
        sort_key = "date"
        search = None
        if context.args:
            if context.args[0].lower() in allowed_sorts:
                sort_key = context.args[0].lower()
                search = " ".join(context.args[1:]).strip() or None
            else:
                search = " ".join(context.args).strip()

        await update.message.reply_text(
            self._render_event_stats(sort_by=sort_key, search=search),
            reply_markup=self._stats_sort_keyboard(),
        )
        return ConversationHandler.END

    async def admin_find_command(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END

        if not context.args:
            await update.message.reply_text(
                "Usage: /admin_find <query>\n"
                "Optional sort first: newest|amount|status|event_date"
            )
            return ConversationHandler.END

        allowed_sorts = {"newest", "amount", "status", "event_date"}
        sort_key = "newest"
        if context.args[0].lower() in allowed_sorts:
            sort_key = context.args[0].lower()
            query_text = " ".join(context.args[1:]).strip()
        else:
            query_text = " ".join(context.args).strip()

        if not query_text:
            await update.message.reply_text("Please provide a search query.")
            return ConversationHandler.END

        rows = self.admin.search_reservations(query_text=query_text, sort_by=sort_key, limit=8)
        if not rows:
            await update.message.reply_text(f'No reservations found for "{query_text}".')
            return ConversationHandler.END

        lines = [f'Reservation search: "{query_text}" (sort: {sort_key})']
        for row in rows:
            lines.append(
                f"{row['code']} | {row['status']} | {float(row['total_price']):.2f} | "
                f"{row['event_title']} ({row['event_datetime']})"
            )
            lines.append(
                f"Buyer: {row['buyer_name']} {row['buyer_surname']} | tg:{row['tg_id']} | "
                f"phone:{row['phone']}"
            )
            lines.append(
                f"Qty {row['quantity']} (boys {row['boys']}, girls {row['girls']}) | {row['created_at']}"
            )

        await update.message.reply_text("\n".join(lines))
        return ConversationHandler.END

    async def admin_guests_open_from_panel(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        if not self.is_admin(update.effective_user.id):
            await query.message.reply_text("Access denied.")
            return ConversationHandler.END

        context.user_data["guest_sort"] = "newest"
        context.user_data["guest_search"] = None
        text, rows = self._render_guest_panel(sort_by="newest", search=None)
        await query.edit_message_text(text, reply_markup=self._guest_panel_keyboard(rows, "newest", None))
        return ADMIN_GUEST_PANEL

    async def admin_guests_command(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END

        allowed_sorts = {"newest", "name", "event", "reservation", "status"}
        sort_key = "newest"
        search = None
        if context.args:
            if context.args[0].lower() in allowed_sorts:
                sort_key = context.args[0].lower()
                search = " ".join(context.args[1:]).strip() or None
            else:
                search = " ".join(context.args).strip() or None

        context.user_data["guest_sort"] = sort_key
        context.user_data["guest_search"] = search
        text, rows = self._render_guest_panel(sort_by=sort_key, search=search)
        await update.message.reply_text(text, reply_markup=self._guest_panel_keyboard(rows, sort_key, search))
        return ADMIN_GUEST_PANEL

    async def admin_guests_callback(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        if not self.is_admin(update.effective_user.id):
            await query.message.reply_text("Access denied.")
            return ConversationHandler.END

        parts = query.data.split(":")
        action = parts[1] if len(parts) > 1 else ""
        sort_key = context.user_data.get("guest_sort", "newest")
        search = context.user_data.get("guest_search")

        if action == "sort" and len(parts) > 2:
            sort_key = parts[2]
            context.user_data["guest_sort"] = sort_key
            text, rows = self._render_guest_panel(sort_by=sort_key, search=search)
            await query.edit_message_text(text, reply_markup=self._guest_panel_keyboard(rows, sort_key, search))
            return ADMIN_GUEST_PANEL

        if action == "search" and len(parts) > 2:
            mode = parts[2]
            if mode == "start":
                await query.message.reply_text("Send search text for guests/reservation/event/buyer.")
                return ADMIN_GUEST_SEARCH_TEXT
            context.user_data["guest_search"] = None
            text, rows = self._render_guest_panel(sort_by=sort_key, search=None)
            await query.edit_message_text(text, reply_markup=self._guest_panel_keyboard(rows, sort_key, None))
            return ADMIN_GUEST_PANEL

        if action == "open" and len(parts) > 2 and parts[2].isdigit():
            attendee_id = int(parts[2])
            row = self.admin.get_guest(attendee_id)
            if not row:
                await query.message.reply_text("Guest not found.")
                return ADMIN_GUEST_PANEL
            await query.edit_message_text(
                self._render_guest_detail(row),
                reply_markup=self._guest_detail_keyboard(attendee_id),
            )
            return ADMIN_GUEST_PANEL

        if action == "rename" and len(parts) > 2 and parts[2].isdigit():
            context.user_data["guest_rename_id"] = int(parts[2])
            await query.message.reply_text('Send new guest name in format "Name Surname".')
            return ADMIN_GUEST_RENAME_TEXT

        if action == "remove" and len(parts) > 2 and parts[2].isdigit():
            attendee_id = int(parts[2])
            result = self.admin.remove_guest(attendee_id=attendee_id)
            await query.message.reply_text(result.message)
            text, rows = self._render_guest_panel(sort_by=sort_key, search=search)
            await query.message.reply_text(text, reply_markup=self._guest_panel_keyboard(rows, sort_key, search))
            return ADMIN_GUEST_PANEL

        if action == "add" and len(parts) > 2:
            mode = parts[2]
            if mode == "start":
                rows = self.admin.list_active_reservations(limit=10)
                await query.edit_message_text(
                    self._reservation_picker_text(rows),
                    reply_markup=self._reservation_picker_keyboard(rows),
                )
                return ADMIN_GUEST_PANEL
            if mode == "res" and len(parts) > 3 and parts[3].isdigit():
                reservation = self.reservations.get_by_id(int(parts[3]))
                if not reservation:
                    await query.message.reply_text("Reservation not found.")
                    return ADMIN_GUEST_PANEL
                context.user_data["guest_add_reservation_code"] = reservation.code
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("Boy", callback_data="adminguests:add:gender:boy"),
                            InlineKeyboardButton("Girl", callback_data="adminguests:add:gender:girl"),
                        ],
                        [InlineKeyboardButton("Back", callback_data="adminguests:back")],
                    ]
                )
                await query.edit_message_text(
                    f"Selected reservation: {reservation.code}\nChoose gender for new guest:",
                    reply_markup=keyboard,
                )
                return ADMIN_GUEST_PANEL
            if mode == "gender" and len(parts) > 3:
                gender = parts[3]
                if gender not in {"boy", "girl"}:
                    await query.message.reply_text("Invalid gender.")
                    return ADMIN_GUEST_PANEL
                context.user_data["guest_add_gender"] = gender
                await query.message.reply_text('Send guest name in format "Name Surname".')
                return ADMIN_GUEST_ADD_NAME_TEXT

        text, rows = self._render_guest_panel(sort_by=sort_key, search=search)
        await query.message.reply_text(text, reply_markup=self._guest_panel_keyboard(rows, sort_key, search))
        return ADMIN_GUEST_PANEL

    async def admin_guests_search_text(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END
        context.user_data["guest_search"] = update.message.text.strip() or None
        sort_key = context.user_data.get("guest_sort", "newest")
        search = context.user_data.get("guest_search")
        text, rows = self._render_guest_panel(sort_by=sort_key, search=search)
        await update.message.reply_text(text, reply_markup=self._guest_panel_keyboard(rows, sort_key, search))
        return ADMIN_GUEST_PANEL

    async def admin_guest_rename_text(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END
        attendee_id = context.user_data.get("guest_rename_id")
        if not attendee_id:
            await update.message.reply_text("No guest selected for rename.")
            return ADMIN_GUEST_PANEL
        full_name = update.message.text.strip()
        if len(full_name.split()) < 2:
            await update.message.reply_text('Name must be in format "Name Surname".')
            return ADMIN_GUEST_RENAME_TEXT
        result = self.admin.rename_guest(attendee_id=attendee_id, full_name=full_name)
        context.user_data.pop("guest_rename_id", None)
        await update.message.reply_text(result.message)
        sort_key = context.user_data.get("guest_sort", "newest")
        search = context.user_data.get("guest_search")
        text, rows = self._render_guest_panel(sort_by=sort_key, search=search)
        await update.message.reply_text(text, reply_markup=self._guest_panel_keyboard(rows, sort_key, search))
        return ADMIN_GUEST_PANEL

    async def admin_guest_add_name_text(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END
        reservation_code = context.user_data.get("guest_add_reservation_code")
        gender = context.user_data.get("guest_add_gender")
        if not reservation_code or not gender:
            await update.message.reply_text("Guest add context missing. Start again from Guests panel.")
            return ADMIN_GUEST_PANEL
        full_name = update.message.text.strip()
        if len(full_name.split()) < 2:
            await update.message.reply_text('Name must be in format "Name Surname".')
            return ADMIN_GUEST_ADD_NAME_TEXT

        result = self.admin.add_guest(reservation_code=reservation_code, full_name=full_name, gender=gender)
        context.user_data.pop("guest_add_reservation_code", None)
        context.user_data.pop("guest_add_gender", None)
        await update.message.reply_text(result.message)
        sort_key = context.user_data.get("guest_sort", "newest")
        search = context.user_data.get("guest_search")
        text, rows = self._render_guest_panel(sort_by=sort_key, search=search)
        await update.message.reply_text(text, reply_markup=self._guest_panel_keyboard(rows, sort_key, search))
        return ADMIN_GUEST_PANEL

    async def admin_guest_add_command(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END

        if len(context.args) < 3:
            await update.message.reply_text(
                "Usage: /admin_guest_add <reservation_code> <boy|girl> <Name Surname>"
            )
            return ConversationHandler.END

        reservation_code = context.args[0].strip()
        gender = context.args[1].strip().lower()
        full_name = " ".join(context.args[2:]).strip()
        if len(full_name.split()) < 2:
            await update.message.reply_text('Guest name must be in format "Name Surname".')
            return ConversationHandler.END

        result = self.admin.add_guest(reservation_code=reservation_code, full_name=full_name, gender=gender)
        if result.success and result.reservation:
            await update.message.reply_text(
                f"{result.message}\n"
                f"Reservation: {result.reservation.code}\n"
                f"Boys: {result.reservation.boys} | Girls: {result.reservation.girls}\n"
                f"Total: {result.reservation.total_price:.2f}"
            )
        else:
            await update.message.reply_text(result.message)
        return ConversationHandler.END

    async def admin_guest_remove_command(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END

        if len(context.args) != 1 or not context.args[0].isdigit():
            await update.message.reply_text("Usage: /admin_guest_remove <attendee_id>")
            return ConversationHandler.END

        attendee_id = int(context.args[0])
        result = self.admin.remove_guest(attendee_id=attendee_id)
        if result.success and result.reservation:
            await update.message.reply_text(
                f"{result.message}\n"
                f"Reservation: {result.reservation.code}\n"
                f"Boys: {result.reservation.boys} | Girls: {result.reservation.girls}\n"
                f"Total: {result.reservation.total_price:.2f}"
            )
        else:
            await update.message.reply_text(result.message)
        return ConversationHandler.END

    async def admin_guest_rename_command(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END

        if len(context.args) < 2 or not context.args[0].isdigit():
            await update.message.reply_text("Usage: /admin_guest_rename <attendee_id> <Name Surname>")
            return ConversationHandler.END

        attendee_id = int(context.args[0])
        full_name = " ".join(context.args[1:]).strip()
        if len(full_name.split()) < 2:
            await update.message.reply_text('Guest name must be in format "Name Surname".')
            return ConversationHandler.END

        result = self.admin.rename_guest(attendee_id=attendee_id, full_name=full_name)
        await update.message.reply_text(result.message)
        return ConversationHandler.END

    async def admin_event_show_command(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END
        if len(context.args) != 1 or not context.args[0].isdigit():
            await update.message.reply_text("Usage: /admin_event_show <event_id>")
            return ConversationHandler.END

        event = self.events.get(int(context.args[0]))
        if not event:
            await update.message.reply_text("Event not found.")
            return ConversationHandler.END

        await update.message.reply_text(
            self._event_edit_text(event),
            reply_markup=self._event_edit_keyboard(event.id),
        )
        return ConversationHandler.END

    async def admin_event_set_command(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END
        if len(context.args) < 3:
            await update.message.reply_text(
                "Usage: /admin_event_set <event_id> <field> <value>\n"
                "Fields: title, location, datetime, caption, early_boy, early_girl, early_qty, "
                "tier1_boy, tier1_girl, tier1_qty, tier2_boy, tier2_girl, tier2_qty"
            )
            return ConversationHandler.END
        if not context.args[0].isdigit():
            await update.message.reply_text("event_id must be numeric.")
            return ConversationHandler.END

        event_id = int(context.args[0])
        field = context.args[1].strip().lower()
        value = " ".join(context.args[2:]).strip()
        ok, message = self.admin.set_event_fields(event_id, {field: value})
        await update.message.reply_text(message)
        return ConversationHandler.END

    async def event_edit_pick(self, update: Update, _context):
        query = update.callback_query
        await query.answer()
        if not self.is_admin(update.effective_user.id):
            await query.message.reply_text("Access denied.")
            return ConversationHandler.END
        event_id = int(query.data.split(":")[-1])
        event = self.events.get(event_id)
        if not event:
            await query.edit_message_text("Event not found.")
            return ConversationHandler.END
        await query.edit_message_text(
            self._event_edit_text(event),
            reply_markup=self._event_edit_keyboard(event_id),
        )
        _context.user_data["event_edit_event_id"] = event_id
        return ADMIN_EVENT_EDIT_PANEL

    async def event_edit_action(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        if not self.is_admin(update.effective_user.id):
            await query.message.reply_text("Access denied.")
            return ConversationHandler.END
        parts = query.data.split(":")
        if len(parts) >= 4 and parts[1] == "set" and parts[2].isdigit():
            event_id = int(parts[2])
            field = parts[3]
            context.user_data["event_edit_event_id"] = event_id
            context.user_data["event_edit_field"] = field
            await query.message.reply_text(f"Send new value for {field}.")
            return ADMIN_EVENT_EDIT_VALUE

        if len(parts) >= 3 and parts[1] == "pick" and parts[2].isdigit():
            event_id = int(parts[2])
            event = self.events.get(event_id)
            if not event:
                await query.edit_message_text("Event not found.")
                return ConversationHandler.END
            await query.edit_message_text(
                self._event_edit_text(event),
                reply_markup=self._event_edit_keyboard(event_id),
            )
            return ADMIN_EVENT_EDIT_PANEL

        await query.message.reply_text("Unknown event edit action.")
        return ADMIN_EVENT_EDIT_PANEL

    async def event_edit_value(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END
        event_id = context.user_data.get("event_edit_event_id")
        field = context.user_data.get("event_edit_field")
        if not event_id or not field:
            await update.message.reply_text("Event edit context missing.")
            return ConversationHandler.END
        value = update.message.text.strip()
        ok, message = self.admin.set_event_fields(event_id, {field: value})
        await update.message.reply_text(message)
        if not ok:
            return ADMIN_EVENT_EDIT_VALUE
        event = self.events.get(event_id)
        if not event:
            return ConversationHandler.END
        await update.message.reply_text(
            self._event_edit_text(event),
            reply_markup=self._event_edit_keyboard(event_id),
        )
        return ADMIN_EVENT_EDIT_PANEL

    def _parse_non_negative_float(self, text: str) -> Optional[float]:
        try:
            value = float(text.strip())
        except ValueError:
            return None
        return value if value >= 0 else None

    def _parse_non_negative_int(self, text: str) -> Optional[int]:
        value = text.strip()
        if not value.isdigit():
            return None
        return int(value)

    async def admin_event_title(self, update: Update, context):
        context.user_data["event_title"] = update.message.text.strip()
        await update.message.reply_text("Event date/time? Use YYYY-MM-DD HH:MM (Budapest time)")
        return ADMIN_EVENT_DATETIME

    async def admin_event_datetime(self, update: Update, context):
        value = update.message.text.strip()
        try:
            self.db.parse_event_datetime(value)
        except ValueError:
            await update.message.reply_text(
                "Invalid format. Use exactly YYYY-MM-DD HH:MM, example: 2026-03-15 21:30"
            )
            return ADMIN_EVENT_DATETIME

        context.user_data["event_datetime"] = value
        await update.message.reply_text("Location?")
        return ADMIN_EVENT_LOCATION

    async def admin_event_location(self, update: Update, context):
        context.user_data["event_location"] = update.message.text.strip()
        await update.message.reply_text("Event caption/description?")
        return ADMIN_EVENT_CAPTION

    async def admin_event_caption(self, update: Update, context):
        context.user_data["event_caption"] = update.message.text.strip()
        await update.message.reply_text("Send event photo now (mandatory).")
        return ADMIN_EVENT_PHOTO

    async def admin_event_photo(self, update: Update, context):
        context.user_data["event_photo_file_id"] = update.message.photo[-1].file_id
        await update.message.reply_text("Early Bird boys price?")
        return ADMIN_EB_BOY

    async def admin_event_photo_required(self, update: Update, _context):
        await update.message.reply_text("Photo is mandatory. Please send a photo.")
        return ADMIN_EVENT_PHOTO

    async def admin_eb_boy_price(self, update: Update, context):
        value = self._parse_non_negative_float(update.message.text)
        if value is None:
            await update.message.reply_text("Enter a valid non-negative number.")
            return ADMIN_EB_BOY
        context.user_data["eb_boy_price"] = value
        await update.message.reply_text("Early Bird girls price?")
        return ADMIN_EB_GIRL

    async def admin_eb_girl_price(self, update: Update, context):
        value = self._parse_non_negative_float(update.message.text)
        if value is None:
            await update.message.reply_text("Enter a valid non-negative number.")
            return ADMIN_EB_GIRL
        context.user_data["eb_girl_price"] = value
        await update.message.reply_text("Early Bird quantity?")
        return ADMIN_EB_QTY

    async def admin_eb_qty(self, update: Update, context):
        value = self._parse_non_negative_int(update.message.text)
        if value is None:
            await update.message.reply_text("Enter a valid non-negative integer.")
            return ADMIN_EB_QTY
        context.user_data["eb_qty"] = value
        await update.message.reply_text("Regular Tier-1 boys price?")
        return ADMIN_T1_BOY

    async def admin_t1_boy_price(self, update: Update, context):
        value = self._parse_non_negative_float(update.message.text)
        if value is None:
            await update.message.reply_text("Enter a valid non-negative number.")
            return ADMIN_T1_BOY
        context.user_data["t1_boy_price"] = value
        await update.message.reply_text("Regular Tier-1 girls price?")
        return ADMIN_T1_GIRL

    async def admin_t1_girl_price(self, update: Update, context):
        value = self._parse_non_negative_float(update.message.text)
        if value is None:
            await update.message.reply_text("Enter a valid non-negative number.")
            return ADMIN_T1_GIRL
        context.user_data["t1_girl_price"] = value
        await update.message.reply_text("Regular Tier-1 quantity?")
        return ADMIN_T1_QTY

    async def admin_t1_qty(self, update: Update, context):
        value = self._parse_non_negative_int(update.message.text)
        if value is None:
            await update.message.reply_text("Enter a valid non-negative integer.")
            return ADMIN_T1_QTY
        context.user_data["t1_qty"] = value
        await update.message.reply_text("Regular Tier-2 boys price?")
        return ADMIN_T2_BOY

    async def admin_t2_boy_price(self, update: Update, context):
        value = self._parse_non_negative_float(update.message.text)
        if value is None:
            await update.message.reply_text("Enter a valid non-negative number.")
            return ADMIN_T2_BOY
        context.user_data["t2_boy_price"] = value
        await update.message.reply_text("Regular Tier-2 girls price?")
        return ADMIN_T2_GIRL

    async def admin_t2_girl_price(self, update: Update, context):
        value = self._parse_non_negative_float(update.message.text)
        if value is None:
            await update.message.reply_text("Enter a valid non-negative number.")
            return ADMIN_T2_GIRL
        context.user_data["t2_girl_price"] = value
        await update.message.reply_text("Regular Tier-2 quantity?")
        return ADMIN_T2_QTY

    async def admin_t2_qty(self, update: Update, context):
        value = self._parse_non_negative_int(update.message.text)
        if value is None:
            await update.message.reply_text("Enter a valid non-negative integer.")
            return ADMIN_T2_QTY

        context.user_data["t2_qty"] = value
        total_qty = context.user_data["eb_qty"] + context.user_data["t1_qty"] + context.user_data["t2_qty"]
        if total_qty <= 0:
            await update.message.reply_text("At least one tier must have quantity > 0. Enter Tier-2 quantity again.")
            return ADMIN_T2_QTY

        event_id = self.events.create(
            title=context.user_data["event_title"],
            event_datetime=context.user_data["event_datetime"],
            location=context.user_data["event_location"],
            caption=context.user_data["event_caption"],
            photo_file_id=context.user_data["event_photo_file_id"],
            early_boy_price=context.user_data["eb_boy_price"],
            early_girl_price=context.user_data["eb_girl_price"],
            early_qty=context.user_data["eb_qty"],
            tier1_boy_price=context.user_data["t1_boy_price"],
            tier1_girl_price=context.user_data["t1_girl_price"],
            tier1_qty=context.user_data["t1_qty"],
            tier2_boy_price=context.user_data["t2_boy_price"],
            tier2_girl_price=context.user_data["t2_girl_price"],
            tier2_qty=context.user_data["t2_qty"],
        )

        await update.message.reply_text(
            f"Event created with ID {event_id}.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Edit prices", callback_data=f"priceedit:start:{event_id}")]]
            ),
        )
        return ConversationHandler.END

    async def admin_approve(self, update: Update, _context):
        query = update.callback_query
        await query.answer()
        if not self.is_admin(update.effective_user.id):
            await query.message.reply_text("Access denied.")
            return

        reservation_id = int(query.data.split(":")[-1])
        result = self.reservations.approve_by_admin(reservation_id, update.effective_user.id)
        await query.message.reply_text(result.message)
        if result.success and result.reservation:
            await self._notify_user_after_review(result.reservation, approved=True, note="")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

    async def admin_reject_template(self, update: Update, _context):
        query = update.callback_query
        await query.answer()
        if not self.is_admin(update.effective_user.id):
            await query.message.reply_text("Access denied.")
            return

        parts = query.data.split(":")
        template_key = parts[-2]
        reservation_id = int(parts[-1])
        reason = "Payment proof unreadable. Please resend with clear details."
        if template_key == "amount":
            reason = "Transferred amount does not match booking total. Please contact admin."

        result = self.reservations.reject_by_admin(reservation_id, update.effective_user.id, reason)
        await query.message.reply_text(result.message)
        if result.success and result.reservation:
            await self._notify_user_after_review(result.reservation, approved=False, note=reason)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

    async def admin_reject_custom_start(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        if not self.is_admin(update.effective_user.id):
            await query.message.reply_text("Access denied.")
            return ConversationHandler.END

        reservation_id = int(query.data.split(":")[-1])
        context.user_data["reject_reservation_id"] = reservation_id
        await query.message.reply_text("Send custom rejection message for the user.")
        return ADMIN_REJECT_NOTE

    async def admin_reject_custom_submit(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END

        reservation_id = context.user_data.get("reject_reservation_id")
        if not reservation_id:
            await update.message.reply_text("No pending rejection context.")
            return ConversationHandler.END

        note = update.message.text.strip()
        result = self.reservations.reject_by_admin(reservation_id, update.effective_user.id, note)
        await update.message.reply_text(result.message)
        if result.success and result.reservation:
            await self._notify_user_after_review(result.reservation, approved=False, note=note)
        context.user_data.pop("reject_reservation_id", None)
        return ConversationHandler.END

    async def price_edit_start(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        if not self.is_admin(update.effective_user.id):
            await query.message.reply_text("Access denied.")
            return ConversationHandler.END

        event_id = int(query.data.split(":")[-1])
        event = self.events.get(event_id)
        if not event:
            await query.message.reply_text("Event not found.")
            return ConversationHandler.END

        context.user_data["price_edit_event_id"] = event_id
        await query.message.reply_text(
            f"Select price field to edit for event {event_id}.",
            reply_markup=self._price_edit_keyboard(event_id),
        )
        return ADMIN_PRICE_EDIT_CHOOSE

    async def price_edit_choose(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        if not self.is_admin(update.effective_user.id):
            await query.message.reply_text("Access denied.")
            return ConversationHandler.END

        parts = query.data.split(":")
        event_id = int(parts[2])
        field_key = parts[3]
        context.user_data["price_edit_event_id"] = event_id
        context.user_data["price_edit_field"] = field_key

        label_map = dict(self.admin.price_field_labels())
        await query.message.reply_text(f"Send new value for {label_map.get(field_key, field_key)}")
        return ADMIN_PRICE_EDIT_VALUE

    async def price_edit_value(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END

        value = self._parse_non_negative_float(update.message.text)
        if value is None:
            await update.message.reply_text("Please send a valid non-negative number.")
            return ADMIN_PRICE_EDIT_VALUE

        event_id = context.user_data.get("price_edit_event_id")
        field_key = context.user_data.get("price_edit_field")
        if not event_id or not field_key:
            await update.message.reply_text("Price edit context missing.")
            return ConversationHandler.END

        ok = self.admin.set_event_price(event_id, field_key, value)
        if not ok:
            await update.message.reply_text("Failed to update price.")
            return ConversationHandler.END

        await update.message.reply_text(
            f"Updated price successfully.",
            reply_markup=self._price_edit_keyboard(event_id),
        )
        return ADMIN_PRICE_EDIT_CHOOSE

    async def price_edit_cancel(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        context.user_data.pop("price_edit_event_id", None)
        context.user_data.pop("price_edit_field", None)
        await query.edit_message_text("Price editing finished.")
        return ConversationHandler.END

    async def export_event(self, update: Update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return ConversationHandler.END
        if not context.args:
            await update.message.reply_text("Usage: /export <event_id>")
            return ConversationHandler.END
        if not context.args[0].isdigit():
            await update.message.reply_text("event_id must be numeric.")
            return ConversationHandler.END

        event_id = int(context.args[0])
        rows = self.admin.export_event_csv(event_id)
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Reservation code",
                "Ticket type",
                "Boys",
                "Girls",
                "Quantity",
                "Total price",
                "Status",
                "Payment file type",
                "Payment file id",
                "Admin note",
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
    bot.application = application
    application.run_polling()


if __name__ == "__main__":
    main()
