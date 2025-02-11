import ast
import asyncio
import datetime
import json
import math
import re
import secrets
import string

from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, WebAppInfo, InlineKeyboardMarkup, \
    InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove
from geopy.distance import geodesic
from geopy.exc import GeopyError
from geopy.geocoders import Nominatim
from sqlalchemy import Column, Integer, String, ForeignKey, select, DateTime, Float
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from keep_alive import keep_alive


def generate_token(length=16):
    return ''.join(secrets.choice(string.ascii_letters) for _ in range(length))


TOKEN = "7874928619:AAHdmduqLLfYUQF-Tgw_aXYcMp41X3maLTc"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# DATABASE_URL = "sqlite+aiosqlite:///database.sqlite3"
# DATABASE_URL = "postgresql+asyncpg://smart_food_user:IAb8lvnJBTGbiJBpol4Yti6k5yhRuC2o@dpg-cu8i7t8gph6c73cpshe0-a.oregon-postgres.render.com/smart_food"
engine = create_async_engine(DATABASE_URL, future=True)
async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Products(Base):
    __tablename__ = "products_product"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    price = Column(String)


class User(Base):
    __tablename__ = "User_user"
    id = Column(Integer, primary_key=True)
    tg_id = Column(String)
    token = Column(String)
    real_name = Column(String, nullable=True)
    role = Column(String, default="User")
    phone_number = Column(String, nullable=True)


class Locations_user(Base):
    __tablename__ = "products_location_user"
    id = Column(Integer, primary_key=True)
    longitude = Column(Float)
    latitude = Column(Float)
    address = Column(String)
    user_id = Column(Integer, ForeignKey("User_user.id"))


class Sale(Base):
    __tablename__ = "products_sale"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    expired_at = Column(String)


class state(Base):
    __tablename__ = "products_state_for_state"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("User_user.id"))
    data = Column(String)


class Products_list(Base):
    __tablename__ = "products_productquantity"
    id = Column(Integer, primary_key=True)
    product = Column(Integer, ForeignKey('products_product.id'))
    quantity = Column(Integer)


class Basket(Base):
    __tablename__ = "products_checkout"

    id = Column(Integer, primary_key=True)
    latitude = Column(Float)
    longitude = Column(Float)
    user = Column(Integer, ForeignKey('User_user.id'))
    created_at = Column(DateTime, default=datetime.datetime.now)
    delivery_cost = Column(Float)
    delivery_option = Column(String, default='')
    total_price = Column(Float)
    address = Column(String)
    products = Column(String)


class Orders(Base):
    __tablename__ = "products_order"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('User_user.id'))
    basket_id = Column(Integer, ForeignKey('products_checkout.id'))
    status = Column(String, default='Not checked')
    created_at = Column(DateTime, default=datetime.datetime.now)


class OrderState(StatesGroup):
    OPTION = State()
    NAME = State()
    DELIVERY_COST = State()
    IDS = State()
    ID = State()
    LOCATION = State()
    LOCATION_CONFIRMED = State()
    ADDRESS = State()
    PRODUCTS = State()
    PHONE = State()
    CONFIRM = State()


class RedirectState(StatesGroup):
    menu = State()


async def get_product_quantity(id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Products_list).where(Products_list.id == int(id)))
            result = data.scalar_one_or_none()
            if result:
                return result.product


async def get_product_cost(id_product_list):
    async with async_session() as session:
        async with session.begin():
            id = await get_product_quantity(id_product_list)
            data = await session.execute(select(Products).where(Products.id == int((id))))
            result = data.scalar_one_or_none()
            if result:
                return result.name, result.price
            return None


async def get_user_role(role):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(User.tg_id).where(User.role == role))
            result = data.scalars().all()
            if result:
                return result


async def get_price(id):
    async with async_session() as session:
        data = await session.execute(select(Products).where(Products.id == int(id)))
        result = data.scalar()
        return result.name, result.price


async def update_product_list(id, quantity, product_id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Products_list).where(Products_list.id == int(id)))
            result = data.scalar_one_or_none()
            if result:
                result.quantity = quantity
                result.product_id = product_id
                await session.commit()
                return result.id
            return None


async def get_uniqe_token(token):
    """Ensure the generated token is unique."""
    while True:
        async with async_session() as session:
            async with session.begin():
                data = await session.execute(select(User).where(User.token == token))
                result = data.scalar_one_or_none()
                if not result:
                    return token  # Token is unique, return it
        token = generate_token()


async def get_user_id(tg_id):
    """Get user ID by Telegram ID or create a new user."""
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(User).where(User.tg_id == str(tg_id)))
            result = data.scalar_one_or_none()
            if result:
                return result.id  # Return existing user ID


async def get_user_data_all(tg_id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(User).where(User.tg_id == str(tg_id)))
            result = data.scalar_one_or_none()
            if result:
                return result


async def get_user_strict(tg_id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(User).where(User.tg_id == str(tg_id)))
            result = data.scalar_one_or_none()

            if result:
                return True
            else:
                return False


async def create_location(address, longitude, latitude, user_id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Locations_user).where(Locations_user.user_id == user_id))
            result = data.scalar_one_or_none()
            if result:
                result.address = address
                result.longitude = longitude
                result.latitude = latitude
                return
            new = Locations_user(user_id=user_id, address=address, longitude=longitude, latitude=latitude)
            session.add(new)
            await session.flush()
            await session.commit()
            return


async def get_locations(user_id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Locations_user).where(Locations_user.user_id == user_id))
            result = data.scalar_one_or_none()
            if result:
                return result


async def get_user_phone(tg_id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(User.phone_number).where(User.tg_id == tg_id))
            result = data.scalar()
            if result:
                return result


async def get_user_phone_number_by_id(id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(User.phone_number).where(User.id == id))
            result = data.scalar_one_or_none()
            if result:
                return result


