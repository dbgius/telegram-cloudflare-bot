 #!/usr/bin/env python3
"""
✨ ENHANCED SUBSCRIPTION CODE BOT - PROFESSIONAL VERSION ✨
Improved with better structure, ban/unban system, and enhanced admin panel.
"""

import asyncio
import logging
import re
import json
import time
import pickle
import os
from typing import Dict, Optional, Tuple, List, Any, Set
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path

# Third-party imports
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode, ChatAction

# ==================== ENHANCED CONFIGURATION ====================
BOT_TOKEN = "8278734441:AAEqPI3swV6L0aLTncKXEA_ivvYOFM3zhz8"
ADMIN_CHAT_IDS = {7853409680}  # ⚠️ REPLACE WITH ACTUAL IDs

# Payment Wallets (⚠️ REPLACE WITH ACTUAL ADDRESSES)
WALLETS = {
    "USDT_TRC20": "TXYZabc123...",
    "USDT_BEP20": "0xABCdef456..."
}

# Bot Settings
SCREENSHOT_TIMEOUT = 300
ORDER_EXPIRY = 3600
DATA_FILE = "bot_data.pkl"  # File for persisting data

# ==================== ENHANCED DATA STRUCTURES ====================
class Product(Enum):
    DAY = {
        "name": "1 Day",
        "price": 10,
        "emoji": "🎯",
        "duration": "24 hours"
    }
    WEEK = {
        "name": "1 Week", 
        "price": 30,
        "emoji": "🚀",
        "duration": "7 days"
    }
    MONTH = {
        "name": "1 Month",
        "price": 50,
        "emoji": "👑",
        "duration": "30 days"
    }
    YEAR = {
        "name": "1 Year",
        "price": 150,
        "emoji": "🏆",
        "duration": "365 days"
    }

class OrderStatus(Enum):
    INIT = "🆕 New"
    AWAIT_PAYMENT = "⏳ Awaiting Payment"
    UNDER_REVIEW = "🔍 Under Review"
    REJECTED = "❌ Rejected"
    COMPLETED = "✅ Completed"
    CANCELLED = "🚫 Cancelled"

@dataclass
class Order:
    user_id: int
    username: str
    product: Product
    network: str
    amount: float
    status: OrderStatus
    created_at: float
    screenshot_id: Optional[str] = None
    
    @property
    def description(self) -> str:
        return f"{self.product.value['emoji']} {self.product.value['name']} (${self.amount}) via {self.network}"

