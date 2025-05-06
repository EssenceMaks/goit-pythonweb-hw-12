import os
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from dotenv import load_dotenv

# Завантажуємо змінні середовища з .env файлу
load_dotenv()

# Конфигурация Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

def upload_image(file, folder="avatars"):
    """
    Загрузка изображения в Cloudinary
    :param file: файл зображення
    :param folder: папка в Cloudinary
    :return: URL загруженного изображения и public_id
    """
    try:
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            overwrite=True,
            resource_type="image"
        )
        url = result['secure_url']
        public_id = result['public_id']
        return url, public_id
    except Exception as e:
        print(f"Error uploading to cloudinary: {e}")
        return None, None

def delete_image(public_id):
    """
    Видалення зображення з Cloudinary
    :param public_id: public_id изображения
    :return: результат видалення
    """
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result
    except Exception as e:
        print(f"Error deleting from cloudinary: {e}")
        return None

def generate_url(public_id, **options):
    """
    Генерація URL для зображення з трансформаціями
    :param public_id: public_id изображения
    :param options: опції трансформації
    :return: URL изображения
    """
    try:
        url, options = cloudinary_url(public_id, **options)
        return url
    except Exception as e:
        print(f"Error generating cloudinary URL: {e}")
        return None