async def update_phone_number(phone_number, tg_id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(User).where(User.tg_id == tg_id))
            result = data.scalar()
            if result:
                result.phone_number = phone_number
                await session.flush()
                await session.commit()
                return


async def create_product_list(quantity, product_id):
    async with async_session() as session:
        async with session.begin():
            new_product = Products_list(quantity=int(quantity), product=int(product_id))
            session.add(new_product)
            await session.flush()
    return new_product.id


async def get_product_list(id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Products_list).where(Products_list.id == id))
            result = data.scalars().first()
            if result:
                return result


async def create_user_strict(tg_id: int, phone_number: str, real_name: str) -> None:
    async with async_session() as session:
        async with session.begin():
            token = await get_uniqe_token(generate_token())
            phone_number = phone_number[1:] if phone_number[0] == '+' else phone_number
            new_user = User(
                tg_id=str(tg_id),  # Ensure tg_id is stored as a string
                phone_number=str(phone_number),  # Ensure phone_number is a string
                real_name=real_name,
                token=token  # Assign the unique token
            )
            session.add(new_user)
            await session.flush()
            await session.commit()


async def delete_product_list(id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Products_list).where(Products_list.id == id))
            result = data.scalars().first()
            if result:
                await session.delete(result)
                return


async def get_user_token(tg_id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(User).where(User.tg_id == str(tg_id)))
            result = data.scalar_one_or_none()
            if result:
                return result.token


async def create():
    async with async_session() as session:
        async with session.begin():
            sale = Sale(name="Xot dog", description="Discount", expired_at="2025-02-01")
            session.add(sale)
            await session.commit()


async def create_basket(user_id, product_list, address, latitude, longitude, delivery_cost, total_price,
                        delivery_option):
    async with async_session() as session:
        async with session.begin():
            new_basket = Basket(user=user_id, products=json.dumps([]), address=address, latitude=latitude,
                                longitude=longitude, total_price=total_price, delivery_cost=delivery_cost,
                                delivery_option=delivery_option)
            session.add(new_basket)
            await session.flush()
            new_basket.products = json.dumps(product_list)  # Store as JSON

            await session.commit()
            return new_basket.id


async def create_state(user_id, data):
    async with async_session() as session:
        async with session.begin():
            exist = await session.execute(select(state).where(state.user_id == user_id))
            result = exist.scalar_one_or_none()
            if result:
                valid_products = []
                for product_id_str in data:
                    valid_products.append(product_id_str)
                if valid_products:
                    result.data = json.dumps(valid_products)
                await session.commit()
                return
            new_basket = state(user_id=user_id, data=json.dumps([]))
            session.add(new_basket)
            await session.flush()
            valid_products = []
            for product_id_str in data:
                valid_products.append(product_id_str)

            if valid_products:
                new_basket.data = json.dumps(valid_products)  # Store as JSON

            await session.commit()
            return new_basket.id


async def get_basket_id(id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Orders.basket_id).where(Orders.id == id))
            result = data.scalar_one_or_none()
            if result:
                return result


async def get_basket_data(id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Basket).where(Basket.id == id))
            result = data.scalar_one_or_none()
            if result:
                return result
            return None


async def get_basket_products(id):
    async with async_session() as session:
        async with session.begin():
            basket_id = await get_basket_id(id)
            data = await session.execute(select(Basket).where(Basket.id == basket_id))
            result = data.scalar_one_or_none()
            if result:
                return result
            return None


async def get_state(user_id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(state).where(state.user_id == user_id))
            result = data.scalar_one_or_none()
            if result:
                return result.data
            return


async def create_order(user_id, basket_id):
    async with async_session() as session:
        async with session.begin():
            new_order = Orders(user_id=user_id, basket_id=basket_id)
            session.add(new_order)
            await session.commit()
            await session.flush()
            return new_order.id


async def get_order(basket_id):
    async with async_session() as session:
        async with session.begin():
            new_order = await session.execute(select(Orders).where(Orders.basket_id == int(basket_id)))
            order = new_order.scalar_one_or_none()
            if order:
                return order
            else:
                return


async def delete_basket(id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Basket).where(Basket.id == int(id)))
            result = data.scalar_one_or_none()
            if result:
                await session.delete(result)
            return


async def get_sales():
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(Sale))
            sales = result.scalars().all()

            today = datetime.date.today()
            valid_sales = []  # Collect valid sales
            for sale in sales:
                expired_at = datetime.datetime.strptime(sale.expired_at, "%Y-%m-%d").date()

                if expired_at > today:
                    valid_sales.append(sale)  # Add non-expired sales to list

            return valid_sales


async def get_my_products_db(user_id):
    async with async_session() as session:
        async with session.begin():
            user = await session.execute(select(User.id).where(User.tg_id == user_id))
            user_ids = user.scalar()
            if user_ids:
                product = await session.execute(select(Basket).where(Basket.user == int(user_ids)))
                products = product.scalars().all()
                return products


async def update_order_status(id, status):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Orders).where(Orders.id == int(id)))
            result = data.scalar_one_or_none()
            if result:
                result.status = status
                return


async def update_order_is_cooked(id, status):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Orders).where(Orders.id == int(id)))
            result = data.scalar_one_or_none()
            if result:
                result.is_cooked = status
                return


async def update_order_is_delivered(id, status):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(Orders).where(Orders.id == int(id)))
            result = data.scalar_one_or_none()
            if result:
                result.is_delivered = status
                return


async def get_user_tg_id(user_id):
    async with async_session() as session:
        async with session.begin():
            data = await session.execute(select(User).where(User.id == user_id))
            result = data.scalar_one_or_none()
            if result:
                return result.tg_id


back = '🔙 Ortga'


def menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text='🛍 Xarid qilish'),
         KeyboardButton(text="📦 Mening xaridlarim")],
        [KeyboardButton(text="🎉 Aksiyalar")]
    ], resize_keyboard=True, one_time_keyboard=False)


def send_to_checker(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='✅ Tasdiqlash', callback_data=f'data_check.{order_id}'),
            InlineKeyboardButton(text='❌ Bekor qilish', callback_data=f'data_cross.{order_id}')
        ]
    ])
    return keyboard


def delivery_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚚 Yetkazib berish"),
         KeyboardButton(text="🏃 Olib ketish")],
        [KeyboardButton(text=back)]
    ], resize_keyboard=True)


async def location_request():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📍 Manzilni yuborish", request_location=True)],
        [KeyboardButton(text=back)]
    ], resize_keyboard=True, one_time_keyboard=True)


def send_phone():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Telefon raqamni yuborish", request_contact=True)],
            [KeyboardButton(text="🔙 Orqaga")]  # Assuming "back" is meant to be "🔙 Orqaga"
        ],
        resize_keyboard=True
    )


async def open_miniapp(tg_id, message_id):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Mahsulotni tanlash",
                            web_app=WebAppInfo(
                                url=f'https://smart-food-tgj7.onrender.com?token={await get_user_token(tg_id)}&message_id={message_id}')), ],
            [KeyboardButton(text=back)]
        ],
        resize_keyboard=True
    )


async def edit2(array, tg_id, message_id):
    data = ''
    for j in array:
        id = j.split('.')[3]
        # id = 26
        count = j.split('.')[2]
        # count = 12
        data += f"data-item-id={id}&count={count}&"
    data += f"token={await get_user_token(tg_id)}&message_id={int(message_id)+2}"
    print(data)
    inline = [
        [
            InlineKeyboardButton(
                text='🔄 Mahsulot tanlash',
                web_app=WebAppInfo(url=f'https://smart-food-tgj7.onrender.com/public?{data}')
            )
        ],
        [
            InlineKeyboardButton(
                text='🗑 Savatni tozalash',
                callback_data='clear_products'
            )
        ]
    ]
    a = []
    for i in array:
        product_list_id = i.split('.')[0]
        name = i.split('.')[1]
        callback_edit_minus = f"edit_{product_list_id}.minus"
        callback_edit_plus = f"edit_{product_list_id}.plus"
        a.append(product_list_id)
        inline.append([
            InlineKeyboardButton(text='➖', callback_data=callback_edit_minus),
            InlineKeyboardButton(text=name, callback_data='a'),
            InlineKeyboardButton(text='➕', callback_data=callback_edit_plus),
        ])

    inline.append([InlineKeyboardButton(text='✅ Tasdiqlash', callback_data=f'confirm_edit.{a}')])
    inline.append([InlineKeyboardButton(text='⬅️ Orqaga', callback_data='back')])

    return InlineKeyboardMarkup(inline_keyboard=inline)


def confirm_edit_send():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='✅ Tasdiqlash', callback_data='confirm_send_tick'),
             InlineKeyboardButton(text='❌ Bekor qilish', callback_data='confirm_send_cross')],
        ]
    )


def is_valid_uzb_number(phone: str) -> bool:
    return bool(re.fullmatch(r"\+?998\d{9}", phone))


def has_numbers(text: str) -> bool:
    return any(char.isdigit() for char in text)


def check_chef(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Tayyor', callback_data=f'chef_check.{order_id}'),
         InlineKeyboardButton(text='❌ Bekor qilish', callback_data=f'chef_cross.{order_id}')],
    ])


def delivery_check(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Tastiqlash', callback_data=f'delivery_check.{order_id}'),
         InlineKeyboardButton(text='❌ Buyurtmani bekor qilish', callback_data=f'delivery_cross.{order_id}')],
    ])


