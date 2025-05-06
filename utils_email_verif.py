import os
import aiosmtplib
from email.message import EmailMessage

async def send_verification_email(to_email: str, code: str):
    msg = EmailMessage()
    msg['From'] = os.getenv("EMAIL_HOST_USER")
    msg['To'] = to_email
    msg['Subject'] = "Код підтвердження реєстрації"
    msg.set_content(f"Ваш код підтвердження: {code}")

    await aiosmtplib.send(
        msg,
        hostname=os.getenv("EMAIL_HOST"),
        port=int(os.getenv("EMAIL_PORT")),
        username=os.getenv("EMAIL_HOST_USER"),
        password=os.getenv("EMAIL_HOST_PASSWORD"),
        start_tls=True
    )

# Добавляем новую функцию для отправки ссылки сброса пароля
async def send_password_reset_email(to_email: str, reset_url: str, username: str = ""):
    msg = EmailMessage()
    msg['From'] = os.getenv("EMAIL_HOST_USER")
    msg['To'] = to_email
    msg['Subject'] = "Скидання пароля для вашого облікового запису"
    
    # Створюємо HTML повідомлення з клікабельним посиланням на українській мові
    greeting = f"Вітаємо, {username}!" if username else "Вітаємо!"
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.5;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
          <h2 style="color: #333;">{greeting}</h2>
          <p>Ви зробили запит на скидання пароля для Вашого облікового запису.</p>
          <p>Щоб встановити новий пароль, перейдіть за посиланням нижче:</p>
          <p style="margin: 20px 0;">
            <a href="{reset_url}" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 4px;">
              Встановити новий пароль
            </a>
          </p>
          <p>Або скопіюйте це посилання в браузер: <br/><a href="{reset_url}" target="_blank" style="color: #0066cc;">{reset_url}</a></p>
          <p>Посилання дійсне протягом 24 годин.</p>
          <p>Якщо Ви не запитували скидання пароля, просто ігноруйте цей лист.</p>
          <p>З повагою,<br/>Команда підтримки</p>
        </div>
      </body>
    </html>
    """
    
    # Установка содержимого и типа контента
    msg.set_content(f"Вітаємо!\n\nВи зробили запит на скидання пароля для Вашого облікового запису.\n\nЩоб встановити новий пароль, перейдіть за посиланням: {reset_url}\n\nПосилання дійсне протягом 24 годин.\n\nЯкщо Ви не запитували скидання пароля, просто ігноруйте цей лист.")
    msg.add_alternative(html_content, subtype='html')

    # Отправляем email
    await aiosmtplib.send(
        msg,
        hostname=os.getenv("EMAIL_HOST"),
        port=int(os.getenv("EMAIL_PORT")),
        username=os.getenv("EMAIL_HOST_USER"),
        password=os.getenv("EMAIL_HOST_PASSWORD"),
        start_tls=True
    )
