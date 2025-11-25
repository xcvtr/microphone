import pyaudio
import wave
import threading
from pynput import keyboard
import pyautogui
import pyperclip
import io
import base64
import requests
import winsound
import os
import json
import yaml
from dotenv import load_dotenv
from vosk import Model, KaldiRecognizer

# Загрузить переменные окружения
load_dotenv()


class AudioTranscriber:
    def __init__(self):
        self.is_recording = False
        self.audio = pyaudio.PyAudio()
        self.frames = []
        self.stream = None
        self.saved_hwnd = None
        
        # Загрузить конфигурацию
        self.load_config()
        
        # Инициализировать Vosk если выбран
        if self.config['engine'] == 'vosk':
            self.init_vosk()
    
    def load_config(self):
        """Загрузить конфигурацию из config.yaml"""
        try:
            with open('config.yaml', 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            print(f"⚙️ Движок распознавания: {self.config['engine'].upper()}")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки config.yaml: {e}")
            # Дефолтная конфигурация
            self.config = {
                'engine': 'vosk',
                'vosk': {'model_path': 'model', 'sample_rate': 16000},
                'google': {
                    'language_code': 'ru-RU',
                    'alternative_languages': ['en-US'],
                    'model': 'latest_long',
                    'enable_punctuation': True
                }
            }
    
    def init_vosk(self):
        """Инициализировать модели Vosk (русская и английская)"""
        self.vosk_model_ru = None
        self.vosk_model_en = None
        
        try:
            # Загрузить русскую модель
            model_path_ru = self.config['vosk']['model_path']
            if os.path.exists(model_path_ru):
                print(f"📦 Загрузка русской модели из '{model_path_ru}'...")
                self.vosk_model_ru = Model(model_path_ru)
                print("✅ Русская модель загружена")
            else:
                print(f"❌ Русская модель не найдена в '{model_path_ru}'")
            
            # Загрузить английскую модель
            model_path_en = self.config['vosk'].get('model_path_en', 'model/model-en')
            if os.path.exists(model_path_en):
                print(f"📦 Загрузка английской модели из '{model_path_en}'...")
                self.vosk_model_en = Model(model_path_en)
                print("✅ Английская модель загружена")
            else:
                print(f"⚠️ Английская модель не найдена в '{model_path_en}'")
                print("   Запустите download_model.cmd для скачивания")
                
        except Exception as e:
            print(f"❌ Ошибка инициализации Vosk: {e}")
    
    def start_listening(self):
        """Начать запись и транскрибацию"""
        if self.is_recording:
            return
        
        # Проверить доступность движка
        if self.config['engine'] == 'vosk':
            if not self.vosk_model_ru and not self.vosk_model_en:
                print("❌ Ни одна модель Vosk не загружена")
                return
            if not self.vosk_model_ru:
                print("⚠️ Русская модель не загружена, используется только английская")
            if not self.vosk_model_en:
                print("⚠️ Английская модель не загружена, используется только русская")
        
        # Сохранить текущее окно с фокусом
        try:
            import ctypes
            self.saved_hwnd = ctypes.windll.user32.GetForegroundWindow()
            print(f"💾 Сохранен фокус окна: {self.saved_hwnd}")
        except Exception as e:
            print(f"⚠️ Не удалось сохранить фокус: {e}")
            self.saved_hwnd = None
        
        self.is_recording = True
        self.frames = []
        
        # Проиграть звук "ding" при старте
        threading.Thread(target=self._play_start_sound, daemon=True).start()
        
        print("🎤 Запись началась... Говорите! (Нажмите Alt+` или Win+` для остановки)")
        
        def record():
            try:
                sample_rate = self.config['vosk']['sample_rate'] if self.config['engine'] == 'vosk' else 16000
                
                self.stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=sample_rate,
                    input=True,
                    frames_per_buffer=1024
                )
                
                while self.is_recording:
                    data = self.stream.read(1024, exception_on_overflow=False)
                    self.frames.append(data)
            
            except Exception as e:
                print(f"❌ Ошибка записи: {e}")
            finally:
                if self.stream:
                    self.stream.stop_stream()
                    self.stream.close()
                self.transcribe_audio()
        
        threading.Thread(target=record, daemon=True).start()
    
    def stop_listening(self):
        """Остановить запись"""
        if self.is_recording:
            self.is_recording = False
            
            # Проиграть звук "dong" при окончании
            threading.Thread(target=self._play_stop_sound, daemon=True).start()
            
            print("⏹️ Запись остановлена, обработка...")
    
    def transcribe_audio(self):
        """Транскрибировать записанное аудио"""
        if not self.frames:
            print("⚠️ Нет записанного аудио")
            return
        
        if self.config['engine'] == 'vosk':
            self.transcribe_vosk()
        elif self.config['engine'] == 'google':
            self.transcribe_google()
        else:
            print(f"❌ Неизвестный движок: {self.config['engine']}")
    
    def transcribe_vosk(self):
        """Транскрибация через Vosk с двумя моделями"""
        if not self.vosk_model_ru and not self.vosk_model_en:
            print("❌ Модели Vosk не загружены")
            return
        
        try:
            audio_data = b''.join(self.frames)
            sample_rate = self.config['vosk']['sample_rate']
            
            # Распознать русской моделью
            text_ru = ""
            words_ru = []
            if self.vosk_model_ru:
                print("🔄 Распознавание русской моделью...")
                rec_ru = KaldiRecognizer(self.vosk_model_ru, sample_rate)
                rec_ru.SetWords(True)
                
                if rec_ru.AcceptWaveform(audio_data):
                    result_ru = json.loads(rec_ru.Result())
                else:
                    result_ru = json.loads(rec_ru.FinalResult())
                
                text_ru = result_ru.get('text', '').strip()
                words_ru = result_ru.get('result', [])
                print(f"🇷🇺 Русская: {text_ru}")
            
            # Распознать английской моделью
            text_en = ""
            words_en = []
            if self.vosk_model_en:
                print("🔄 Распознавание английской моделью...")
                rec_en = KaldiRecognizer(self.vosk_model_en, sample_rate)
                rec_en.SetWords(True)
                
                if rec_en.AcceptWaveform(audio_data):
                    result_en = json.loads(rec_en.Result())
                else:
                    result_en = json.loads(rec_en.FinalResult())
                
                text_en = result_en.get('text', '').strip()
                words_en = result_en.get('result', [])
                print(f"🇺🇸 Английская: {text_en}")
            
            # Комбинировать результаты
            if words_ru and words_en:
                final_text = self.combine_results(words_ru, words_en, text_ru, text_en)
            elif text_ru:
                final_text = text_ru
            elif text_en:
                final_text = text_en
            else:
                print("⚠️ Не удалось распознать речь")
                return
            
            print(f"📝 Итого: {final_text}")
            self.insert_text(final_text)
        
        except Exception as e:
            print(f"❌ Ошибка Vosk: {e}")
    
    def combine_results(self, words_ru, words_en, text_ru, text_en):
        """Комбинировать результаты двух моделей через DeepSeek AI"""
        print(f"  🇷🇺 Русская: {text_ru}")
        print(f"  🇺🇸 Английская: {text_en}")
        
        # Попробовать использовать DeepSeek для умного комбинирования
        deepseek_key = os.getenv('DEEPSEEK_API_KEY')
        if deepseek_key:
            try:
                print(f"  🤖 Отправка в DeepSeek AI...")
                result = self.combine_with_ai(words_ru, words_en, deepseek_key)
                if result:
                    return result
            except Exception as e:
                print(f"  ⚠️ Ошибка DeepSeek: {e}")
        
        # Fallback: простое комбинирование по уверенности
        print(f"  🔄 Fallback: комбинирование по уверенности")
        result = []
        max_len = max(len(words_ru), len(words_en))
        
        for i in range(max_len):
            if i < len(words_ru) and i < len(words_en):
                word_ru = words_ru[i]
                word_en = words_en[i]
                
                word_text_ru = word_ru.get('word', '')
                word_text_en = word_en.get('word', '')
                conf_ru = word_ru.get('conf', 0)
                conf_en = word_en.get('conf', 0)
                
                if conf_en > conf_ru:
                    result.append(word_text_en)
                else:
                    result.append(word_text_ru)
            elif i < len(words_ru):
                result.append(words_ru[i].get('word', ''))
            elif i < len(words_en):
                result.append(words_en[i].get('word', ''))
        
        return ' '.join(result)
    
    def combine_with_ai(self, words_ru, words_en, api_key):
        """Использовать DeepSeek AI для умного комбинирования"""
        # Собрать полные фразы
        text_ru = ' '.join(w.get('word', '') for w in words_ru)
        text_en = ' '.join(w.get('word', '') for w in words_en)
        
        # Подготовить детальную информацию по словам
        ru_words_detail = ', '.join(f"'{w.get('word', '')}' ({w.get('conf', 0):.2f})" for w in words_ru)
        en_words_detail = ', '.join(f"'{w.get('word', '')}' ({w.get('conf', 0):.2f})" for w in words_en)
        
        prompt = f"""Распознавание одной речи двумя моделями:

РУССКАЯ МОДЕЛЬ: {text_ru}
Уверенность по словам: {ru_words_detail}

АНГЛИЙСКАЯ МОДЕЛЬ: {text_en}
Уверенность по словам: {en_words_detail}

Задача: выбрать ОДИН из двух вариантов или скомбинировать их.

КРИТИЧЕСКИ ВАЖНО:
- Используй ТОЛЬКО слова из этих двух вариантов
- НЕ придумывай новые слова
- НЕ добавляй слова, которых нет ни в RU, ни в EN варианте

Пользователь говорит ПРЕИМУЩЕСТВЕННО НА РУССКОМ языке.

Правила выбора:
1. Если RU дала осмысленную фразу с conf > 0.9 - используй её ЦЕЛИКОМ
2. Если RU бессмысленная, а EN осмысленная - используй EN
3. Если оба варианта бессмысленные - выбери RU (по умолчанию)
4. Для смешанной речи: если в RU есть транслитерация ("хеллоу"), а в EN латиница ("hello") - замени только эти слова

Верни ТОЛЬКО итоговый текст без объяснений."""

        try:
            response = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'deepseek-chat',
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.1,
                    'max_tokens': 150
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result['choices'][0]['message']['content'].strip()
                # Убрать возможные кавычки
                text = text.strip('"\'')
                print(f"  🤖 DeepSeek: {text}")
                return text
            else:
                print(f"  ⚠️ DeepSeek API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"  ⚠️ DeepSeek request failed: {e}")
            return None
    
    def transcribe_google(self):
        """Транскрибация через Google Speech-to-Text (онлайн)"""
        try:
            # Создать WAV в памяти
            wav_buffer = io.BytesIO()
            wf = wave.open(wav_buffer, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            
            audio_content = wav_buffer.getvalue()
            
            # Получить API ключ
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                print("❌ GOOGLE_API_KEY не найден в .env файле")
                return
            
            url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"
            audio_base64 = base64.b64encode(audio_content).decode('utf-8')
            
            google_config = self.config['google']
            data = {
                "config": {
                    "encoding": "LINEAR16",
                    "sampleRateHertz": 16000,
                    "languageCode": google_config['language_code'],
                    "alternativeLanguageCodes": google_config['alternative_languages'],
                    "model": google_config['model'],
                    "enableAutomaticPunctuation": google_config['enable_punctuation']
                },
                "audio": {
                    "content": audio_base64
                }
            }
            
            print("🔄 Отправка на Google Speech-to-Text...")
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                if 'results' in result and result['results']:
                    text = result['results'][0]['alternatives'][0]['transcript']
                    print(f"📝 Распознано: {text}")
                    self.insert_text(text)
                else:
                    print("⚠️ Не удалось распознать речь")
            else:
                print(f"❌ Ошибка API: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"❌ Ошибка Google Speech: {e}")
    
    def insert_text(self, text):
        """Вставить текст в активное окно"""
        try:
            import time
            
            # Сохранить текущее содержимое буфера обмена
            try:
                old_clipboard = pyperclip.paste()
            except:
                old_clipboard = None
            
            # Копировать в буфер обмена
            pyperclip.copy(text + ' ')
            time.sleep(0.1)
            
            # Восстановить фокус на сохраненное окно
            if self.saved_hwnd:
                try:
                    import ctypes
                    print(f"🔄 Восстановление фокуса на окно: {self.saved_hwnd}")
                    
                    ctypes.windll.user32.BringWindowToTop(self.saved_hwnd)
                    result = ctypes.windll.user32.SetForegroundWindow(self.saved_hwnd)
                    
                    if result == 0:
                        print(f"⚠️ SetForegroundWindow вернул 0, используем Alt+Tab")
                        pyautogui.hotkey('alt', 'tab')
                        time.sleep(0.3)
                    else:
                        time.sleep(0.2)
                        print(f"✅ Фокус восстановлен")
                except Exception as e:
                    print(f"⚠️ Ошибка восстановления фокуса: {e}")
                    print(f"🔄 Переключение через Alt+Tab")
                    pyautogui.hotkey('alt', 'tab')
                    time.sleep(0.3)
            else:
                print(f"🔄 Переключение на предыдущее окно через Alt+Tab")
                pyautogui.hotkey('alt', 'tab')
                time.sleep(0.3)
            
            # Вставить текст
            pyautogui.hotkey('ctrl', 'v')
            print("✅ Текст вставлен")
            
            # Восстановить старое содержимое буфера обмена
            time.sleep(0.1)
            if old_clipboard is not None:
                try:
                    pyperclip.copy(old_clipboard)
                    print("♻️ Буфер обмена восстановлен")
                except:
                    pass
        
        except Exception as e:
            print(f"❌ Ошибка вставки текста: {e}")
    
    def _play_start_sound(self):
        """Проиграть звук начала записи"""
        try:
            # Двойной beep для надежности
            winsound.Beep(1200, 100)
            winsound.Beep(1400, 100)
        except Exception as e:
            print(f"⚠️ Не удалось проиграть звук: {e}")
    
    def _play_stop_sound(self):
        """Проиграть звук окончания записи"""
        try:
            # Двойной beep для надежности
            winsound.Beep(1000, 100)
            winsound.Beep(800, 150)
        except Exception as e:
            print(f"⚠️ Не удалось проиграть звук: {e}")
    
    def toggle_recording(self):
        """Переключить состояние записи"""
        if self.is_recording:
            self.stop_listening()
        else:
            self.start_listening()


def main():
    print("=" * 50)
    print("🎙️ ТРАНСКРИБАЦИЯ АУДИО В ТЕКСТ")
    print("=" * 50)
    print("\nГорячие клавиши:")
    print("  Alt+` - Начать/остановить запись")
    print("  Ctrl+C - Выход")
    print("\nОжидание команды...")
    
    transcriber = AudioTranscriber()
    
    def on_activate_record():
        print("🔥 Горячая клавиша нажата!")
        transcriber.toggle_recording()
    
    # Регистрация горячих клавиш
    def hotkey_listener():
        try:
            with keyboard.GlobalHotKeys({
                '<alt>+`': on_activate_record
            }) as h:
                print("✅ Горячая клавиша Alt+` зарегистрирована")
                h.join()
        except Exception as e:
            print(f"❌ Ошибка регистрации горячей клавиши: {e}")
    
    threading.Thread(target=hotkey_listener, daemon=True).start()
    
    # Держать программу запущенной
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Выход из программы")
        transcriber.stop_listening()
        transcriber.audio.terminate()


if __name__ == "__main__":
    main()