@dp.message(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    user = await get_user_strict(tg_id=int(message.from_user.id))

    if not user:
        await message.answer(
            "📱 Iltimos, telefon raqamingizni pastdagi tugma orqali yuboring yoki qo'lda 998 bilan boshlang. 📞\n\n"
            "❗️ Raqam faqat Oʻzbekiston kodi (998) bilan boshlanishi kerak.",
            reply_markup=send_phone()
        )
        await state.set_state(OrderState.PHONE)
        return

    await message.answer(text="🏠 Menyu ", reply_markup=menu())
    await state.clear()


@dp.message(RedirectState.menu)
async def menu_State(message: types.Message, state: FSMContext):
    if message.text == back:
        await message.answer(text='🏘 Menu', reply_markup=menu())
        await state.clear()
        return


@dp.message(OrderState.PHONE)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        await message.answer("✍️ Iltimos, to‘liq ism-sharifingizni kiriting (F.I.O).",
                             reply_markup=ReplyKeyboardRemove())
        await state.set_state(OrderState.NAME)
        await state.update_data(PHONE=message.contact.phone_number)
        return
    if is_valid_uzb_number(message.text):
        await message.answer("✍️ Iltimos, to‘liq ism-sharifingizni kiriting (F.I.O).",
                             reply_markup=ReplyKeyboardRemove())
        await state.set_state(OrderState.NAME)
        await state.update_data(PHONE=message.text)
        return
    await message.answer(
        text="📱 Iltimos, telefon raqamingizni pastdagi tugma orqali yuboring yoki qo'lda 998 bilan boshlang. 📞\n\n"
             "❗️ Raqam faqat Oʻzbekiston kodi (998) bilan boshlanishi kerak.",
        reply_markup=send_phone()
    )
    await state.set_state(OrderState.PHONE)
    return


@dp.message(OrderState.NAME)
async def process_name(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("✍️ Iltimos, to‘liq ism-sharifingizni kiriting (F.I.O).",
                             reply_markup=ReplyKeyboardRemove())
        await state.set_state(OrderState.NAME)
        return
    if not has_numbers(message.text):
        await message.answer(text='🏘 Menu', reply_markup=menu())
        data = await state.get_data()
        phone = data['PHONE']
        name = message.text
        await create_user_strict(tg_id=str(message.from_user.id), phone_number=phone, real_name=name)
        await state.clear()
        return
    await message.answer("✍️ Iltimos, to‘liq ism-sharifingizni kiriting (F.I.O).", reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderState.NAME)
    return


@dp.message(F.text == '🛍 Xarid qilish')
async def Buy_message(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(text="🚚 Yetkazib berish turini tanlang", reply_markup=delivery_menu())
    await state.set_state(OrderState.OPTION)
    return


@dp.message(OrderState.OPTION)
async def delivery_options(message: types.Message, state: FSMContext):
    if message.text == back:
        await message.answer(text="🏠 Menyu", reply_markup=menu())
        await state.clear()
        return
    await message.answer(text="📍 Manzilingizni yuboring",
                         reply_markup=await location_request())
    await state.update_data(OPTION=message.text)
    await state.set_state(OrderState.LOCATION)
    return


@dp.message(OrderState.LOCATION)
async def process_location(message: types.Message, state: FSMContext):
    if message.text == back:
        await message.answer(text="🚚 Yetkazib berish turini tanlang", reply_markup=delivery_menu())
        await state.set_state(OrderState.OPTION)
        return
    if message.text == (await get_locations(await get_user_id(message.from_user.id))).address if await get_locations(
            await get_user_id(message.from_user.id)) is not None else False:
        location_user = await get_locations(await get_user_id(message.from_user.id))
        user_location = f"{location_user.latitude}, {location_user.longitude}"
        try:
            geolocator = Nominatim(user_agent="xusanboyman")
            location = geolocator.reverse(user_location, language="uz")
            address = location.address if location else "Noma'lum manzil"
        except GeopyError as e:
            address = "Geokodlash xatosi tufayli manzil aniqlanmadi."

        shop_coords = (40.503687, 72.338752)
        distance_km = geodesic(shop_coords, user_location).km

        delivery_cost = 0 if distance_km <= 6 else math.ceil((distance_km - 6) * 1000)

        location_menu = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="📍 Manzilni qayta yuborish", request_location=True),
             KeyboardButton(text="✅ Tasdiqlash")],
            [KeyboardButton(text="📌 Manzilni saqlash"), KeyboardButton(text=back)]
        ], resize_keyboard=True, one_time_keyboard=True)

        await state.set_state(OrderState.LOCATION_CONFIRMED)
        await message.answer(f"📍 Manzilingiz: {address} \nManzilni tasdiqlaysizmi?", reply_markup=location_menu)
        await state.update_data(LOCATION=user_location, DELIVERY_COST=delivery_cost, ADDRESS=address)
        return
    if not message.location:
        await message.answer(text="📍 Manzilingizni yuboring",
                             reply_markup=await location_request())
        await state.update_data(OPTION=message.text)
        await state.set_state(OrderState.OPTION)
        return
    user_location = (message.location.latitude, message.location.longitude)
    try:
        geolocator = Nominatim(user_agent="xusanboyman")
        location = geolocator.reverse(user_location, language="uz")
        address = location.address if location else "Noma'lum manzil"
    except GeopyError as e:
        address = "Geokodlash xatosi tufayli manzil aniqlanmadi."

    shop_coords = (40.503687, 72.338752)
    distance_km = geodesic(shop_coords, user_location).km

    delivery_cost = 0 if distance_km <= 6 else math.ceil((distance_km - 6) * 1000)

    location_menu = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📍 Manzilni qayta yuborish", request_location=True)],
        [KeyboardButton(text="✅ Tasdiqlash")],
        [KeyboardButton(text=back)]
    ], resize_keyboard=True, one_time_keyboard=True)

    await state.set_state(OrderState.LOCATION_CONFIRMED)
    await message.answer(f"📍 Manzilingiz: {address} \nManzilni tasdiqlaysizmi?", reply_markup=location_menu)
    await state.update_data(LOCATION=user_location, DELIVERY_COST=delivery_cost, ADDRESS=address)
    return


@dp.message(OrderState.LOCATION_CONFIRMED)
async def process_location_confirmed(message: Message, state: FSMContext):
    print(message.message_id)
    if message.text == back:
        await state.set_state(OrderState.OPTION)
        await message.answer(text="🚚 Yetkazib berish turini tanlang", reply_markup=delivery_menu())
        return
    if message.text == '✅ Tasdiqlash':
        await message.answer(text="🛒 Mahsulot tanlash uchun mini ilovani oching",
                             reply_markup=await open_miniapp(message.from_user.id, message_id=message.message_id))
        return
    if message.text == '📌 Manzilni saqlash':
        data = await state.get_data()
        location = data['LOCATION']
        address = data['ADDRESS']
        location_menu = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="📍 Manzilni qayta yuborish", request_location=True),
             KeyboardButton(text="✅ Tasdiqlash")],
            [KeyboardButton(text="📌 Manzilni saqlash"), KeyboardButton(text=back)]
        ], resize_keyboard=True, one_time_keyboard=True)
        await create_location(latitude=location[0], longitude=location[1], address=address,
                              user_id=await get_user_id(message.from_user.id))
        await message.answer(text=f"{address} muaffaqiyatli saqlandi")
        await message.answer('📍 Manzilnigizni tastiqlaysizmi ?', reply_markup=location_menu)
    if message.location:
        user_location = (message.location.latitude, message.location.longitude)
        geolocator = Nominatim(user_agent="xusanboyman")
        location = geolocator.reverse(user_location, language="uz")
        address = location.address if location else "Noma'lum manzil"
        shop_coords = (40.503687, 72.338752)
        distance_km = geodesic(shop_coords, user_location).km

        delivery_cost = 0 if distance_km <= 6 else math.ceil((distance_km - 6) * 1000)

        location_menu = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="📍 Manzilni qayta yuborish", request_location=True),
             KeyboardButton(text="✅ Tasdiqlash")],
            [KeyboardButton(text="📌 Manzilni saqlash"), KeyboardButton(text=back)]
        ], resize_keyboard=True, one_time_keyboard=True)

        await state.set_state(OrderState.LOCATION_CONFIRMED)
        await message.answer(f"📍 Manzilingiz: {address} \nManzilni tasdiqlaysizmi?", reply_markup=location_menu)
        await state.update_data(LOCATION=user_location, DELIVERY_COST=delivery_cost, ADDRESS=address)
        return


