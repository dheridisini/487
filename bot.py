import logging
import re

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from datetime import datetime, timedelta
from config import BOT_TOKEN, USER_DB, DOMAINS
from database import (
    get_user_session,
    create_session,
    delete_session,
    update_user_filters,
    get_user_filters
)
from adsterra_api import (
    get_stats,
    get_placements,
    calculate_summary,
    format_summary,
    format_stats
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
LOGIN, MAIN_MENU, DATE_FILTER, DOMAIN_FILTER, PLACEMENT_FILTER = range(5)

# Helper functions
def get_preset_dates(preset):
    today = datetime.now().date()
    
    if preset == "today":
        return today, today
    elif preset == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif preset == "last7":
        return today - timedelta(days=6), today
    elif preset == "last30":
        return today - timedelta(days=29), today
    elif preset == "thismonth":
        start = today.replace(day=1)
        return start, today
    elif preset == "thisyear":
        start = today.replace(month=1, day=1)
        return start, today
    else:
        return today, today

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    filters = get_user_filters(user_id) or {}

    # Build menu with current filters
    start_date = filters.get('start_date', 'Today')
    end_date = filters.get('end_date', 'Today')
    domain = DOMAINS.get(filters.get('domain'), 'All Domains')
    placement = f"Placement {filters.get('placement')}" if filters.get('placement') else 'All Placements'
    group_by = filters.get('group_by', 'date').capitalize()

    keyboard = [
        [
            InlineKeyboardButton("📊 Today's Report", callback_data="report_today"),
            InlineKeyboardButton("📅 Date Filter", callback_data="date_filter")
        ],
        [
            InlineKeyboardButton(f"🌐 Domain: {domain}", callback_data="domain_filter"),
            InlineKeyboardButton(f"🎯 {placement}", callback_data="placement_filter")
        ],
        [
            InlineKeyboardButton(f"📌 Group By: {group_by}", callback_data="toggle_group"),
            InlineKeyboardButton("🔄 Reset Filters", callback_data="reset_filters")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "📊 *Adsterra Dashboard* - Main Menu\n\nCurrent filters:"

    if update.callback_query:
        try:
            # 🧹 Hapus pesan lama dulu
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=update.callback_query.message.message_id
            )
        except Exception as e:
            print(f"❗ Gagal hapus pesan lama: {e}")

        # Kirim menu baru di bawah
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        # Saat /start atau message awal
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )





async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE, start_date=None, end_date=None):
    user_id = update.effective_user.id
    filters = get_user_filters(user_id) or {}
    
    if not start_date or not end_date:
        start_date = filters.get('start_date', datetime.now().date().isoformat())
        end_date = filters.get('end_date', datetime.now().date().isoformat())
    
    domain = filters.get('domain')
    placement = filters.get('placement')
    group_by = filters.get('group_by', 'date')
    
    # Get stats from API
    stats = await get_stats(start_date, end_date, domain, placement, group_by)
    
    if not stats:
        await update.callback_query.answer("Failed to fetch data from Adsterra API")
        return
    
    # Calculate and show summary
    summary = calculate_summary(stats)
    summary_text = format_summary(summary, start_date, end_date)
    
    # Show detailed stats
    detailed_stats = format_stats(stats, group_by)
    
    # Send summary first
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📈 *Adsterra Report Summary*\n\n{summary_text}",
        parse_mode='Markdown'
    )
    
    # Then send detailed stats (split if too long)
    if len(detailed_stats) > 4000:
        parts = [detailed_stats[i:i+4000] for i in range(0, len(detailed_stats), 4000)]
        for part in parts:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=part,
                parse_mode='Markdown'
            )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=detailed_stats,
            parse_mode='Markdown'
        )
    
    # Show menu again
    await show_main_menu(update, context)

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    if session:
        await update.message.reply_text(
            f"Welcome back, {session[1]}!",
            reply_markup=ReplyKeyboardRemove()
        )
        await show_main_menu(update, context)
    else:
        await update.message.reply_text(
            "🔒 Please login to access Adsterra Dashboard.\n\n"
            "Send your credentials in this format:\n"
            "`username|password`",
            parse_mode='Markdown'
        )
        return LOGIN

    return ConversationHandler.END  # keluar dari conversation apapun

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if '|' not in text:
        await update.message.reply_text(
            "Invalid format. Please send:\n`username|password`",
            parse_mode='Markdown'
        )
        return LOGIN
    
    username, password = text.split('|', 1)
    username = username.strip()
    password = password.strip()
    
    if username in USER_DB and USER_DB[username] == password:
        # Successful login
        create_session(user_id, username)
        await update.message.reply_text(
            f"✅ Login successful! Welcome, {username}.",
            reply_markup=ReplyKeyboardRemove()
        )
        await show_main_menu(update, context)
        return MAIN_MENU
    else:
        await update.message.reply_text(
            "❌ Invalid credentials. Please try again.\n\n"
            "Send your credentials in this format:\n"
            "`username|password`",
            parse_mode='Markdown'
        )
        return LOGIN

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    delete_session(user_id)
    await update.message.reply_text(
        "You have been logged out successfully.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Operation cancelled.',
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Callback handlers
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == 'report_today':
        today = datetime.now().date().isoformat()
        await generate_report(update, context, today, today)
    
    elif data == 'date_filter':
        keyboard = [
            [
                InlineKeyboardButton("Today", callback_data="preset_today"),
                InlineKeyboardButton("Yesterday", callback_data="preset_yesterday")
            ],
            [
                InlineKeyboardButton("Last 7 Days", callback_data="preset_last7"),
                InlineKeyboardButton("Last 30 Days", callback_data="preset_last30")
            ],
            [
                InlineKeyboardButton("This Month", callback_data="preset_thismonth"),
                InlineKeyboardButton("This Year", callback_data="preset_thisyear")
            ],
            [
                InlineKeyboardButton("Custom Range", callback_data="preset_custom")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")
            ]
        ]
        
        await query.edit_message_text(
            text="📅 Select date range:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('preset_'):
        preset = data.split('_')[1]
        
        if preset == 'custom':
            await query.edit_message_text(
                text="Please send the date range in format:\n"
                     "`YYYY-MM-DD to YYYY-MM-DD`\n\n"
                     "Example: `2023-10-01 to 2023-10-07`",
                parse_mode='Markdown'
            )
            return DATE_FILTER
        else:
            start_date, end_date = get_preset_dates(preset)
            update_user_filters(
                user_id,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            )
            await generate_report(update, context, start_date.isoformat(), end_date.isoformat())
            return MAIN_MENU
    
    elif data == 'domain_filter':
        keyboard = []
        
        # Add all domains option
        keyboard.append([
            InlineKeyboardButton("All Domains", callback_data="domain_all")
        ])
        
        # Add each domain as a button
        for domain_id, domain_name in DOMAINS.items():
            keyboard.append([
                InlineKeyboardButton(domain_name, callback_data=f"domain_{domain_id}")
            ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")
        ])
        
        await query.edit_message_text(
            text="🌐 Select domain:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('domain_'):
        domain_part = data.split('_')[1]
        
        if domain_part == 'all':
            update_user_filters(user_id, domain=None, placement=None)
            await query.edit_message_text(
                text="✅ Filter updated: All domains selected"
            )
        else:
            domain_id = int(domain_part)
            update_user_filters(user_id, domain=domain_id, placement=None)
            await query.edit_message_text(
                text=f"✅ Filter updated: Domain {DOMAINS.get(domain_id, domain_id)} selected"
            )
        
        await show_main_menu(update, context)
        return MAIN_MENU
    
    elif data == 'placement_filter':
        filters = get_user_filters(user_id) or {}
        domain_id = filters.get('domain')
        
        if not domain_id:
            await query.answer("Please select a domain first")
            return
        
        placements = await get_placements(domain_id)
        
        if not placements:
            await query.answer("No placements found for this domain")
            return
        
        keyboard = []
        
        # Add all placements option
        keyboard.append([
            InlineKeyboardButton("All Placements", callback_data="placement_all")
        ])
        
        # Add each placement as a button
        for placement in placements[:10]:  # Limit to 10 placements
            placement_id = placement.get('id')
            placement_name = placement.get('alias') or placement.get('title') or f"Placement {placement_id}"
            keyboard.append([
                InlineKeyboardButton(placement_name, callback_data=f"placement_{placement_id}")
            ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")
        ])
        
        await query.edit_message_text(
            text="🎯 Select placement:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('placement_'):
        placement_part = data.split('_')[1]
        
        if placement_part == 'all':
            update_user_filters(user_id, placement=None)
            await query.edit_message_text(
                text="✅ Filter updated: All placements selected"
            )
        else:
            placement_id = int(placement_part)
            update_user_filters(user_id, placement=placement_id)
            await query.edit_message_text(
                text=f"✅ Filter updated: Placement {placement_id} selected"
            )
        
        await show_main_menu(update, context)
        return MAIN_MENU
    
    elif data == 'toggle_group':
        filters = get_user_filters(user_id) or {}
        current_group = filters.get('group_by', 'date')
        new_group = 'country' if current_group == 'date' else 'date'
        
        update_user_filters(user_id, group_by=new_group)
        await query.edit_message_text(
            text=f"✅ Group by changed to {new_group.capitalize()}"
        )
        await generate_report(update, context)
        return MAIN_MENU
    
    elif data == 'reset_filters':
        update_user_filters(user_id, start_date=None, end_date=None, domain=None, placement=None, group_by='date')
        await query.edit_message_text(
            text="✅ All filters have been reset"
        )
        await show_main_menu(update, context)
        return MAIN_MENU
    
    elif data == 'back_to_menu':
        await show_main_menu(update, context)
        return MAIN_MENU

async def date_filter_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    try:
        if ' to ' in text:
            start_str, end_str = text.split(' to ', 1)
            start_date = datetime.strptime(start_str.strip(), '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str.strip(), '%Y-%m-%d').date()
            
            if start_date > end_date:
                raise ValueError("Start date cannot be after end date")
            
            update_user_filters(
                user_id,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            )
            
            await update.message.reply_text(
                f"✅ Date range set to {start_date} to {end_date}"
            )
            await generate_report(update, context, start_date.isoformat(), end_date.isoformat())
            return MAIN_MENU
        else:
            raise ValueError("Invalid format")
    
    except ValueError as e:
        await update.message.reply_text(
            f"❌ Invalid date format: {e}\n\n"
            "Please send dates in format:\n"
            "`YYYY-MM-DD to YYYY-MM-DD`\n\n"
            "Example: `2023-10-01 to 2023-10-07`",
            parse_mode='Markdown'
        )
        return DATE_FILTER

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # ⬅️ Start handler DI LUAR ConversationHandler
    application.add_handler(CommandHandler('start', start))

    # 🎯 Conversation handler untuk bagian interaktif lainnya
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler)  # misalnya menu pakai tombol
        ],
        states={
            LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, login)],
            MAIN_MENU: [CallbackQueryHandler(button_handler)],
            DATE_FILTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_filter_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('logout', logout))

    application.run_polling()

if __name__ == '__main__':
    main()