# ==================== DATA MANAGER ====================
class DataManager:
    def __init__(self):
        self.user_orders: Dict[int, Order] = {}
        self.admin_pending: Dict[int, int] = {}
        self.banned_users: Set[int] = set()
        self.data_file = DATA_FILE
        
    def save_data(self):
        """Save all data to file"""
        data = {
            'user_orders': self.user_orders,
            'banned_users': list(self.banned_users)
        }
        try:
            with open(self.data_file, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"Data saved successfully: {len(self.user_orders)} orders, {len(self.banned_users)} banned users")
        except Exception as e:
            logger.error(f"Failed to save data: {e}")
    
    def load_data(self):
        """Load data from file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'rb') as f:
                    data = pickle.load(f)
                self.user_orders = data.get('user_orders', {})
                self.banned_users = set(data.get('banned_users', []))
                logger.info(f"Data loaded: {len(self.user_orders)} orders, {len(self.banned_users)} banned users")
            except Exception as e:
                logger.error(f"Failed to load data: {e}")
                self.user_orders = {}
                self.banned_users = set()
        else:
            logger.info("No existing data file, starting fresh")
    
    def add_order(self, order: Order):
        """Add new order"""
        self.user_orders[order.user_id] = order
        self.save_data()
    
    def update_order_status(self, user_id: int, status: OrderStatus):
        """Update order status"""
        if user_id in self.user_orders:
            self.user_orders[user_id].status = status
            self.save_data()
    
    def delete_order(self, user_id: int):
        """Delete order"""
        if user_id in self.user_orders:
            del self.user_orders[user_id]
            self.save_data()
    
    def ban_user(self, user_id: int):
        """Ban a user"""
        self.banned_users.add(user_id)
        self.save_data()
        logger.info(f"User {user_id} banned")
    
    def unban_user(self, user_id: int):
        """Unban a user"""
        if user_id in self.banned_users:
            self.banned_users.remove(user_id)
            self.save_data()
            logger.info(f"User {user_id} unbanned")
    
    def is_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        return user_id in self.banned_users
    
    def get_pending_orders(self) -> List[Order]:
        """Get all pending orders"""
        return [order for order in self.user_orders.values() 
                if order.status == OrderStatus.UNDER_REVIEW]
    
    def get_stats(self) -> Dict[str, int]:
        """Get bot statistics"""
        total_orders = len(self.user_orders)
        completed = len([o for o in self.user_orders.values() if o.status == OrderStatus.COMPLETED])
        cancelled = len([o for o in self.user_orders.values() if o.status == OrderStatus.CANCELLED])
        pending = len([o for o in self.user_orders.values() if o.status == OrderStatus.UNDER_REVIEW])
        active = len([o for o in self.user_orders.values() if o.status in [OrderStatus.INIT, OrderStatus.AWAIT_PAYMENT, OrderStatus.UNDER_REVIEW]])
        
        return {
            'total_orders': total_orders,
            'completed': completed,
            'cancelled': cancelled,
            'pending': pending,
            'active': active,
            'banned_users': len(self.banned_users)
        }

# ==================== INITIALIZE DATA MANAGER ====================
data_manager = DataManager()

# ==================== ENHANCED LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot_operations.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS ====================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_CHAT_IDS

def can_create_order(user_id: int) -> Tuple[bool, Optional[str]]:
    """Check if user can create a new order"""
    if data_manager.is_banned(user_id):
        return False, "🚫 **Your account is banned!**\n\nFor assistance, contact support."
    
    if user_id in data_manager.user_orders:
        status = data_manager.user_orders[user_id].status
        if status in [OrderStatus.UNDER_REVIEW, OrderStatus.AWAIT_PAYMENT, OrderStatus.INIT]:
            return False, f"⏳ You have an active order ({status.value}). Please complete or cancel it first."
        return True, None
    return True, None

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'[<>{}`]', '', text)[:1000]

def format_time(seconds: float) -> str:
    """Format seconds to readable time"""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# ==================== KEYBOARD BUILDERS ====================
def build_product_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    for product in Product:
        btn = InlineKeyboardButton(
            f"{product.value['emoji']} {product.value['name']} - ${product.value['price']}",
            callback_data=f"product_{product.name}"
        )
        keyboard.append([btn])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_order")])
    return InlineKeyboardMarkup(keyboard)

def build_network_keyboard(product: Product) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🌐 USDT (TRC20)", callback_data="network_TRC20")],
        [InlineKeyboardButton("🔗 USDT (BEP20)", callback_data="network_BEP20")],
        [InlineKeyboardButton("↩️ Back", callback_data="back_to_products")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_order")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_payment_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📸 Upload Screenshot", callback_data="upload_screenshot"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_order")
        ],
        [InlineKeyboardButton("ℹ️ Help", callback_data="payment_help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_cancel_confirmation_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Cancel", callback_data="confirm_cancel"),
            InlineKeyboardButton("❌ No, Keep", callback_data="keep_order")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_admin_review_keyboard(user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"admin_accept_{user_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Admin main panel with ONLY pending orders and ban/unban options"""
    keyboard = [
        [InlineKeyboardButton("📋 Pending Orders", callback_data="admin_pending")],
        [InlineKeyboardButton("🚫 | ✅ Ban/Unban User", callback_data="admin_ban_panel")],
        [InlineKeyboardButton("🚪 User Mode", callback_data="admin_user_mode")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_ban_panel_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for ban/unban panel"""
    keyboard = [
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban_user")],
        [InlineKeyboardButton("✅ Unban User", callback_data="admin_unban_user")],
        [InlineKeyboardButton("📋 Banned List", callback_data="admin_banned_list")],
        [InlineKeyboardButton("↩️ Back", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== MESSAGE TEMPLATES ====================
WELCOME_USER = """
✨ **Welcome to Premium Codes Bot** ✨

Your trusted source for premium subscription codes.

**Why Choose Us:**
• ⚡️ Instant delivery
• 🔒 Secure process
• 🌟 24/7 support
• 💎 High quality

Select your package:
"""

WELCOME_ADMIN = """
👑 **Admin Control Panel** 👑

Welcome back, administrator!

**Quick Actions:**
📋 **Pending Orders:** View orders awaiting review
🚫 | ✅ **Ban/Unban:** Manage banned users
🚪 **User Mode:** Switch to normal user mode
"""

PAYMENT_INSTRUCTIONS = """
💳 **PAYMENT INSTRUCTIONS**

**Send To:** `{wallet}`
**Amount:** `${amount} {network}`
**Network:** {network}

**⚠️ IMPORTANT:**
• Send **EXACT** amount (${amount})
• Use **{network}** network only
• Include transaction fee

**After Payment:**
1. Click '📸 Upload Screenshot'
2. Send ONE clear screenshot
3. Wait for verification

⏰ **Order expires in 60 minutes**
"""

SCREENSHOT_GUIDE = """
📸 **SCREENSHOT GUIDE**

Send **ONE clear screenshot** showing:

**Required:**
✅ Transaction Hash/ID
✅ Sender/Receiver Addresses
✅ Amount Sent (${amount})
✅ Network ({network})
✅ Timestamp

**Note:** Only first screenshot accepted.
"""

# ==================== MAIN HANDLERS ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user = update.effective_user
    
    # Load data on start
    data_manager.load_data()
    
    if is_admin(user.id):
        await update.message.reply_text(
            WELCOME_ADMIN,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_admin_main_keyboard()
        )
        return
    
    # Check if user is banned
    if data_manager.is_banned(user.id):
        await update.message.reply_text(
            "🚫 **Your account is banned!**\n\n"
            "You cannot use the bot.\n"
            "For assistance, contact support.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Clear any terminal state orders
    if user.id in data_manager.user_orders and data_manager.user_orders[user.id].status in [
        OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.COMPLETED
    ]:
        data_manager.delete_order(user.id)
    
    await show_user_interface(update, context)

async def show_user_interface(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user interface (product selection)"""
    user = update.effective_user
    
    # Check if user can create new order
    can_create, reason = can_create_order(user.id)
    if not can_create:
        # Create a keyboard with cancel button
        keyboard = [[InlineKeyboardButton("❌ Cancel Order", callback_data="cancel_order")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ **Order Conflict**\n\n{reason}\n\nYou can cancel your current order below.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return
    
    await update.message.reply_text(
        WELCOME_USER,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_product_keyboard()
    )

async def handle_product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle product selection"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    product_name = query.data.replace("product_", "")
    
    try:
        product = Product[product_name]
    except KeyError:
        await query.edit_message_text("❌ Invalid selection.")
        return
    
    # Create or update order
    if user.id not in data_manager.user_orders:
        order = Order(
            user_id=user.id,
            username=user.username or user.first_name or str(user.id),
            product=product,
            network="",
            amount=product.value['price'],
            status=OrderStatus.INIT,
            created_at=time.time()
        )
        data_manager.add_order(order)
    else:
        data_manager.user_orders[user.id].product = product
        data_manager.user_orders[user.id].amount = product.value['price']
        data_manager.user_orders[user.id].status = OrderStatus.INIT
        data_manager.save_data()
    
    await query.edit_message_text(
        f"🎯 **Selected:** {product.value['emoji']} {product.value['name']}\n"
        f"💰 **Price:** ${product.value['price']}\n"
        f"⏱️ **Duration:** {product.value['duration']}\n\n"
        f"**Choose payment network:**",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_network_keyboard(product)
    )

async def handle_network_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle network selection"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    if query.data == "back_to_products":
        await query.edit_message_text(
            WELCOME_USER,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_product_keyboard()
        )
        return
    
    if query.data == "cancel_order":
        await handle_cancel_confirmation(update, context)
        return
    
    if user.id not in data_manager.user_orders:
        await query.edit_message_text("❌ Session expired. Start over with /start")
        return
    
    # Parse network
    if query.data.startswith("network_"):
        network_type = query.data.replace("network_", "")
        wallet_key = f"USDT_{network_type}"
        
        if wallet_key not in WALLETS:
            await query.edit_message_text("❌ Network unavailable.")
            return
        
        # Update order
        data_manager.user_orders[user.id].network = wallet_key
        data_manager.user_orders[user.id].status = OrderStatus.AWAIT_PAYMENT
        data_manager.save_data()
        
        wallet_address = WALLETS[wallet_key]
        
        instructions = PAYMENT_INSTRUCTIONS.format(
            wallet=wallet_address,
            amount=data_manager.user_orders[user.id].amount,
            network=network_type
        )
        
        await query.edit_message_text(
            instructions,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_payment_keyboard()
        )
    else:
        # Fallback for unknown callback
        await query.edit_message_text("❌ Unknown action. Please start over with /start")

async def handle_payment_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show payment help"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if user.id not in data_manager.user_orders:
        await query.edit_message_text("❌ No active order.")
        return
    
    order = data_manager.user_orders[user.id]
    network_type = order.network.replace("USDT_", "")
    
    await query.edit_message_text(
        SCREENSHOT_GUIDE.format(
            amount=order.amount,
            network=network_type
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_payment_keyboard()
    )

async def handle_upload_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch to screenshot upload mode"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if user.id not in data_manager.user_orders:
        await query.edit_message_text("❌ No active order.")
        return
    
    order = data_manager.user_orders[user.id]
    if order.status != OrderStatus.AWAIT_PAYMENT:
        await query.edit_message_text("⚠️ Invalid action in current state.")
        return
    
    # Set screenshot expectation
    context.user_data['expecting_screenshot'] = True
    context.user_data['screenshot_time'] = time.time()
    
    network_type = order.network.replace("USDT_", "")
    
    await query.edit_message_text(
        SCREENSHOT_GUIDE.format(
            amount=order.amount,
            network=network_type
        ),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process uploaded screenshot"""
    if not context.user_data.get('expecting_screenshot', False):
        return
    
    user = update.effective_user
    
    if user.id not in data_manager.user_orders:
        await update.message.reply_text("❌ No active order.")
        context.user_data.pop('expecting_screenshot', None)
        return
    
    # Check timeout
    screenshot_time = context.user_data.get('screenshot_time', 0)
    if time.time() - screenshot_time > SCREENSHOT_TIMEOUT:
        await update.message.reply_text("⚠️ Screenshot upload timeout. Restart process.")
        context.user_data.pop('expecting_screenshot', None)
        return
    
    # Validate only one screenshot
    order = data_manager.user_orders[user.id]
    if order.screenshot_id:
        await update.message.reply_text("⚠️ Screenshot already submitted.")
        return
    
    # Get photo
    if not update.message.photo:
        await update.message.reply_text("❌ Please send a valid image.")
        return
    
    photo = update.message.photo[-1]
    
    # Update order
    data_manager.user_orders[user.id].screenshot_id = photo.file_id
    data_manager.user_orders[user.id].status = OrderStatus.UNDER_REVIEW
    data_manager.save_data()
    
    # Clear expectation flag
    context.user_data.pop('expecting_screenshot', None)
    context.user_data.pop('screenshot_time', None)
    
    # Notify user
    await update.message.reply_text(
        "✅ **Screenshot Received!**\n\n"
        "Your payment is now under review.\n"
        "• Status: 🔍 Under Review\n"
        "• Estimated time: 5-15 minutes\n\n"
        "Thank you for your patience!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Alert admins
    admin_message = (
        f"🚨 **NEW PAYMENT SUBMISSION**\n\n"
        f"**User:** @{order.username} (ID: `{order.user_id}`)\n"
        f"**Order:** {order.description}\n"
        f"**Amount:** ${order.amount}\n"
        f"**Network:** {order.network}\n"
        f"**Status:** ⏳ Awaiting Review\n\n"
        f"**Actions Required:**\n"
        f"1. Verify screenshot\n"
        f"2. Check payment\n"
        f"3. Approve or reject"
    )
    
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=order.screenshot_id,
                caption=admin_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_admin_review_keyboard(user.id)
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    logger.info(f"Screenshot received from user {user.id}")

async def handle_cancel_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show cancellation confirmation"""
    query = update.callback_query if update.callback_query else None
    user = update.effective_user
    
    # Handle command-based cancellation
    if user.id not in data_manager.user_orders:
        if query:
            await query.edit_message_text("❌ No active order to cancel.")
        else:
            await update.message.reply_text("❌ No active order to cancel.")
        return
    
    order = data_manager.user_orders[user.id]
    if order.status in [OrderStatus.COMPLETED, OrderStatus.REJECTED]:
        message = f"⚠️ Order already {order.status.value.lower()}."
        if query:
            await query.edit_message_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    confirmation_text = (
        "⚠️ **Confirm Cancellation**\n\n"
        f"Order: {order.description}\n"
        f"Status: {order.status.value}\n"
        f"Amount: ${order.amount}\n\n"
        "Are you sure you want to cancel?\n"
        "This cannot be undone."
    )
    
    if query:
        await query.edit_message_text(
            confirmation_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_cancel_confirmation_keyboard()
        )
    else:
        await update.message.reply_text(
            confirmation_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_cancel_confirmation_keyboard()
        )

async def handle_cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process cancel confirmation"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    if query.data == "confirm_cancel":
        if user.id in data_manager.user_orders:
            # Clean up admin pending if exists
            for admin_id, pending_user in list(data_manager.admin_pending.items()):
                if pending_user == user.id:
                    del data_manager.admin_pending[admin_id]
            
            # Update order status
            data_manager.update_order_status(user.id, OrderStatus.CANCELLED)
            
            # Clear the order from storage
            data_manager.delete_order(user.id)
            
            await query.edit_message_text(
                "✅ **Order Cancelled**\n\n"
                "Your order has been cancelled successfully.\n\n"
                "Start a new order with /start",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Start New Order", callback_data="user_start")]])
            )
            logger.info(f"Order cancelled for user {user.id}")
        else:
            await query.edit_message_text("❌ No active order.")
    
    elif query.data == "keep_order":
        # Go back to current state
        if user.id in data_manager.user_orders:
            order = data_manager.user_orders[user.id]
            if order.status == OrderStatus.INIT:
                await query.edit_message_text(
                    WELCOME_USER,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=build_product_keyboard()
                )
            elif order.status == OrderStatus.AWAIT_PAYMENT:
                network_type = order.network.replace("USDT_", "")
                wallet_address = WALLETS.get(order.network, "")
                
                instructions = PAYMENT_INSTRUCTIONS.format(
                    wallet=wallet_address,
                    amount=order.amount,
                    network=network_type
                )
                
                await query.edit_message_text(
                    instructions,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=build_payment_keyboard()
                )
            elif order.status == OrderStatus.UNDER_REVIEW:
                await query.edit_message_text(
                    "⏳ **Order Under Review**\n\n"
                    "Your order is currently under review by an admin.\n"
                    "Please wait for the verification process to complete.\n\n"
                    "Status: 🔍 Under Review",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(
                    f"✅ **Order Kept**\n\nStatus: {order.status.value}",
                    parse_mode=ParseMode.MARKDOWN
                )
        else:
            await query.edit_message_text(
                "❌ Order not found. Start over with /start",
                parse_mode=ParseMode.MARKDOWN
            )

# ==================== ADMIN HANDLERS ====================
async def handle_admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin accept/reject decisions"""
    query = update.callback_query
    await query.answer()
    
    admin = update.effective_user
    if not is_admin(admin.id):
        await context.bot.send_message(
            chat_id=admin.id,
            text="❌ Unauthorized."
        )
        return
    
    # Parse action and user_id
    if query.data.startswith("admin_accept_"):
        user_id = int(query.data.replace("admin_accept_", ""))
        action = "accept"
    elif query.data.startswith("admin_reject_"):
        user_id = int(query.data.replace("admin_reject_", ""))
        action = "reject"
    else:
        await context.bot.send_message(
            chat_id=admin.id,
            text="❌ Invalid action."
        )
        return
    
    # Get order
    if user_id not in data_manager.user_orders:
        try:
            await query.edit_message_text("❌ Order no longer exists.")
        except:
            await context.bot.send_message(
                chat_id=admin.id,
                text="❌ Order no longer exists."
            )
        return
    
    order = data_manager.user_orders[user_id]
    if order.status != OrderStatus.UNDER_REVIEW:
        try:
            await query.edit_message_text(f"⚠️ Already processed: {order.status.value}")
        except Exception as e:
            try:
                await query.edit_message_caption(f"⚠️ Already processed: {order.status.value}")
            except:
                await context.bot.send_message(
                    chat_id=admin.id,
                    text=f"⚠️ Already processed: {order.status.value}"
                )
        return
    
    if action == "accept":
        # Lock order for this admin
        data_manager.admin_pending[admin.id] = user_id
        
        try:
            # If message has caption (image)
            await query.edit_message_caption(
                caption=f"✅ **ACCEPTED** - Order for user {user_id}\n\n"
                       f"**User:** @{order.username}\n"
                       f"**Amount:** ${order.amount}\n\n"
                       "**Please send the subscription code in your next message.**\n"
                       "Format: Plain text code only\n\n"
                       "⚠️ Code will be sent directly to user.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            # If normal text message
            try:
                await query.edit_message_text(
                    f"✅ **ACCEPTED** - Order for user {user_id}\n\n"
                    f"**User:** @{order.username}\n"
                    f"**Amount:** ${order.amount}\n\n"
                    "**Please send the subscription code in your next message.**\n"
                    "Format: Plain text code only\n\n"
                    "⚠️ Code will be sent directly to user.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e2:
                # If all fails, send new message
                await context.bot.send_message(
                    chat_id=admin.id,
                    text=f"✅ **ACCEPTED** - Order for user {user_id}\n\n"
                         f"**User:** @{order.username}\n"
                         f"**Amount:** ${order.amount}\n\n"
                         "**Please send the subscription code in your next message.**\n"
                         "Format: Plain text code only\n\n"
                         "⚠️ Code will be sent directly to user.",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        # Notify user
        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 **Payment Approved!**\n\n"
                 "Your payment has been verified!\n"
                 "Admin is preparing your code.\n"
                 "You'll receive it shortly.\n\n"
                 "Thank you for your purchase!",
            parse_mode=ParseMode.MARKDOWN
        )
        
    elif action == "reject":
        # Update order status
        data_manager.update_order_status(user_id, OrderStatus.REJECTED)
        
        try:
            # If message has caption (image)
            await query.edit_message_caption(
                caption=f"❌ **REJECTED** - Order for user {user_id}\n\n"
                       f"**User:** @{order.username}\n"
                       f"**Action:** User notified",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            # If normal text message
            try:
                await query.edit_message_text(
                    f"❌ **REJECTED** - Order for user {user_id}\n\n"
                    f"**User:** @{order.username}\n"
                    f"**Action:** User notified",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e2:
                # If all fails, send new message
                await context.bot.send_message(
                    chat_id=admin.id,
                    text=f"❌ **REJECTED** - Order for user {user_id}\n\n"
                         f"**User:** @{order.username}\n"
                         f"**Action:** User notified",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        # Notify user
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ **Payment Review Result**\n\n"
                 "Unfortunately, your payment could not be verified.\n\n"
                 "**Possible reasons:**\n"
                 "• Incorrect amount\n"
                 "• Wrong network\n"
                 "• Unclear screenshot\n"
                 "• Payment not found\n\n"
                 "**You can:**\n"
                 "• Try again with /start\n"
                 "• Ensure exact amount and correct network\n\n"
                 "We appreciate your understanding.",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_admin_code_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process admin's code submission"""
    admin = update.effective_user
    
    if not is_admin(admin.id) or admin.id not in data_manager.admin_pending:
        return
    
    user_id = data_manager.admin_pending[admin.id]
    
    if user_id not in data_manager.user_orders:
        await update.message.reply_text("❌ Order no longer exists.")
        del data_manager.admin_pending[admin.id]
        return
    
    order = data_manager.user_orders[user_id]
    if order.status != OrderStatus.UNDER_REVIEW:
        await update.message.reply_text(f"⚠️ Order status changed: {order.status.value}")
        del data_manager.admin_pending[admin.id]
        return
    
    # Get and sanitize code
    code = sanitize_text(update.message.text.strip())
    if not code or len(code) < 4:
        await update.message.reply_text("❌ Invalid code. Minimum 4 characters.")
        return
    
    # Send code to user
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎁 **YOUR SUBSCRIPTION CODE** 🎁\n\n"
                 f"**Package:** {order.description}\n"
                 f"**Code:** `{code}`\n\n"
                 f"**Instructions:**\n"
                 f"1. Use this code to activate subscription\n"
                 f"2. Code is valid for one use\n"
                 f"3. Store securely\n\n"
                 f"💎 **Thank you for your purchase!** 💎",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Update order status
        data_manager.update_order_status(user_id, OrderStatus.COMPLETED)
        
        # Cleanup
        del data_manager.admin_pending[admin.id]
        
        # Confirm to admin
        await update.message.reply_text(
            f"✅ **CODE DELIVERED**\n\n"
            f"User: @{order.username}\n"
            f"Order: {order.description}\n"
            f"Code: `{code}`\n\n"
            f"Transaction completed.",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Failed to send code to user {user_id}: {e}")
        await update.message.reply_text(f"❌ Failed to deliver code: {str(e)[:100]}")

# ==================== ENHANCED ADMIN PANEL ====================
async def handle_admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show pending orders to admin"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Unauthorized.")
        return
    
    pending_orders = data_manager.get_pending_orders()
    
    if not pending_orders:
        await query.edit_message_text(
            "✅ **No pending orders**\n\nAll orders processed.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="admin_back")]])
        )
        return
    
    message = "📋 **PENDING ORDERS**\n\n"
    for i, order in enumerate(pending_orders[:10], 1):  # Limit to 10 orders
        time_ago = format_time(time.time() - order.created_at)
        message += (
            f"**{i}. User:** @{order.username} (ID: `{order.user_id}`)\n"
            f"**Order:** {order.description}\n"
            f"**Amount:** ${order.amount}\n"
            f"**Time:** {time_ago} ago\n\n"
            "---\n\n"
        )
    
    if len(pending_orders) > 10:
        message += f"**+ {len(pending_orders) - 10} additional orders**\n\n"
    
    message += f"**Total:** {len(pending_orders)} pending orders"
    
    await query.edit_message_text(
        message[:4000],
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="admin_back")]])
    )

async def handle_admin_ban_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show ban/unban panel"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Unauthorized.")
        return
    
    await query.edit_message_text(
        "🚫 | ✅ **User Ban/Unban Panel**\n\n"
        "Choose the action you want to perform:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_ban_panel_keyboard()
    )

async def handle_admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initiate ban user process"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Unauthorized.")
        return
    
    # Set state for user ID input
    context.user_data['awaiting_ban_user_id'] = True
    
    await query.edit_message_text(
        "🚫 **Ban User**\n\n"
        "Send the user ID you want to ban:\n"
        "(Must be numeric ID)\n\n"
        "⚠️ You can get ID from:\n"
        "• /id command for the user\n"
        "• From banned list\n"
        "• From pending orders",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="admin_ban_panel")]])
    )