# @dp.message(F.text == 'a')
async def get_web(data, user_id, message_id):  # 'state' should be an instance of FSMContext
    array = []
    # data = ['1:3', '2:5']
    text = ''
    total = 0
    new_arr = []
    formated_data = ast.literal_eval(data)
    for i in formated_data:
        quantity = i.split(':')[1]
        id = i.split(':')[0]
        product = await get_product_cost(id)
        product_list_id = await create_product_list(quantity=quantity, product_id=id)
        cost = product[1]
        pr_id = product_list_id
        name = product[0]
        new_arr.append(f'{id}:{pr_id}.{quantity}.{name}')
        price = int(quantity) * int(cost)
        text += f"{name.capitalize()} x {quantity} = {price}\n"
        array.append(f"{pr_id}.{name}.{quantity}.{id}")
        total += price
    await create_state(user_id=user_id, data=new_arr)
    text += f"\nUmumiy narx: {total}\n"
    try:
        await bot.delete_message(message_id=message_id, chat_id=user_id)
        await bot.send_message(chat_id=user_id, text=text,
                               reply_markup=await edit2(array=array, tg_id=user_id, message_id=message_id + 1))
    except TelegramBadRequest as e:
        print(e)
        await bot.send_message(chat_id=user_id, text=text,
                               reply_markup=await edit2(array=array, tg_id=user_id, message_id=message_id))


@dp.callback_query(F.data.startswith('edit_'))
async def handle_edit(call: CallbackQuery, state: FSMContext):
    data = call.data.split('_')[1]
    product_list_id = call.data.split('.')[0].split('_')[1]
    state_db = await get_state(user_id=call.from_user.id)
    converted_list = ast.literal_eval(state_db)
    await state.update_data(IDS=converted_list)
    action = data.split('.')[1]

    new_arr = []
    total = 0
    text = ''
    send_array = []
    pool = []
    for i in converted_list:
        n = i.split(':')[1]
        id = i.split(':')[0]
        product_list_id_state = i.split(':')[1].split('.')[0]
        quantity = int(n.split('.')[1])
        name = i.split('.')[2].capitalize()
        product_list_id_state = str(product_list_id_state).strip()
        pool.append(product_list_id_state)
        if product_list_id_state == product_list_id:
            quantity = max(0, quantity + 1 if action == 'plus' else quantity - 1)  # Allow quantity to go to 0
            if quantity == 0:
                await delete_product_list(product_list_id)
                continue
            else:
                product = await get_product_cost(id)
                cost = product[1]
                price = quantity * int(cost)
                await update_product_list(quantity=quantity, id=product_list_id, product_id=id)
                new_arr.append(f'{id}:{product_list_id}.{quantity}.{name}')
                text += f"{name} x {quantity} = {price}\n"
                send_array.append(f"{product_list_id}.{name}.{quantity}.{id}")
                total += price
        else:
            product = await get_product_cost(id)
            cost = product[1]
            price = quantity * int(cost)
            new_arr.append(f'{id}:{product_list_id_state}.{quantity}.{name}')
            text += f"{name.capitalize()} x {quantity} = {price}\n"
            send_array.append(f"{product_list_id_state}.{name}.{quantity}.{id}")
            total += price

    text += f"\nUmumiy narx: {total}\n"
    new_reply_markup = await edit2(array=send_array, tg_id=call.from_user.id,
                                   message_id=call.message.message_id)  # Generate the new keyboard

    # Check if the message content or reply markup has changed
    current_text = call.message.text.strip()
    current_markup = str(call.message.reply_markup)

    is_text_changed = current_text != text.strip()
    is_markup_changed = current_markup != str(new_reply_markup)

    if is_text_changed or is_markup_changed:
        await state.update_data(ID=pool)
        await state.update_data(IDS=new_arr)
        await create_state(user_id=call.from_user.id, data=new_arr)
        if len(send_array) != 0:
            await call.message.edit_text(text=text, reply_markup=new_reply_markup)
        else:
            await call.message.delete()
            await call.message.answer(text=f"Sizda hech qanday mahsulot yoq davom ettirush uchun mahsulotni tanlang",
                                      reply_markup=await open_miniapp(call.from_user.id,
                                                                      message_id=call.message.message_id))
    else:
        await call.answer("No changes detected.", show_alert=True)


