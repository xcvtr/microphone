# Установка модели Vosk

## Быстрый старт

1. Скачайте модель Vosk для русского языка:
   - **Рекомендуется**: [vosk-model-small-ru-0.22](https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip) (~45 MB)
   - Альтернатива: [vosk-model-ru-0.42](https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip) (~1.5 GB, лучше качество)

2. Распакуйте архив в папку проекта

3. Переименуйте папку в `model`:
   ```
   microphone/
   ├── model/           ← папка с моделью
   │   ├── am/
   │   ├── conf/
   │   ├── graph/
   │   └── ...
   ├── main.py
   └── config.yaml
   ```

4. Запустите программу:
   ```bash
   .venv\Scripts\activate
   python main.py
   ```

## Переключение на Google Speech-to-Text

Если хотите использовать Google Speech-to-Text вместо Vosk:

1. Откройте `config.yaml`
2. Измените `engine: "vosk"` на `engine: "google"`
3. Добавьте API ключ в `.env`:
   ```
   GOOGLE_API_KEY=ваш_ключ_здесь
   ```

## Другие модели

Больше моделей на https://alphacephei.com/vosk/models:
- Английский: vosk-model-small-en-us-0.15
- Многоязычная: vosk-model-small-0.22