async def handle_admin_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initiate unban user process"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Unauthorized.")
        return
    
    # Set state for user ID input
    context.user_data['awaiting_unban_user_id'] = True
    
    await query.edit_message_text(
        "✅ **Unban User**\n\n"
        "Send the user ID you want to unban:\n"
        "(Must be numeric ID)\n\n"
        "You can get banned users list from '📋 Banned List'",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="admin_ban_panel")]])
    )

async def handle_admin_banned_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of banned users"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Unauthorized.")
        return
    
    if not data_manager.banned_users:
        await query.edit_message_text(
            "✅ **No banned accounts currently**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="admin_ban_panel")]])
        )
        return
    
    message = "🚫 **Banned Users List**\n\n"
    for i, user_id in enumerate(data_manager.banned_users, 1):
        message += f"{i}. `{user_id}`\n"
    
    message += f"\n**Total:** {len(data_manager.banned_users)} banned users"
    
    await query.edit_message_text(
        message[:4000],
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="admin_ban_panel")]])
    )

async def handle_admin_user_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin input for user ID (ban/unban)"""
    admin = update.effective_user
    
    if not is_admin(admin.id):
        return
    
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid ID. Must be a number.\n"
            "Try again or click '↩️ Back'.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="admin_ban_panel")]])
        )
        return
    
    # Handle ban
    if context.user_data.get('awaiting_ban_user_id'):
        context.user_data.pop('awaiting_ban_user_id', None)
        
        if user_id in ADMIN_CHAT_IDS:
            await update.message.reply_text("❌ Cannot ban an admin.")
        elif data_manager.is_banned(user_id):
            await update.message.reply_text(f"⚠️ User `{user_id}` is already banned.")
        else:
            data_manager.ban_user(user_id)
            
            # Cancel any active orders for this user
            if user_id in data_manager.user_orders:
                data_manager.update_order_status(user_id, OrderStatus.CANCELLED)
            
            await update.message.reply_text(
                f"✅ **User banned successfully**\n\n"
                f"User ID: `{user_id}`\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Any active orders for this user have been cancelled.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="admin_ban_panel")]])
            )
    
    # Handle unban
    elif context.user_data.get('awaiting_unban_user_id'):
        context.user_data.pop('awaiting_unban_user_id', None)
        
        if not data_manager.is_banned(user_id):
            await update.message.reply_text(f"⚠️ User `{user_id}` is not banned.")
        else:
            data_manager.unban_user(user_id)
            await update.message.reply_text(
                f"✅ **User unbanned successfully**\n\n"
                f"User ID: `{user_id}`\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="admin_ban_panel")]])
            )

async def handle_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Go back to admin main menu"""
    query = update.callback_query
    await query.answer()
    
    # Clear any input states
    context.user_data.pop('awaiting_ban_user_id', None)
    context.user_data.pop('awaiting_unban_user_id', None)
    
    await query.edit_message_text(
        WELCOME_ADMIN,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_admin_main_keyboard()
    )