@dp.callback_query(F.data.startswith('confirm_edit'))
async def callback_confirm(call: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        state_db = await get_state(user_id=call.from_user.id)
        converted_list = ast.literal_eval(state_db)
        await state.update_data(IDS=converted_list)
        location = data.get("LOCATION")
        delivery_cost = data.get("DELIVERY_COST")
        delivery_option = data.get("OPTION").capitalize()
        text = ''
        total = int(delivery_cost)
        address = data.get("ADDRESS")
        latitude, longitude = eval(str(location))
        user_id = await get_user_id(call.from_user.id)
        products = []
        for i in converted_list:
            name = i.split(':')[1].split('.')[2].capitalize()
            quantity = int(i.split(':')[1].split('.')[1])
            products.append(int(i.split(':')[1].split('.')[0]))
            id = i.split(':')[0]
            product = await get_product_cost(id)
            cost = product[1]
            price = quantity * int(cost)
            text += f'{name} x {quantity} = {price}\n'
            total += price
        id_basket = await create_basket(user_id=user_id, product_list=products, address=address,
                                        delivery_cost=delivery_cost, total_price=total, latitude=latitude,
                                        longitude=longitude, delivery_option=delivery_option)
        text += f"🚚 Yetkazib berish narxi: {delivery_cost}\n💰 Umumiy narx: {total}\n📦 Yetkazib berish turi: {delivery_option}\n📍 Yetkazib berish manzili: {address}"
        await call.message.edit_text(text=text, reply_markup=confirm_edit_send())
        await state.update_data(ID=id_basket)
    except:
        await call.message.answer(
            text='Muamo yuzaga chiqdi iltimos boshqattan urinib koring aks xolda @xusanboyman200 ga boglaning')
        await call.message.answer(text='🏠 Menu', reply_markup=menu())
        await call.message.delete()
        await state.clear()


@dp.callback_query(F.data.startswith('confirm_send_'))
async def callback_confirm_send(call: CallbackQuery, state: FSMContext):
    data = call.data.split('_')[2]
    if data == 'tick':
        data = await state.get_data()
        delivery_cost = data.get("DELIVERY_COST")
        Basket_id = data.get("ID")
        state_array = data.get('IDS')
        address = data.get("ADDRESS")
        delivery_option = data.get("OPTION").capitalize()
        user_id = await get_user_id(call.from_user.id)
        id_basket = await create_order(user_id=user_id, basket_id=Basket_id)
        text = ''
        total = int(delivery_cost)
        n = 0
        for i in state_array:
            n += 1
            name = i.split(':')[1].split('.')[2].capitalize()
            quantity = int(i.split(':')[1].split('.')[1])
            id = i.split(':')[0]
            product = await get_product_cost(id)
            cost = product[1]
            price = quantity * int(cost)
            text += f'{name} x {quantity} = {price}\n'
            total += price
        phone_number = await get_user_phone(call.from_user.id)
        user_name = (await get_user_data_all(call.from_user.id)).real_name
        text += f"🚛 Yetkazib berish narxi: {delivery_cost} so'm\n💵 Umumiy narx: {total} so'm\n🚚 Yetkazib berish turi: {delivery_option}\n📍 Manzil: {address}\n📞 Telefon raqami: {phone_number if str(phone_number)[0] == '+' else '+' + str(phone_number)}\n🧑‍💼 Xaridor ismi: {user_name}"
        await call.message.answer(text=text)
        Admins = await get_user_role('Admin')
        try:
            for i in Admins:
                await bot.send_message(
                    chat_id=i,
                    text=f"🛒 Buyurtma {id_basket}\n\n{text}\n\n",
                    reply_markup=send_to_checker(order_id=id_basket)
                )
        except:
            await call.message.answer(text="⚠️ Nimadir xato ketdi! Iltimos, qaytadan urinib ko'ring 🔄")
            await state.clear()
            return
        await call.message.answer(
            text=f"🛍 Buyurtma raqami: {id_basket}\n⏳ Buyurtmangiz tasdiqlangandan so'ng {math.ceil(n) * 30} - {math.ceil(n) * 30 / 2} daqiqa ichida yetkazib beriladi 🚀",
            reply_markup=menu())
        await call.message.delete()
        await state.clear()
        return
    elif data == 'cross':
        data = await state.get_data()
        basket_id = data.get("ID")
        await delete_basket(basket_id)
        await call.message.answer(text=f"🏠 Menyu", reply_markup=menu())
        await state.clear()
        await call.message.delete()
        return


@dp.callback_query(F.data.startswith('data_'))
async def confirm_user_data(call: CallbackQuery, state: FSMContext):
    data = call.data.split('_')[1]
    order_id = data.split('.')[1]
    if data.split('.')[0] == 'check':
        confirm = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Ha', callback_data=f'data2_check.{order_id}'),
             InlineKeyboardButton(text='❌ Yo\'q', callback_data=f'data2_cross.{order_id}')]])
        await call.message.edit_text(f'🛍 Siz  🆔 {order_id}\n  Tayyorlashga ruhsat berdingizmi?', reply_markup=confirm)
    else:
        confirm = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Ha', callback_data=f'data2_checkd.{order_id}'),
             InlineKeyboardButton(text='❌ Yo\'q', callback_data=f'data2_cross.{order_id}')]])
        await call.message.edit_text(f'🛍 Siz  🆔 {order_id}\n Bekor qilasizmi?', reply_markup=confirm)


