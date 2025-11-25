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
        """Инициализировать модель Vosk"""
        try:
            model_path = self.config['vosk']['model_path']
            if not os.path.exists(model_path):
                print(f"❌ Модель Vosk не найдена в '{model_path}'")
                print("📥 Скачайте модель с https://alphacephei.com/vosk/models")
                print("   Рекомендуется: vosk-model-small-ru-0.22 для русского")
                self.vosk_model = None
                return
            
            print(f"📦 Загрузка модели Vosk из '{model_path}'...")
            self.vosk_model = Model(model_path)
            self.vosk_recognizer = KaldiRecognizer(
                self.vosk_model,
                self.config['vosk']['sample_rate']
            )
            print("✅ Модель Vosk загружена")
        except Exception as e:
            print(f"❌ Ошибка инициализации Vosk: {e}")
            self.vosk_model = None
    
    def start_listening(self):
        """Начать запись и транскрибацию"""
        if self.is_recording:
            return
        
        # Проверить доступность движка
        if self.config['engine'] == 'vosk' and not hasattr(self, 'vosk_model'):
            print("❌ Модель Vosk не инициализирована")
            return
        
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
        """Транскрибация через Vosk (офлайн)"""
        if not self.vosk_model:
            print("❌ Модель Vosk не загружена")
            return
        
        try:
            print("🔄 Распознавание через Vosk...")
            
            # Создать новый распознаватель для этой записи
            recognizer = KaldiRecognizer(
                self.vosk_model,
                self.config['vosk']['sample_rate']
            )
            
            # Обработать аудио
            audio_data = b''.join(self.frames)
            
            if recognizer.AcceptWaveform(audio_data):
                result = json.loads(recognizer.Result())
            else:
                result = json.loads(recognizer.FinalResult())
            
            text = result.get('text', '').strip()
            
            if text:
                print(f"📝 Распознано: {text}")
                self.insert_text(text)
            else:
                print("⚠️ Не удалось распознать речь")
        
        except Exception as e:
            print(f"❌ Ошибка Vosk: {e}")
    
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
        transcriber.toggle_recording()
    
    # Регистрация горячих клавиш
    def hotkey_listener():
        with keyboard.GlobalHotKeys({
            '<alt>+`': on_activate_record
        }) as h:
            h.join()
    
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
