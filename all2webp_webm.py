#!/usr/bin/env python3
"""
Рекурсивная конвертация медиафайлов в lossless WebP/WebM с поддержкой Chrome.
Видео: lossless VP9 + аудио Opus с битрейтом исходника (если есть аудио).
Аудио: Opus с битрейтом исходника.
Изображения: lossless WebP.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.apng'}
VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg'}
AUDIO_EXTS = {'.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma', '.opus'}

def check_ffmpeg():
    """Проверяет наличие ffmpeg и ffprobe."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Ошибка: FFmpeg (или ffprobe) не найден. Установите FFmpeg и добавьте его в PATH.")
        sys.exit(1)

def has_audio_stream(file_path):
    """
    Проверяет, есть ли в файле хотя бы один аудиопоток.
    Возвращает True/False.
    """
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a',
            '-show_entries', 'stream=index',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Если есть вывод (хотя бы одна строка с индексом), значит аудио есть
        return bool(result.stdout.strip())
    except Exception:
        # В случае ошибки считаем, что аудио нет (безопаснее)
        return False

def get_audio_bitrate(file_path):
    """
    Извлекает битрейт первого аудиопотока в файле с помощью ffprobe.
    Возвращает строку вида '128k' или None, если не удалось определить.
    """
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a:0',          # первый аудиопоток
            '-show_entries', 'stream=bit_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        bitrate_str = result.stdout.strip()
        if bitrate_str and bitrate_str.isdigit():
            bitrate_bps = int(bitrate_str)      # битрейт в бит/с
            if bitrate_bps == 0:
                return None  # нулевой битрейт – скорее всего переменный или неизвестный
            kbps = bitrate_bps // 1000
            # Opus поддерживает битрейт от 6 до 510 kbps, ограничим
            if kbps < 8:
                kbps = 8
            elif kbps > 510:
                kbps = 510
            return f"{kbps}k"
        else:
            return None
    except Exception:
        return None

def convert_file(input_path, output_path, file_type, force, default_bitrate):
    """Конвертирует один файл, автоматически определяя наличие аудио и битрейт."""
    if output_path.exists() and not force:
        print(f"Пропуск (уже существует): {output_path}")
        return

    if file_type == 'image':
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-c:v', 'libwebp',
            '-lossless', '1',
            '-compression_level', '6',
            '-loop', '0',
            '-an',
            '-y', str(output_path)
        ]
        print(f"Конвертация: {input_path} -> {output_path}")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при конвертации {input_path}: {e.stderr}")

    elif file_type == 'video':
        # Проверяем наличие аудио
        if has_audio_stream(input_path):
            # Пытаемся определить битрейт
            audio_bitrate = get_audio_bitrate(input_path)
            if audio_bitrate is None:
                audio_bitrate = default_bitrate
                print(f"  Не удалось определить битрейт аудио, используется {audio_bitrate} (задано по умолчанию)")
            else:
                print(f"  Определён битрейт аудио: {audio_bitrate}")

            cmd = [
                'ffmpeg', '-i', str(input_path),
                '-c:v', 'libvpx-vp9',
                '-lossless', '1',
                '-b:v', '0',
                '-pix_fmt', 'yuva420p',
                '-c:a', 'libopus',
                '-b:a', audio_bitrate,
                '-y', str(output_path)
            ]
        else:
            print("  Аудиопоток отсутствует, видео будет без звука")
            cmd = [
                'ffmpeg', '-i', str(input_path),
                '-c:v', 'libvpx-vp9',
                '-lossless', '1',
                '-b:v', '0',
                '-pix_fmt', 'yuva420p',
                '-an',
                '-y', str(output_path)
            ]

        print(f"Конвертация: {input_path} -> {output_path}")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при конвертации {input_path}: {e.stderr}")

    elif file_type == 'audio':
        # Для аудиофайлов проверяем, есть ли аудиопоток (обычно есть всегда, но на всякий случай)
        if not has_audio_stream(input_path):
            print(f"Предупреждение: в файле {input_path} нет аудиопотока, пропускаем.")
            return

        audio_bitrate = get_audio_bitrate(input_path)
        if audio_bitrate is None:
            audio_bitrate = default_bitrate
            print(f"  Не удалось определить битрейт, используется {audio_bitrate} (задано по умолчанию)")
        else:
            print(f"  Определён битрейт: {audio_bitrate}")

        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-c:a', 'libopus',
            '-b:a', audio_bitrate,
            '-y', str(output_path)
        ]
        print(f"Конвертация: {input_path} -> {output_path}")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при конвертации {input_path}: {e.stderr}")

def main():
    parser = argparse.ArgumentParser(description="Конвертировать медиафайлы в lossless WebP/WebM с автоопределением битрейта аудио")
    parser.add_argument('input_dir', nargs='?', default='.',
                        help='Корневая папка для поиска (по умолчанию текущая)')
    parser.add_argument('--force', action='store_true',
                        help='Перезаписывать существующие выходные файлы')
    parser.add_argument('--default-bitrate', default='128k',
                        help='Битрейт аудио по умолчанию (если не удалось определить или аудио есть). Например: 64k, 128k, 192k')
    args = parser.parse_args()

    check_ffmpeg()

    root_dir = Path(args.input_dir).resolve()
    if not root_dir.is_dir():
        print(f"Ошибка: {root_dir} не является папкой.")
        sys.exit(1)

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            input_path = Path(dirpath) / filename
            ext = input_path.suffix.lower()

            if ext in IMAGE_EXTS:
                out_path = input_path.with_suffix('.webp')
                convert_file(input_path, out_path, 'image', args.force, args.default_bitrate)
            elif ext in VIDEO_EXTS:
                out_path = input_path.with_suffix('.webm')
                convert_file(input_path, out_path, 'video', args.force, args.default_bitrate)
            elif ext in AUDIO_EXTS:
                out_path = input_path.with_suffix('.webm')
                convert_file(input_path, out_path, 'audio', args.force, args.default_bitrate)

if __name__ == '__main__':
    main()