@dp.callback_query(F.data.startswith('data2_'))
async def confirm_user_data(call: CallbackQuery, state: FSMContext):
    data = call.data.split('_')[1]
    order_id = data.split('.')[1]
    if data.split('.')[0] == 'check':
        await update_order_status(id=order_id, status='Mahsulot psihirilmoqda')
        await call.answer(text=f'Siz {order_id} li mahsulot ni tayyorlashga ruxsat berdingiz', show_alert=True)
        products = await get_basket_products(id=order_id)
        if products:
            formatted_products = json.loads(products.products)  # Parse the JSON string
            text = f'🥘 Buyurtma {order_id}\n\n'
            for product_id in formatted_products:
                product = await get_product_cost(product_id)
                if product:
                    product_name, product_price = product
                    product_quantity = await get_product_list(product_id)
                    if product_quantity:
                        text += f"{product_name.capitalize()} x {product_quantity.quantity} = {int(product_price) * int(product_quantity.quantity)}\n"

            try:
                for chef_id in await get_user_role('Chef'):
                    await bot.send_message(chat_id=chef_id, text=text, reply_markup=check_chef(order_id))
            except:
                await call.message.answer('Nimadir xato ketdi!')
        admins = await get_user_role('Admin')
        for admin in admins:
            await bot.delete_message(chat_id=admin, message_id=call.message.message_id)
            await call.answer('✅ Tastiqlandi')
    elif data.split('.')[0] == 'checkd':
        user = await get_basket_products(id=order_id)
        user_id = await get_user_tg_id(user.user)
        await bot.send_message(chat_id=user_id, text=f"❌ Buyurtmangiz ({order_id}) bekor qilindi.")
    else:
        basket_id = await get_basket_id(order_id)
        basket = await get_basket_data(basket_id)
        address = basket.address
        delivery_option = basket.delivery_option
        total = basket.total_price
        delivery_cost = basket.delivery_cost
        products = basket.products
        formated_products = ast.literal_eval(products)
        text = ''
        for i in formated_products:
            product_list_data = await get_product_list(i)
            quantity = product_list_data.quantity
            id = product_list_data.product
            product = await get_product_cost(id)
            cost = product[1]
            name = product[0]
            price = quantity * int(cost)
            text += f'{name} x {quantity} = {price}\n'
        basket = await get_basket_data(order_id)
        tg_id = await get_user_tg_id(basket.user)
        phone_number = await get_user_phone(tg_id)
        user_name = (await get_user_data_all(tg_id)).real_name
        text += f"🚛 Yetkazib berish narxi: {delivery_cost} so'm\n💵 Umumiy narx: {total} so'm\n🚚 Yetkazib berish turi: {delivery_option}\n📍 Manzil: {address}\n📞 Telefon raqami: {phone_number if str(phone_number)[0] == '+' else '+' + str(phone_number)}\n🧑‍💼 Xaridor ismi: {user_name}"
        reply_markup = send_to_checker(order_id=order_id)
        await bot.edit_message_text(chat_id=call.from_user.id, text=f"🛒 Buyurtma {order_id}\n\n{text}\n\n",
                                    message_id=call.message.message_id, reply_markup=reply_markup)
        return


@dp.callback_query(F.data.startswith('chef_'))
async def confirm_chef(call: CallbackQuery, state: FSMContext):
    data = call.data.split('_')[1].split('.')
    order_id = data[1]
    if data[0] == 'check':
        confirm = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Ha', callback_data=f'chef2_check.{order_id}'),
             InlineKeyboardButton(text='⬅️ Ortga ', callback_data=f"chef2_cross.{order_id}")]])
        await call.message.edit_text(text=f'Siz {order_id} ni tayyorlab boldingizmi?', reply_markup=confirm)
    else:
        confirm = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Ha', callback_data=f'chef2_checkd.{order_id}'),
             InlineKeyboardButton(text='⬅️ Ortga ', callback_data=f"chef2_cross.{order_id}")]])
        await call.message.edit_text(text=f'Siz {order_id} ni Bekor qilasizmi?', reply_markup=confirm)


@dp.callback_query(F.data.startswith('chef2_'))
async def confirm_chef(call: CallbackQuery, state: FSMContext):
    data = call.data.split('_')[1].split('.')
    order_id = data[1]
    if data[0] == 'check':
        await call.answer(text=f'Siz {order_id} mahsulotni tayyorlab bolganingiz uchun rahamt', show_alert=True)
        await call.message.delete()
        basket_id = await get_basket_id(order_id)
        basket_data = await get_basket_data(basket_id)
        phone_number = await get_user_phone_number_by_id(basket_data.user)
        tg_id = await get_user_tg_id(basket_data.user)
        user_name = (await get_user_data_all(tg_id)).real_name
        text = f"Buyurtma  raqami: {order_id}\nManzil: {basket_data.address}\nTelefon raqami: {phone_number}\nXaridor ismi: {user_name}"
        user_id = await get_user_tg_id((await get_basket_data(await get_basket_id(order_id))).user)
        await bot.send_message(text='Sizning mahsulotnigiz tayyorlanib boldi va yetkazilmoqda', chat_id=user_id)
        if basket_data.delivery_option != '🏃 olib ketish':
            await update_order_status(id=order_id, status='🚀 Yetkazilmoqda')
            try:
                for i in await get_user_role('Delivery'):
                    await bot.send_location(latitude=basket_data.latitude, longitude=basket_data.longitude, chat_id=i)
                    await bot.send_message(chat_id=i, text=text, reply_markup=delivery_check(order_id),
                                           reply_to_message_id=call.message.message_id + 2)
            except:
                await call.message.answer(text='Qandayadir muamo kelib chiqdi!')
                return
        await update_order_status(id=order_id, status='Olib ketishga tayyor')
        await bot.send_message(text=f"🛒  {order_id} \nMahsulotingiz tayyor iltimos olib keting", chat_id=user_id)
        return
    if data[0] == 'checkd':
        await call.message.answer(text=f'Siz {order_id} ni bekor qildingiz', show_alert=True)
        await update_order_status(id=order_id, status='❌ Oshpaz rad etdi')
        for j in await get_user_role('Chef'):
            await bot.delete_message(chat_id=j, message_id=call.message.message_id)
        user_id = await get_user_tg_id((await get_basket_data(await get_basket_id(order_id))).user)
        await bot.send_message(text='Sizning mahsulotnigizni oshpaz bekor qildi', chat_id=user_id)
    else:
        products = await get_basket_products(id=order_id)
        if products:
            formatted_products = json.loads(products.products)  # Parse the JSON string
            text = f'🥘 Buyurtma {order_id}\n\n'
            for product_id in formatted_products:
                product = await get_product_cost(product_id)
                if product:
                    product_name, product_price = product
                    product_quantity = await get_product_list(product_id)
                    if product_quantity:
                        text += f"{product_name.capitalize()} x {product_quantity.quantity} = {int(product_price) * int(product_quantity.quantity)}\n"
            try:
                await bot.edit_message_text(message_id=call.message.message_id, chat_id=call.from_user.id, text=text,
                                            reply_markup=check_chef(order_id))
            except:
                await call.message.answer('Nimadir xato ketdi!')