async def handle_admin_user_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch to user mode"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    # Clear any terminal state orders
    if user.id in data_manager.user_orders and data_manager.user_orders[user.id].status in [
        OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.COMPLETED
    ]:
        data_manager.delete_order(user.id)
    
    # Check if user can create new order
    can_create, reason = can_create_order(user.id)
    if not can_create:
        keyboard = [[InlineKeyboardButton("❌ Cancel Order", callback_data="cancel_order")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⚠️ **Order Conflict**\n\n{reason}\n\nYou can cancel your current order below.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return
    
    await query.edit_message_text(
        WELCOME_USER,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_product_keyboard()
    )

async def handle_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user start from callback"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    # Clear any terminal state orders
    if user.id in data_manager.user_orders and data_manager.user_orders[user.id].status in [
        OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.COMPLETED
    ]:
        data_manager.delete_order(user.id)
    
    # Check if user can create new order
    can_create, reason = can_create_order(user.id)
    if not can_create:
        keyboard = [[InlineKeyboardButton("❌ Cancel Order", callback_data="cancel_order")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⚠️ **Order Conflict**\n\n{reason}\n\nYou can cancel your current order below.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return
    
    await query.edit_message_text(
        WELCOME_USER,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_product_keyboard()
    )

# ==================== ADDITIONAL COMMANDS ====================
async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user ID"""
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 **Your ID:** `{user.id}`\n"
        f"👤 **Username:** @{user.username or 'None'}\n"
        f"📛 **Name:** {user.first_name or ''} {user.last_name or ''}",
        parse_mode=ParseMode.MARKDOWN
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics for admin"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    stats = data_manager.get_stats()
    
    message = (
        "📊 **Bot Statistics**\n\n"
        f"**Total Orders:** {stats['total_orders']}\n"
        f"**Completed:** {stats['completed']}\n"
        f"**Cancelled:** {stats['cancelled']}\n"
        f"**Pending:** {stats['pending']}\n"
        f"**Currently Active:** {stats['active']}\n"
        f"**Banned Users:** {stats['banned_users']}\n\n"
        f"**Data Saved:** Yes"
    )
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

# ==================== FIXED HANDLERS ====================
async def handle_direct_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle direct cancel button clicks"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    await handle_cancel_confirmation(update, context)

async def handle_unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown callback queries"""
    query = update.callback_query
    await query.answer("⚠️ Unknown action. Please use the buttons provided.", show_alert=False)
    
    user = update.effective_user
    if user.id in data_manager.user_orders:
        order = data_manager.user_orders[user.id]
        
        if order.status == OrderStatus.INIT:
            await query.edit_message_text(
                WELCOME_USER,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_product_keyboard()
            )
        elif order.status == OrderStatus.AWAIT_PAYMENT:
            network_type = order.network.replace("USDT_", "")
            wallet_address = WALLETS.get(order.network, "")
            
            instructions = PAYMENT_INSTRUCTIONS.format(
                wallet=wallet_address,
                amount=order.amount,
                network=network_type
            )
            
            await query.edit_message_text(
                instructions,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_payment_keyboard()
            )
    else:
        await query.edit_message_text(
            "⚠️ **Session expired**\n\nPlease start over with /start",
            parse_mode=ParseMode.MARKDOWN
        )

# ==================== ERROR HANDLER ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler"""
    logger.error(f"Exception: {context.error}", exc_info=context.error)
    
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ An error occurred. Please try again."
            )
    except:
        pass

# ==================== MAIN APPLICATION ====================
def main() -> None:
    """Initialize and run the bot"""
    
    # Validate configuration
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Set BOT_TOKEN in configuration")
        exit(1)
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Load existing data
    data_manager.load_data()
    
    # ===== USER HANDLERS =====
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("cancel", handle_cancel_confirmation))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(handle_product_selection, pattern=r"^product_"))
    application.add_handler(CallbackQueryHandler(handle_network_selection, pattern=r"^(network_|back_to_products|cancel_order)"))
    application.add_handler(CallbackQueryHandler(handle_payment_help, pattern=r"^payment_help$"))
    application.add_handler(CallbackQueryHandler(handle_upload_screenshot, pattern=r"^upload_screenshot$"))
    application.add_handler(CallbackQueryHandler(handle_cancel_action, pattern=r"^(confirm_cancel|keep_order)$"))
    application.add_handler(CallbackQueryHandler(handle_direct_cancel, pattern=r"^cancel_order$"))
    application.add_handler(CallbackQueryHandler(handle_user_start, pattern=r"^user_start$"))
    
    # Admin callback handlers
    application.add_handler(CallbackQueryHandler(handle_admin_decision, pattern=r"^admin_(accept|reject)_"))
    application.add_handler(CallbackQueryHandler(handle_admin_pending, pattern=r"^admin_pending$"))
    application.add_handler(CallbackQueryHandler(handle_admin_ban_panel, pattern=r"^admin_ban_panel$"))
    application.add_handler(CallbackQueryHandler(handle_admin_ban_user, pattern=r"^admin_ban_user$"))
    application.add_handler(CallbackQueryHandler(handle_admin_unban_user, pattern=r"^admin_unban_user$"))
    application.add_handler(CallbackQueryHandler(handle_admin_banned_list, pattern=r"^admin_banned_list$"))
    application.add_handler(CallbackQueryHandler(handle_admin_back, pattern=r"^admin_back$"))
    application.add_handler(CallbackQueryHandler(handle_admin_user_mode, pattern=r"^admin_user_mode$"))
    
    # Unknown callback handler (catch-all)
    application.add_handler(CallbackQueryHandler(handle_unknown_callback))
    
    # Message handlers
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & 
        filters.User(ADMIN_CHAT_IDS),
        handle_admin_code_submission
    ))
    
    # Admin user ID input handler
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & 
        filters.User(ADMIN_CHAT_IDS),
        handle_admin_user_id_input
    ))
    
    application.add_handler(MessageHandler(
        filters.PHOTO & filters.ChatType.PRIVATE,
        handle_screenshot
    ))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    print("\n" + "="*60)
    print("✨ SUBSCRIPTION BOT - ENHANCED VERSION ✨")
    print("="*60)
    print("\n✅ ENHANCED FEATURES:")
    print("• Automatic data persistence ✓")
    print("• User ban/unban system ✓")
    print("• Simplified admin panel (pending orders + ban/unban) ✓")
    print("• Banned users list ✓")
    print("• /id command to show user ID ✓")
    print("• /stats command to show statistics ✓")
    print("• Improved user interface ✓")
    print("\n🤖 Starting bot...")
    print("="*60 + "\n")
    
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
        # Save data before exit
        data_manager.save_data()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        print(f"💥 Bot crashed: {e}")
        # Save data before crash
        data_manager.save_data()

if __name__ == "__main__":
    main()