@dp.callback_query(F.data.startswith('delivery_'))
async def confirm_delivery(call: CallbackQuery, state: FSMContext):
    data = call.data.split('_')[1].split('.')
    order_id = data[1]
    if data[0] == 'check':
        confirm = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Ha', callback_data=f'delivery2_check.{order_id}'),
             InlineKeyboardButton(text='🔙 Ortga', callback_data=f'delivery2_back.{order_id}')]])
        await call.message.edit_text(text='Siz mahsulotni mijozga yetkazdingizmi?', reply_markup=confirm)
    else:
        confirm = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Ha', callback_data=f'delivery2_checkd.{order_id}'),
             InlineKeyboardButton(text='🔙 Ortga', callback_data=f'delivery2_back.{order_id}')]])
        await call.message.edit_text(text='Mahsulotni yetkazib bermadingizmi?', reply_markup=confirm)


@dp.callback_query(F.data.startswith('delivery2_'))
async def confirm_delivery2(call: CallbackQuery, state: FSMContext):
    data = call.data.split('_')[1].split('.')
    order_id = data[1]
    if data[0] == 'check':
        await call.message.answer(text='Mahsulotni 🚀 yetkazib berganingiz uchun rahmat 😉')
        await update_order_status(order_id, status='Mahsulotni yetkazib berilgan')
        user_id = await get_user_tg_id((await get_basket_data(await get_basket_id(order_id))).user)
        await bot.send_message(text='Sizning mahsulotnigiz mazilga yetib bordi', chat_id=user_id)
        for i in await get_user_role('Delivery'):
            await bot.delete_message(chat_id=i, message_id=call.message.message_id)
            await bot.delete_message(chat_id=i, message_id=call.message.message_id - 1)
        return
    if data[0] == 'checkd':
        await call.message.answer(text='Siz mahsulotni bekor qildingiz')
        await update_order_status(order_id, status='Yetkazib berish jamosi bekor qilgan')
        user_id = await get_user_tg_id((await get_basket_data(await get_basket_id(order_id))).user)
        await bot.send_message(text='Sizning mahsulotnigiz mazilga yetib bormadi va bekor qilindi', chat_id=user_id)
        for i in await get_user_role('Delivery'):
            await bot.delete_message(chat_id=i, message_id=call.message.message_id)
            await bot.delete_message(chat_id=i, message_id=call.message.message_id - 1)
        return
    else:
        basket_id = await get_basket_id(order_id)
        basket_data = await get_basket_data(basket_id)
        phone_number = await get_user_phone_number_by_id(basket_data.user)
        tg_id = await get_user_tg_id(basket_data.user)
        user_name = (await get_user_data_all(tg_id)).real_name
        text = f"Buyurtma  raqami: {order_id}\nManzil: {basket_data.address}\nTelefon raqami: {phone_number}\nXaridor ismi: {user_name}"
        await bot.edit_message_text(chat_id=call.from_user.id, text=text, reply_markup=delivery_check(order_id),
                                    message_id=call.message.message_id)
        return


@dp.callback_query(F.data.startswith('clear_products'))
async def callback_clear_products(call: CallbackQuery):
    products = await get_my_products_db(user_id=call.from_user.id)
    for i in products:
        for j in i.products:
            if j.isdigit():
                await delete_product_list(j)
    await call.message.delete()
    await call.message.answer(text='Menu', reply_markup=menu())


@dp.message(F.text == '🎉 Aksiyalar')
async def actions(message: Message, state: FSMContext):
    await state.clear()
    sales = await get_sales()

    if sales:
        for sale in sales:
            formatted_date = sale.expired_at
            await message.answer(
                text=f"🎉 Aktsiya\n\n{sale.name}\n{sale.description}\n⏳ {formatted_date} gacha davom etadi",
                reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=str(back))]], resize_keyboard=True)
            )
        await state.set_state(RedirectState.menu)
        return
    else:
        await message.answer(text='ℹ️ Hozirda hech qanday aksiyalar mavjud emas.')
        await message.answer(text='🏠 Menyu', reply_markup=menu())


@dp.message(F.text == '📦 Mening xaridlarim')
async def get_my_products(message: Message):
    products = await get_my_products_db(user_id=message.from_user.id)
    text = ''
    if len(products) == 0:
        await message.answer(text='🍟🤷‍♂️ Siz hali hech narsa harid qilmagansiz')
        await message.answer(text='Menu', reply_markup=menu())
        return

    for i in products:
        order = await get_order(i.id)
        if not order:
            continue  # Skip if the order doesn't exist

        text += f"🛒 Buyurtma {order.id}\n\n"
        text2 = ''
        formatted_array = ast.literal_eval(i.products)
        for j in formatted_array:
            id = await get_product_list(j)
            product = await get_product_cost(id.product)
            text2 += f"{product[0]} x {id.quantity} = {int(product[1]) * int(id.quantity)}\n"
        text += f"{text2}\n"
        time = str(order.created_at).split(':')[:2]
        formatted_time = f'{time[0]}:{time[1]}'
        text += (
            f"🚛 Yetkazib berish narxi: {i.delivery_cost} so'm\n"
            f"💵 Umumiy narx: {i.total_price} so'm\n"
            f"🚚 Yetkazib berish turi: {i.delivery_option}\n"
            f"📍 Manzil: {i.address}\n"
            f"📦 Buyurtma holati: {order.status}\n"
            f"📅 Buyurtma sanasi: {formatted_time}"
        )
        await message.answer(text=text)
        text = ''


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    await init()
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    try:
        keep_alive()
        asyncio.run(main())

    except KeyboardInterrupt:
        print('Bye')
